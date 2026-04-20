"""
generate_nav_data.py
====================
Data pipeline — optional synthetic NAV generator | Robo-Adviser Platform

**Deprecated for production:** use `download_yfinance_data.py` + `fund_universe.py`
for real ETF prices. This script remains as an optional synthetic-data generator.

Generates 15 years of realistic monthly NAV history (Jan 2010 – Dec 2024, 180 observations)
for 10 FSMOne funds spanning 6 distinct asset classes, using a multivariate Geometric
Brownian Motion (GBM) model with a calibrated correlation/volatility structure.

Each fund's monthly log-return is drawn from:
    r_t ~ N(μ_monthly, Σ_monthly)

where Σ_monthly is derived from the annualised covariance C via:
    Σ_monthly = C / 12

NAV series are initialised to 10.0000 and reconstructed as:
    NAV_t = NAV_{t-1} × exp(r_t)

Output: one CSV per fund in /data/raw/  with schema:
    date (ISO 8601, first business day of month), nav (4dp), fund_code
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path

# Force UTF-8 output on Windows to avoid GBK codec errors with Unicode symbols
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ── Reproducibility ──────────────────────────────────────────────────────────
RANDOM_SEED = 42

# ── Fund Universe ─────────────────────────────────────────────────────────────
# 10 funds across 6 asset classes as specified in PRD Appendix A.
FUNDS = [
    {
        "fund_code":  "LU0321462953",
        "fund_name":  "Fidelity Funds - World Fund A-USD",
        "asset_class": "Equity-Global",
        "currency":   "USD",
        "nav_start":  10.0000,
    },
    {
        "fund_code":  "SG9999009836",
        "fund_name":  "Nikko AM Shenton Global Opportunities Fund",
        "asset_class": "Equity-Global",
        "currency":   "USD",
        "nav_start":  10.0000,
    },
    {
        "fund_code":  "LU0231203729",
        "fund_name":  "Schroder ISF Asian Equity Yield A Acc USD",
        "asset_class": "Equity-Regional",
        "currency":   "USD",
        "nav_start":  10.0000,
    },
    {
        "fund_code":  "LU0011850392",
        "fund_name":  "Franklin Templeton Emerging Markets Fund A",
        "asset_class": "Equity-Regional",
        "currency":   "USD",
        "nav_start":  10.0000,
    },
    {
        "fund_code":  "IE00B3DBRK16",
        "fund_name":  "PIMCO GIS Income Fund E Class Acc USD-H",
        "asset_class": "Fixed-Income",
        "currency":   "USD",
        "nav_start":  10.0000,
    },
    {
        "fund_code":  "LU0093503795",
        "fund_name":  "Fidelity Funds - Global Bond Fund A-USD",
        "asset_class": "Fixed-Income",
        "currency":   "USD",
        "nav_start":  10.0000,
    },
    {
        "fund_code":  "LU0153384099",
        "fund_name":  "Pictet - High Yield P USD",
        "asset_class": "Fixed-Income",
        "currency":   "USD",
        "nav_start":  10.0000,
    },
    {
        "fund_code":  "SG9999013561",
        "fund_name":  "Manulife Income Builder Fund Class A",
        "asset_class": "Multi-Asset",
        "currency":   "USD",
        "nav_start":  10.0000,
    },
    {
        "fund_code":  "LU0209135028",
        "fund_name":  "BlackRock World Real Estate Securities A2 USD",
        "asset_class": "REIT",
        "currency":   "USD",
        "nav_start":  10.0000,
    },
    {
        "fund_code":  "LU0171305526",
        "fund_name":  "BlackRock World Gold Fund A2 USD",
        "asset_class": "Commodity",
        "currency":   "USD",
        "nav_start":  10.0000,
    },
]

# Index mapping for readability
# 0: Global Eq 1 | 1: Global Eq 2 | 2: Asia-Pac Eq | 3: EM Eq
# 4: IG Bond 1   | 5: IG Bond 2   | 6: HY Bond     | 7: Multi-Asset
# 8: REIT        | 9: Gold/Commodity

# ── Calibrated Annual Parameters ─────────────────────────────────────────────
# Annualised expected log-returns (drift) and volatilities.
# Sourced from long-run historical averages of comparable asset classes.
ANNUAL_MU = np.array([
    0.0900,   # 0: Global Equity 1    (~9% p.a.)
    0.0850,   # 1: Global Equity 2    (~8.5% p.a.)
    0.0750,   # 2: Asia-Pacific Eq    (~7.5% p.a.)
    0.0800,   # 3: EM Equity          (~8% p.a.)
    0.0380,   # 4: IG Fixed Income 1  (~3.8% p.a.)
    0.0350,   # 5: IG Fixed Income 2  (~3.5% p.a.)
    0.0600,   # 6: High Yield Bond    (~6% p.a.)
    0.0620,   # 7: Multi-Asset        (~6.2% p.a.)
    0.0780,   # 8: REIT               (~7.8% p.a.)
    0.0550,   # 9: Gold/Commodity     (~5.5% p.a.)
], dtype=np.float64)

ANNUAL_VOL = np.array([
    0.1600,   # 0: Global Equity 1
    0.1650,   # 1: Global Equity 2
    0.1800,   # 2: Asia-Pacific Eq
    0.2200,   # 3: EM Equity
    0.0500,   # 4: IG Fixed Income 1
    0.0480,   # 5: IG Fixed Income 2
    0.0950,   # 6: High Yield Bond
    0.1050,   # 7: Multi-Asset
    0.1700,   # 8: REIT
    0.1800,   # 9: Gold/Commodity
], dtype=np.float64)

# ── Correlation Matrix ────────────────────────────────────────────────────────
# 10×10 symmetric, positive definite.
# Off-diagonal entries reflect realistic cross-asset correlations.
CORR = np.array([
# GEq1  GEq2  APEq  EMEq  IGBd1 IGBd2 HYBd  MAsst REIT  Gold
 [1.00, 0.87, 0.68, 0.72, -0.15, -0.18, 0.42, 0.72, 0.60, 0.08],  # GEq1
 [0.87, 1.00, 0.65, 0.70, -0.12, -0.15, 0.40, 0.70, 0.58, 0.06],  # GEq2
 [0.68, 0.65, 1.00, 0.75, -0.10, -0.12, 0.38, 0.62, 0.52, 0.10],  # APEq
 [0.72, 0.70, 0.75, 1.00, -0.08, -0.10, 0.45, 0.65, 0.55, 0.12],  # EMEq
 [-0.15,-0.12,-0.10,-0.08, 1.00, 0.82, 0.38, 0.35, 0.15,-0.05],   # IGBd1
 [-0.18,-0.15,-0.12,-0.10, 0.82, 1.00, 0.40, 0.38, 0.18,-0.08],   # IGBd2
 [0.42, 0.40, 0.38, 0.45, 0.38, 0.40, 1.00, 0.55, 0.40, 0.05],    # HYBd
 [0.72, 0.70, 0.62, 0.65, 0.35, 0.38, 0.55, 1.00, 0.58, 0.10],    # Multi-Asset
 [0.60, 0.58, 0.52, 0.55, 0.15, 0.18, 0.40, 0.58, 1.00, 0.05],    # REIT
 [0.08, 0.06, 0.10, 0.12,-0.05,-0.08, 0.05, 0.10, 0.05, 1.00],    # Gold
], dtype=np.float64)


def _ensure_positive_definite(matrix: np.ndarray, epsilon: float = 1e-8) -> np.ndarray:
    """
    Nudge a near-singular correlation matrix to be strictly positive definite
    by adding epsilon to the diagonal.  Required because hand-crafted
    correlation matrices can have near-zero eigenvalues.
    """
    min_eig = np.linalg.eigvalsh(matrix).min()
    if min_eig < 0:
        matrix = matrix + (-min_eig + epsilon) * np.eye(matrix.shape[0])
    return matrix


def build_covariance_matrix(annual_vol: np.ndarray, corr: np.ndarray) -> np.ndarray:
    """
    Construct the annualised covariance matrix from volatilities and correlation:
        Σ_annual[i,j] = σ_i × σ_j × ρ_{i,j}
    """
    vol_outer = np.outer(annual_vol, annual_vol)
    cov_annual = vol_outer * corr
    return cov_annual.astype(np.float64)


def generate_monthly_nav_series(
    annual_mu: np.ndarray,
    cov_annual: np.ndarray,
    n_months: int,
    nav_start: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Simulate a single fund's monthly NAV using the scalar slice of the
    multivariate log-return distribution.  The full multivariate draw is
    performed once for all funds together; this function receives that slice.

    Actually, this helper is not used directly — see simulate_all_nav() below.
    """
    raise NotImplementedError("Use simulate_all_nav() instead.")


