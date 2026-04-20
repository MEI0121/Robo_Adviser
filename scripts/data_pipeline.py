"""
data_pipeline.py
================
Data pipeline — NAV → μ, Σ, GMVP, frontier | Robo-Adviser Platform

Full quantitative pipeline:

  raw NAV CSVs
      v
  log returns:   r_{i,t} = ln(NAV_{i,t} / NAV_{i,t-1})
      v
  μ vector:      μ_i = mean(r_{i,:}) × 12          (annualised)
  Σ matrix:      Σ = Cov(R_excess) × 12             (annualised)
      v
  GMVP:          W = Σ⁻¹ 1 / (1ᵀ Σ⁻¹ 1)            (closed-form)
      v
  Frontier:      50-point parametric sweep           (SLSQP, long-only)
      v
  JSON exports:  mu_vector.json, cov_matrix.json,
                 gmvp_weights.json, frontier_points.json
                 -> /data/processed/

All computations use float64.  Annualisation factor = 12 (monthly data).
Risk-free rate r_f = 0.03 (annualised).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import TypedDict

# Force UTF-8 on both stdout and stderr to avoid GBK codec errors on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from fund_universe import FUND_CODES, FUND_METADATA

import numpy as np
import pandas as pd
from scipy.optimize import minimize, OptimizeResult

# ── Constants ─────────────────────────────────────────────────────────────────
ANNUALISATION_FACTOR: int    = 12          # monthly -> annual
RISK_FREE_RATE:       float  = 0.03        # r_f = 3% p.a.
N_FRONTIER_POINTS:    int    = 50          # PRD requirement: 50 frontier points
SLSQP_OPTIONS:        dict   = {"ftol": 1e-9, "maxiter": 2000}

RAW_DIR:       Path = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR: Path = Path(__file__).parent.parent / "data" / "processed"


# ── Data Classes ─────────────────────────────────────────────────────────────

class FrontierPoint(TypedDict):
    target_return:  float
    min_variance:   float
    volatility:     float
    sharpe_ratio:   float
    weights:        list[float]


# ── Step 1: Load & Align NAV Data ─────────────────────────────────────────────

def load_nav_matrix(raw_dir: Path, fund_codes: list[str]) -> pd.DataFrame:
    """
    Load all fund CSVs, merge on date column, and return a (T, N) DataFrame
    where rows are dates and columns are fund codes.

    Dates are aligned to the intersection of all funds' date ranges to guarantee
    a complete (no-NaN) matrix suitable for covariance estimation.
    """
    frames: dict[str, pd.Series] = {}

    for code in fund_codes:
        csv_path = raw_dir / f"{code}.csv"
        if not csv_path.exists():
            raise FileNotFoundError(
                f"NAV CSV not found: {csv_path}\n"
                f"Run: python scripts/download_yfinance_data.py"
            )
        df = pd.read_csv(csv_path, parse_dates=["date"])
        df = df.sort_values("date").set_index("date")
        frames[code] = df["nav"]

    nav_df = pd.DataFrame(frames)  # aligns on date index automatically
    nav_df = nav_df.dropna()       # keep only dates present in all funds

    # Verify minimum history requirement: ≥ 120 monthly rows
    if len(nav_df) < 121:  # 120 returns = 121 NAV rows (incl. t=0)
        raise ValueError(
            f"Insufficient history: only {len(nav_df)} rows "
            f"(need ≥ 121 NAV rows for 120 monthly returns)."
        )

    print(f"  NAV matrix loaded: {len(nav_df)} dates × {len(fund_codes)} funds")
    print(f"  Date range: {nav_df.index[0].date()} -> {nav_df.index[-1].date()}")
    return nav_df


# ── Step 2: Compute Log Returns ───────────────────────────────────────────────

def compute_log_returns(nav_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute monthly log returns:
        r_{i,t} = ln(NAV_{i,t} / NAV_{i,t-1})

    Returns a (T-1, N) DataFrame; the first row is dropped (NaN).
    """
    log_ret = np.log(nav_df / nav_df.shift(1)).dropna()
    print(f"  Log returns computed: {len(log_ret)} monthly observations per fund")
    return log_ret


# ── Step 3: Annualised μ Vector ───────────────────────────────────────────────

def compute_mu_vector(log_returns: pd.DataFrame) -> np.ndarray:
    """
    Annualised mean return vector:
        μ_i = mean(r_{i,:}) × 12

    Returns shape (N,) float64.
    """
    mu = log_returns.mean().values.astype(np.float64) * ANNUALISATION_FACTOR
    return mu


