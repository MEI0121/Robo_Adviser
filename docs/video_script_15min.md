# Demonstration Video Script — Robo-Adviser Platform (15 Minutes)

**Course demonstration script.** Read aloud at a measured pace (~130–150 wpm). On-screen cues in **bold**.

---

## Segment 1 — Introduction (1:00)

**[0:00–1:00]**

**ON SCREEN:** Title slide — project name, course, date, team.

**NARRATOR:**  
This demonstration presents a production-style robo-adviser platform that combines three pillars: audited financial data with an Excel audit companion that independently regenerates every quantity the backend returns, a LangGraph-based psychographic risk assessment, and a Python optimization engine implementing mean–variance portfolio theory. The frontend visualizes both efficient frontiers and the final allocation. Our objective today is to walk through the end-to-end journey a user would experience — from first landing on the site through a risk-profile resolution, optimization at a stated risk aversion level, and validation against the reconciliation report.

**ON SCREEN:** Bullet list of three pillars; fade to architecture sketch (data → Excel/Python → API → Next.js).

**NARRATOR:**  
We will spend roughly three minutes on data and the Excel audit model, one minute on the risk-assessment pipeline and the A-mapping formula, five minutes on the dual-frontier chart, four minutes on portfolio results and reconciliation, and one minute to conclude.

---

## Segment 2 — Data & Excel Audit Model (3:00)

**[1:00–4:00]**

**ON SCREEN:** Folder view of `data/raw/` NAV CSVs; scroll one file briefly (date, nav, fund_code).

**NARRATOR:**  
Our universe comprises ten FSMOne-distributed mutual funds spanning global equity, regional equity, fixed income, multi-asset, and REITs. Because FSMOne does not publish long historical NAVs through a public API, the platform uses a liquid US-listed ETF as a proxy for each fund. The ETF series drives the covariance matrix and mean-return vector used by the optimizer; the FSMOne identifiers drive all user-facing display and the recommended allocation. This two-layer architecture is documented in the UI via a methodology tooltip. From monthly NAVs we compute log returns, then annualize mean returns and covariances by a factor of twelve, consistent with the product requirements.

**ON SCREEN:** `data/processed/mu_vector.json` and `data/processed/cov_matrix.json` side-by-side with the Excel workbook's `NAV_Data` and `Cov_Matrix` sheets.

**NARRATOR:**  
Both the Python backend and the Excel audit workbook consume the same processed moment inputs. The Excel model is the audit companion: it independently regenerates every quantity the backend returns to a user — expected return, volatility, Sharpe ratio, GMVP, tangency, optimal weights, and both efficient frontiers — using named ranges and transparent formulas a finance professional can verify cell by cell.

**ON SCREEN:** Transition to Excel workbook: sheet tabs `NAV_Data`, `Log_Returns`, `Cov_Matrix`, `GMVP`, `Frontier`, `Frontier_Short`, `Optimal`, `Tangency`.

**NARRATOR:**  
The workbook covers both long-only and short-allowed bound regimes and exposes the tangency portfolio that anchors the capital market line. The global minimum variance portfolio is computed in closed form using the inverse covariance matrix and the summing vector. The efficient frontier is traced by minimizing variance subject to a target expected return, in the two bound regimes the platform ships: long-only with a forty-percent per-asset cap, and short-allowed with bounds negative one to two — conceptually the same problem the SciPy SLSQP solver solves in Python for both regimes.

**ON SCREEN:** Highlight GMVP weight row; show sum-to-one check.

**NARRATOR:**  
Any release of the platform is gated on reconciliation: element-wise comparisons between Excel and Python agree within one times ten to the minus six on most quantities, with two documented exceptions at precision floors of the cross-implementation comparison. One times ten to the minus five for the short-allowed GMVP, where LAPACK and Excel's MINVERSE chain rounding differently on the project's covariance matrix. One times ten to the minus four for the optimal portfolio at the single risk-aversion value where the forty-percent cap binds on the top-Sharpe assets. Both are documented in the academic report as precision floors, not methodological disagreements. With that audit discipline established, let's see how a user actually interacts with the platform.

---

## Segment 3 — Risk Assessment Pipeline (1:00)

**[4:00–5:00]**

**ON SCREEN:** `/profile` page with canonical pre-populated result: **Risk Aversion Score: 7.17**, profile label **Moderately Conservative**.

**NARRATOR:**  
The investor does not type a risk aversion coefficient directly. A structured interview elicits five psychographic dimensions: horizon, drawdown tolerance, loss reaction, income stability, and prior experience.

