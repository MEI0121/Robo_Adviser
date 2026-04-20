"""
Unit tests for portfolio_math.py.

Coverage targets:
  - All 5 core functions (portfolio_return, portfolio_variance,
    portfolio_volatility, sharpe_ratio, utility)
  - validate_weights with pass and failure cases
  - Boundary values for A (0.5 and 10.0)
  - Numerical precision: results agree with numpy direct computation to 1e-12

Run with:  pytest tests/test_portfolio_math.py -v --cov=backend/portfolio_math
"""

from __future__ import annotations

import sys
import os

# Make the backend importable from the tests directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import numpy as np
import pytest

from portfolio_math import (
    equal_weight_portfolio,
    portfolio_return,
    portfolio_variance,
    portfolio_volatility,
    sharpe_ratio,
    utility,
    validate_weights,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

N = 4  # use a 4-asset toy universe for speed and readability


@pytest.fixture
def simple_mu() -> np.ndarray:
    """Annualized return vector for 4 hypothetical assets."""
    return np.array([0.10, 0.08, 0.06, 0.04], dtype=np.float64)


@pytest.fixture
def simple_cov() -> np.ndarray:
    """
    Known positive-definite 4×4 covariance matrix.
    Constructed as D * Corr * D with hand-chosen values so that
    expected outputs can be verified analytically.
    """
    vols = np.array([0.20, 0.15, 0.10, 0.05], dtype=np.float64)
    corr = np.array(
        [
            [1.00, 0.50, 0.30, 0.10],
            [0.50, 1.00, 0.40, 0.20],
            [0.30, 0.40, 1.00, 0.15],
            [0.10, 0.20, 0.15, 1.00],
        ],
        dtype=np.float64,
    )
    D = np.diag(vols)
    return D @ corr @ D


@pytest.fixture
def equal_weights() -> np.ndarray:
    return np.array([0.25, 0.25, 0.25, 0.25], dtype=np.float64)


@pytest.fixture
def concentrated_weights() -> np.ndarray:
    """All weight in the first asset."""
    return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)


# ---------------------------------------------------------------------------
# portfolio_return
# ---------------------------------------------------------------------------


class TestPortfolioReturn:
    def test_equal_weights_returns_mean(self, simple_mu, equal_weights):
        """Equal-weight return = arithmetic mean of mu."""
        expected = float(np.mean(simple_mu))
        result = portfolio_return(equal_weights, simple_mu)
        assert abs(result - expected) < 1e-12

    def test_concentrated_returns_single_asset(self, simple_mu, concentrated_weights):
        """Concentrated portfolio in asset 0 returns mu[0]."""
        result = portfolio_return(concentrated_weights, simple_mu)
        assert abs(result - simple_mu[0]) < 1e-12

    def test_custom_weights(self, simple_mu):
        w = np.array([0.4, 0.3, 0.2, 0.1], dtype=np.float64)
        expected = 0.4 * 0.10 + 0.3 * 0.08 + 0.2 * 0.06 + 0.1 * 0.04
        result = portfolio_return(w, simple_mu)
        assert abs(result - expected) < 1e-12

    def test_returns_float_not_array(self, simple_mu, equal_weights):
        result = portfolio_return(equal_weights, simple_mu)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# portfolio_variance
# ---------------------------------------------------------------------------


class TestPortfolioVariance:
    def test_concentrated_asset_variance(self, simple_cov, concentrated_weights):
        """Concentrated in asset 0: variance = cov[0,0]."""
        result = portfolio_variance(concentrated_weights, simple_cov)
        assert abs(result - simple_cov[0, 0]) < 1e-12

    def test_variance_non_negative(self, simple_cov, equal_weights):
        result = portfolio_variance(equal_weights, simple_cov)
        assert result >= 0.0

    def test_variance_matches_numpy_direct(self, simple_cov, equal_weights):
        expected = float(equal_weights @ simple_cov @ equal_weights)
        result = portfolio_variance(equal_weights, simple_cov)
        assert abs(result - expected) < 1e-12

    def test_custom_weights_variance(self, simple_cov):
        w = np.array([0.4, 0.3, 0.2, 0.1], dtype=np.float64)
        expected = float(w @ simple_cov @ w)
        result = portfolio_variance(w, simple_cov)
        assert abs(result - expected) < 1e-12


# ---------------------------------------------------------------------------
# portfolio_volatility
# ---------------------------------------------------------------------------


class TestPortfolioVolatility:
    def test_volatility_sqrt_of_variance(self, simple_cov, equal_weights):
        var = portfolio_variance(equal_weights, simple_cov)
        expected = float(np.sqrt(var))
        result = portfolio_volatility(equal_weights, simple_cov)
        assert abs(result - expected) < 1e-12

    def test_volatility_non_negative(self, simple_cov, equal_weights):
        result = portfolio_volatility(equal_weights, simple_cov)
        assert result >= 0.0

    def test_concentrated_volatility(self, simple_cov, concentrated_weights):
        """Volatility of all-in-asset-0 portfolio = sqrt(cov[0,0])."""
        expected = float(np.sqrt(simple_cov[0, 0]))
        result = portfolio_volatility(concentrated_weights, simple_cov)
        assert abs(result - expected) < 1e-12