def simulate_all_nav(
    annual_mu: np.ndarray,
    cov_annual: np.ndarray,
    nav_starts: np.ndarray,
    n_months: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Simulate NAV paths for all N funds jointly.

    Parameters
    ----------
    annual_mu    : (N,) annualised log-drift vector
    cov_annual   : (N, N) annualised covariance matrix
    nav_starts   : (N,) initial NAV values
    n_months     : number of monthly time steps
    rng          : seeded NumPy random Generator

    Returns
    -------
    nav_matrix : (n_months+1, N) float64 array
                 Row 0 = nav_starts; row t = NAV at end of month t
    """
    n_assets = len(annual_mu)

    # Convert annual parameters to monthly
    mu_monthly = annual_mu / 12.0                    # monthly drift
    cov_monthly = cov_annual / 12.0                  # monthly covariance

    # Draw (n_months, N) correlated log-returns from N(mu_monthly, cov_monthly)
    log_returns = rng.multivariate_normal(
        mean=mu_monthly,
        cov=cov_monthly,
        size=n_months,
    ).astype(np.float64)   # shape: (n_months, N)

    # Reconstruct NAV paths: NAV_t = NAV_{t-1} * exp(r_t)
    nav_matrix = np.zeros((n_months + 1, n_assets), dtype=np.float64)
    nav_matrix[0] = nav_starts

    for t in range(1, n_months + 1):
        nav_matrix[t] = nav_matrix[t - 1] * np.exp(log_returns[t - 1])

    return nav_matrix


def generate_monthly_date_index(
    start: str = "2010-01-01",
    periods: int = 181,   # 180 returns + 1 start date
) -> pd.DatetimeIndex:
    """
    Return a DatetimeIndex of first business days of each month.
    Uses pandas MonthBegin offset; business-day adjustment via BMonthBegin.
    """
    dates = pd.date_range(start=start, periods=periods, freq="MS")
    # Snap to first business day of each month
    biz_dates = dates + pd.offsets.BusinessMonthBegin(0)
    return biz_dates


def write_fund_csvs(
    nav_matrix: np.ndarray,
    date_index: pd.DatetimeIndex,
    funds: list[dict],
    output_dir: Path,
) -> None:
    """
    Write one CSV per fund with columns: date, nav, fund_code.
    NAV values are rounded to 4 decimal places.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for i, fund in enumerate(funds):
        code = fund["fund_code"]
        navs = np.round(nav_matrix[:, i], 4)

        df = pd.DataFrame({
            "date":      date_index.strftime("%Y-%m-%d"),
            "nav":       navs,
            "fund_code": code,
        })

        out_path = output_dir / f"{code}.csv"
        df.to_csv(out_path, index=False)
        print(f"  [OK] {code} — {len(df):>3} rows → {out_path.name}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("NAV Data Generator (synthetic)")
    print("Generating 15-year monthly NAV history (Jan 2010 – Dec 2024)")
    print("10 funds | 180 monthly observations each")
    print("=" * 60)

    rng = np.random.default_rng(RANDOM_SEED)

    # ── Build covariance matrix ──────────────────────────────────────────────
    corr_pd = _ensure_positive_definite(CORR)
    cov_annual = build_covariance_matrix(ANNUAL_VOL, corr_pd)

    # Verify positive definiteness via eigenvalues (not raw determinant,
    # which is naturally tiny for a 10×10 matrix with sub-unit variances).
    eigvals = np.linalg.eigvalsh(cov_annual)
    min_eig = eigvals.min()
    assert min_eig > 0, (
        f"Covariance matrix is not positive definite! min eigenvalue = {min_eig:.4e}"
    )
    det  = np.linalg.det(cov_annual)
    cond = np.linalg.cond(cov_annual)
    assert cond < 1e10, (
        f"Covariance matrix is ill-conditioned: κ = {cond:.4e} (threshold 1e10)"
    )
    print(
        f"\nCovariance matrix verified: det(Σ) = {det:.6e} | "
        f"min_eigenval = {min_eig:.6e} | condition # = {cond:.4e}  ✓"
    )

    # ── Simulate NAV paths ───────────────────────────────────────────────────
    N_MONTHS = 180   # 15 years × 12 months
    nav_starts = np.array([f["nav_start"] for f in FUNDS], dtype=np.float64)

    nav_matrix = simulate_all_nav(
        annual_mu=ANNUAL_MU,
        cov_annual=cov_annual,
        nav_starts=nav_starts,
        n_months=N_MONTHS,
        rng=rng,
    )

    # ── Date index ────────────────────────────────────────────────────────────
    date_index = generate_monthly_date_index(start="2010-01-01", periods=N_MONTHS + 1)

    # ── Write CSVs ────────────────────────────────────────────────────────────
    raw_dir = Path(__file__).parent.parent / "data" / "raw"
    print(f"\nWriting CSVs to: {raw_dir}\n")
    write_fund_csvs(nav_matrix, date_index, FUNDS, raw_dir)

    print(f"\n✓ {len(FUNDS)} fund CSVs written.  Each has {N_MONTHS + 1} rows "
          f"(including NAV at t=0).")
    print("\nFund Universe Summary:")
    print(f"  {'Fund Code':<18}  {'Asset Class':<22}  {'Final NAV':>10}  {'Annualised Return':>18}")
    print(f"  {'-'*18}  {'-'*22}  {'-'*10}  {'-'*18}")
    for i, fund in enumerate(FUNDS):
        nav_path = nav_matrix[:, i]
        # Compute realised annualised log-return from the simulated path
        total_log_return = np.log(nav_path[-1] / nav_path[0])
        ann_return = total_log_return / (N_MONTHS / 12.0)
        print(
            f"  {fund['fund_code']:<18}  {fund['asset_class']:<22}  "
            f"{nav_path[-1]:>10.4f}  {ann_return*100:>17.2f}%"
        )


if __name__ == "__main__":
    main()
