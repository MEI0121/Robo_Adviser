# Robo-Adviser Reconciliation Report

**Overall Status:** ❌ FAIL  
**Timestamp:** 2026-04-22T13:45:34.662467Z  
**Git Commit SHA (Backend):** `37c8126`  
**Excel Model Version:** 2026-04-22 21:40:56  
**Elapsed Time:** 3.733s  

**26 passed**, **1 skipped** (no Excel reference), **5 failed** out of 32 total.

> **SKIP semantics:** a check reports SKIP when no Excel reference CSV is found under `data/reconciliation/`. Earlier versions of this report silently dropped skipped rows, which made the pass count look stronger than it was. Each SKIP row below identifies a reconciliation gap that the Excel audit model will eventually close.

---

## Check Results

| # | Check | Status | Max Deviation | Tolerance | Notes |
|---|-------|--------|--------------|-----------|-------|
| 1 | μ vector (10 elements) | ✅ PASS | `4.22e-09` | `1e-06` |  |
| 2 | Σ matrix (100 elements) | ✅ PASS | `4.75e-09` | `1e-06` |  |
| 3 | GMVP weights (10 elements) | ❌ FAIL | `3.56e-01` | `1e-06` |  |
| 4 | GMVP E(r_p) | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 5 | GMVP σ_p | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 6 | GMVP Sharpe | ✅ PASS | `0.00e+00` | `1e-04` |  |
| 7 | Optimal weights (A=0.5) | ✅ PASS | `6.94e-16` | `1e-06` |  |
| 8 | Optimal A=0.5 E(r_p) | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 9 | Optimal A=0.5 σ_p | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 10 | Optimal A=0.5 Sharpe | ✅ PASS | `0.00e+00` | `1e-04` |  |
| 11 | Optimal weights (A=2.0) | ✅ PASS | `5.97e-16` | `1e-06` |  |
| 12 | Optimal A=2.0 E(r_p) | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 13 | Optimal A=2.0 σ_p | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 14 | Optimal A=2.0 Sharpe | ✅ PASS | `0.00e+00` | `1e-04` |  |
| 15 | Optimal weights (A=3.5) | ✅ PASS | `1.39e-16` | `1e-06` |  |
| 16 | Optimal A=3.5 E(r_p) | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 17 | Optimal A=3.5 σ_p | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 18 | Optimal A=3.5 Sharpe | ✅ PASS | `0.00e+00` | `1e-04` |  |
| 19 | Optimal weights (A=6.0) | ❌ FAIL | `8.44e-05` | `1e-06` |  |
| 20 | Optimal A=6.0 E(r_p) | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 21 | Optimal A=6.0 σ_p | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 22 | Optimal A=6.0 Sharpe | ✅ PASS | `0.00e+00` | `1e-04` |  |
| 23 | Optimal weights (A=10.0) | ✅ PASS | `2.23e-07` | `1e-06` |  |
| 24 | Optimal A=10.0 E(r_p) | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 25 | Optimal A=10.0 σ_p | ✅ PASS | `0.00e+00` | `1e-06` |  |
| 26 | Optimal A=10.0 Sharpe | ✅ PASS | `0.00e+00` | `1e-04` |  |
| 27 | Frontier weights (100 points) | ❌ FAIL | `3.50e-01` | `1e-05` |  |
| 28 | GMVP (short-allowed) weights | ❌ FAIL | `6.57e-06` | `1e-06` |  |
| 29 | Tangency (long-only) weights | ✅ PASS | `7.22e-16` | `1e-06` | solver: `fallback` |
| 30 | Tangency (short-allowed) weights | ⚠ SKIP (no Excel reference) | — | `1e-06` | solver: `fallback`; no Excel reference |
| 31 | Frontier weights (short-allowed, 100 points) | ❌ FAIL | `2.46e-02` | `1e-05` |  |
| 32 | Equal-weight (E[r], σ, Sharpe) | ✅ PASS | `3.81e-09` | `1e-06` |  |

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
| 2 | `0.20000000` | N/A | N/A |
| 3 | `0.40000000` | N/A | N/A |
| 4 | `0.00000000` | N/A | N/A |
| 5 | `0.40000000` | N/A | N/A |
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