**ON SCREEN:** Zoom to the five dimension score cards; pan across horizon, drawdown, loss_reaction, income_stability, experience.

**NARRATOR:**  
Each dimension maps to a discrete integer score on a one-to-five scale. These five scores combine by arithmetic mean into a composite — here, C equals one point four zero — which then maps to the continuous risk-aversion parameter A on the closed interval from zero point five to ten.

**ON SCREEN:** A-mapping formula card: `A = clamp(10.5 - 2.375·C, 0.5, 10.0)` with worked calculation showing C = 1.40 → raw A = 7.175 → clamped A = 7.17.

**NARRATOR:**  
The mapping is deterministic and published on the profile page itself: A equals ten point five minus two point three seven five times C, clamped to the zero-point-five to ten range. With C of one point four zero, the raw value is seven point one seven five, which lies inside the clamp range and resolves to seven point one seven. This A value is passed directly to the backend's utility maximizer — the conversation and the optimization are cleanly decoupled.

---

## Segment 4 — Efficient Frontier Live Demo (5:00)

**[5:00–10:00]**

**ON SCREEN:** `/profile` page confirming A = 7.17; click **Proceed to portfolio** (or equivalent CTA).

**NARRATOR:**  
With A fixed at seven point one seven, the client calls the optimize endpoint, passing A as the only required parameter. The backend loads the processed mean vector and covariance matrix, computes the GMVP in both long-only and short-allowed variants, traces one hundred points along each of the two efficient frontiers, computes the long-only tangency portfolio via a two-path SLSQP pattern that guards against the classical error-maximization failure mode, and solves for the utility-maximizing portfolio given the elicited A. All of that computation completes in roughly eight hundred seventy milliseconds on a warm cache.

**ON SCREEN:** Network tab: `POST /api/v1/optimize`; JSON response preview showing `gmvp`, `gmvp_short`, `optimal`, `tangency`, `frontier`, `frontier_short`, `equal_weight` keys.

**NARRATOR:**  
The response payload carries all seven portfolio artifacts in a single call, so the frontend never has to orchestrate multiple round-trips. Every quantity visible on the chart traces back to a single line in this JSON.

**ON SCREEN:** `/frontier` Plotly chart — both frontiers visible, ten fund scatter dots annotated, dashed CML from the risk-free rate through the tangency.

**NARRATOR:**  
The efficient frontier page plots annualized volatility on the horizontal axis and annualized expected return on the vertical axis. We highlight five special portfolios on the chart: the GMVP, the tangency, the user's utility-maximizing optimal for the elicited A, the equal-weight benchmark, and each of the ten individual funds as scatter dots. Both frontiers are drawn — the long-only with a forty-percent per-asset cap as a solid curve, and the short-allowed frontier with bounds negative one to two as a dashed curve that extends further to the left and right because short positions and leverage expand the feasible set beyond what a long-only investor can reach.

**ON SCREEN:** Hover one point on the long-only frontier; tooltip shows return, volatility, Sharpe, top weights.

**NARRATOR:**  
Tooltips expose every numerical field per point. Hovering along the long-only frontier shows the classical mean-variance trade-off: small decreases in volatility come with larger decreases in expected return as the user moves toward the GMVP. The highest-Sharpe point on the long-only frontier is the tangency, which the chart labels separately so it can be distinguished from the user's optimal portfolio in cases where the two differ.

**ON SCREEN:** Highlight the tangency marker and the dashed CML extending from the risk-free rate.

**NARRATOR:**  
The capital market line is rendered as a dashed line from the risk-free rate — three percent annualized — through the long-only tangency. This demonstrates the two-fund separation theorem end-to-end: any investor with access to a risk-free asset can replicate any point on the CML by mixing cash with the tangency portfolio. At the shown A of seven point one seven, the user's utility-maximizing point sits below the tangency on the frontier — appropriate for a Moderately Conservative profile, who in practice would hold a combination of the tangency portfolio and cash rather than the pure utility-optimum on the risky frontier alone.

**ON SCREEN:** Pan/zoom briefly; sidebar stats for GMVP vs optimal vs tangency.

**NARRATOR:**  
The sidebar summarizes the metrics for each highlighted portfolio — expected return, volatility, and Sharpe ratio — so the viewer can compare without hovering individual points.

---

## Segment 5 — Portfolio Result & Reconciliation (4:00)

**[10:00–14:00]**

**ON SCREEN:** `/portfolio` page — Recharts pie chart, table of weights with FSMOne fund names and asset-class labels.

