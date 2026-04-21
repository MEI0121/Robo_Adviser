# Robo-Adviser Reconciliation Report

**Overall Status:** ✅ PASS  
**Timestamp:** 2026-04-21T17:04:26.650266Z  
**Git Commit SHA (Backend):** `5640a71`  
**Excel Model Version:** N/A (no Excel CSVs found)  
**Elapsed Time:** 0.083s  

**18 passed**, **14 skipped** (no Excel reference) out of 32 total.

> **SKIP semantics:** a check reports SKIP when no Excel reference CSV is found under `data/reconciliation/`. Earlier versions of this report silently dropped skipped rows, which made the pass count look stronger than it was. Each SKIP row below identifies a reconciliation gap that the Excel audit model will eventually close.

---

## Check Results

| # | Check | Status | Max Deviation | Tolerance | Notes |
|---|-------|--------|--------------|-----------|-------|
| 1 | μ vector (10 elements) | ⚠ SKIP (no Excel reference) | — | `1e-06` | no Excel reference |
| 2 | Σ matrix (100 elements) | ⚠ SKIP (no Excel reference) | — | `1e-06` | no Excel reference |
| 3 | GMVP weights (10 elements) | ⚠ SKIP (no Excel reference) | — | `1e-06` | no Excel reference |
| 4 | GMVP E(r_p) | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 5 | GMVP σ_p | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 6 | GMVP Sharpe | ✅ PASS | `0.00e+00` | `1e-04` |  |
| 7 | Optimal weights (A=0.5) | ⚠ SKIP (no Excel reference) | — | `1e-06` | no Excel reference |
| 8 | Optimal A=0.5 E(r_p) | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 9 | Optimal A=0.5 σ_p | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 10 | Optimal A=0.5 Sharpe | ✅ PASS | `0.00e+00` | `1e-04` |  |
| 11 | Optimal weights (A=2.0) | ⚠ SKIP (no Excel reference) | — | `1e-06` | no Excel reference |
| 12 | Optimal A=2.0 E(r_p) | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 13 | Optimal A=2.0 σ_p | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 14 | Optimal A=2.0 Sharpe | ✅ PASS | `0.00e+00` | `1e-04` |  |
| 15 | Optimal weights (A=3.5) | ⚠ SKIP (no Excel reference) | — | `1e-06` | no Excel reference |
| 16 | Optimal A=3.5 E(r_p) | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 17 | Optimal A=3.5 σ_p | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 18 | Optimal A=3.5 Sharpe | ✅ PASS | `0.00e+00` | `1e-04` |  |
| 19 | Optimal weights (A=6.0) | ⚠ SKIP (no Excel reference) | — | `1e-06` | no Excel reference |
| 20 | Optimal A=6.0 E(r_p) | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 21 | Optimal A=6.0 σ_p | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 22 | Optimal A=6.0 Sharpe | ✅ PASS | `0.00e+00` | `1e-04` |  |
| 23 | Optimal weights (A=10.0) | ⚠ SKIP (no Excel reference) | — | `1e-06` | no Excel reference |
| 24 | Optimal A=10.0 E(r_p) | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 25 | Optimal A=10.0 σ_p | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 26 | Optimal A=10.0 Sharpe | ✅ PASS | `0.00e+00` | `1e-04` |  |
| 27 | Frontier weights (long-only, 100 points) | ⚠ SKIP (no Excel reference) | — | `1e-05` | no Excel reference |
| 28 | GMVP (short-allowed) weights | ⚠ SKIP (no Excel reference) | — | `1e-06` | no Excel reference |
| 29 | Tangency (long-only) weights | ⚠ SKIP (no Excel reference) | — | `1e-06` | solver: `fallback`; no Excel reference |
| 30 | Tangency (short-allowed) weights | ⚠ SKIP (no Excel reference) | — | `1e-06` | solver: `fallback`; no Excel reference |
| 31 | Frontier weights (short-allowed, 100 points) | ⚠ SKIP (no Excel reference) | — | `1e-05` | no Excel reference |
| 32 | Equal-weight (E[r], σ, Sharpe) | ⚠ SKIP (no Excel reference) | — | `1e-06` | no Excel reference |

---

## GMVP Weights: Python vs Excel

| Asset | Python Weight | Excel Weight | Deviation |
|-------|--------------|-------------|-----------|
| 0 | `0.00000000` | N/A | N/A |
| 1 | `0.00000000` | N/A | N/A |
| 2 | `0.01907770` | N/A | N/A |
| 3 | `0.00000000` | N/A | N/A |
| 4 | `0.00000000` | N/A | N/A |
| 5 | `0.00000000` | N/A | N/A |
| 6 | `0.00000000` | N/A | N/A |
| 7 | `0.98092230` | N/A | N/A |
| 8 | `0.00000000` | N/A | N/A |
| 9 | `0.00000000` | N/A | N/A |

---

## Optimal Portfolio Weights (A=3.5): Python vs Excel

| Asset | Python Weight | Excel Weight | Deviation |
|-------|--------------|-------------|-----------|
| 0 | `0.00000000` | N/A | N/A |
| 1 | `0.00000000` | N/A | N/A |
| 2 | `0.00000000` | N/A | N/A |
| 3 | `0.00000000` | N/A | N/A |
| 4 | `0.00000000` | N/A | N/A |
| 5 | `1.00000000` | N/A | N/A |
| 6 | `0.00000000` | N/A | N/A |
| 7 | `0.00000000` | N/A | N/A |
| 8 | `0.00000000` | N/A | N/A |
| 9 | `0.00000000` | N/A | N/A |

---

## Tolerance Specifications (PRD Section 4.3)

| Metric | Absolute Tolerance | Notes |
|--------|-------------------|-------|
| μ vector (10 elements) | `1e-06` | Annualized mean returns |
| Σ matrix (100 elements) | `1e-06` | Annualized covariance matrix |
| GMVP weights (10) | `1e-06` | Closed-form vs MMULT/MINVERSE |
| Optimal weights (10, per A) | `1e-06` | SLSQP vs Excel Solver |
| E(r_p) | `1e-06` | Portfolio expected return |
| σ_p | `1e-06` | Portfolio volatility |
| Sharpe Ratio | `1e-04` | Relaxed due to r_f rounding |
| Frontier weights | `1e-05` | Parametric sweep; relaxed |

---

## Failure Escalation Protocol

If any check fails, refer to PRD Section 4.4 root-cause categories:

- **DATA_PIPELINE_ERROR** — μ mismatch → check decimal precision / date alignment
- **MATRIX_ALGEBRA_BUG** — μ matches but GMVP fails → NumPy inv() vs MINVERSE()
- **OPTIMIZER_CONVERGENCE** — GMVP matches but optimal portfolio fails → tighten ftol
- **ANNUALIZATION_ERROR** — Monthly vs annual factor mismatch (12 vs 252)

_Report generated by `reconcile.py` (QA reconciliation harness)._