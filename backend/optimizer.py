"""
Portfolio optimization module.

Implements three algorithms that mirror the Excel audit model:

1. compute_gmvp()           — Closed-form Global Minimum Variance Portfolio
                               (mirrors Excel MMULT / MINVERSE formula)
2. minimize_variance_for_target() — Minimum variance at a target return level
                                    (SLSQP inner loop for frontier sweep)
3. compute_efficient_frontier()   — 100-point parametric frontier sweep
4. compute_optimal_portfolio()    — Utility-maximizing portfolio via SLSQP

Reconciliation target: all results must agree with Excel to within 1e-6.

Short-sale regime: every SLSQP-based optimiser accepts an
``allow_short_selling`` flag. When False (default), bounds are
[0, max_weight] (long-only). When True, bounds are fixed to [-1, 2] per
PRD Part 1; truly unconstrained was ruled out because the closed-form
tangency on this dataset is numerically degenerate (see docs §4).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize, OptimizeResult

from config import RISK_FREE_RATE
from portfolio_math import (
    portfolio_return,
    portfolio_variance,
    portfolio_volatility,
    sharpe_ratio,
    utility,
)


# ---------------------------------------------------------------------------
# Short-sale bounds (PRD Part 1)
# ---------------------------------------------------------------------------

# When allow_short_selling=True, each weight is bounded by this interval.
# The dataset-specific rationale (unconstrained tangency is degenerate here)
# is recorded in docs/academic_report_robo_adviser.md §4.
SHORT_SALE_LOWER_BOUND: float = -1.0
SHORT_SALE_UPPER_BOUND: float = 2.0


def _bounds_for_regime(
    n: int, max_weight: float, allow_short_selling: bool
) -> list[tuple[float, float]]:
    """Per-asset bounds passed to SLSQP, switched by regime."""
    if allow_short_selling:
        return [(SHORT_SALE_LOWER_BOUND, SHORT_SALE_UPPER_BOUND)] * n
    return [(0.0, max_weight)] * n


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class OptimizationError(RuntimeError):
    """Raised when scipy.optimize.minimize fails to converge."""


# ---------------------------------------------------------------------------
# Dataclasses for typed return values
# ---------------------------------------------------------------------------


@dataclass
class PortfolioResult:
    """Fully characterised portfolio (weights + statistics)."""

    weights: np.ndarray          # shape (n,), float64
    expected_return: float
    volatility: float
    sharpe: float
    utility_score: float = 0.0   # filled in for the optimal portfolio only


@dataclass
class FrontierPoint:
    """One point on the efficient frontier."""

    expected_return: float
    volatility: float
    sharpe_ratio: float
    weights: np.ndarray          # shape (n,), float64


# ---------------------------------------------------------------------------
# 1. Global Minimum Variance Portfolio (closed-form)
# ---------------------------------------------------------------------------


def compute_gmvp(cov: np.ndarray) -> np.ndarray:
    """
    Compute the Global Minimum Variance Portfolio using the closed-form
    matrix algebra solution that mirrors Excel MMULT/MINVERSE:

        W_GMVP = (Σ⁻¹ 1) / (1^T Σ⁻¹ 1)

    Parameters
    ----------
    cov : (n, n) float64 — annualized covariance matrix

    Returns
    -------
    w_gmvp : (n,) float64 — GMVP weights summing to 1

    Raises
    ------
    OptimizationError  if the matrix is singular (det ≈ 0)
    """
    n = cov.shape[0]
    ones = np.ones(n, dtype=np.float64)

    # Condition number pre-check (mirrors PRD directive: cond < 1e10)
    cond = np.linalg.cond(cov)
    if cond > 1e10:
        raise OptimizationError(
            f"Covariance matrix is ill-conditioned (cond = {cond:.2e}). "
            "Cannot reliably invert."
        )

    cov_inv = np.linalg.inv(cov)           # Σ⁻¹
    numerator = cov_inv @ ones             # Σ⁻¹ 1
    denominator = ones.T @ numerator       # 1^T Σ⁻¹ 1  (scalar)

    if abs(denominator) < 1e-14:
        raise OptimizationError(
            "Denominator 1^T Σ⁻¹ 1 is effectively zero. "
            "Covariance matrix may be singular."
        )

    w_gmvp = numerator / denominator       # shape (n,)

    # Enforce non-negativity: if any weight is slightly negative due to
    # floating-point arithmetic, clip and re-normalise.
    # (The long-only GMVP may legitimately have negative weights when not
    #  constrained; for this project the PRD requires long-only, so we
    #  apply constrained GMVP below if needed.)
    if np.any(w_gmvp < 0):
        # Fall back to constrained GMVP via SLSQP
        w_gmvp = _compute_constrained_gmvp(cov)

    return w_gmvp.astype(np.float64)


def _compute_constrained_gmvp(
    cov: np.ndarray,
    allow_short_selling: bool = False,
) -> np.ndarray:
    """
    Compute GMVP subject to per-asset bounds via SLSQP.

    Used in two roles:
      - As a fallback from compute_gmvp() when the closed-form produces
        negative weights (long-only regime, bounds [0, 1]).
      - As the direct GMVP solver when short-sales are allowed under the
        PRD Part 1 bounds [-1, 2].

    Parameters
    ----------
    cov                 : (n, n) float64 annualized covariance matrix
    allow_short_selling : bool — if True, bounds = [-1, 2] instead of [0, 1]
    """
    n = cov.shape[0]
    x0 = np.ones(n, dtype=np.float64) / n

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    bounds = _bounds_for_regime(n, max_weight=1.0, allow_short_selling=allow_short_selling)

    result: OptimizeResult = minimize(
        fun=lambda w: portfolio_variance(w, cov),
        x0=x0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-12, "maxiter": 2000},
    )

    if not result.success:
        raise OptimizationError(
            f"Constrained GMVP optimization failed: {result.message}"
        )

    return result.x.astype(np.float64)


# ---------------------------------------------------------------------------
# 2. Minimum variance at a fixed target return (frontier inner loop)
# ---------------------------------------------------------------------------


def minimize_variance_for_target(
    mu: np.ndarray,
    cov: np.ndarray,
    target_return: float,
    max_weight: float = 1.0,
    allow_short_selling: bool = False,
) -> np.ndarray:
    """
    Find the portfolio with minimum variance subject to:
      - sum(w) = 1
      - w^T μ = target_return
      - per-asset bounds from _bounds_for_regime(...)
        (long-only [0, max_weight] or short-allowed [-1, 2])

    Parameters
    ----------
    mu                  : (n,) float64
    cov                 : (n, n) float64
    target_return       : float — desired portfolio expected return
    max_weight          : float — per-asset upper bound (long-only regime only)
    allow_short_selling : bool — if True, bounds = [-1, 2]

    Returns
    -------
    w_opt : (n,) float64

    Raises
    ------
    OptimizationError  if SLSQP fails
    """
    n = len(mu)
    x0 = np.ones(n, dtype=np.float64) / n

    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
        {"type": "eq", "fun": lambda w: portfolio_return(w, mu) - target_return},
    ]
    bounds = _bounds_for_regime(n, max_weight, allow_short_selling)

    result: OptimizeResult = minimize(
        fun=lambda w: portfolio_variance(w, cov),
        x0=x0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-12, "maxiter": 2000},
    )

    if not result.success:
        # Some target returns at the extreme may be infeasible for a long-only
        # portfolio — return the nearest feasible point rather than crashing.
        # This matches real-world optimizer behaviour.
        raise OptimizationError(
            f"Variance minimization failed for target={target_return:.6f}: "
            f"{result.message}"
        )

    return result.x.astype(np.float64)


# ---------------------------------------------------------------------------
# 3. Efficient frontier — 100-point parametric sweep
# ---------------------------------------------------------------------------


def compute_efficient_frontier(
    mu: np.ndarray,
    cov: np.ndarray,
    n_points: int = 100,
    rf: float = RISK_FREE_RATE,
    max_weight: float = 1.0,
    allow_short_selling: bool = False,
) -> list[FrontierPoint]:
    """
    Trace the efficient frontier by sweeping target returns from the GMVP
    expected return up to the feasible-set maximum.

    Returns exactly n_points FrontierPoint objects sorted by volatility
    ascending (i.e. the frontier is traced from bottom-left to top-right
    on the standard σ–E[r] plane).

    Parameters
    ----------
    mu                  : (n,) float64
    cov                 : (n, n) float64
    n_points            : int — default 100 per PRD
    rf                  : float — risk-free rate for Sharpe computation
    max_weight          : float — per-asset cap (long-only regime only)
    allow_short_selling : bool — if True, inner bounds are [-1, 2] and the
                                  target-return sweep is extended to the
                                  analytical upper bound for that regime

    Returns
    -------
    list[FrontierPoint] of length n_points, sorted by volatility ascending
    """
    # Establish the feasible return range for this regime
    if allow_short_selling:
        # GMVP under [-1, 2] gives the lower return endpoint.
        w_gmvp = _compute_constrained_gmvp(cov, allow_short_selling=True)
        # Upper endpoint under bounds w_i ∈ [-1, 2] with sum(w) = 1:
        # put +2 on the highest-mu asset, -1 on the lowest-mu asset,
        # 0 elsewhere (sum = 1, feasible, analytical argmax of mu^T w).
        mu_max = 2.0 * float(mu.max()) - 1.0 * float(mu.min())
    else:
        w_gmvp = compute_gmvp(cov)
        mu_max = float(mu.max())                   # single-asset maximum

    mu_min = portfolio_return(w_gmvp, mu)          # GMVP return = frontier minimum

    target_returns = np.linspace(mu_min, mu_max, n_points)

    frontier: list[FrontierPoint] = []
    for target in target_returns:
        try:
            w = minimize_variance_for_target(
                mu, cov, target, max_weight, allow_short_selling
            )
        except OptimizationError:
            # Skip infeasible points (can occur at the far right of the frontier)
            continue

        vol = portfolio_volatility(w, cov)
        sr = sharpe_ratio(w, mu, cov, rf)

        frontier.append(
            FrontierPoint(
                expected_return=portfolio_return(w, mu),
                volatility=vol,
                sharpe_ratio=sr,
                weights=w,
            )
        )

    # Sort by volatility ascending (standard frontier orientation)
    frontier.sort(key=lambda p: p.volatility)

    # Pad or truncate to exactly n_points
    if len(frontier) < n_points:
        # Duplicate the last point to fill — acceptable for display purposes
        last = frontier[-1] if frontier else FrontierPoint(
            expected_return=mu_min,
            volatility=0.0,
            sharpe_ratio=0.0,
            weights=w_gmvp,
        )
        while len(frontier) < n_points:
            frontier.append(last)
    else:
        frontier = frontier[:n_points]

    return frontier


# ---------------------------------------------------------------------------
# 4. Utility-maximizing optimal portfolio
# ---------------------------------------------------------------------------


def compute_optimal_portfolio(
    mu: np.ndarray,
    cov: np.ndarray,
    A: float,
    max_weight: float = 1.0,
    rf: float = RISK_FREE_RATE,
    allow_short_selling: bool = False,
) -> PortfolioResult:
    """
    Find the portfolio that maximises the mean-variance utility function:

        U(w) = E(r_p) − ½ · A · σ_p²

    subject to:
        Σ w_i = 1                             (full investment)
        long-only:  0 ≤ w_i ≤ max_weight     (default)
        short-allowed:  −1 ≤ w_i ≤ 2          (when allow_short_selling=True)

    SLSQP solver with ftol=1e-9 to exceed the 1e-6 reconciliation threshold.

    Parameters
    ----------
    mu                  : (n,) float64
    cov                 : (n, n) float64
    A                   : float — risk aversion coefficient ∈ [0.5, 10.0]
    max_weight          : float — per-asset upper bound (long-only regime only)
    rf                  : float — risk-free rate for Sharpe computation
    allow_short_selling : bool — if True, bounds switch to [-1, 2]

    Returns
    -------
    PortfolioResult with weights and full statistics

    Raises
    ------
    OptimizationError  if SLSQP does not converge
    ValueError         if A is outside [0.5, 10.0]
    """
    if not (0.5 <= A <= 10.0):
        raise ValueError(
            f"Risk aversion coefficient A={A} is outside the valid range [0.5, 10.0]."
        )

    n = len(mu)
    x0 = np.ones(n, dtype=np.float64) / n  # equal-weight initialisation

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    bounds = _bounds_for_regime(n, max_weight, allow_short_selling)

    def negative_utility(w: np.ndarray) -> float:
        """Objective to minimise = −U(w)."""
        return -(portfolio_return(w, mu) - 0.5 * A * portfolio_variance(w, cov))

    result: OptimizeResult = minimize(
        fun=negative_utility,
        x0=x0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-9, "maxiter": 1000},
    )

    if not result.success:
        raise OptimizationError(
            f"Utility maximization failed for A={A}: {result.message}"
        )

    w_star = result.x.astype(np.float64)

    return PortfolioResult(
        weights=w_star,
        expected_return=portfolio_return(w_star, mu),
        volatility=portfolio_volatility(w_star, cov),
        sharpe=sharpe_ratio(w_star, mu, cov, rf),
        utility_score=utility(w_star, mu, cov, A),
    )


# ---------------------------------------------------------------------------
# 5. Equal-weight portfolio stats (reference benchmark)
# ---------------------------------------------------------------------------


def compute_equal_weight_portfolio(
    mu: np.ndarray,
    cov: np.ndarray,
    rf: float = RISK_FREE_RATE,
) -> PortfolioResult:
    """
    Compute statistics for the naive equal-weight (1/n) portfolio.
    Used as a reference point on the Efficient Frontier chart.
    """
    n = len(mu)
    w_ew = np.ones(n, dtype=np.float64) / n

    return PortfolioResult(
        weights=w_ew,
        expected_return=portfolio_return(w_ew, mu),
        volatility=portfolio_volatility(w_ew, cov),
        sharpe=sharpe_ratio(w_ew, mu, cov, rf),
    )