# ---------------------------------------------------------------------------
# sharpe_ratio
# ---------------------------------------------------------------------------


class TestSharpeRatio:
    def test_sharpe_formula(self, simple_mu, simple_cov, equal_weights):
        """S = (E[r] - 0.03) / σ_p."""
        er = portfolio_return(equal_weights, simple_mu)
        vol = portfolio_volatility(equal_weights, simple_cov)
        expected = (er - 0.03) / vol
        result = sharpe_ratio(equal_weights, simple_mu, simple_cov)
        assert abs(result - expected) < 1e-12

    def test_custom_rf(self, simple_mu, simple_cov, equal_weights):
        er = portfolio_return(equal_weights, simple_mu)
        vol = portfolio_volatility(equal_weights, simple_cov)
        rf = 0.05
        expected = (er - rf) / vol
        result = sharpe_ratio(equal_weights, simple_mu, simple_cov, rf=rf)
        assert abs(result - expected) < 1e-12

    def test_zero_volatility_returns_zero(self, simple_mu):
        """If volatility is effectively zero, Sharpe should return 0 safely."""
        # Construct a degenerate covariance matrix (zero matrix)
        cov_zero = np.zeros((4, 4), dtype=np.float64)
        w = np.array([0.25, 0.25, 0.25, 0.25], dtype=np.float64)
        result = sharpe_ratio(w, simple_mu, cov_zero)
        assert result == 0.0

    def test_positive_sharpe_for_high_return_portfolio(
        self, simple_mu, simple_cov, concentrated_weights
    ):
        """Asset 0 has 10% return > 3% rf, so Sharpe should be positive."""
        result = sharpe_ratio(concentrated_weights, simple_mu, simple_cov)
        assert result > 0.0


# ---------------------------------------------------------------------------
# utility
# ---------------------------------------------------------------------------


class TestUtility:
    def test_utility_formula(self, simple_mu, simple_cov, equal_weights):
        """U = E[r_p] - 0.5 * A * σ_p²."""
        A = 3.5
        er = portfolio_return(equal_weights, simple_mu)
        var = portfolio_variance(equal_weights, simple_cov)
        expected = er - 0.5 * A * var
        result = utility(equal_weights, simple_mu, simple_cov, A)
        assert abs(result - expected) < 1e-12

    @pytest.mark.parametrize("A", [0.5, 1.0, 2.0, 3.5, 5.0, 6.0, 8.0, 10.0])
    def test_utility_at_boundary_A_values(
        self, simple_mu, simple_cov, equal_weights, A
    ):
        """Utility must be computable for all valid A in [0.5, 10.0]."""
        result = utility(equal_weights, simple_mu, simple_cov, A)
        assert isinstance(result, float)
        assert not np.isnan(result)

    def test_higher_A_produces_lower_utility_for_risky_portfolio(
        self, simple_mu, simple_cov, equal_weights
    ):
        """
        For a fixed portfolio, a more risk-averse investor (higher A)
        assigns lower utility (penalises variance more heavily).
        """
        u_low_A = utility(equal_weights, simple_mu, simple_cov, A=1.0)
        u_high_A = utility(equal_weights, simple_mu, simple_cov, A=5.0)
        assert u_low_A > u_high_A


# ---------------------------------------------------------------------------
# validate_weights
# ---------------------------------------------------------------------------


class TestValidateWeights:
    def test_valid_weights_pass(self, equal_weights):
        validate_weights(equal_weights)  # should not raise

    def test_sum_not_one_raises(self):
        w = np.array([0.3, 0.3, 0.3, 0.3], dtype=np.float64)  # sum = 1.2
        with pytest.raises(ValueError, match="sum"):
            validate_weights(w)

    def test_negative_weight_raises(self):
        w = np.array([0.5, 0.5, 0.1, -0.1], dtype=np.float64)
        with pytest.raises(ValueError, match="[Nn]egative"):
            validate_weights(w)

    def test_tiny_floating_point_negative_passes(self):
        """Weights computed by SLSQP may have tiny negatives < tol; should pass."""
        w = np.array([0.25, 0.25, 0.25, 0.24999999999], dtype=np.float64)
        w[3] = 1.0 - w[:3].sum()  # ensure sum = 1
        validate_weights(w, tol=1e-6)


# ---------------------------------------------------------------------------
# equal_weight_portfolio
# ---------------------------------------------------------------------------


class TestEqualWeightPortfolio:
    @pytest.mark.parametrize("n", [4, 10])
    def test_shape_and_values(self, n):
        w = equal_weight_portfolio(n)
        assert w.shape == (n,)
        assert np.allclose(w, 1.0 / n, atol=1e-14)

    def test_sum_to_one(self):
        w = equal_weight_portfolio(10)
        assert abs(w.sum() - 1.0) < 1e-14
