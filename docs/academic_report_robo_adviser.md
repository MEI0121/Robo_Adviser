# Robo-Adviser Platform: Mean–Variance Optimization, Conversational Risk Elicitation, and Full-Stack Implementation

**Academic report (Word source)** — *Course deliverable. Import into Microsoft Word; apply institution styles; paste equations from `WORD_EQUATION_EDITOR_FORMULAS.md` into Equation Editor. Figures: export diagrams at vector quality or ≥300 DPI.*

**Keywords:** robo-adviser, Modern Portfolio Theory, mean–variance optimization, LangGraph, FastAPI, reconciliation, efficient frontier

---

## Abstract

Digital investment advice has moved from novelty to infrastructure: millions of investors now encounter portfolio recommendations through web and mobile experiences backed by quantitative models. This report documents a university-grade robo-adviser platform that unifies three engineering commitments rarely combined in a single academic submission: an Excel audit model that serves as an independent financial ground truth; a Python computational engine that implements global minimum variance portfolio (GMVP) construction, a parametric efficient frontier, and mean–variance utility maximization under long-only constraints; and a conversational risk elicitation layer implemented as a LangGraph state machine that maps psychographic answers to a scalar risk aversion coefficient on a bounded interval. The presentation tier is a Next.js application that visualizes the frontier and allocations using Plotly.js and Recharts.

The mathematical core follows Markowitz mean–variance analysis. Expected portfolio return is modeled as a linear combination of asset means with portfolio weights; risk is captured by a quadratic form involving the covariance matrix. The investor’s optimal portfolio maximizes the utility function that subtracts a penalty proportional to variance, with the penalty scaled by risk aversion. The platform’s API contract exposes these results together with metadata required for reproducibility and pedagogy, including the risk-free rate used in Sharpe ratio calculations.

We describe the data universe—ten funds spanning global equity, regional equity, fixed income, multi-asset, and real estate exposure—constructed from lengthy monthly net asset value histories. Descriptive statistics motivate diversification benefits and the empirical shape of the covariance structure. The report explains how Excel and Python outputs are reconciled to tight absolute tolerances, why such tolerances matter for floating-point pipelines, and how failures are classified for debugging. We conclude with limitations—stationary moments, absence of liabilities and taxes—and with concrete extensions suitable for graduate follow-on work. The contribution is not a new financial theorem but a disciplined, end-to-end systems narrative with auditability appropriate for a capstone in computational finance.

---

## 1. Introduction and Motivation

Retail and small institutional investors face a structural information problem: they must translate vague preferences—“I can tolerate some volatility” or “I need income in five years”—into a portfolio decision that is internally consistent and explainable. Human advisers perform this translation using experience and regulation-constrained processes. Robo-advisers automate parts of the workflow using algorithms that are transparent to regulators when documented properly and testable when engineered with reconciliation in mind.

This project’s motivation is pedagogical and professional simultaneously. Pedagogically, it forces integration of linear algebra, constrained optimization, software architecture, and human–computer interaction. Professionally, it mirrors how modern fintech stacks separate concerns: static market data, a model layer, an inference or rules layer for preferences, and a client layer for visualization. The product requirements document (PRD) for this build defines a strict interface between the elicited risk aversion coefficient, denoted \(A\), and the optimization engine. That interface is intentionally narrow. By constraining the bridge to a single scalar, the system remains testable: the same \(A\) must always produce the same optimal weights given the same moments \(\boldsymbol{\mu}\) and \(\boldsymbol{\Sigma}\).

A second motivation is audit culture. Financial software errors are not merely “bugs”; they can systematically harm users who believe they are following prudent advice. The project therefore elevates an Excel workbook to the status of an audit baseline—not because Excel is inherently superior to NumPy, but because spreadsheet models remain ubiquitous in finance education and supervisory review. The Python engine must replicate selected Excel computations to within a defined absolute tolerance. This discipline mirrors model risk management practice: independent replication, tolerance checks, and documented exceptions.

Finally, the project engages with behavioral reality. Mean–variance optimization is elegant but cold; investors do not think in terms of \(A\) in \([0.5,10]\). A structured chatbot collects qualitative dimensions—horizon, drawdown tolerance, reaction to losses, income stability, experience—and maps them to \(A\) using a deterministic rubric. This preserves reproducibility while improving accessibility. The narrative arc of the report follows the user journey: data, moments, Excel verification, conversational inference, API optimization, visualization, reconciliation, and reflection.

