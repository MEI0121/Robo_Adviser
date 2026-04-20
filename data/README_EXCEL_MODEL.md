# Excel Audit Model — Build Instructions
## Excel Audit Model — Build Guide | Robo-Adviser Platform

**Purpose:** This document is the step-by-step construction guide for the Excel audit model.
The Excel model is the **immutable financial source of truth**. Every number it produces
is compared against the Python backend output to within a tolerance of `1e-6`.

---

## Data provenance (must match the repo)

The Python pipeline does **not** use FSMOne NAV exports in the current implementation.
Instead:

| Item | Source |
|------|--------|
| Raw series | `/data/raw/{TICKER}.csv` — monthly **adjusted close** from Yahoo Finance |
| Downloader | `scripts/download_yfinance_data.py` (requires `yfinance`) |
| Universe | `scripts/fund_universe.py` — **10 Yahoo tickers in fixed order** |
| `fund_code` in CSV / JSON | **Ticker symbol** (e.g. `SPY`, `BNDX`), not an ISIN |
| `nav` column | ETF **price proxy** (adjusted monthly close), same role as fund NAV for optimisation |

**Critical:** Build Excel from the **same CSV files** committed or generated in `/data/raw/`.
Do not substitute different date ranges or reorder columns — covariance and GMVP depend on
**identical calendars** across all 10 assets.

**Calendar alignment:** The shortest history among the 10 ETFs sets the common window.
Currently **BNDX** starts later than others, so Python uses the **intersection of dates**
only (see `data/processed/funds_manifest.json` for `data_start_date`, `data_end_date`,
and `num_observations`). Excel must use that **same** intersection: one row per month
present in **all** ten series.

---

## Notation: sample length `T`

Let:

- **`T_nav`** = number of aligned monthly **price** rows (all 10 tickers).
- **`T`** = number of monthly **log-return** rows = `T_nav - 1`.

Example (typical after `download_yfinance_data.py`): `T_nav ≈ 155`, **`T ≈ 154`**.

All formulas below use **`T`** as the count of log-return rows. Replace literal ranges
like `B3:B182` with your actual last row (e.g. `B3:B156` if `T = 154`). The covariance
denominator must be **`(T - 1)`**, matching Python’s `pandas`/`numpy` sample covariance
with `ddof=1`.

---

## Sheet Layout

| Sheet | Contents |
|-------|---------|
| `NAV_Data` | Raw price series for all 10 tickers (from `/data/raw/*.csv`) |
| `Log_Returns` | Monthly log-return matrix |
| `Statistics` | μ vector, diagonal σ values |
| `Cov_Matrix` | 10×10 annualised covariance matrix Σ |
| `GMVP` | Closed-form GMVP via MMULT/MINVERSE |
| `Frontier` | 50-point efficient frontier via Solver (PRD data/Excel baseline) |
| `Export` | Formatted tables for CSV export |

---

## Sheet 1: NAV_Data

1. Copy each ticker’s CSV from `/data/raw/` (columns: `date`, `nav`, `fund_code`).
2. **Inner-join on date:** keep only dates where **every** ticker has a non-blank price
   (same logic as `data_pipeline.load_nav_matrix`).
3. Arrange as a **wide table**: column A = date, columns B–K = **adjusted price** by ticker.
4. Header row 1 — **exact order** (must match `scripts/fund_universe.py`):

   `Date | URTH | AOA | XLV | SPY | VNQ | QQQ | EMB | BNDX | AAXJ | VT`

5. Data rows: **`T_nav` rows** of prices (one per aligned month), not a fixed 181 rows.

---

## Sheet 2: Log_Returns

Reference column A from `NAV_Data`. For cell **B3** (first return for column B):

```excel
=LN(NAV_Data!B3 / NAV_Data!B2)
```

- Copy across columns B–K (tickers 1–10).
- Copy down for **`T` rows** (e.g. rows 3 through `2+T`).
- Row 2 is the first price row — no return on that row.

Named range: `LogReturns` = `B3:K{2+T}` (**T rows × 10 columns**).

---

## Sheet 3: Statistics

### Annualised Mean Return Vector (μ)

In cells **B2:K2** (one cell per ticker), if log returns occupy `B3:K{2+T}`:

```excel
=AVERAGE(Log_Returns!B3:B{2+T}) * 12
```

- Factor `* 12` annualises **monthly** log returns.
- Named range: `mu_vector` = B2:K2.

### Annualised Volatility (Diagonal of Σ)