# ── Step 4: Annualised Σ Covariance Matrix ────────────────────────────────────

def compute_cov_matrix(log_returns: pd.DataFrame) -> np.ndarray:
    """
    Annualised covariance matrix via excess-returns formulation:

        R_excess = R - mean(R)                      shape (T, N)
        Σ_monthly = R_excessᵀ R_excess / (T - 1)    unbiased sample cov
        Σ_annual  = Σ_monthly × 12

    This is algebraically equivalent to log_returns.cov() × 12 and matches
    the Excel formula: =MMULT(TRANSPOSE(excess_returns), excess_returns) / (T-1) * 12

    Returns shape (N, N) float64, positive semi-definite.
    """
    R = log_returns.values.astype(np.float64)   # (T, N)
    T, N = R.shape

    # Excess returns (demeaned)
    R_excess = R - R.mean(axis=0)               # (T, N)

    # Sample covariance (unbiased) -- monthly
    cov_monthly = (R_excess.T @ R_excess) / (T - 1)   # (N, N)

    # Annualise
    cov_annual = cov_monthly * ANNUALISATION_FACTOR     # (N, N)

    return cov_annual.astype(np.float64)


def validate_covariance(cov: np.ndarray, label: str = "Cov") -> None:
    """
    Assert that the covariance matrix is:
    (a) square and symmetric,
    (b) positive definite -- all eigenvalues strictly > 0,
    (c) well-conditioned -- condition number < 1e10.

    Note: The raw determinant of a 10x10 covariance matrix with sub-unit
    variances is naturally tiny (order 1e-20 to 1e-15) and must NOT be
    compared against a fixed threshold.  Positive definiteness is correctly
    verified via the minimum eigenvalue.
    """
    N = cov.shape[0]
    assert cov.shape == (N, N), f"{label} must be square. Got {cov.shape}"
    assert np.allclose(cov, cov.T, atol=1e-12), f"{label} is not symmetric"

    eigvals = np.linalg.eigvalsh(cov)
    min_eig = eigvals.min()
    assert min_eig > 0, (
        f"{label} is not positive definite: min eigenvalue = {min_eig:.4e}"
    )

    cond = np.linalg.cond(cov)
    assert cond < 1e10, (
        f"{label} is ill-conditioned: cond = {cond:.4e} (threshold 1e10)"
    )

    det = np.linalg.det(cov)
    print(
        f"  {label} validation: det = {det:.6e} | "
        f"min_eigenval = {min_eig:.6e} | "
        f"condition_num = {cond:.4e}  [OK]"
    )


# ── Step 5: Portfolio Metrics ─────────────────────────────────────────────────

def portfolio_return(w: np.ndarray, mu: np.ndarray) -> float:
    """E(r_p) = wᵀ μ"""
    return float(w @ mu)


def portfolio_variance(w: np.ndarray, cov: np.ndarray) -> float:
    """σ_p² = wᵀ Σ w"""
    return float(w @ cov @ w)


def portfolio_volatility(w: np.ndarray, cov: np.ndarray) -> float:
    """σ_p = √(wᵀ Σ w)"""
    return float(np.sqrt(portfolio_variance(w, cov)))


def sharpe_ratio(
    w: np.ndarray,
    mu: np.ndarray,
    cov: np.ndarray,
    rf: float = RISK_FREE_RATE,
) -> float:
    """S_p = (E(r_p) − r_f) / σ_p"""
    er   = portfolio_return(w, mu)
    vol  = portfolio_volatility(w, cov)
    return float((er - rf) / vol) if vol > 1e-12 else 0.0


def utility(w: np.ndarray, mu: np.ndarray, cov: np.ndarray, A: float) -> float:
    """U = E(r_p) − 0.5 × A × σ_p²"""
    return float(portfolio_return(w, mu) - 0.5 * A * portfolio_variance(w, cov))


# ── Step 6: Global Minimum Variance Portfolio (GMVP) ─────────────────────────