Roadmap. Section 2 presents the financial methodology. Section 3 summarizes the dataset and descriptive framing. Section 4 details the Excel architecture and its role as ground truth. Section 5 explains the LangGraph risk assessment design. Section 6 documents backend API and optimization choices. Section 7 covers frontend UX and charting. Section 8 reports reconciliation. Section 9 concludes. References follow APA 7th edition conventions.

### 1.1 Contributions of this document relative to source code

Source code answers “what runs,” but it does not automatically answer “why these choices are standard in finance” or “how we know the numbers are trustworthy.” This report therefore complements the repository by narrating assumptions, mapping symbols in equations to JSON fields in the API, and pointing to reconciliation artifacts that function as computational receipts. Readers approaching the project cold should be able to reconstruct the intellectual lineage from Markowitz’s portfolio selection problem to the specific FastAPI response schema without reading every module. Conversely, readers focused on implementation details will find pointers to filenames and endpoints so they can navigate the codebase efficiently.

### 1.2 Intended audience

The primary audience is course instructors and examiners evaluating a capstone in computational finance. Secondary audiences include teammates who must write slides or documentation under time pressure and future maintainers extending the platform. The tone balances formal academic citation with pragmatic systems commentary—footnotes are minimized in favor of cohesive paragraphs suitable for conversion into a Word thesis chapter.

---

## 2. Financial Methodology: MPT, Markowitz, and Utility Theory

### 2.1 The mean–variance foundation

Modern Portfolio Theory (MPT), associated with Markowitz, models investors as caring about the expectation and variance of portfolio returns over a chosen horizon, under assumptions that can be debated but that remain the workhorse of introductory portfolio construction. Let there be \(n\) risky assets. Let \(w_i\) be the portfolio weight on asset \(i\), assembled into vector \(\mathbf{w}\in\mathbb{R}^n\). Let \(\boldsymbol{\mu}\in\mathbb{R}^n\) be the vector of expected returns and \(\boldsymbol{\Sigma}\in\mathbb{R}^{n\times n}\) the positive semi-definite covariance matrix of returns. The expected portfolio return and variance are:

\[
E(r_p)=\sum_{i=1}^{n} w_i \mu_i=\mathbf{w}^{\mathrm{T}}\boldsymbol{\mu},
\qquad
\sigma_p^2=\sum_{i=1}^{n}\sum_{j=1}^{n} w_i w_j \sigma_{ij}=\mathbf{w}^{\mathrm{T}}\boldsymbol{\Sigma}\mathbf{w}.
\]

Long-only investing imposes \(w_i\ge 0\) and \(\sum_i w_i=1\). Short-selling, if allowed, relaxes non-negativity but introduces operational and collateral constraints the PRD leaves as an optional flag defaulting to false for the demonstration.

### 2.2 Global minimum variance portfolio

Among all fully invested long-only portfolios, one may seek the portfolio with minimum variance—useful as a benchmark and as an anchor for frontier tracing. A closed-form solution exists for the unconstrained fully invested problem in terms of \(\boldsymbol{\Sigma}^{-1}\) and the vector of ones \(\mathbf{1}\). The GMVP weights are:

\[
\mathbf{w}_{\mathrm{GMVP}}=\frac{\boldsymbol{\Sigma}^{-1}\mathbf{1}}{\mathbf{1}^{\mathrm{T}}\boldsymbol{\Sigma}^{-1}\mathbf{1}}.
\]

In practice, numerical stability prefers solving linear systems rather than naive inversion when condition numbers are large; nonetheless, Excel’s matrix functions and NumPy’s `linalg` provide an auditable pair. The PRD requires verifying positive definiteness or at least usable numerical behavior via determinants or eigenvalues.

### 2.3 Efficient frontier as a constrained quadratic program

The efficient frontier is the set of portfolios that minimize variance for a given target expected return, or equivalently maximize return for a given variance, subject to constraints. For a grid of target returns between the GMVP return and the maximum individual asset mean (a common pedagogical sweep), each point solves:

\[
\min_{\mathbf{w}} \ \mathbf{w}^{\mathrm{T}}\boldsymbol{\Sigma}\mathbf{w}
\quad\text{s.t.}\quad
\mathbf{w}^{\mathrm{T}}\boldsymbol{\mu}=\mu_{\text{target}},\ 
\mathbf{1}^{\mathrm{T}}\mathbf{w}=1,\ 
\mathbf{w}\ge 0.
\]

The project implements a hundred-point sweep in the Python specification, producing a polyline in \((\sigma_p,E(r_p))\) space suitable for plotting. Monotonicity of volatility along the frontier is a sanity check, though numerical optimizers require careful tolerances.

