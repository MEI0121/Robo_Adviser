"""
Tests for the allow_short_selling regime (PRD Part 1).

Uses the real 10-ETF market data under data/processed/. When short-sales
are allowed, per-asset bounds widen from [0, max_weight] to [-1, 2]
(documented in backend/optimizer.py:SHORT_SALE_*).

Three properties are asserted:
  1. The long-only GMVP on the current dataset has all weights ≥ 0 (no
     regression from baseline behaviour).
  2. The short-allowed GMVP on the current dataset takes non-trivial
     short positions in URTH / VNQ / QQQ / VT, matching the diagnostic
     in docs §5 (sign of those weights, not bit-exact magnitudes).
  3. Dominance: the short-allowed efficient frontier dominates the
     long-only frontier in the σ–E(r) plane. At any volatility σ* on
     the long-only frontier, the short-allowed frontier attains an
     expected return ≥ μ_long(σ*) − 1e-4, because relaxing constraints
     can only expand the feasible set.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import numpy as np
import pytest

from optimizer import (
    compute_efficient_frontier,
    compute_gmvp,
    _compute_constrained_gmvp,
)


# Canonical proxy-ticker ordering (matches data/processed/mu_vector.json's
# `fund_codes` array and fund_metadata.json's `proxy_ticker` sequence).
# This is the internal data-row ordering, not the FSMOne display-layer
# `fund_code` ordering — those are now "FSMONE_..." strings.
_PROXY_TICKER_ORDER = [
    "URTH", "AOA", "XLV", "SPY", "VNQ", "QQQ", "EMB", "BNDX", "AAXJ", "VT",
]


_DATA_PRESENT = (
    Path(__file__).resolve().parent.parent / "data" / "processed" / "mu_vector.json"
).exists()

pytestmark = pytest.mark.skipif(
    not _DATA_PRESENT, reason="Real market data required for short-sale tests"
)


# ---------------------------------------------------------------------------
# 1. Long-only GMVP on the current dataset has no negatives
# ---------------------------------------------------------------------------


class TestLongOnlyGMVPOnCurrentDataset:
    def test_all_weights_non_negative(self, mu_vector, cov_matrix):
        w = compute_gmvp(cov_matrix)
        assert np.all(w >= -1e-8), (
            f"Long-only GMVP produced a negative weight: min = {w.min():.6e}"
        )

    def test_weights_sum_to_one(self, mu_vector, cov_matrix):
        w = compute_gmvp(cov_matrix)
        assert abs(w.sum() - 1.0) < 1e-8


# ---------------------------------------------------------------------------
# 2. Short-allowed GMVP takes the expected short positions
# ---------------------------------------------------------------------------


class TestShortAllowedGMVPOnCurrentDataset:
    """
    Reference values from docs §5 (closed-form unconstrained diagnostic):
        URTH -12.8%, VNQ -17.7%, QQQ -17.8%, VT -8.5%
    The [-1, 2] SLSQP solution will be close but not bit-identical to
    closed-form, so we assert only sign + meaningful magnitude (> 1% in
    absolute value) for these four tickers.
    """

    @pytest.fixture(scope="class")
    def w_short(self, cov_matrix) -> np.ndarray:
        return _compute_constrained_gmvp(cov_matrix, allow_short_selling=True)

    def test_weights_sum_to_one(self, w_short):
        assert abs(w_short.sum() - 1.0) < 1e-6

    def test_bounds_respected(self, w_short):
        assert w_short.min() >= -1.0 - 1e-6
        assert w_short.max() <= 2.0 + 1e-6

    @pytest.mark.parametrize("ticker", ["URTH", "VNQ", "QQQ", "VT"])
    def test_expected_shorts(self, w_short, ticker):
        idx = _PROXY_TICKER_ORDER.index(ticker)
        assert w_short[idx] < -0.01, (
            f"{ticker} (idx {idx}) expected to be a meaningful short "
            f"(< -1%) when short-sales are allowed; got {w_short[idx]:+.4f}"
        )

    def test_has_lower_or_equal_variance_than_long_only(
        self, mu_vector, cov_matrix, w_short
    ):
        """
        Short-allowed GMVP variance ≤ long-only GMVP variance (relaxed
        constraints can only reduce — or at worst tie — the minimum).
        """
        w_long = compute_gmvp(cov_matrix)
        var_long = float(w_long @ cov_matrix @ w_long)
        var_short = float(w_short @ cov_matrix @ w_short)
        assert var_short <= var_long + 1e-10, (
            f"Short-allowed GMVP variance {var_short:.8f} > "
            f"long-only {var_long:.8f}"
        )


# ---------------------------------------------------------------------------
# 3. Short-allowed frontier dominates long-only frontier in the σ–E(r) plane
# ---------------------------------------------------------------------------


def _frontier_arrays(frontier) -> tuple[np.ndarray, np.ndarray]:
    sigma = np.array([p.volatility for p in frontier], dtype=np.float64)
    mu = np.array([p.expected_return for p in frontier], dtype=np.float64)
    return sigma, mu


def _monotone_unique(sigma: np.ndarray, mu: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Return (sigma, mu) reduced to strictly increasing sigma. The frontier
    sweep pads with duplicate endpoints when some target returns are
    infeasible; interpolation needs a strictly increasing x-array.
    """
    order = np.argsort(sigma, kind="stable")
    s, m = sigma[order], mu[order]
    keep = np.concatenate([[True], np.diff(s) > 1e-12])
    return s[keep], m[keep]


class TestShortAllowedDominatesLongOnly:
    def test_dominance_at_matched_volatility(self, mu_vector, cov_matrix):
        fr_long = compute_efficient_frontier(
            mu_vector, cov_matrix, n_points=100, allow_short_selling=False
        )
        fr_short = compute_efficient_frontier(
            mu_vector, cov_matrix, n_points=100, allow_short_selling=True
        )

        sigma_long, mu_long = _frontier_arrays(fr_long)
        sigma_short, mu_short = _frontier_arrays(fr_short)

        s_short_u, m_short_u = _monotone_unique(sigma_short, mu_short)

        # Short-allowed frontier should reach lower volatility than long-only
        # (it has a GMVP with lower variance).
        assert s_short_u[0] <= sigma_long[0] + 1e-8, (
            f"Short-allowed frontier min σ ({s_short_u[0]:.6f}) exceeds "
            f"long-only min σ ({sigma_long[0]:.6f})"
        )

        # Sample 9 interior points across the long-only range; skip 5 at
        # each end to avoid padded duplicates near the right edge.
        sampled_idx = list(range(5, 95, 10))
        checked = 0
        for i in sampled_idx:
            sigma_star = float(sigma_long[i])
            mu_star = float(mu_long[i])

            # np.interp silently clamps when sigma_star is out of range;
            # guard explicitly so we don't compare against a flat-line value.
            if sigma_star < s_short_u[0] - 1e-9 or sigma_star > s_short_u[-1] + 1e-9:
                continue

            mu_short_at_star = float(np.interp(sigma_star, s_short_u, m_short_u))
            assert mu_short_at_star >= mu_star - 1e-4, (
                f"Dominance violated at σ = {sigma_star:.6f}: "
                f"long-only μ = {mu_star:.6f}, "
                f"short-allowed μ (interpolated) = {mu_short_at_star:.6f}, "
                f"deficit = {mu_star - mu_short_at_star:.3e}"
            )
            checked += 1

        assert checked >= 5, (
            f"Only {checked} comparable σ points — test coverage is too thin; "
            "check that both frontiers span overlapping volatility ranges."
        )