def compute_gmvp(cov: np.ndarray) -> np.ndarray:
    """
    Closed-form GMVP using matrix algebra -- mirrors Excel MMULT/MINVERSE:

        W_GMVP = Σ⁻¹ 1 / (1ᵀ Σ⁻¹ 1)

    where 1 is the ones vector.  Long-only weights are NOT enforced here
    because the closed-form solution is the unconstrained GMVP.  If any
    weight is negative (short), the constrained GMVP is obtained via
    compute_gmvp_constrained().

    Returns shape (N,) float64.
    """
    N    = cov.shape[0]
    ones = np.ones(N, dtype=np.float64)
    cov_inv    = np.linalg.inv(cov)           # Σ⁻¹
    numerator  = cov_inv @ ones               # Σ⁻¹ 1
    denominator = ones @ cov_inv @ ones       # 1ᵀ Σ⁻¹ 1
    w_gmvp = numerator / denominator
    return w_gmvp.astype(np.float64)


def compute_gmvp_constrained(
    cov: np.ndarray,
    max_weight: float = 1.0,
) -> np.ndarray:
    """
    Long-only GMVP via SLSQP (used when closed-form gives negative weights).

        min  wᵀ Σ w
        s.t. Σw_i = 1,  w_i ∈ [0, max_weight]

    Returns shape (N,) float64.
    """
    N  = cov.shape[0]
    x0 = np.ones(N, dtype=np.float64) / N

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    bounds      = [(0.0, max_weight)] * N

    result: OptimizeResult = minimize(
        fun        = lambda w: portfolio_variance(w, cov),
        x0         = x0,
        method     = "SLSQP",
        bounds     = bounds,
        constraints= constraints,
        options    = SLSQP_OPTIONS,
    )

    if not result.success:
        raise RuntimeError(f"Constrained GMVP failed: {result.message}")

    return result.x.astype(np.float64)


# ── Step 7: Efficient Frontier (50-point parametric sweep) ────────────────────

def _minimize_variance_for_target(
    mu: np.ndarray,
    cov: np.ndarray,
    target_return: float,
    max_weight: float = 1.0,
) -> OptimizeResult:
    """
    Solve the minimum-variance problem for a fixed target return:

        min  wᵀ Σ w
        s.t. Σw_i = 1
             wᵀ μ = target_return
             w_i ∈ [0, max_weight]   (long-only)

    Returns the SciPy OptimizeResult.
    """
    N  = cov.shape[0]
    x0 = np.ones(N, dtype=np.float64) / N

    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
        {"type": "eq", "fun": lambda w: portfolio_return(w, mu) - target_return},
    ]
    bounds = [(0.0, max_weight)] * N

    return minimize(
        fun         = lambda w: portfolio_variance(w, cov),
        x0          = x0,
        method      = "SLSQP",
        bounds      = bounds,
        constraints = constraints,
        options     = SLSQP_OPTIONS,
    )


def compute_efficient_frontier(
    mu: np.ndarray,
    cov: np.ndarray,
    n_points: int = N_FRONTIER_POINTS,
    max_weight: float = 1.0,
) -> list[FrontierPoint]:
    """
    Parametric efficient frontier sweep.

    Sweeps target return from μ_GMVP (constrained) to max(μ) in n_points
    equal steps.  For each target, minimises portfolio variance subject to
    the full-investment and return constraints.

    Returns a list of FrontierPoint dicts sorted by volatility ascending.
    """
    # Determine the return range [μ_GMVP, max(μ)]
    w_gmvp = compute_gmvp_constrained(cov, max_weight)
    mu_min  = portfolio_return(w_gmvp, mu)
    mu_max  = float(mu.max())

    targets = np.linspace(mu_min, mu_max, n_points)

    frontier: list[FrontierPoint] = []
    failed = 0

    for target in targets:
        result = _minimize_variance_for_target(mu, cov, target, max_weight)
        if not result.success:
            failed += 1
            continue   # skip infeasible points silently

        w   = result.x.astype(np.float64)
        var = portfolio_variance(w, cov)
        vol = float(np.sqrt(max(var, 0.0)))   # guard against tiny negatives
        er  = portfolio_return(w, mu)
        sr  = float((er - RISK_FREE_RATE) / vol) if vol > 1e-12 else 0.0

        frontier.append(FrontierPoint(
            target_return = float(target),
            min_variance  = float(var),
            volatility    = vol,
            sharpe_ratio  = sr,
            weights       = [round(float(wi), 8) for wi in w],
        ))

    if failed > 0:
        print(f"  [WARN]  {failed}/{n_points} frontier points failed to converge (skipped)")

    # Sort by volatility ascending
    frontier.sort(key=lambda p: p["volatility"])
    print(f"  Efficient frontier computed: {len(frontier)} points")
    return frontier


# ── Step 8: JSON Export ───────────────────────────────────────────────────────