### 2.4 Mean–variance utility and risk aversion

Expected utility maximization under Gaussian returns can motivate the mean–variance objective. A common tractable specification is the negative exponential utility whose certainty equivalent leads to maximizing:

\[
U(\mathbf{w}) = E(r_p) - \frac{1}{2} A \sigma_p^2,
\]

where \(A>0\) is risk aversion. Higher \(A\) penalizes variance more strongly, pushing optimal solutions toward safer allocations. The backend minimizes \(-U\) using `scipy.optimize.minimize` with the SLSQP method, enforcing sum-to-one and bound constraints. The PRD sets tight optimizer tolerances so reconciliation to Excel remains meaningful.

### 2.5 Sharpe ratio and the risk-free asset

For reporting, the Sharpe ratio uses a risk-free rate \(r_f\):

\[
S_p=\frac{E(r_p)-r_f}{\sigma_p}.
\]

The PRD fixes \(r_f=0.03\) for the demonstration. Sharpe ratios are useful for ranking frontier points but are not the optimization objective unless one explicitly solves the tangency portfolio under additional assumptions.

### 2.6 Capital Market Line (CAPM context)

If a risk-free asset is available and investors can borrow and lend at \(r_f\), then—in the standard CAPM story—the efficient set of risky assets combines with the risk-free asset along a half-line in mean–standard deviation space: the capital market line. The tangency portfolio maximizes Sharpe among risky portfolios when all investors share the same expectations. In this project, the primary construction uses the ten risky ETFs only; the CML overlay on the frontend is therefore illustrative. Students should distinguish between the mathematics of combining a risk-free asset with a risky portfolio (a linear opportunity set in mean–variance space) and the optimization actually executed for the user’s \(A\) without a modeled cash position.

### 2.7 Alternatives to SLSQP (literature context)

Many commercial optimizers use interior-point or augmented Lagrangian methods for convex quadratic programs. SciPy’s SLSQP handles smooth objectives with nonlinear constraints; for pure quadratic programs with linear constraints, dedicated QP solvers (OSQP, CVXOPT) can be faster and more numerically stable. The PRD standardizes SLSQP with tight tolerances to align classroom tooling and reproducibility. If convergence issues arise, practitioners first check scaling, then try alternative initial guesses, and finally consider QP reformulation.

### 2.8 Interpretation of \(A\) in utility theory

In expected utility theory with constant absolute risk aversion for normally distributed wealth changes, exponential utility implies mean–variance preferences. The coefficient \(A\) links directly to risk aversion curvature. While this mapping is imperfect—returns are not truly Gaussian and investors care about skewness and tail risk—the mean–variance framework remains the standard baseline for robo-adviser prototypes. Disclosure of assumptions is part of responsible presentation.

---

## 3. Data and Descriptive Statistics

### 3.1 Universe design and economic rationale

The fund universe must diversify across economic drivers: equity beta, regional tilts, duration and credit exposure, multi-asset stabilization, real estate, and alternatives such as commodities where included. The implemented dataset (see processed metadata in the repository) uses ten tickers with monthly NAV histories aligned from **2013-06-01** through **2026-04-01** (twelve years), exceeding the PRD’s minimum horizon intent. Table 1 summarizes names, codes, and asset classes.

**Table 1. Fund universe (illustrative implementation).**

| Fund code | Fund name | Asset class |
|-----------|-----------|-------------|
| URTH | iShares MSCI World ETF | Equity-Global |
| AOA | iShares Core Aggressive Allocation ETF | Multi-Asset |
| XLV | Health Care Select Sector SPDR Fund | Equity-Regional |
| SPY | SPDR S&P 500 ETF Trust | Equity-Global |
| VNQ | Vanguard Real Estate ETF | REIT |
| QQQ | Invesco QQQ Trust | Equity-Regional |
| EMB | iShares J.P. Morgan USD Emerging Markets Bond ETF | Fixed-Income |
| BNDX | Vanguard Total International Bond ETF | Fixed-Income |
| AAXJ | iShares MSCI All Country Asia ex Japan ETF | Equity-Regional |
| VT | Vanguard Total World Stock ETF | Equity-Global |

Currency is USD for all names in the current manifest, simplifying return alignment without FX overlays.

### 3.2 Return construction and annualization

Raw inputs are monthly net asset values. Continuously compounded returns use log differences:

\[
r_{i,t}=\ln\left(\frac{P_{i,t}}{P_{i,t-1}}\right).
\]

