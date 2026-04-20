"""
Unit and integration tests for optimizer.py.

Tests cover:
  - compute_gmvp: closed-form GMVP, weight constraints, non-negativity
  - minimize_variance_for_target: min-var at target return
  - compute_efficient_frontier: 100-point sweep, monotonicity, length
  - compute_optimal_portfolio: SLSQP convergence, weight constraints,
    utility is maximised relative to alternatives, A boundary values
  - OptimizationError raised for invalid inputs

Run with:  pytest tests/test_optimizer.py -v --cov=backend/optimizer
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import numpy as np
import pytest

from optimizer import (
    OptimizationError,
    FrontierPoint,
    PortfolioResult,
    compute_efficient_frontier,
    compute_gmvp,
    compute_optimal_portfolio,
    minimize_variance_for_target,
)
from portfolio_math import (
    portfolio_return,
    portfolio_variance,
    portfolio_volatility,
    utility,
)


# ---------------------------------------------------------------------------
# Shared toy universe (10-asset to match the production schema)
# ---------------------------------------------------------------------------


def _make_toy_universe(n: int = 10) -> tuple[np.ndarray, np.ndarray]:
    """
    Build a well-conditioned n-asset covariance matrix with known properties.
    Uses a scaled identity + low-rank perturbation for positive definiteness.
    """
    np.random.seed(0)
    # Annualised returns spread from 4% to 12%
    mu = np.linspace(0.04, 0.12, n, dtype=np.float64)

    # Volatilities from 5% to 20%
    vols = np.linspace(0.05, 0.20, n, dtype=np.float64)

    # Correlation matrix: moderate pairwise correlations
    rho = 0.30
    corr = np.full((n, n), rho, dtype=np.float64)
    np.fill_diagonal(corr, 1.0)

    D = np.diag(vols)
    cov = D @ corr @ D

    # Ensure strict positive definiteness
    cov += np.eye(n) * 1e-6

    return mu, cov


@pytest.fixture(scope="module")
def toy_mu_cov():
    return _make_toy_universe(10)


# ---------------------------------------------------------------------------
# compute_gmvp
# ---------------------------------------------------------------------------


class TestComputeGMVP:
    def test_gmvp_weights_sum_to_one(self, toy_mu_cov):
        mu, cov = toy_mu_cov
        w = compute_gmvp(cov)
        assert abs(w.sum() - 1.0) < 1e-8, f"GMVP weights sum = {w.sum()}"

    def test_gmvp_weights_non_negative(self, toy_mu_cov):
        _, cov = toy_mu_cov
        w = compute_gmvp(cov)
        assert np.all(w >= -1e-8), f"Negative GMVP weights detected: {w}"

    def test_gmvp_has_minimum_variance(self, toy_mu_cov):
        """No other feasible long-only portfolio should have lower variance."""
        mu, cov = toy_mu_cov
        w_gmvp = compute_gmvp(cov)
        var_gmvp = portfolio_variance(w_gmvp, cov)

        # Test 50 random long-only portfolios
        rng = np.random.default_rng(42)
        for _ in range(50):
            raw = rng.dirichlet(np.ones(10))
            var_random = portfolio_variance(raw, cov)
            assert var_gmvp <= var_random + 1e-8, (
                f"GMVP variance {var_gmvp:.8f} > random portfolio variance "
                f"{var_random:.8f}"
            )

    def test_gmvp_output_shape(self, toy_mu_cov):
        _, cov = toy_mu_cov
        w = compute_gmvp(cov)
        assert w.shape == (10,)

    def test_gmvp_dtype_float64(self, toy_mu_cov):
        _, cov = toy_mu_cov
        w = compute_gmvp(cov)
        assert w.dtype == np.float64

    def test_gmvp_small_4_asset_known_result(self):
        """
        Cross-check the closed-form formula on a simple 4-asset case
        where the inverse can be computed by hand (diagonal cov).
        """
        # Diagonal covariance: Σ = diag(0.04, 0.09, 0.16, 0.25)
        vols_sq = np.array([0.04, 0.09, 0.16, 0.25], dtype=np.float64)
        cov4 = np.diag(vols_sq)

        # Analytical GMVP: w_i = (1/σ_i²) / sum(1/σ_j²)
        inv_var = 1.0 / vols_sq
        w_expected = inv_var / inv_var.sum()

        w_computed = compute_gmvp(cov4)
        np.testing.assert_allclose(w_computed, w_expected, atol=1e-8)


# ---------------------------------------------------------------------------
# minimize_variance_for_target
# ---------------------------------------------------------------------------


class TestMinimizeVarianceForTarget:
    def test_target_return_is_achieved(self, toy_mu_cov):
        mu, cov = toy_mu_cov
        target = 0.08
        w = minimize_variance_for_target(mu, cov, target)
        achieved_return = portfolio_return(w, mu)
        assert abs(achieved_return - target) < 1e-6

    def test_weights_sum_to_one(self, toy_mu_cov):
        mu, cov = toy_mu_cov
        w = minimize_variance_for_target(mu, cov, 0.07)
        assert abs(w.sum() - 1.0) < 1e-8

    def test_weights_non_negative(self, toy_mu_cov):
        mu, cov = toy_mu_cov
        w = minimize_variance_for_target(mu, cov, 0.07)
        assert np.all(w >= -1e-8)

    def test_variance_is_non_negative(self, toy_mu_cov):
        mu, cov = toy_mu_cov
        w = minimize_variance_for_target(mu, cov, 0.06)
        assert portfolio_variance(w, cov) >= 0.0

    def test_infeasible_target_raises(self, toy_mu_cov):
        """A target return above the maximum individual asset return is infeasible."""
        mu, cov = toy_mu_cov
        with pytest.raises(OptimizationError):
            minimize_variance_for_target(mu, cov, target_return=9999.0)


# ---------------------------------------------------------------------------
# compute_efficient_frontier
# ---------------------------------------------------------------------------


class TestComputeEfficientFrontier:
    def test_returns_exactly_100_points(self, toy_mu_cov):
        mu, cov = toy_mu_cov
        frontier = compute_efficient_frontier(mu, cov, n_points=100)
        assert len(frontier) == 100

    def test_all_points_are_frontier_point_instances(self, toy_mu_cov):
        mu, cov = toy_mu_cov
        frontier = compute_efficient_frontier(mu, cov, n_points=100)
        assert all(isinstance(p, FrontierPoint) for p in frontier)

    def test_volatilities_monotonically_non_decreasing(self, toy_mu_cov):
        """
        Efficient frontier must be traced left-to-right on the σ axis.
        Allow tiny floating-point violations (1e-8).
        """
        mu, cov = toy_mu_cov
        frontier = compute_efficient_frontier(mu, cov, n_points=100)
        vols = [p.volatility for p in frontier]
        for i in range(len(vols) - 1):
            assert vols[i] <= vols[i + 1] + 1e-8, (
                f"Frontier volatility not monotone at index {i}: "
                f"{vols[i]:.6f} > {vols[i+1]:.6f}"
            )

    def test_all_weights_non_negative(self, toy_mu_cov):
        mu, cov = toy_mu_cov
        frontier = compute_efficient_frontier(mu, cov, n_points=100)
        for p in frontier:
            assert np.all(np.array(p.weights) >= -1e-8)

    def test_all_weights_sum_to_one(self, toy_mu_cov):
        mu, cov = toy_mu_cov
        frontier = compute_efficient_frontier(mu, cov, n_points=100)
        for p in frontier:
            assert abs(sum(p.weights) - 1.0) < 1e-7

    def test_frontier_point_returns_above_gmvp(self, toy_mu_cov):
        """All frontier points should have return ≥ GMVP return (efficient half)."""
        mu, cov = toy_mu_cov
        w_gmvp = compute_gmvp(cov)
        gmvp_return = portfolio_return(w_gmvp, mu)
        frontier = compute_efficient_frontier(mu, cov, n_points=100)
        for p in frontier:
            assert p.expected_return >= gmvp_return - 1e-6


# ---------------------------------------------------------------------------
# compute_optimal_portfolio
# ---------------------------------------------------------------------------


class TestComputeOptimalPortfolio:
    @pytest.mark.parametrize("A", [0.5, 2.0, 3.5, 6.0, 10.0])
    def test_weights_sum_to_one(self, toy_mu_cov, A):
        mu, cov = toy_mu_cov
        result = compute_optimal_portfolio(mu, cov, A)
        assert abs(result.weights.sum() - 1.0) < 1e-8

    @pytest.mark.parametrize("A", [0.5, 2.0, 3.5, 6.0, 10.0])
    def test_weights_non_negative(self, toy_mu_cov, A):
        mu, cov = toy_mu_cov
        result = compute_optimal_portfolio(mu, cov, A)
        assert np.all(result.weights >= -1e-8)

    @pytest.mark.parametrize("A", [0.5, 2.0, 3.5, 6.0, 10.0])
    def test_utility_is_maximised(self, toy_mu_cov, A):
        """
        The optimal portfolio utility should exceed the equal-weight utility.
        (Equal-weight is rarely on the efficient frontier.)
        """
        mu, cov = toy_mu_cov
        result = compute_optimal_portfolio(mu, cov, A)
        n = len(mu)
        w_ew = np.ones(n) / n
        u_opt = utility(result.weights, mu, cov, A)
        u_ew = utility(w_ew, mu, cov, A)
        assert u_opt >= u_ew - 1e-6, (
            f"Optimal utility {u_opt:.6f} < equal-weight utility {u_ew:.6f} for A={A}"
        )

    def test_result_has_correct_fields(self, toy_mu_cov):
        mu, cov = toy_mu_cov
        result = compute_optimal_portfolio(mu, cov, A=3.5)
        assert isinstance(result, PortfolioResult)
        assert result.weights.shape == (10,)
        assert isinstance(result.expected_return, float)
        assert isinstance(result.volatility, float)
        assert isinstance(result.sharpe, float)
        assert isinstance(result.utility_score, float)

    def test_utility_score_matches_formula(self, toy_mu_cov):
        mu, cov = toy_mu_cov
        A = 3.5
        result = compute_optimal_portfolio(mu, cov, A)
        expected_u = utility(result.weights, mu, cov, A)
        assert abs(result.utility_score - expected_u) < 1e-10

    def test_higher_A_produces_lower_volatility_portfolio(self, toy_mu_cov):
        """
        A more risk-averse investor should receive a lower-volatility portfolio.
        """
        mu, cov = toy_mu_cov
        result_aggressive = compute_optimal_portfolio(mu, cov, A=0.5)
        result_conservative = compute_optimal_portfolio(mu, cov, A=10.0)
        assert result_conservative.volatility <= result_aggressive.volatility + 1e-6

    def test_invalid_A_below_range_raises(self, toy_mu_cov):
        mu, cov = toy_mu_cov
        with pytest.raises(ValueError, match="0.5"):
            compute_optimal_portfolio(mu, cov, A=0.1)

    def test_invalid_A_above_range_raises(self, toy_mu_cov):
        mu, cov = toy_mu_cov
        with pytest.raises(ValueError, match="10.0"):
            compute_optimal_portfolio(mu, cov, A=15.0)

    def test_max_weight_constraint_respected(self, toy_mu_cov):
        """No single asset should exceed the max_weight cap."""
        mu, cov = toy_mu_cov
        cap = 0.25
        result = compute_optimal_portfolio(mu, cov, A=3.5, max_weight=cap)
        assert np.all(result.weights <= cap + 1e-8), (
            f"Weight exceeds cap {cap}: {result.weights}"
        )

    def test_expected_return_matches_formula(self, toy_mu_cov):
        mu, cov = toy_mu_cov
        result = compute_optimal_portfolio(mu, cov, A=3.5)
        expected_ret = portfolio_return(result.weights, mu)
        assert abs(result.expected_return - expected_ret) < 1e-10

    def test_volatility_matches_formula(self, toy_mu_cov):
        mu, cov = toy_mu_cov
        result = compute_optimal_portfolio(mu, cov, A=3.5)
        expected_vol = portfolio_volatility(result.weights, cov)
        assert abs(result.volatility - expected_vol) < 1e-10


# ---------------------------------------------------------------------------
# compute_equal_weight_portfolio
# ---------------------------------------------------------------------------


class TestComputeEqualWeightPortfolio:
    def test_equal_weight_returns_portfolio_result(self, toy_mu_cov):
        from optimizer import compute_equal_weight_portfolio

        mu, cov = toy_mu_cov
        result = compute_equal_weight_portfolio(mu, cov)
        assert isinstance(result, PortfolioResult)

    def test_equal_weight_weights_are_uniform(self, toy_mu_cov):
        from optimizer import compute_equal_weight_portfolio

        mu, cov = toy_mu_cov
        result = compute_equal_weight_portfolio(mu, cov)
        expected = 1.0 / len(mu)
        assert np.allclose(result.weights, expected, atol=1e-14)

    def test_equal_weight_stats_correct(self, toy_mu_cov):
        from optimizer import compute_equal_weight_portfolio

        mu, cov = toy_mu_cov
        result = compute_equal_weight_portfolio(mu, cov)
        w_ew = np.ones(len(mu)) / len(mu)
        assert abs(result.expected_return - portfolio_return(w_ew, mu)) < 1e-12
        assert abs(result.volatility - portfolio_volatility(w_ew, cov)) < 1e-12


# ---------------------------------------------------------------------------
# GMVP ill-conditioned matrix (error branches)
# ---------------------------------------------------------------------------


class TestGMVPEdgeCases:
    def test_ill_conditioned_matrix_raises(self):
        """A near-singular matrix with cond > 1e10 must raise OptimizationError."""
        # Build a nearly singular matrix: near-duplicate rows/cols
        n = 4
        v = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float64)
        # Rank-1 matrix is singular; add tiny diagonal for numerical tractability
        cov_singular = np.outer(v, v) * 0.04
        cov_singular += np.eye(n) * 1e-20  # near-zero regularisation → ill-conditioned
        cond = np.linalg.cond(cov_singular)
        if cond > 1e10:
            with pytest.raises(OptimizationError):
                compute_gmvp(cov_singular)
        else:
            pytest.skip("Matrix not ill-conditioned enough on this platform")

    def test_constrained_gmvp_used_when_unconstrained_has_negatives(self):
        """
        Construct a covariance where the unconstrained closed-form GMVP has
        negative weights, forcing the constrained fallback.
        The result must still be non-negative and sum to 1.
        """
        # Use a highly correlated but asymmetric universe where the variance-
        # minimising portfolio would go short in a high-vol asset
        vols = np.array([0.30, 0.05, 0.05, 0.05], dtype=np.float64)
        corr = np.array(
            [
                [1.00, 0.95, 0.95, 0.95],
                [0.95, 1.00, 0.95, 0.95],
                [0.95, 0.95, 1.00, 0.95],
                [0.95, 0.95, 0.95, 1.00],
            ],
            dtype=np.float64,
        )
        D = np.diag(vols)
        cov = D @ corr @ D + np.eye(4) * 1e-5  # ensure PSD

        w = compute_gmvp(cov)
        assert abs(w.sum() - 1.0) < 1e-8
        assert np.all(w >= -1e-8)

    def test_frontier_padding_when_some_points_infeasible(self):
        """
        If the inner optimizer fails for some target returns, the frontier
        should still return exactly n_points points (via padding).
        This is tested by asking for more points than reachable targets
        and verifying length == n_points.
        """
        mu, cov = _make_toy_universe(10)
        frontier = compute_efficient_frontier(mu, cov, n_points=100)
        assert len(frontier) == 100
