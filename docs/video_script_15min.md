# Demonstration Video Script — Robo-Adviser Platform (15 Minutes)

**Course demonstration script.** Read aloud at a measured pace (~130–150 wpm). On-screen cues in **bold**.

---

## Segment 1 — Introduction (1:00)

**[0:00–1:00]**

**ON SCREEN:** Title slide — project name, course, date, team.

**NARRATOR:**  
This demonstration presents a production-style robo-adviser platform that combines three pillars: audited financial data and an Excel ground-truth model, a LangGraph-based psychographic risk assessment, and a Python optimization engine implementing mean–variance portfolio theory. The frontend visualizes the efficient frontier and final allocations. Our objective today is to walk through the end-to-end journey a user would experience—from first landing on the site through a risk conversation, optimization at a stated risk aversion level, and validation against reconciliation outputs.

**ON SCREEN:** Bullet list of three pillars; fade to architecture sketch (data → Excel/Python → API → Next.js).

**NARRATOR:**  
We will spend roughly three minutes on data and the Excel audit mindset, three minutes on the AI chatbot, four minutes on the efficient frontier live demo, three minutes on portfolio results and reconciliation, and one minute to conclude.

---

## Segment 2 — Data & Excel Audit Model (3:00)

**[1:00–4:00]**

**ON SCREEN:** Folder view of `/data/raw/` CSVs; scroll one file (date, nav, fund_code).

**NARRATOR:**  
Our universe comprises ten liquid funds and ETFs spanning multiple asset classes—global equity, regional equity, fixed income, multi-asset, REITs, and others—each with a long monthly NAV history aligned on a common calendar. From monthly net asset values we compute log returns, then annualize mean returns and covariances using a factor of twelve for monthly data, consistent with the product requirements.

**ON SCREEN:** Transition to Excel workbook: sheet tabs `NAV_Data`, `Log_Returns`, `Cov_Matrix`, `GMVP`, `Frontier`.

**NARRATOR:**  
The Excel model is the immutable audit baseline. It holds the same return series as the backend JSON inputs. The global minimum variance portfolio is computed in closed form using the inverse covariance matrix and the summing vector. The efficient frontier is traced by minimizing variance subject to a target expected return and long-only constraints—conceptually the same problem the SciPy solver solves in Python.

**ON SCREEN:** Highlight GMVP weight row; show sum-to-one check.

**NARRATOR:**  
Any release of the platform is gated on reconciliation: element-wise comparisons between Excel exports and Python outputs must agree within one times ten to the minus six on key quantities, with slightly relaxed tolerances only where the specification explicitly allows—for example, Sharpe ratios near the risk-free rate.

**ON SCREEN:** Optional: `mu_vector.json` / `cov_matrix.json` side-by-side with Excel export (blur sensitive paths if needed).

---

## Segment 3 — AI Risk Assessment Chatbot (3:00)

**[4:00–7:00]**

**ON SCREEN:** Browser — landing page; click **Start assessment** (or equivalent CTA).

**NARRATOR:**  
The investor does not type a risk aversion coefficient directly. Instead, a structured interview elicits horizon, drawdown tolerance, reaction to losses, income stability, and experience. Each dimension maps to a discrete score, which feeds a deterministic composite mapping onto the continuous parameter A on the closed interval from zero point five to ten.

**ON SCREEN:** `/assess` chat UI; show multi-turn messages; progress indicator advancing across five dimensions.

**NARRATOR:**  
The orchestration layer is implemented as a LangGraph state machine: each node updates a shared state object until the terminal node emits a validated risk profile—coefficient A, categorical label such as Moderate or Conservative, and the underlying dimension scores for transparency.

**ON SCREEN:** When `is_terminal` is true, show **Continue to profile** enabled.

**NARRATOR:**  
This design keeps the optimization engine deterministic given A while preserving a natural conversational experience. The frontend persists the terminal state for downstream API calls.

---

## Segment 4 — Efficient Frontier Live Demo (4:00)

**[7:00–11:00]**

**ON SCREEN:** Risk profile confirmation page showing A and label; **Proceed** to optimization.

**NARRATOR:**  
With A fixed, the client calls the optimize endpoint. The backend loads the mean vector and covariance matrix, computes the global minimum variance portfolio, traces one hundred points along the efficient frontier sorted by volatility, and solves for the utility-maximizing long-only portfolio using sequential least squares programming.

**ON SCREEN:** Network tab optional: `POST /api/v1/optimize` request body with `risk_aversion_coefficient`; JSON response preview.

**NARRATOR:**  
The efficient frontier page plots annualized volatility on the horizontal axis and annualized expected return on the vertical axis. We highlight special portfolios: the global minimum variance point, the user’s optimal portfolio for the elicited A, and an equal-weight benchmark for context. Color encodes Sharpe ratio so viewers can see risk-adjusted quality along the frontier.

**ON SCREEN:** `/frontier` Plotly chart; hover one point; show tooltip fields (return, volatility, Sharpe, top weights if implemented).

**NARRATOR:**  
The capital market line may appear as a reference from the risk-free rate through the tangency portfolio, reinforcing the link between mean–variance analysis and asset pricing intuition.

**ON SCREEN:** Pan/zoom slightly; sidebar stats for GMVP vs optimal.

---

## Segment 5 — Portfolio Result & Reconciliation (3:00)

**[11:00–14:00]**

**ON SCREEN:** `/portfolio` page — Recharts pie chart, table of weights and labels.

**NARRATOR:**  
The allocation view translates optimal weights into percentages, names, and asset classes. Users can verify at a glance whether constraints bind—for example, a maximum single-name weight cap—and whether the solution respects non-negativity and full investment.

**ON SCREEN:** Open `reports/reconciliation_report.md` or summarized PASS table.

**NARRATOR:**  
Independent reconciliation scripts compare Python outputs to Excel where both are available, reporting maximum absolute deviation per metric. This project treats disagreement as a defect to be resolved before sign-off, not as noise to be ignored.

**ON SCREEN:** Highlight row: GMVP weights PASS; optimal portfolio at A equals three point five PASS.

**NARRATOR:**  
Sharpe ratios are cross-checked with an independently computed numerator and denominator from the same mean vector and covariance matrix, reducing the risk of silent inconsistencies between subsystems.

---

## Segment 6 — Conclusion (1:00)

**[14:00–15:00]**

**ON SCREEN:** Summary slide — four deliverables: Excel model, full-stack app, academic report, this video.

**NARRATOR:**  
We have shown a complete pipeline from audited data and Excel validation through conversational risk elicitation, constrained optimization, and transparent visualization—with numerical reconciliation as the quality gate. Future work could add transaction costs, tax-aware optimization, and out-of-sample stress testing; the current architecture separates data, inference, and math cleanly so those extensions can be introduced without redesigning the core contract between the chatbot and the optimizer.

**ON SCREEN:** Thank you / Q&A.

**[END 15:00]**

---

### Production notes (not read aloud)

- Rehearse transitions between browser and Excel; use two monitors or pre-record segments if window switching is clumsy.
- Keep `risk_aversion_coefficient` visible in one frame for assessors who verify API compliance.
- If reconciliation shows Excel “N/A,” narrate the *intent* of reconciliation and show PASS on Python-internal checks without claiming Excel parity that is not present in the repo.