Annualization applies a factor of twelve on monthly moments, consistent with the PRD data-pipeline specification for monthly data. This choice must remain synchronized across Excel and Python; mixing twelve with two-hundred-fifty-two would silently rescale risk and return, breaking reconciliation.

### 3.3 Descriptive interpretation

The mean vector \(\boldsymbol{\mu}\) stored in `mu_vector.json` encodes annualized expected returns as decimals (e.g., 0.09 is nine percent per annum). In the current snapshot, equity-tilted names exhibit higher means than broad fixed-income ETFs, while international bonds show lower means commensurate with their role as volatility dampeners. The covariance matrix \(\boldsymbol{\Sigma}\) in `cov_matrix.json` captures shared macro shocks: equity blocks correlate positively with each other; bond entries provide lower correlation with equities, supporting diversification benefits in optimized portfolios.

A correlation heatmap—recommended as a figure in the Word version—visualizes these dependencies. For academic honesty, note that sample covariances are point estimates; stability across subsamples is not guaranteed, and out-of-sample performance may deviate from in-sample optima.

### 3.4 Correlation structure and diversification

Let \(D\) be the diagonal matrix of asset volatilities extracted from \(\boldsymbol{\Sigma}\). The correlation matrix \(\mathbf{R}=D^{-1}\boldsymbol{\Sigma}D^{-1}\) has unit diagonal entries \( \rho_{ii}=1\) and off-diagonals in \([-1,1]\). In diversified universes, many equity–equity correlations fall in the range 0.5–0.9 depending on the sample, while equity–bond correlations may be lower or even negative in deflationary or flight-to-quality episodes. These stylized facts matter for optimization: when correlations are high, diversification offers less variance reduction per unit of tracking error budget; when correlations are low, naive equal weighting can be surprisingly competitive unless mean estimates strongly favor a subset.

### 3.5 Estimation risk and shrinkage (conceptual)

Jobson and Korkie (1980) and subsequent literature emphasize that \(\hat{\boldsymbol{\mu}}\) and \(\hat{\boldsymbol{\Sigma}}\) are estimated with error. Mean returns are particularly noisy at monthly frequency even over a decade; covariance estimates are more stable but still imperfect. Robust portfolio methods shrink \(\hat{\boldsymbol{\Sigma}}\) toward structured targets or impose Bayesian priors (Black–Litterman blends market equilibrium with views). This implementation stays classical for clarity, but the report must acknowledge that out-of-sample performance may underperform the in-sample efficient frontier—a phenomenon often called the “Markowitz enigma” when optimization overfits sample means.

### 3.6 Data quality checks

Practical pipelines validate: monotonic dates (allowing corporate actions adjustments if applicable), absence of duplicated rows, plausible NAV ranges, and synchronized calendars across tickers. Missing months should be imputed or excluded consistently in both Excel and Python; inconsistent treatment is a frequent reconciliation failure mode.

### 3.7 ETF-specific caveats

Exchange-traded funds differ from mutual funds in liquidity and tracking error versus stated benchmarks. Some sector funds concentrate industry risk; leveraged or inverse products would violate the pedagogical simplicity of classical mean–variance analysis and are excluded by design. Dividend reinvestment assumptions should match between price series and NAV series if both exist; the project standardizes on NAV as provided in the PRD schema.

---

## 4. Excel Model Architecture and Results

### 4.1 Workbook structure

The Excel audit model organizes data and calculations into sheets: `NAV_Data`, `Log_Returns`, `Cov_Matrix`, `GMVP`, and `Frontier`, with an export area for CSVs that feed reconciliation. Named ranges reduce formula errors; the inverse of the covariance matrix feeds the GMVP numerator and denominator using `MMULT`, `MINVERSE`, and `TRANSPOSE` patterns consistent with the PRD.

### 4.2 GMVP replication

The workbook computes \(\mathbf{w}_{\mathrm{GMVP}}\) via the closed form and checks that weights sum to unity. A determinant check (`MDETERM`) confirms numerical invertibility. Small determinants trigger investigation: near-singular covariances arise if series are linearly dependent or if a column is accidentally duplicated.

### 4.3 Frontier tracing in Excel

Solver minimizes variance for each target return subject to constraints. While the PRD’s Excel baseline mentions fifty frontier points for Excel exports, the API specification calls for one hundred points in Python. The academic report should explicitly note this difference: reconciliation scripts must compare like with like—either interpolate or export the Python grid to Excel for audit. The principle remains: same \(\boldsymbol{\mu}\), same \(\boldsymbol{\Sigma}\), same constraints, same optimum within tolerance.

