"""
Tests for compute_tangency_portfolio (PRD Part 1).

Core correctness property:
    The tangency portfolio maximises Sharpe over the feasible set. Any
    portfolio on the efficient frontier with the same bounds must have a
    Sharpe ratio ≤ the tangency's, up to numerical tolerance.

Each regime is exercised:
  - long-only, max_weight=1.0  (uncapped long-only)
  - long-only, max_weight=0.4  (the PRD default — expected to trip the
    primary path's bound check and exercise the fallback)
  - short-allowed, w ∈ [-1, 2]

For each, we also assert weight-sum and bound compliance of the result.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import numpy as np
import pytest

from optimizer import (
    SHORT_SALE_LOWER_BOUND,
    SHORT_SALE_UPPER_BOUND,
    compute_efficient_frontier,
    compute_tangency_portfolio,
)


_DATA_PRESENT = (
    Path(__file__).resolve().parent.parent / "data" / "processed" / "mu_vector.json"
).exists()

pytestmark = pytest.mark.skipif(
    not _DATA_PRESENT, reason="Real market data required for tangency tests"
)


# ---------------------------------------------------------------------------
# Parametrised across the three regimes used in Step 3's API response
# ---------------------------------------------------------------------------


_REGIMES = [
    pytest.param(
        {"max_weight": 1.0, "allow_short_selling": False},
        id="long_only_uncapped",
    ),
    pytest.param(
        {"max_weight": 0.4, "allow_short_selling": False},
        id="long_only_cap_0p4",
    ),
    pytest.param(
        {"max_weight": 1.0, "allow_short_selling": True},
        id="short_allowed_neg1_to_2",
    ),
]


def _expected_bounds(max_weight: float, allow_short: bool) -> tuple[float, float]:
    if allow_short:
        return SHORT_SALE_LOWER_BOUND, SHORT_SALE_UPPER_BOUND
    return 0.0, max_weight


class TestTangencyProperties:
    @pytest.mark.parametrize("regime", _REGIMES)
    def test_weights_sum_to_one(self, mu_vector, cov_matrix, regime):
        tan = compute_tangency_portfolio(mu_vector, cov_matrix, **regime)
        assert abs(tan.weights.sum() - 1.0) < 1e-6

    @pytest.mark.parametrize("regime", _REGIMES)
    def test_bounds_respected(self, mu_vector, cov_matrix, regime):
        tan = compute_tangency_portfolio(mu_vector, cov_matrix, **regime)
        lo, hi = _expected_bounds(regime["max_weight"], regime["allow_short_selling"])
        assert tan.weights.min() >= lo - 1e-6
        assert tan.weights.max() <= hi + 1e-6

    @pytest.mark.parametrize("regime", _REGIMES)
    def test_solver_path_reported(self, mu_vector, cov_matrix, regime):
        tan = compute_tangency_portfolio(mu_vector, cov_matrix, **regime)
        assert tan.solver_path in ("primary", "fallback")


class TestTangencyDominatesFrontier:
    """
    Headline correctness: tangency Sharpe ≥ every frontier point's Sharpe
    under the same regime, within 1e-4 (SLSQP ftol is 1e-9 / 1e-12 but
    the frontier sweep uses a coarse 100-point grid, so equality is only
    attained asymptotically).
    """

    @pytest.mark.parametrize("regime", _REGIMES)
    def test_tangency_sharpe_exceeds_frontier(self, mu_vector, cov_matrix, regime):
        tan = compute_tangency_portfolio(mu_vector, cov_matrix, **regime)
        frontier = compute_efficient_frontier(
            mu_vector, cov_matrix, n_points=100, **regime
        )
        max_frontier_sharpe = max(p.sharpe_ratio for p in frontier)
        assert tan.sharpe >= max_frontier_sharpe - 1e-4, (
            f"Tangency Sharpe {tan.sharpe:.6f} is below the best frontier "
            f"sample {max_frontier_sharpe:.6f} by "
            f"{max_frontier_sharpe - tan.sharpe:.3e}  "
            f"(solver_path={tan.solver_path!r})"
        )

    def test_tangency_has_positive_sharpe_on_live_data(self, mu_vector, cov_matrix):
        """Sanity: the 10-ETF dataset admits at least one portfolio with Sharpe>0."""
        tan = compute_tangency_portfolio(mu_vector, cov_matrix)
        assert tan.sharpe > 0.0


class TestRegimeMonotonicity:
    """Relaxing constraints can only weakly improve the achievable Sharpe."""

    def test_short_allowed_sharpe_ge_long_only(self, mu_vector, cov_matrix):
        tan_long = compute_tangency_portfolio(
            mu_vector, cov_matrix, allow_short_selling=False
        )
        tan_short = compute_tangency_portfolio(
            mu_vector, cov_matrix, allow_short_selling=True
        )
        assert tan_short.sharpe >= tan_long.sharpe - 1e-6, (
            f"Short-allowed tangency Sharpe {tan_short.sharpe:.6f} below "
            f"long-only {tan_long.sharpe:.6f}"
        )

    def test_uncapped_sharpe_ge_capped(self, mu_vector, cov_matrix):
        """Long-only tangency with max_weight=1.0 must match or beat max_weight=0.4."""
        tan_uncapped = compute_tangency_portfolio(
            mu_vector, cov_matrix, max_weight=1.0, allow_short_selling=False
        )
        tan_capped = compute_tangency_portfolio(
            mu_vector, cov_matrix, max_weight=0.4, allow_short_selling=False
        )
        assert tan_uncapped.sharpe >= tan_capped.sharpe - 1e-6
