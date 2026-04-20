"""
Core portfolio mathematics module.

All functions are pure NumPy operations (no Pandas in the hot path) and
accept / return float64 arrays as required by the PRD.

Mathematical definitions follow the PRD Appendix B notation:
  w  ∈ ℝ^n   — portfolio weights vector
  μ  ∈ ℝ^n   — annualized mean return vector
  Σ  ∈ ℝⁿˣⁿ  — annualized covariance matrix
  r_f         — risk-free rate (default 0.03 per PRD)
  A           — investor risk aversion coefficient ∈ [0.5, 10.0]
"""

from __future__ import annotations

import numpy as np


# ---------------------------------------------------------------------------
# Primitive portfolio statistics
# ---------------------------------------------------------------------------


def portfolio_return(w: np.ndarray, mu: np.ndarray) -> float:
    """
    Compute expected portfolio return.

    E(r_p) = w^T μ

    Parameters
    ----------
    w   : (n,) float64  — portfolio weights (must sum to 1)
    mu  : (n,) float64  — annualized mean returns

    Returns
    -------
    float — annualized expected portfolio return
    """
    return float(np.dot(w, mu))


def portfolio_variance(w: np.ndarray, cov: np.ndarray) -> float:
    """
    Compute portfolio variance.

    σ_p² = w^T Σ w

    Parameters
    ----------
    w   : (n,) float64
    cov : (n, n) float64 — annualized covariance matrix

    Returns
    -------
    float — annualized portfolio variance (always ≥ 0)
    """
    return float(w @ cov @ w)


def portfolio_volatility(w: np.ndarray, cov: np.ndarray) -> float:
    """
    Compute portfolio volatility (standard deviation).

    σ_p = √(w^T Σ w)

    Parameters
    ----------
    w   : (n,) float64
    cov : (n, n) float64

    Returns
    -------
    float — annualized portfolio volatility
    """
    var = portfolio_variance(w, cov)
    # Guard against tiny floating-point negatives from near-zero variance
    return float(np.sqrt(max(var, 0.0)))


def sharpe_ratio(
    w: np.ndarray,
    mu: np.ndarray,
    cov: np.ndarray,
    rf: float = 0.03,
) -> float:
    """
    Compute the Sharpe Ratio.

    S_p = (E(r_p) - r_f) / σ_p

    Parameters
    ----------
    w   : (n,) float64
    mu  : (n,) float64
    cov : (n, n) float64
    rf  : float — risk-free rate, default 0.03 per PRD

    Returns
    -------
    float — Sharpe Ratio (0.0 if volatility is effectively zero)
    """
    er = portfolio_return(w, mu)
    vol = portfolio_volatility(w, cov)
    if vol < 1e-12:
        return 0.0
    return float((er - rf) / vol)


def utility(
    w: np.ndarray,
    mu: np.ndarray,
    cov: np.ndarray,
    A: float,
) -> float:
    """
    Compute mean-variance investor utility.

    U(w) = E(r_p) - ½ · A · σ_p²

    Parameters
    ----------
    w   : (n,) float64
    mu  : (n,) float64
    cov : (n, n) float64
    A   : float — risk aversion coefficient ∈ [0.5, 10.0]

    Returns
    -------
    float — utility value (higher is better for the investor)
    """
    er = portfolio_return(w, mu)
    var = portfolio_variance(w, cov)
    return float(er - 0.5 * A * var)


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------


def validate_weights(w: np.ndarray, tol: float = 1e-8) -> None:
    """
    Assert that weights are non-negative and sum to 1 within tolerance.

    Parameters
    ----------
    w   : (n,) float64
    tol : float — tolerance for sum-to-one check

    Raises
    ------
    ValueError if constraints are violated.
    """
    if np.any(w < -tol):
        raise ValueError(
            f"Negative weight detected: min(w) = {w.min():.6e}. "
            "Long-only constraint violated."
        )
    weight_sum = np.sum(w)
    if abs(weight_sum - 1.0) > tol:
        raise ValueError(
            f"Weights do not sum to 1. sum(w) = {weight_sum:.10f}, "
            f"deviation = {abs(weight_sum - 1.0):.2e}."
        )


def equal_weight_portfolio(n: int) -> np.ndarray:
    """
    Return the equal-weight portfolio as a (n,) float64 array.

    Parameters
    ----------
    n : int — number of assets

    Returns
    -------
    np.ndarray — [1/n, 1/n, ..., 1/n]
    """
    return np.full(n, 1.0 / n, dtype=np.float64)