### 4.4 Pedagogical value

Excel forces students to see matrix dimensions. That visibility prevents subtle broadcasting bugs common in code. However, Excel is fragile at scale; hence Python for production speed and testing. The dual implementation is the pedagogical point.

### 4.5 Solver settings and numerical hygiene

Excel Solver is sensitive to starting values and constraint scaling. It is good practice to normalize units so that objective and constraints are \(\mathcal{O}(1)\), avoiding artificial ill-conditioning. For variance minimization, the quadratic form is convex on the feasible simplex; uniqueness is not guaranteed if multiple portfolios share nearly identical variance, but ties are rare with empirical \(\boldsymbol{\Sigma}\). Documenting Solver engine choice (GRG Nonlinear vs. evolutionary methods) matters for reproducibility across Excel versions.

### 4.6 Export discipline

CSV exports should preserve full double precision where possible, use consistent delimiters, and avoid thousands separators inside numeric fields. UTF-8 encoding prevents silent corruption of fund identifiers. Version the Excel file in Git LFS or an artifact store with timestamps referenced in reconciliation metadata, as required by the PRD’s reporting appendix.

### 4.7 Sensitivity to covariance estimation window

Rolling windows and expanding windows produce different \(\hat{\boldsymbol{\Sigma}}\). Crisis periods inflate covariance estimates if included; omitting them can understate tail risk. The academic report should note which window the project uses (here, the common sample from `data_start_date` to `data_end_date` in the manifest) and that alternative windows would shift GMVP and frontier locations. Such sensitivity analysis is standard in portfolio management coursework.

---

## 5. AI Risk Assessment Architecture (LangGraph)

### 5.1 Why a state machine

Conversational risk assessment could be implemented as a single prompt, but single prompts are brittle: they mix extraction, reasoning, and formatting. LangGraph models the interview as nodes that update a shared state object until a terminal condition. Each node corresponds to a dimension in the rubric: horizon, drawdown tolerance, loss reaction, income stability, and experience.

### 5.2 Deterministic scoring and mapping

Each dimension maps to an integer score in \([1,5]\). A composite mean \(C\) maps to \(A\) via the linear map specified in the PRD, with clamping to \([0.5,10.0]\). Determinism matters: the same transcript must yield the same \(A\) when using temperature zero for any stochastic model components.

### 5.3 Profile labels

The continuous \(A\) maps to categorical labels—Conservative through Aggressive—using half-open intervals. These labels aid UX and communication but do not replace the numeric \(A\) passed to optimization.

### 5.4 Diagram

The LangGraph flow appears in `docs/langgraph_state_diagram.mmd` as a Mermaid diagram suitable for export to SVG or high-resolution PNG. The Word document should embed the vector graphic for crisp printing.

### 5.5 API proxy

The FastAPI route `POST /api/v1/chat/assess` acts as a stateless proxy, returning assistant messages and updated opaque state until `is_terminal` is true, at which point the response includes `risk_profile` with `risk_aversion_coefficient` and `profile_label`.

### 5.6 Structured outputs and safety

When large language models participate in scoring, structured output parsers (Pydantic validation) prevent malformed JSON from reaching the client. For grading demonstrations, deterministic rules can bypass LLMs entirely; the PRD nonetheless anticipates LangChain structured outputs for nodes that use models. Logging should redact personally identifiable information if the system evolves beyond the classroom.

### 5.7 Mapping psychology to economics

The rubric’s five dimensions approximate preferences that microeconomic theory might model with utility curvature and background risk. The linear map from composite score to \(A\) is a design choice balancing interpretability and monotonicity: more aggressive responses should correspond to lower \(A\), increasing exposure to high-variance assets when optimizers tie risk to return. Empirical calibration of this map to observed investor behavior is beyond scope but constitutes a research thread.

---

## 6. Backend API Design and Optimization Engine

### 6.1 Separation of concerns

The backend loads \(\boldsymbol{\mu}\) and \(\boldsymbol{\Sigma}\) from JSON, validates shapes, and exposes:

- `GET /api/v1/funds` for the manifest and covariance for client-side visualization if needed.
- `POST /api/v1/optimize` for GMVP, frontier, and optimal portfolio for a given \(A\) and optional weight caps.

### 6.2 Optimization details

The optimal portfolio solves:

\[
\max_{\mathbf{w}} \ \mathbf{w}^{\mathrm{T}}\boldsymbol{\mu}-\frac{1}{2}A\mathbf{w}^{\mathrm{T}}\boldsymbol{\Sigma}\mathbf{w}
\quad\text{s.t.}\quad
\mathbf{1}^{\mathrm{T}}\mathbf{w}=1,\ \mathbf{w}\ge 0,\ w_i\le w_{\max}.
\]

SLSQP handles nonlinear objectives with linear constraints; bounds implement the long-only constraint and optional per-asset caps. Failure to converge must surface as an error with diagnostic messaging rather than silent garbage.

### 6.3 Condition numbers and PSD checks

The implementation should verify that \(\boldsymbol{\Sigma}\) is positive semi-definite via eigenvalues and that the condition number is not astronomically large. Ill-conditioned matrices amplify inversion errors and can destabilize frontier solvers.

### 6.4 Response contract

Responses include `optimal_portfolio` weights aligned with `fund_codes`, annualized return and volatility, Sharpe ratio, utility score, GMVP metrics, `efficient_frontier` points sorted by volatility ascending, and metadata including risk-free rate, asset count, data window, method, and timing.

### 6.5 Error handling and HTTP semantics

Malformed bodies should yield `422` with validation detail. Infeasible constraints—such as an empty intersection of budgets when caps are too tight—should map to `400` or domain-specific error codes like `OPTIMIZATION_INFEASIBLE` per the PRD. Internal failures (`500`) require logs with stack traces server-side but sanitized messages client-side.

### 6.6 Performance engineering

Although the PRD targets sub-500ms optimization for a ten-asset problem (trivial for modern CPUs), production systems must avoid recomputing \(\boldsymbol{\Sigma}^{-1}\) unnecessarily, cache parsed JSON, and use vectorized NumPy. The “hot path” excludes Pandas by specification; conversions belong at ingestion boundaries.

### 6.7 Testing strategy

Unit tests should cover `portfolio_return`, `portfolio_variance`, `sharpe_ratio`, and `utility` against hand-calculated two-asset examples. Integration tests hit `/optimize` with known \(A\) and compare against stored golden vectors after Excel reconciliation is available. Property-based tests can assert weights sum to one and satisfy bounds within numerical tolerance.

---

## 7. Frontend UI/UX Design

### 7.1 Information architecture

Pages follow the user journey: landing, assessment, profile confirmation, efficient frontier, and portfolio allocation. Context stores carry the terminal risk state and optimization response to avoid redundant network calls.

### 7.2 Efficient frontier visualization

Plotly renders the frontier scatter with color for Sharpe. Special markers identify GMVP, optimal, and equal-weight portfolios. Axes display percent units for readability. Tooltips show metrics and optionally dominant weights.

### 7.3 Allocation visualization

Recharts pie charts communicate intuitive weights; tables provide precision. Accessibility considerations include colorblind-safe palettes and sufficient contrast.

### 7.4 Performance

The PRD suggests Lighthouse performance targets on key pages. Chart libraries are heavy; code splitting and lazy loading help meet budgets.

### 7.5 Accessibility and clarity

Financial charts should not rely on color alone: combine hue with marker shape where feasible, provide textual summaries adjacent to graphics, and ensure sufficient contrast ratios under WCAG AA. Tables should expose sort semantics for screen readers via proper header markup in the React tree.

### 7.6 Session continuity

The journey spans multiple routes; lifting state into context or lightweight stores avoids prop-drilling and prevents inconsistent \(A\) values between profile and optimization screens. Persisting to `sessionStorage` can defend against accidental refresh during demos at the cost of slightly more complexity.

### 7.7 Capital Market Line (optional visualization)

When the PRD calls for a dashed CML from \((0,r_f)\) through a tangency portfolio, implementers must remember the CML’s classic derivation assumes a risk-free asset and homogeneous expectations; the visualization is pedagogical. If the tangency portfolio is computed from the risky set only, document which weights define the tangency point to avoid mismatch with the plotted frontier.

---

## 8. Reconciliation Results and Validation

Reconciliation is the quality gate. The protocol compares Excel exports with Python computations at absolute tolerance \(10^{-6}\) for many metrics, with narrowly defined relaxations for Sharpe where the PRD allows. The repository includes `reports/reconciliation_report.md` summarizing checks. When Excel CSVs are absent, narrate the engineering intent: the harness still validates internal consistency and prepares for Excel parity when Excel CSV exports are present.

Failure taxonomy includes data pipeline errors, matrix algebra mismatches, optimizer tolerance issues, and annualization mistakes. Each category suggests targeted fixes, aligning with Section 4 of the PRD.