In cells **B3:K3`:

```excel
=STDEV.S(Log_Returns!B3:B{2+T}) * SQRT(12)
```

(`STDEV.S` = sample standard deviation; matches `pandas` default for series.)

Named range: `sigma_vector` = B3:K3.

---

## Sheet 4: Cov_Matrix

### Excess Returns Matrix

Create a block `ExcessReturns` (**T × 10**):

```excel
=Log_Returns!B3 - AVERAGE(Log_Returns!B$3:B${2+T})
```

Copy across all 10 columns and all **T** rows.

### Covariance Matrix (mirrors PRD / Python)

For the **single** 10×10 block (e.g. `Cov_Matrix` = B2:K11), top-left cell:

```excel
=MMULT(TRANSPOSE(ExcessReturns), ExcessReturns) / (T - 1) * 12
```

Replace **`T`** with your **numeric** count of log-return rows (e.g. `154`), or use a
named cell `T_returns` so the divisor is `T_returns - 1`.

This is an **array formula** — enter with **Ctrl+Shift+Enter** (or Enter in Excel 365).

### Verify Positive Definiteness

```excel
=MDETERM(Cov_Matrix)
```

For **decimal**-scaled covariance (returns as decimals), the determinant is often very
small (e.g. `1e-25`). That does **not** mean singular — check **minimum eigenvalue > 0**
or condition number; align with `scripts/data_pipeline.py` validation.

---

## Sheet 5: GMVP

### Ones Vector

Name a vertical range of 10 cells containing `1` as `ones_vec`.

### Numerator: Σ⁻¹ × 1

```excel
=MMULT(MINVERSE(Cov_Matrix), ones_vec)
```

### Denominator: 1ᵀ × Σ⁻¹ × 1

```excel
=MMULT(TRANSPOSE(ones_vec), MMULT(MINVERSE(Cov_Matrix), ones_vec))
```

### GMVP Weights

```excel
=gmvp_numer / gmvp_denom
```

If Excel’s unconstrained GMVP includes small negative weights (Python may switch to
**constrained** long-only SLSQP), use Solver for a **long-only** GMVP to match the
backend when needed.

### Verification

```excel
=SUM(gmvp_weights)   → must equal 1.0000000000
```

### GMVP Portfolio Statistics

| Metric | Formula |
|--------|---------|
| E(r_p) | `=SUMPRODUCT(mu_vector, gmvp_weights)` or equivalent MMULT with matching shapes |
| σ_p²   | `=MMULT(TRANSPOSE(gmvp_weights), MMULT(Cov_Matrix, gmvp_weights))` |
| σ_p    | `=SQRT(...)` of variance cell |
| Sharpe | `=(gmvp_er - 0.03) / gmvp_vol` |

---

## Sheet 6: Frontier (50-Point Parametric Sweep)

The PRD data/Excel baseline requires **50** frontier points in Excel. The FastAPI spec (`POST /optimize`)
uses **100** points in Python — that is **intentional**; reconcile **μ, Σ, GMVP** and
either export 50 Python points for comparison or document the grid difference for QA reconciliation.

### Setup

1. Column A (rows 2–51): target returns from `gmvp_er` to `MAX(mu_vector)`.
2. Columns B–K: Solver-optimised weights per row.
3. Variance / vol / Sharpe columns as needed.

### Solver Configuration

| Setting | Value |
|---------|-------|
| **Objective** | Minimize `wᵀ Σ w` |
| **Variables** | `w_range` (10 weights) |
| **Constraint 1** | `SUM(w) = 1` |
| **Constraint 2** | `w >= 0` |
| **Constraint 3** | `wᵀ μ = target_return` |
| **Method** | GRG Nonlinear |
| **Precision** | 1e-8 or tighter |

---

## Sheet 7: Export

| Export File | Description |
|-------------|-------------|
| `excel_mu_vector.csv` | 10 annualised means |
| `excel_cov_matrix.csv` | 10×10 Σ |
| `excel_gmvp_weights.csv` | 10 GMVP weights |
| `excel_frontier.csv` | 50 frontier rows |

Use **UTF-8** CSV; **ticker** symbols in row labels must match `fund_universe.py`.

---

## Cross-Validation Against Python

From the project root:

```powershell
pip install -r requirements-data.txt
python scripts/download_yfinance_data.py
python scripts/data_pipeline.py
python scripts/reconcile.py
```

(`reconcile.py` — when present — compares Excel exports to `data/processed/*.json`.)

---

## Fund Universe Reference (current implementation)

Order **must** match columns in `NAV_Data` and rows in μ / Σ.

| # | Ticker (`fund_code`) | Name | Asset Class |
|---|----------------------|------|-------------|
| 1 | URTH | iShares MSCI World ETF | Equity-Global |
| 2 | AOA | iShares Core Aggressive Allocation ETF | Multi-Asset |
| 3 | XLV | Health Care Select Sector SPDR Fund | Equity-Regional |
| 4 | SPY | SPDR S&P 500 ETF Trust | Equity-Global |
| 5 | VNQ | Vanguard Real Estate ETF | REIT |
| 6 | QQQ | Invesco QQQ Trust | Equity-Regional |
| 7 | EMB | iShares J.P. Morgan USD EM Bond ETF | Fixed-Income |
| 8 | BNDX | Vanguard Total International Bond ETF | Fixed-Income |
| 9 | AAXJ | iShares MSCI AC Asia ex Japan ETF | Equity-Regional |
| 10 | VT | Vanguard Total World Stock ETF | Equity-Global |

---

## Key Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Risk-free rate r_f | 0.03 | 3% annualised |
| Annualisation | ×12 / ×√12 | On **monthly** log returns / std dev |
| Sample length `T` | **Variable** | Read from `funds_manifest.json` → `num_observations` |
| Assets N | 10 | Fixed |
| Excel frontier points | 50 | PRD data/Excel baseline |
| Python API frontier points | 100 | PRD backend spec — do not confuse in reconciliation |
| Reconciliation tolerance | 1e-6 | Absolute, per PRD |

---

*Data/Excel baseline should be frozen before QA reconciliation runs against exports.*