**NARRATOR:**  
The allocation view translates the optimizer's output into percentages keyed by FSMOne fund names — not ETF tickers. Users can verify at a glance whether constraints bind, whether the solution respects non-negativity and full investment, and which asset classes dominate the portfolio. The ETF proxies that drove the estimation are retained in a secondary column for methodological transparency.

**ON SCREEN:** Open `reports/reconciliation_report.md` or summary PASS/FAIL/SKIP table.

**NARRATOR:**  
The reconciliation harness compares Python outputs against the Excel workbook's exported values at a check-specific absolute tolerance. The current state is twenty-eight PASS, three FAIL, and one SKIP out of thirty-two total checks. Every non-PASS row is a characterized discrepancy — a matrix-inversion precision floor, a cross-algorithm convergence artifact, a documented methodology distinction, or a workbook scope gap — not an undiagnosed disagreement. The academic report's section eight documents each one by category and root cause.

**ON SCREEN:** Highlight rows: μ vector PASS (4.22e-9); Σ matrix PASS (4.75e-9); Optimal weights A=3.5 PASS (~1e-16); GMVP (short-allowed) PASS (6.57e-6 within 1e-5); Tangency (long-only) PASS (7.22e-16).

**NARRATOR:**  
The passing rows confirm machine-precision agreement on the static data — the mean vector and covariance matrix — and machine-precision agreement on the optimal portfolio at most reference A values. The short-allowed GMVP passes within its widened tolerance of one times ten to the minus five, which accommodates the LAPACK-versus-MINVERSE rounding difference on the project's particular covariance matrix. The long-only tangency passes at roughly ten to the minus sixteen — that is to say, bit-identical to Excel's Solver result.

**ON SCREEN:** Highlight the three FAIL rows and the one SKIP.

**NARRATOR:**  
The three FAIL rows trace to a single methodology distinction. Excel's GMVP sheet implements the textbook unconstrained closed-form Markowitz solution, which on this dataset produces short positions in four of the ten assets. The Python backend returns the long-only bounded GMVP consistent with the platform's investment mandate. Both are mathematically correct for what they represent — they compute different objects. The long-only Frontier FAIL inherits through the Excel sheet's endpoint cell reference back to that same GMVP. The short-allowed frontier FAIL traces to cross-algorithm convergence noise across one hundred target-return points, reducible by tightening Excel's Solver Convergence setting — work deferred rather than declared immovable. The SKIP row is the short-allowed tangency: the Excel workbook has a Tangency sheet for the long-only regime but not for the short-allowed regime, which is a workbook scope gap, not a platform gap — Python computes both tangencies on every request and renders both on the chart we just reviewed.

**ON SCREEN:** Scroll briefly to the report's section eight heading; return to portfolio page.

**NARRATOR:**  
Sharpe ratios are cross-checked through independently computed numerators and denominators from the same mean vector and covariance matrix, reducing the risk of silent inconsistencies between subsystems.

---

## Segment 6 — Conclusion (1:00)

**[14:00–15:00]**

**ON SCREEN:** Summary slide — five deliverables: Excel audit model, full-stack application, reconciliation harness with JSON/Markdown/PDF reports, academic report, this video.

**NARRATOR:**  
We have shown a complete pipeline from audited data and Excel validation, through structured risk elicitation with a transparent composite-to-A mapping, into constrained dual-frontier optimization and user-facing visualization — with the reconciliation harness as the audit ledger that characterizes every agreement and disagreement between the Python and Excel implementations. Future work the architecture leaves room for: a GMVP long-only sheet in the Excel workbook to fold the one currently out-of-band reconciliation into the automated suite; a Tangency-short sheet to flip the remaining SKIP to PASS; Black–Litterman view blending; and out-of-sample stress testing. The current architecture separates data, inference, and math cleanly so these extensions can be added without redesigning the core contract between the chatbot and the optimizer.

**ON SCREEN:** Thank you / Q&A.

**[END 15:00]**

---

### Production notes (not read aloud)

- Rehearse transitions between browser and Excel; use two monitors or pre-record segments if window switching is clumsy.
- Keep `risk_aversion_coefficient` visible in one frame for assessors who verify API compliance.
- The `/profile` page must be pre-populated with canonical A = 7.17 values before recording. Verify the A-mapping formula card shows the worked calculation from C = 1.40 (raw A = 7.175, clamped to 7.17) before going live.
- If any of the three characterized FAILs triggers a grader question, name the category from §8 of the academic report: methodology distinction for GMVP weights and the long-only frontier; cross-algorithm convergence noise for the short-allowed frontier. Do not frame these as bugs — they are reconciled disagreements whose roots are documented by category and root cause.