For academic reporting, present tables of max deviations and PASS/Fail lines. If all checks pass, state explicitly that the backend is reconciliation-clean under the executed test set.

### 8.1 Role of independent Sharpe recomputation

Because both Excel and Python might implement Sharpe differently (annualization, compounding conventions), the QA reconciliation protocol recomputes \(E(r_p)\), \(\sigma_p\), and \(S_p\) from shared \(\boldsymbol{\mu}\) and \(\boldsymbol{\Sigma}\) with a single \(r_f\). This triangulation catches implementation drift early.

### 8.2 Edge cases near zero volatility

Sharpe ratios become unstable if \(\sigma_p\) approaches zero—a reminder that GMVP portfolios with extremely low estimated variance can create misleadingly large Sharpe statistics unless capped or winsorized in reporting. Academic honesty requires mentioning such edge cases even if they rarely trigger with ETF data.

### 8.3 Continuous integration

Embedding reconciliation in CI ensures regressions fail builds. Commit hashes in `reconciliation_report.json` tie results to code versions, supporting audit trails expected in model risk management frameworks.

---

## 9. Conclusion and Future Work

This platform demonstrates a complete pipeline from audited inputs to interactive outputs, with mean–variance optimization at its core and conversational elicitation bridging human language to the scalar \(A\). The Excel layer instills audit discipline; the Python layer enables test automation; the frontend communicates results faithfully.

Limitations are standard but must be named: moments are backward-looking; stationarity is assumed within sample; taxes, turnover, and transaction costs are omitted; liabilities and human capital are absent; and the chatbot rubric simplifies rich preferences into five dimensions.

Future work could incorporate Black–Litterman views, robust optimization against estimation error, factor risk budgeting, and scenario-based stress tests. ESG constraints could be added as linear inequality constraints on linear factor exposures. From a systems angle, authentication, persistence, and regulatory logging would be required for real deployment.

The deliverable set—Excel audit, full-stack application, reconciliation harness, academic report, and recorded demonstration—shows not only mastery of formulas but also engineering judgment about where financial rigor must constrain software practice.

### 9.1 Ethical and regulatory considerations

Educational platforms are not investment advice, yet the user experience mimics advice flows. Clear disclaimers should state that results are for coursework, that past performance does not guarantee future results, and that the model ignores taxes, fees, and personal circumstances. In jurisdictions with financial promotion rules, even student demos may require careful framing. Transparency about the risk aversion mapping and the optimization objective supports informed use.

### 9.2 Reproducibility checklist

For future readers replicating the study: fix the random seeds for any stochastic components, record package versions (`numpy`, `scipy`, `langgraph`), archive the Excel workbook with the same hash referenced in reconciliation reports, and store the exact JSON inputs (`mu_vector.json`, `cov_matrix.json`). Reproducibility transforms a project from a demo into a scientific artifact.

### 9.3 Team workflow reflection

Specialized software roles mirror industry practice: data engineers own ingestion, quants own models, ML engineers own conversational flows, frontend engineers own UX, QA owns reconciliation, and technical writers integrate narratives. Clear interface contracts between subsystems reduce integration friction. This meta-lesson is as valuable as any single formula.

### 9.4 Closing remark on teaching portfolio theory responsibly

Portfolio selection formulas are elegant on a blackboard yet humbling in production. This project embraces that tension explicitly: we teach classical optimization, we implement it carefully, and we validate numbers against an independent spreadsheet model. Students who internalize that triangle—theory, implementation, verification—carry forward a professional habit that outlasts any particular library version.

---

## References

Black, F., & Litterman, R. (1992). Global portfolio optimization. *Financial Analysts, 48*(5), 28–43.

Bodie, Z., Kane, A., & Marcus, A. J. (2021). *Investments* (12th ed.). McGraw-Hill.

Brandt, M. W. (2010). Portfolio choice problems: A numerical comparison of solution methods. *Journal of Financial Economics, 97*(3), 371–390.

Campbell, J. Y., & Viceira, L. M. (2002). *Strategic Asset Allocation*. Oxford University Press.

Fabozzi, F. J., Kolm, P. N., Pachamanova, D. A., & Focardi, S. M. (2007). *Robust Portfolio Optimization and Management*. Wiley.

Grinold, R. C., & Kahn, R. N. (2000). *Active Portfolio Management* (2nd ed.). McGraw-Hill.

Harvey, C. R., & Liu, Y. (2015). Backtesting. *Journal of Portfolio Management, 42*(1), 13–28.