def export_json(data: object, path: Path, label: str) -> None:
    """Serialise data to a UTF-8 JSON file with 6-decimal precision."""
    path.parent.mkdir(parents=True, exist_ok=True)

    # Custom float formatter: round to 8 dp to preserve 1e-6 tolerance headroom
    class _Encoder(json.JSONEncoder):
        def iterencode(self, o, _one_shot=False):
            if isinstance(o, (np.floating, float)):
                yield f"{o:.8f}"
            elif isinstance(o, np.integer):
                yield str(int(o))
            elif isinstance(o, np.ndarray):
                yield from super().iterencode(o.tolist())
            else:
                yield from super().iterencode(o, _one_shot)

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, cls=_Encoder)

    print(f"  [Exported] {label} -> {path.name}")


# ── Fund metadata: imported from fund_universe.py (Yahoo tickers + labels) ───


# ── Main Pipeline ─────────────────────────────────────────────────────────────

def run_pipeline() -> dict:
    """
    Execute the full data pipeline and return a summary dict.
    All intermediate and final objects are serialised to /data/processed/.
    """
    t_start = time.perf_counter()

    print("=" * 70)
    print("Data Pipeline — NAV to processed JSON")
    print("=" * 70)

    # ── 1. Load NAVs ──────────────────────────────────────────────────────────
    print("\n[1/6] Loading NAV data …")
    nav_df = load_nav_matrix(RAW_DIR, FUND_CODES)

    # ── 2. Log returns ────────────────────────────────────────────────────────
    print("\n[2/6] Computing log returns …")
    log_ret = compute_log_returns(nav_df)
    T, N    = log_ret.shape

    # ── 3. μ vector ───────────────────────────────────────────────────────────
    print("\n[3/6] Computing annualised μ vector …")
    mu = compute_mu_vector(log_ret)
    print(f"  μ vector (annualised):")
    for i, (code, m) in enumerate(zip(FUND_CODES, mu)):
        print(f"    [{i:>2}] {code}  μ = {m*100:+.4f}%")

    # ── 4. Σ covariance matrix ────────────────────────────────────────────────
    print("\n[4/6] Computing annualised Σ covariance matrix …")
    cov = compute_cov_matrix(log_ret)
    validate_covariance(cov, label="Σ")

    # ── 5. GMVP ───────────────────────────────────────────────────────────────
    print("\n[5/6] Computing GMVP (closed-form) …")
    w_gmvp_cf = compute_gmvp(cov)   # unconstrained closed-form

    if np.any(w_gmvp_cf < -1e-6):
        print("  [WARN]  Closed-form GMVP has negative weights -> using constrained GMVP")
        w_gmvp = compute_gmvp_constrained(cov)
        gmvp_method = "constrained_SLSQP"
    else:
        # Clip tiny negatives from floating-point noise, renormalise
        w_gmvp_cf = np.clip(w_gmvp_cf, 0.0, 1.0)
        w_gmvp    = w_gmvp_cf / w_gmvp_cf.sum()
        gmvp_method = "closed_form_MMULT_MINVERSE"

    # Verify sum-to-one
    assert abs(w_gmvp.sum() - 1.0) < 1e-8, (
        f"GMVP weights do not sum to 1: sum = {w_gmvp.sum():.10f}"
    )

    gmvp_er  = portfolio_return(w_gmvp, mu)
    gmvp_vol = portfolio_volatility(w_gmvp, cov)
    gmvp_sr  = sharpe_ratio(w_gmvp, mu, cov)

    print(f"  GMVP method          : {gmvp_method}")
    print(f"  GMVP sum(w)          : {w_gmvp.sum():.10f}  (should be 1.0)")
    print(f"  GMVP E(r_p)          : {gmvp_er*100:.4f}%")
    print(f"  GMVP σ_p             : {gmvp_vol*100:.4f}%")
    print(f"  GMVP Sharpe Ratio    : {gmvp_sr:.4f}")
    print(f"  GMVP weights:")
    for i, (code, wi) in enumerate(zip(FUND_CODES, w_gmvp)):
        bar = "█" * int(wi * 40)
        print(f"    [{i:>2}] {code}  {wi*100:6.2f}%  {bar}")

    # ── 6. Efficient Frontier ─────────────────────────────────────────────────
    print("\n[6/6] Computing efficient frontier (50 points) …")
    frontier = compute_efficient_frontier(mu, cov, n_points=N_FRONTIER_POINTS)
    assert len(frontier) == N_FRONTIER_POINTS, (
        f"Expected {N_FRONTIER_POINTS} frontier points, got {len(frontier)}"
    )

    # Verify volatilities are (weakly) monotonically increasing
    vols = [p["volatility"] for p in frontier]
    assert all(vols[i] <= vols[i+1] + 1e-8 for i in range(len(vols) - 1)), (
        "Efficient frontier volatilities are not monotonically non-decreasing!"
    )
    print(f"  Frontier return range  : {frontier[0]['target_return']*100:.2f}% -> "
          f"{frontier[-1]['target_return']*100:.2f}%")
    print(f"  Frontier vol range     : {frontier[0]['volatility']*100:.2f}% -> "
          f"{frontier[-1]['volatility']*100:.2f}%")

    # ── 7. Enrich fund metadata with computed statistics ──────────────────────
    enriched_funds: list[dict] = []
    for i, meta in enumerate(FUND_METADATA):
        w_eq  = np.zeros(N, dtype=np.float64)
        w_eq[i] = 1.0
        enriched_funds.append({
            **meta,
            "annualized_return":     round(float(mu[i]), 8),
            "annualized_volatility": round(float(np.sqrt(cov[i, i])), 8),
            "sharpe_ratio":          round(
                float((mu[i] - RISK_FREE_RATE) / np.sqrt(cov[i, i])), 8
            ),
            "nav_history_years":     int(T // 12),
        })

    # ── 8. JSON exports ───────────────────────────────────────────────────────
    print("\n[+] Exporting JSON artefacts …")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # mu_vector.json -- shape (10,)
    mu_payload = {
        "fund_codes":  FUND_CODES,
        "mu_vector":   [round(float(m), 8) for m in mu],
        "description": "Annualised mean log-return vector μ. Factor = 12.",
        "units":       "decimal (e.g. 0.09 = 9% p.a.)",
    }
    export_json(mu_payload, PROCESSED_DIR / "mu_vector.json", "μ vector")

    # cov_matrix.json -- shape (10, 10)
    cov_payload = {
        "fund_codes":  FUND_CODES,
        "cov_matrix":  [[round(float(cov[r, c]), 8) for c in range(N)] for r in range(N)],
        "description": "Annualised covariance matrix Σ. Factor = 12.",
        "units":       "decimal² (e.g. 0.025 = 2.5% variance)",
    }
    export_json(cov_payload, PROCESSED_DIR / "cov_matrix.json", "Σ matrix")

    # gmvp_weights.json
    # Renormalise weights after SLSQP so they sum to exactly 1.0 before rounding.
    w_gmvp_norm = w_gmvp / w_gmvp.sum()
    gmvp_payload = {
        "fund_codes":             FUND_CODES,
        "weights":                [round(float(wi), 8) for wi in w_gmvp_norm],
        "expected_annual_return": round(gmvp_er, 8),
        "annual_volatility":      round(gmvp_vol, 8),
        "sharpe_ratio":           round(gmvp_sr, 8),
        "method":                 gmvp_method,
        "sum_weights":            round(float(w_gmvp_norm.sum()), 10),
    }
    export_json(gmvp_payload, PROCESSED_DIR / "gmvp_weights.json", "GMVP weights")

    # frontier_points.json -- 50 points
    export_json(frontier, PROCESSED_DIR / "frontier_points.json", "Frontier (50 pts)")

    # funds_manifest.json -- used by GET /api/v1/funds
    funds_manifest = {
        "funds":            enriched_funds,
        "covariance_matrix": [[round(float(cov[r, c]), 8) for c in range(N)]
                               for r in range(N)],
        "risk_free_rate":   RISK_FREE_RATE,
        "annualisation_factor": ANNUALISATION_FACTOR,
        "data_start_date":  str(nav_df.index[0].date()),
        "data_end_date":    str(nav_df.index[-1].date()),
        "num_observations": int(T),
    }
    export_json(funds_manifest, PROCESSED_DIR / "funds_manifest.json", "Funds manifest")

    # ── 9. Summary ────────────────────────────────────────────────────────────
    elapsed = (time.perf_counter() - t_start) * 1000
    print(f"\n{'='*70}")
    print(f"[OK] Pipeline complete in {elapsed:.0f} ms")
    print(f"  Observations (T)     : {T}")
    print(f"  Assets (N)           : {N}")
    print(f"  μ range              : {mu.min()*100:.2f}% -> {mu.max()*100:.2f}%")
    print(f"  Diagonal σ range     : "
          f"{np.sqrt(cov.diagonal()).min()*100:.2f}% -> "
          f"{np.sqrt(cov.diagonal()).max()*100:.2f}%")
    print(f"  det(Σ)               : {np.linalg.det(cov):.6e}")
    print(f"  GMVP σ_p             : {gmvp_vol*100:.4f}%")
    print(f"  Frontier points      : {len(frontier)}")
    print(f"{'='*70}")

    return {
        "mu":       mu,
        "cov":      cov,
        "w_gmvp":   w_gmvp,
        "frontier": frontier,
        "T":        T,
        "N":        N,
    }


# ── Acceptance Criteria Checks ────────────────────────────────────────────────

def run_acceptance_checks(results: dict) -> None:
    """
    Execute all Definition-of-Done checks from the PRD and print a report.
    These mirror the criteria in PRD Section 3 (data/Excel module DoD).
    """
    print("\n" + "=" * 70)
    print("Acceptance Criteria (Definition of Done) — data pipeline")
    print("=" * 70)
    checks: list[tuple[str, bool, str]] = []

    mu   = results["mu"]
    cov  = results["cov"]
    w    = results["w_gmvp"]
    fpts = results["frontier"]
    T    = results["T"]

    # [1] ≥ 120 monthly NAV rows in each CSV
    all_csvs_ok = all(
        (RAW_DIR / f"{c}.csv").exists() for c in FUND_CODES
    )
    checks.append(("10 fund CSVs present in /data/raw/", all_csvs_ok, ""))

    min_rows = min(
        len(pd.read_csv(RAW_DIR / f"{c}.csv")) for c in FUND_CODES
    )
    checks.append((
        f"Each CSV ≥ 121 rows (incl t=0); min found = {min_rows}",
        min_rows >= 121,
        ""
    ))

    # [2] μ and Σ computed without NaN
    checks.append(("μ vector has no NaN/Inf", bool(np.all(np.isfinite(mu))), ""))
    checks.append(("Σ matrix has no NaN/Inf", bool(np.all(np.isfinite(cov))), ""))

    # [3] Positive definiteness — verified via minimum eigenvalue and condition number.
    # Note: raw det of a 10x10 scaled covariance is naturally ~1e-22; not a singularity signal.
    # PRD MDETERM > 1e-10 guideline applies to the Excel model which uses percentage-scaled data;
    # the Python model uses decimal form. The correct PD check is min_eigenvalue > 0.
    min_eig = float(np.linalg.eigvalsh(cov).min())
    cond_num = float(np.linalg.cond(cov))
    pd_ok = (min_eig > 0) and (cond_num < 1e10)
    checks.append((
        f"Cov matrix positive definite: min_eigenval={min_eig:.4e}, "
        f"cond={cond_num:.2e} < 1e10",
        pd_ok, ""
    ))

    # [4] GMVP weights sum to 1.0
    w_sum = w.sum()
    checks.append((
        f"GMVP sum(w) = {w_sum:.10f} ≈ 1.0",
        bool(abs(w_sum - 1.0) < 1e-8),
        ""
    ))

    # [5] GMVP all weights ≥ 0 (long-only)
    checks.append((
        f"GMVP all w_i ≥ 0  (min = {w.min():.6f})",
        bool(np.all(w >= -1e-8)),
        ""
    ))

    # [6] Efficient frontier has exactly 50 points
    checks.append((
        f"Efficient frontier = {len(fpts)} points (need 50)",
        len(fpts) == 50,
        ""
    ))

    # [7] All 4 JSON files present in /data/processed/
    json_files = [
        "mu_vector.json", "cov_matrix.json",
        "gmvp_weights.json", "frontier_points.json",
    ]
    for fname in json_files:
        exists = (PROCESSED_DIR / fname).exists()
        checks.append((f"/data/processed/{fname} present", exists, ""))

    # Print report
    all_pass = True
    for desc, passed, note in checks:
        status = "[OK] PASS" if passed else "[FAIL] FAIL"
        line   = f"  [{status}]  {desc}"
        if note:
            line += f"  <- {note}"
        print(line)
        if not passed:
            all_pass = False

    print(f"\n{'='*70}")
    if all_pass:
        print("  [OK] ALL ACCEPTANCE CRITERIA PASSED -- data pipeline DoD satisfied.")
    else:
        print("  [FAIL] SOME CHECKS FAILED -- review output above.")
    print("=" * 70)


if __name__ == "__main__":
    results = run_pipeline()
    run_acceptance_checks(results)