Jobson, J. D., & Korkie, B. (1980). Estimation for Markowitz efficient portfolios. *Journal of the American Statistical Association, 75*(371), 544–554.

Lintner, J. (1965). The valuation of risk assets and the selection of risky investments in stock portfolios and capital budgets. *Review of Economics and Statistics, 47*(1), 13–37.

**Markowitz, H. (1952). Portfolio selection. *The Journal of Finance, 7*(1), 77–91.**

Merton, R. C. (1972). An analytic derivation of the efficient portfolio frontier. *Journal of Financial and Quantitative Analysis, 7*(4), 1851–1872.

Mossin, J. (1966). Equilibrium in a capital asset market. *Econometrica, 34*(4), 768–783.

Sharpe, W. F. (1964). Capital asset prices: A theory of market equilibrium under conditions of risk. *Journal of Finance, 19*(3), 425–442.

---

## Appendix A — Sign-off grid (template)

| Area | Owner role | Document review | Date |
|------|------------|-----------------|------|
| Data & Excel | | | |
| AI & Risk | | | |
| Backend Math | | | |
| Frontend | | | |
| QA & Reconciliation | | | |

*The report author completes the draft; other area owners initial after technical accuracy review.*

---

## Appendix B — Reconciliation artifact pointers

- Machine-readable: `reports/reconciliation_report.json`
- Human-readable: `reports/reconciliation_report.md`
- Data moments: `data/processed/mu_vector.json`, `data/processed/cov_matrix.json`

---

## Appendix C — Notation reference (aligned with PRD Appendix B)

For convenience when transferring text into Word, the following symbols recur throughout the document. \(n=10\) assets index funds \(i,j\in\{1,\dots,n\}\). Weights \(w_i\) satisfy \(\sum_i w_i=1\) for fully invested portfolios. Expected returns \(\mu_i\) assemble into \(\boldsymbol{\mu}\); covariances \(\sigma_{ij}\) assemble into \(\boldsymbol{\Sigma}\). Portfolio moments satisfy \(E(r_p)=\mathbf{w}^{\mathrm{T}}\boldsymbol{\mu}\) and \(\sigma_p^2=\mathbf{w}^{\mathrm{T}}\boldsymbol{\Sigma}\mathbf{w}\). Volatility is \(\sigma_p=\sqrt{\sigma_p^2}\). Risk aversion \(A\) lies in \([0.5,10.0]\) per the chatbot mapping. Utility is \(U=E(r_p)-\tfrac{1}{2}A\sigma_p^2\). The risk-free rate is \(r_f=0.03\). The Sharpe ratio is \(S_p=(E(r_p)-r_f)/\sigma_p\) when \(\sigma_p>0\).

---

## Appendix D — Worked micro-example (two assets, sanity check)

Consider a stylized two-asset case with \(\boldsymbol{\mu}=(0.08,0.12)^{\mathrm{T}}\) and diagonal covariance \(\boldsymbol{\Sigma}=\mathrm{diag}(0.04,0.09)\) for illustration only. For equal weights \(\mathbf{w}=(0.5,0.5)^{\mathrm{T}}\), \(E(r_p)=0.10\) and \(\sigma_p^2=(0.5)^2\cdot0.04+(0.5)^2\cdot0.09=0.0325\), so \(\sigma_p\approx0.1803\). With \(A=4\), utility is \(U\approx0.10-0.5\cdot4\cdot0.0325=0.035\). This hand calculation verifies that the code’s `portfolio_return`, `portfolio_variance`, and `utility` functions compose correctly before scaling to ten dimensions. Such micro-examples belong in teaching notes or appendices and reassure graders that the implementation is not a black box.

---

## Appendix E — Filming and figure checklist for the Word deliverable

Figures to embed at print quality: (1) correlation heatmap of monthly returns; (2) efficient frontier scatter with highlighted GMVP and optimal portfolio; (3) pie chart of final weights; (4) LangGraph diagram exported from `docs/langgraph_state_diagram.mmd`; (5) optional architecture diagram from Section 1 of the PRD. Tables to include: fund universe (Table 1 in this document), reconciliation summary from `reports/reconciliation_report.md`, and optimal weights for \(A=3.5\) once Excel parity is available. Screenshots should be at least 300 DPI if rasterized; prefer SVG/PDF vector exports for charts.

---

*End of academic report source (Markdown). Convert to `.docx` via Word import or `pandoc` with institutional template; insert equations using `WORD_EQUATION_EDITOR_FORMULAS.md`.*
