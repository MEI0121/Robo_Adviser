# Product Requirements Document & Task Specifications
## Robo-Adviser Platform — Financial Modeling Final Project

**Version:** 1.0.0  
**Classification:** Internal Engineering Reference  
**Authors:** Senior PM & Chief Architect  
**Date:** 2026-04-20  
**Status:** APPROVED FOR EXECUTION

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Section 1: Global Architecture & Data Flow](#section-1-global-architecture--data-flow)
3. [Section 2: Strict API Contract](#section-2-strict-api-contract)
4. [Section 3: Task Specifications — Module Assignments](#section-3-task-specifications--module-assignments)
5. [Section 4: Financial-Grade Reconciliation & QA](#section-4-financial-grade-reconciliation--qa)
6. [Appendix A: Fund Universe & Data Schema](#appendix-a-fund-universe--data-schema)
7. [Appendix B: Glossary of Mathematical Notation](#appendix-b-glossary-of-mathematical-notation)

---

## Executive Summary

This document is the single source of engineering truth for a cross-functional course team building a production-grade Robo-Adviser platform with conversational risk assessment. The system ingests 10 FSMOne funds spanning at least 10 years of NAV history, applies Modern Portfolio Theory (MPT) optimization via a Python/Scipy backend, surfaces results through a Next.js frontend with Plotly.js and Recharts visualizations, and gates the entire flow behind a LangGraph-driven psychographic risk assessment chatbot. An Excel model independently replicates every matrix calculation and serves as the financial audit ground-truth. All computed values between the Python engine and the Excel model must agree within a tolerance of `1e-6`.

The platform must clear four final deliverables: the Excel optimization model, the full-stack web application, a comprehensive academic Word report, and a 15-minute demonstration video.

---

## Section 1: Global Architecture & Data Flow

### 1.1 End-to-End User Journey

The platform executes the following deterministic state machine for every user session:

```
[Landing Page]
     │
     ▼
[Risk Assessment Chatbot]  ← LangGraph state machine (multi-turn)
     │   Emits: { risk_score: A, profile_label: str }
     ▼
[Risk Profile Confirmation Screen]
     │   User acknowledges profile; session token minted
     ▼
[POST /api/optimize]  ← Backend optimization call with A score
     │   Returns: { weights[], E_rp, sigma_p, sharpe, frontier_points[] }
     ▼
[Efficient Frontier Screen]  ← Plotly.js scatter plot
     │   Highlights: GMVP, Optimal Portfolio, Current User Portfolio
     ▼
[Portfolio Allocation Screen]  ← Recharts pie chart + data table
     │   Shows: Asset weights, Expected Return, Volatility, Sharpe Ratio
     ▼
[Download / Export]  ← PDF summary (optional stretch goal)
```

### 1.2 System Component Topology

| Layer | Technology | Responsibility |
|-------|-----------|----------------|
| Presentation | Next.js 14 (App Router) + TailwindCSS | Page routing, SSR, UI shells |
| Charting | Plotly.js (scatter) + Recharts (pie) | Financial visualization |
| AI Gateway | LangGraph + OpenAI GPT-4o (or local Ollama) | Risk chatbot state machine |
| API Layer | FastAPI (Python 3.11) | REST endpoints, input validation |
| Math Engine | NumPy + SciPy (`scipy.optimize.minimize`) | MPT calculations |
| Data Store | Static JSON / CSV seeded from FSMOne | Historical NAV, fund metadata |
| Audit Baseline | Microsoft Excel (Solver + MMULT + MINVERSE) | Independent ground-truth |
| Reconciliation | Pytest + Pandas | Tolerance-checked diff reports |

### 1.3 Risk Aversion Score ($A$) Pipeline

The $A$ score is the sole parameter bridging the AI layer and the Math Engine. Its pipeline is:

**Step 1 — LangGraph Elicitation**

The chatbot conducts a structured, multi-turn interview covering:
- Investment horizon (years)
- Maximum tolerable drawdown (%)
- Emotional response to a 20% portfolio decline
- Income stability and liquidity needs
- Prior investment experience

Each dimension is scored 1–5. A weighted composite is mapped to the continuous $A$ scale via a calibration table (see risk-assessment module spec). The LangGraph graph emits a terminal `RiskProfileState` object with a strict JSON schema.

**Step 2 — Frontend → Backend Transmission**

The frontend extracts `risk_score` from the terminal LangGraph state and injects it into the `POST /api/optimize` request body as the field `risk_aversion_coefficient` (a `float64`, range `[0.5, 10.0]`).

**Step 3 — Utility Function Optimization**

The backend Python engine uses $A$ to maximize the mean-variance utility function:

$$U(w) = E(r_p) - \frac{1}{2} \cdot A \cdot \sigma_p^2$$

where:
- $E(r_p) = w^T \mu$ is the portfolio expected return (dot product of weights vector $w$ and the mean annual returns vector $\mu$)
- $\sigma_p^2 = w^T \Sigma w$ is the portfolio variance ($\Sigma$ = annualized covariance matrix)
- $w \in \mathbb{R}^{10}$ subject to $\sum_{i=1}^{10} w_i = 1$ and $w_i \geq 0$ (long-only constraint)

**Step 4 — Optimal Portfolio Return**

`scipy.optimize.minimize` with `method='SLSQP'` minimizes the negative utility $-U(w)$. The resulting $w^*$ is the optimal portfolio for investor risk profile $A$.

### 1.4 Data Flow Diagram (Textual)

```
FSMOne NAV CSVs
      │
      ▼
[Data & Excel baseline]
  - Compute log returns: r_t = ln(NAV_t / NAV_{t-1})
  - Annualize: μ_i = mean(r_t) × 252
  - Covariance: Σ = Cov(R) × 252
  - Output: mu_vector.json, cov_matrix.json, raw_nav.csv
      │
      ├──────────────────────────────────────────┐
      ▼                                          ▼
[Excel Audit Model]                    [FastAPI Backend]
  MMULT / MINVERSE / Solver              numpy / scipy
  GMVP, Efficient Frontier              GMVP, Frontier, Optimal W
      │                                          │
      └───────── [QA & reconciliation] ──────┘
                   Tolerance: 1e-6
                          │
                          ▼
                   [Next.js Frontend]
                  Chatbot → Frontier → Pie Chart
```

---

## Section 2: Strict API Contract

### 2.1 Base URL & Versioning

```
Development:  http://localhost:8000/api/v1
Production:   https://api.robo-adviser.internal/api/v1
```

All endpoints consume and produce `application/json`. Authentication is deferred (out of scope for final project demo); all routes are open.

---

### 2.2 `POST /api/v1/optimize` — Core Optimization Endpoint

**Purpose:** Given investor risk aversion coefficient $A$, compute the optimal portfolio weights and return the full efficient frontier locus.

#### Request Body Schema

```json
{
  "risk_aversion_coefficient": {
    "type": "float",
    "minimum": 0.5,
    "maximum": 10.0,
    "description": "Investor risk aversion parameter A from LangGraph chatbot. Higher = more risk-averse.",
    "example": 3.5
  },
  "constraints": {
    "type": "object",
    "properties": {
      "allow_short_selling": {
        "type": "boolean",
        "default": false,
        "description": "If false, enforces w_i >= 0 for all assets."
      },
      "max_single_weight": {
        "type": "float",
        "minimum": 0.1,
        "maximum": 1.0,
        "default": 1.0,
        "description": "Upper bound on any single asset weight. Set 0.4 to cap at 40%."
      }
    },
    "required": []
  }
}
```

**Example Request:**
```json
{
  "risk_aversion_coefficient": 3.5,
  "constraints": {
    "allow_short_selling": false,
    "max_single_weight": 1.0
  }
}
```

#### Response Body Schema

```json
{
  "status": {
    "type": "string",
    "enum": ["success", "error"],
    "example": "success"
  },
  "optimal_portfolio": {
    "type": "object",
    "properties": {
      "weights": {
        "type": "array",
        "items": { "type": "float" },
        "length": 10,
        "description": "Optimal asset allocation weights w*. Sum = 1.0.",
        "example": [0.12, 0.08, 0.22, 0.05, 0.18, 0.10, 0.07, 0.09, 0.06, 0.03]
      },
      "fund_codes": {
        "type": "array",
        "items": { "type": "string" },
        "length": 10,
        "description": "FSMOne fund codes in the same order as weights.",
        "example": ["LU0321462953", "SG9999009836", "..."]
      },
      "expected_annual_return": {
        "type": "float",
        "description": "E(r_p) = w^T * mu. Annualized. Decimal form.",
        "example": 0.0923
      },
      "annual_volatility": {
        "type": "float",
        "description": "sigma_p = sqrt(w^T * Sigma * w). Annualized. Decimal form.",
        "example": 0.1145
      },
      "sharpe_ratio": {
        "type": "float",
        "description": "(E(r_p) - r_f) / sigma_p. Risk-free rate = 0.03 (configurable).",
        "example": 0.5424
      },
      "utility_score": {
        "type": "float",
        "description": "U = E(r_p) - 0.5 * A * sigma_p^2. Maximized value.",
        "example": 0.0690
      }
    }
  },
  "gmvp": {
    "type": "object",
    "description": "Global Minimum Variance Portfolio.",
    "properties": {
      "weights": {
        "type": "array",
        "items": { "type": "float" },
        "length": 10
      },
      "expected_annual_return": { "type": "float" },
      "annual_volatility": { "type": "float" },
      "sharpe_ratio": { "type": "float" }
    }
  },
  "efficient_frontier": {
    "type": "array",
    "description": "N=100 portfolio points along the efficient frontier, sorted by volatility ascending.",
    "items": {
      "type": "object",
      "properties": {
        "expected_return": { "type": "float" },
        "volatility": { "type": "float" },
        "sharpe_ratio": { "type": "float" },
        "weights": {
          "type": "array",
          "items": { "type": "float" }
        }
      }
    }
  },
  "metadata": {
    "type": "object",
    "properties": {
      "risk_aversion_coefficient": { "type": "float" },
      "risk_free_rate": { "type": "float", "example": 0.03 },
      "num_assets": { "type": "integer", "example": 10 },
      "data_start_date": { "type": "string", "format": "date", "example": "2015-01-02" },
      "data_end_date": { "type": "string", "format": "date", "example": "2025-12-31" },
      "optimization_method": { "type": "string", "example": "SLSQP" },
      "computation_time_ms": { "type": "integer" }
    }
  }
}
```

---

### 2.3 `GET /api/v1/funds` — Fund Universe Manifest

**Purpose:** Returns the static list of 10 funds, their metadata, and pre-computed statistics.

**Response Body Schema:**
```json
{
  "funds": [
    {
      "fund_code": { "type": "string" },
      "fund_name": { "type": "string" },
      "asset_class": {
        "type": "string",
        "enum": ["Equity-Global", "Equity-Regional", "Fixed-Income", "Multi-Asset", "Commodity", "REIT"]
      },
      "currency": { "type": "string" },
      "annualized_return": { "type": "float" },
      "annualized_volatility": { "type": "float" },
      "sharpe_ratio": { "type": "float" },
      "nav_history_years": { "type": "integer", "minimum": 10 }
    }
  ],
  "covariance_matrix": {
    "type": "array",
    "description": "10x10 annualized covariance matrix Sigma. Row-major order.",
    "items": {
      "type": "array",
      "items": { "type": "float" }
    }
  }
}
```

---

### 2.4 `POST /api/v1/chat/assess` — LangGraph Risk Chatbot Proxy

**Purpose:** Stateless proxy that forwards a user message and session state to the LangGraph graph runner and returns the updated state.

**Request Body:**
```json
{
  "session_id": { "type": "string", "format": "uuid" },
  "user_message": { "type": "string" },
  "current_state": { "type": "object", "description": "Opaque LangGraph state snapshot." }
}
```

**Response Body:**
```json
{
  "session_id": { "type": "string" },
  "assistant_message": { "type": "string" },
  "updated_state": { "type": "object" },
  "is_terminal": {
    "type": "boolean",
    "description": "True when the graph has reached the terminal RiskProfileState node."
  },
  "risk_profile": {
    "type": "object",
    "description": "Only present when is_terminal = true.",
    "properties": {
      "risk_aversion_coefficient": { "type": "float" },
      "profile_label": {
        "type": "string",
        "enum": ["Conservative", "Moderately Conservative", "Moderate", "Moderately Aggressive", "Aggressive"]
      },
      "dimension_scores": { "type": "object" }
    }
  }
}
```

---

### 2.5 Error Schema (All Endpoints)

```json
{
  "status": "error",
  "error_code": { "type": "string", "example": "OPTIMIZATION_INFEASIBLE" },
  "message": { "type": "string" },
  "details": { "type": "object" }
}
```

Standard HTTP status codes: `400` (bad input), `422` (validation error), `500` (internal math failure).

---

## Section 3: Task Specifications — Module Assignments

### Module 1 — The Quant: Excel & Data Architect

#### Role & Mission

This module is the data foundation of the entire system. It owns the raw NAV pipeline (FSMOne ingestion → return computation → statistical summary) and the Excel audit model. Every number produced here is the financial ground truth against which all Python outputs are validated—the last line of defense against computational errors.

#### Core Engineering Tasks

1. **Fund Selection:** Select exactly 10 funds from FSMOne Fund Selector spanning at least 6 distinct asset classes. Each fund must have a minimum of 10 years (≥2,520 trading days) of continuous NAV history. Acceptable classes: Global Equity, Regional Equity, Fixed Income (IG and HY), Multi-Asset Balanced, Commodities (Gold/Energy), REITs.

2. **NAV Data Download:** Download monthly NAV data (minimum 10 years, recommend 15 years) per fund as CSV. Store raw CSVs in `/data/raw/`. Standardize date index to first business day of each month.

3. **Log Return Computation (Excel):** In Excel, compute:
   - Monthly log returns: `=LN(NAV_t / NAV_{t-1})` for each cell
   - Annualized mean return vector $\mu$: `=AVERAGE(log_returns_column) * 12`
   - Annualized covariance matrix $\Sigma$: `=MMULT(TRANSPOSE(excess_returns_matrix), excess_returns_matrix) / (T-1) * 12` where $T$ = number of monthly observations

4. **GMVP via Matrix Algebra (Excel):** Implement the closed-form GMVP:
   $$W_{GMVP} = \frac{\Sigma^{-1} \mathbf{1}}{\mathbf{1}^T \Sigma^{-1} \mathbf{1}}$$
   Using: `=MMULT(MINVERSE(cov_range), ones_vector)` for the numerator, and `=MMULT(TRANSPOSE(ones_vector), MMULT(MINVERSE(cov_range), ones_vector))` for the denominator.

5. **Efficient Frontier (Excel Solver):** Use Excel Solver to trace the efficient frontier:
   - Minimize portfolio variance $\sigma_p^2 = w^T \Sigma w$ (`=MMULT(TRANSPOSE(w), MMULT(cov_range, w))`)
   - Subject to: $\sum w_i = 1$ (equality), $w_i \geq 0$ (non-negativity), $E(r_p) = \mu_{target}$ (parameterized return target)
   - Generate 50 frontier points by iterating $\mu_{target}$ from $\mu_{GMVP}$ to $\max(\mu)$ in equal steps
   - Use Excel Data Table (two-variable sensitivity) to automate the sweep

6. **Data Export:** Export `mu_vector.json`, `cov_matrix.json`, `gmvp_weights.json`, and `frontier_points.json` from Excel via Power Query or manual JSON formatting. These feed directly into the FastAPI backend's data layer.

#### Mathematical / Technical Directives

- Log return formula: $r_{i,t} = \ln\left(\frac{P_{i,t}}{P_{i,t-1}}\right)$
- Annualization factor: 12 for monthly data (not 252; NAV is monthly)
- Sharpe Ratio: $S = \frac{E(r_p) - r_f}{\sigma_p}$ where $r_f = 0.03$ (annualized)
- MMULT for $w^T \Sigma w$: `=MMULT(TRANSPOSE(w_range), MMULT(cov_range, w_range))`
- MINVERSE requires the covariance matrix to be invertible — verify `=MDETERM(cov_range) > 1e-10`

#### Definition of Done (DoD) / Acceptance Criteria

- [ ] All 10 fund NAV CSVs present in `/data/raw/`, minimum 120 monthly rows each
- [ ] Excel model computes $\mu$ vector and $\Sigma$ matrix with no circular references
- [ ] `=MDETERM(cov_range)` is strictly positive (positive definite matrix confirmed)
- [ ] GMVP weights sum to 1.0 (verify: `=SUM(gmvp_weights_range) = 1`)
- [ ] Efficient Frontier has exactly 50 parameterized points exported
- [ ] All four JSON files (`mu_vector.json`, `cov_matrix.json`, `gmvp_weights.json`, `frontier_points.json`) present in `/data/processed/`
- [ ] QA sign-off: Python vs Excel tolerance ≤ `1e-6` on GMVP weights

---

### Module 2 — AI & Risk: State-Machine Engineer

#### Role & Mission

This module owns the intelligence layer: a LangGraph-based multi-turn chatbot that psychographically profiles the investor, computes a numerical Risk Aversion Score ($A \in [0.5, 10.0]$), and emits a strictly typed `RiskProfileState` JSON object that the frontend passes to the optimization engine. Outputs must be deterministic and reproducible — the same conversation must always produce the same $A$ score.

#### Core Engineering Tasks

1. **Graph Design:** Design the LangGraph `StateGraph` with the following nodes:
   - `collect_horizon` → collects investment horizon (years)
   - `collect_drawdown_tolerance` → collects max acceptable drawdown
   - `collect_loss_reaction` → collects emotional/behavioral response to loss
   - `collect_income_stability` → collects income reliability and liquidity
   - `collect_experience` → collects investment experience level
   - `score_and_classify` → aggregates scores, maps to $A$, emits terminal state
   
   Each node is a Python function receiving the current `RiskProfileState` TypedDict and returning an updated state.

2. **Scoring Rubric:** Define a deterministic scoring matrix. Each dimension is scored 1–5:

   | Score | Horizon | Drawdown Tolerance | Loss Reaction | Income Stability | Experience |
   |-------|---------|-------------------|---------------|-----------------|------------|
   | 1 | < 2 yrs | < 5% | Panic sell | Very low | None |
   | 3 | 5–10 yrs | 10–20% | Hold | Moderate | Intermediate |
   | 5 | > 20 yrs | > 30% | Buy more | Very high | Expert |

3. **$A$ Score Mapping:** Compute composite score $C = \frac{1}{5}\sum_{k=1}^{5} s_k$ (mean of 5 dimension scores, each 1–5). Map to $A$:
   $$A = 10.5 - C \times \frac{(10.0 - 0.5)}{5 - 1} = 10.5 - C \times 2.375$$
   This gives $A = 10.0$ when $C = 0.5$ (most conservative) and $A = 0.5$ when $C = 4.6$ (most aggressive). Clamp to $[0.5, 10.0]$.

4. **Profile Label Assignment:**

   | $A$ Range | Profile Label |
   |-----------|--------------|
   | $[8.0, 10.0]$ | Conservative |
   | $[5.5, 8.0)$ | Moderately Conservative |
   | $[3.5, 5.5)$ | Moderate |
   | $[1.5, 3.5)$ | Moderately Aggressive |
   | $[0.5, 1.5)$ | Aggressive |

5. **Structured Output Enforcement:** Use LangChain's `with_structured_output()` with a Pydantic model for each node's LLM call to guarantee JSON compliance. The terminal `RiskProfileState` must validate against the Pydantic schema before the graph exits.

6. **Pydantic Schema (Terminal State):**
   ```python
   class RiskProfileState(BaseModel):
       session_id: str
       risk_aversion_coefficient: float  # A score
       profile_label: Literal["Conservative", "Moderately Conservative",
                               "Moderate", "Moderately Aggressive", "Aggressive"]
       dimension_scores: dict[str, int]  # {"horizon": 3, "drawdown": 4, ...}
       composite_score: float
       conversation_turns: int
       is_terminal: bool = True
   ```

#### Mathematical / Technical Directives

- LangGraph version: `langgraph>=0.2.0`
- Use `StateGraph(RiskProfileState)` with `TypedDict` for intermediate states
- All LLM calls: `model.with_structured_output(DimensionScore)` — never parse raw text
- $A$ mapping must be implemented as a pure function with 100% unit test coverage
- Conditional edges: graph exits only when all 5 dimensions have `score > 0`

#### Definition of Done (DoD) / Acceptance Criteria

- [ ] LangGraph graph compiles without errors: `graph.compile()` succeeds
- [ ] 10-turn conversation produces a valid `RiskProfileState` JSON
- [ ] $A$ score always in $[0.5, 10.0]$; raises `ValueError` outside range
- [ ] Same conversation transcript always yields the same $A$ (determinism test with `temperature=0`)
- [ ] Unit tests cover all 5 scoring rubric boundary conditions (score = 1, 3, 5 per dimension)
- [ ] `POST /api/v1/chat/assess` returns `is_terminal: true` with `risk_profile` populated after all dimensions collected
- [ ] Frontend successfully reads `risk_aversion_coefficient` from terminal state and passes to optimize endpoint

---

### Module 3 — Backend Math Engineer: Optimization Engine

#### Role & Mission

This module implements the Python mathematical core: matrix operations via NumPy, constrained portfolio optimization via SciPy, and all FastAPI endpoint logic. Its outputs are the authoritative computational results for the web platform, and they must reconcile with the Excel baseline (Module 1) to within `1e-6`.

#### Core Engineering Tasks

1. **Data Loading Module:** Implement `data_loader.py`:
   ```python
   def load_market_data() -> tuple[np.ndarray, np.ndarray]:
       """Returns (mu_vector, cov_matrix) as float64 NumPy arrays."""
   ```
   Load from `/data/processed/mu_vector.json` and `/data/processed/cov_matrix.json`. Validate shapes: `mu.shape == (10,)` and `cov.shape == (10, 10)`.

2. **Portfolio Math Module:** Implement `portfolio_math.py`:
   - `portfolio_return(w, mu)`: $E(r_p) = w^T \mu$
   - `portfolio_variance(w, cov)`: $\sigma_p^2 = w^T \Sigma w$
   - `portfolio_volatility(w, cov)`: $\sigma_p = \sqrt{w^T \Sigma w}$
   - `sharpe_ratio(w, mu, cov, rf=0.03)`: $(E(r_p) - r_f) / \sigma_p$
   - `utility(w, mu, cov, A)`: $E(r_p) - 0.5 \cdot A \cdot \sigma_p^2$

3. **GMVP Computation:** Implement using closed-form matrix algebra (mirrors the Excel baseline):
   ```python
   def compute_gmvp(cov: np.ndarray) -> np.ndarray:
       ones = np.ones(cov.shape[0])
       cov_inv = np.linalg.inv(cov)
       numerator = cov_inv @ ones
       denominator = ones.T @ cov_inv @ ones
       w_gmvp = numerator / denominator
       return w_gmvp  # shape: (10,)
   ```

4. **Efficient Frontier Computation:** Parametric sweep over 100 target return levels:
   ```python
   def compute_efficient_frontier(mu, cov, n_points=100) -> list[dict]:
       mu_min = portfolio_return(compute_gmvp(cov), mu)
       mu_max = mu.max()
       targets = np.linspace(mu_min, mu_max, n_points)
       frontier = []
       for target in targets:
           w = minimize_variance_for_target(mu, cov, target)
           frontier.append({...})
       return frontier
   ```

5. **Optimal Portfolio (Utility Maximization):**
   ```python
   from scipy.optimize import minimize

   def compute_optimal_portfolio(mu, cov, A, max_weight=1.0) -> np.ndarray:
       n = len(mu)
       constraints = [
           {"type": "eq", "fun": lambda w: np.sum(w) - 1}  # weights sum to 1
       ]
       bounds = [(0, max_weight)] * n  # long-only
       x0 = np.ones(n) / n  # equal-weight initialization
       result = minimize(
           fun=lambda w: -(portfolio_return(w, mu) - 0.5 * A * portfolio_variance(w, cov)),
           x0=x0,
           method="SLSQP",
           bounds=bounds,
           constraints=constraints,
           options={"ftol": 1e-9, "maxiter": 1000}
       )
       if not result.success:
           raise OptimizationError(result.message)
       return result.x
   ```

6. **FastAPI Application:** Implement `main.py` with CORS enabled for `http://localhost:3000`. Mount all routers. Include Pydantic request/response models matching Section 2 schemas exactly.

#### Mathematical / Technical Directives

- All NumPy arrays: `dtype=np.float64`
- Matrix inversion: use `np.linalg.inv()`, verify with `np.linalg.cond(cov) < 1e10` (condition number check)
- SLSQP tolerance: `ftol=1e-9` to exceed the `1e-6` reconciliation requirement
- Positive semi-definiteness check: `np.all(np.linalg.eigvals(cov) >= 0)`
- No Pandas in the hot path — NumPy only for performance

#### Definition of Done (DoD) / Acceptance Criteria

- [ ] `uvicorn main:app --reload` starts without errors
- [ ] `GET /api/v1/funds` returns all 10 funds with valid metadata
- [ ] `POST /api/v1/optimize` with $A=3.5$ returns in < 500ms
- [ ] GMVP weights from Python agree with Excel GMVP to within `1e-6` (QA sign-off)
- [ ] Efficient frontier has exactly 100 points; volatilities are monotonically increasing
- [ ] All optimal portfolio weights satisfy $w_i \geq 0$ and $\sum w_i = 1.0$ to within `1e-8`
- [ ] Pytest coverage ≥ 90% on `portfolio_math.py` and `optimizer.py`

---

### Module 4 — Frontend: Visualization & UI/UX

#### Role & Mission

This module owns the complete Next.js application: the landing page, the chatbot UI, the risk profile confirmation screen, the Efficient Frontier scatter plot, and the portfolio allocation dashboard. The UI must be production-quality, fully responsive, and capable of rendering financial data with precision and clarity.

#### Core Engineering Tasks

1. **Project Setup:** Initialize with `create-next-app@14` using App Router, TypeScript, and TailwindCSS. Install `plotly.js`, `react-plotly.js`, `recharts`, and `axios`.

2. **Page Structure:**
   - `/` — Landing page with hero section, platform overview, CTA to start chatbot
   - `/assess` — Multi-turn chatbot UI (conversation thread + progress indicator)
   - `/profile` — Risk profile confirmation (displays $A$ score, label, dimension breakdown)
   - `/frontier` — Efficient Frontier page (Plotly.js scatter + sidebar with GMVP/Optimal stats)
   - `/portfolio` — Final allocation page (Recharts pie chart + data table + export button)

3. **Chatbot UI (`/assess`):** Implement a scrollable conversation thread. Each assistant message streams in (if streaming is enabled). A progress bar shows completion across 5 dimensions. The "Get My Profile" CTA is enabled only when `is_terminal === true`.

4. **Efficient Frontier Chart (Plotly.js):** Render two traces:
   - `Frontier` trace: scatter plot of 100 $(\sigma_p, E(r_p))$ points, color-coded by Sharpe ratio
   - `Special Points` trace: three annotated markers — GMVP (blue), Optimal Portfolio (gold star), Equal-Weight Portfolio (grey)
   - X-axis: Annual Volatility (%), Y-axis: Annual Expected Return (%)
   - Hover tooltip: show `E(r_p)`, `σ_p`, `Sharpe`, and top 3 weights

5. **Portfolio Allocation (Recharts):** `PieChart` with `Cell` components per fund. Color palette: 10 distinct, accessible colors (WCAG AA compliant). Below the chart, render a sortable `<Table>` with columns: Fund Name, Asset Class, Weight (%), Expected Contribution.

6. **State Management:** Use React Context or Zustand to persist the `RiskProfileState` and `OptimizationResponse` across pages. Never re-fetch unless the session changes.

#### Mathematical / Technical Directives

- Efficient Frontier: x-axis values are `volatility * 100` (convert decimal to percentage)
- Plotly colorscale for Sharpe: `"RdYlGn"` (red = low Sharpe, green = high)
- Pie chart: weights already in decimal; multiply by 100 for label display
- CML (Capital Market Line): render as a dashed line from $(0, r_f)$ through the tangency portfolio point

#### Definition of Done (DoD) / Acceptance Criteria

- [ ] `npm run dev` starts without errors; all 5 pages accessible
- [ ] Chatbot completes a full session and transitions to `/profile` with correct $A$ score displayed
- [ ] Efficient Frontier renders all 100 points; GMVP and Optimal Portfolio markers visible
- [ ] Pie chart weights sum to 100% (display) with no rounding gaps
- [ ] Responsive layout: no horizontal overflow on 375px viewport (iPhone SE)
- [ ] Lighthouse Performance score ≥ 85 on `/frontier` and `/portfolio`
- [ ] No TypeScript `any` types in component props

---

### Module 5 — Integrator & QA: System & Data Reconciliation

#### Role & Mission

This workstream is the guardian of system integrity. It owns integration testing, end-to-end test suites, and — most critically — the financial data reconciliation protocol comparing the Python backend against the Excel ground truth. Failed checks block release until resolved.

#### Core Engineering Tasks

1. **API Integration Tests:** Use `pytest` + `httpx.AsyncClient` to test all FastAPI endpoints against expected response schemas.

2. **Reconciliation Pipeline:** Implement `reconcile.py` that:
   - Reads Excel outputs (exported CSVs from the data/Excel workstream)
   - Reads Python API responses
   - Performs element-wise comparison
   - Reports pass/fail with maximum observed deviation

3. **E2E Test Suite:** Use Playwright to automate the full user journey: land → chat → profile → frontier → portfolio.

4. **Data Integrity Checks:** Validate that `mu_vector.json` and `cov_matrix.json` in `/data/processed/` are identical to the values in the Excel model (manual cross-check + automated CSV diff).

#### Mathematical / Technical Directives

- Tolerance for all floating-point comparisons: `atol=1e-6`, `rtol=0` (absolute tolerance only — no relative tolerance, as near-zero weights would create false positives with rtol)
- Use `np.testing.assert_allclose(actual, desired, atol=1e-6, rtol=0)`
- GMVP check: compare all 10 weights individually, not just the sum
- Sharpe ratio check: compute independently in the reconciliation script rather than trusting either system's reported value

#### Definition of Done (DoD) / Acceptance Criteria

- [ ] `pytest tests/` passes with 0 failures
- [ ] Reconciliation script outputs `PASS` for GMVP weights, $\mu$ vector, $\Sigma$ matrix, and all 100 frontier points
- [ ] Maximum observed deviation across all reconciled values ≤ `1e-6`
- [ ] Playwright E2E test completes full user journey in < 120 seconds
- [ ] All API endpoints return correct HTTP status codes for invalid inputs (400/422)
- [ ] Reconciliation report PDF generated and committed to `/reports/reconciliation_report.pdf`

---

### Module 6 — Technical Writing & Delivery Lead

#### Role & Mission

This module produces the academic Word document and the demonstration video script. It translates engineering work into a coherent academic narrative, ensuring financial mathematics are precisely cited, architectural decisions are justified, and the video showcases the platform within the 15-minute constraint.

#### Core Engineering Tasks

1. **Word Document Structure:**
   - Abstract (250 words)
   - Section 1: Introduction & Motivation
   - Section 2: Financial Methodology (MPT, Markowitz, Utility Theory)
   - Section 3: Data & Descriptive Statistics (fund table, correlation heatmap)
   - Section 4: Excel Model Architecture & Results
   - Section 5: AI Risk Assessment Architecture (LangGraph state diagram)
   - Section 6: Backend API Design & Optimization Engine
   - Section 7: Frontend UI/UX Design
   - Section 8: Reconciliation Results & Validation
   - Section 9: Conclusion & Future Work
   - References (APA 7th edition)

2. **Mathematical Typesetting:** All formulas in Microsoft Word Equation Editor. Mandatory formulas to include:
   - Portfolio return: $E(r_p) = \sum_{i=1}^{n} w_i \mu_i = w^T \mu$
   - Portfolio variance: $\sigma_p^2 = \sum_i \sum_j w_i w_j \sigma_{ij} = w^T \Sigma w$
   - GMVP: $W = \frac{\Sigma^{-1} \mathbf{1}}{\mathbf{1}^T \Sigma^{-1} \mathbf{1}}$
   - Utility function: $U = E(r_p) - \frac{1}{2} A \sigma_p^2$
   - Sharpe ratio: $S_p = \frac{E(r_p) - r_f}{\sigma_p}$

3. **Video Script:** 15-minute script structured as: Intro (1 min) → Data & Excel (3 min) → AI Chatbot Demo (3 min) → Efficient Frontier Live Demo (4 min) → Portfolio Result & Reconciliation (3 min) → Conclusion (1 min).

#### Definition of Done (DoD) / Acceptance Criteria

- [ ] Word document ≥ 5,000 words, all sections complete
- [ ] Every formula rendered in Word Equation Editor (no screenshots of math)
- [ ] All figures (charts, diagrams) are vector-quality or ≥ 300 DPI
- [ ] LangGraph state diagram included as a flow diagram
- [ ] Video script complete with on-screen action cues and timing markers
- [ ] References section contains ≥ 10 peer-reviewed sources (Markowitz 1952 mandatory)
- [ ] Document reviewed and signed off by the rest of the project team

---

## Section 4: Financial-Grade Reconciliation & QA

### 4.1 Reconciliation Philosophy

The Excel model is the immutable financial Source of Truth. The Python backend is a computational replica. Any discrepancy between them is a defect — regardless of which system produced it. The reconciliation protocol is non-negotiable and must be executed before any deliverable is declared complete.

### 4.2 Reconciliation Protocol — Step by Step

**Phase 1: Static Data Reconciliation**

1. The data/Excel owner exports the following from Excel as UTF-8 CSVs:
   - `excel_mu_vector.csv` — 10 rows, 1 column (annualized mean returns)
   - `excel_cov_matrix.csv` — 10 rows, 10 columns (annualized covariance matrix)
   - `excel_gmvp_weights.csv` — 10 rows, 1 column
   - `excel_frontier.csv` — 50 rows × {target_return, min_variance, weights[10]} columns

2. The backend owner runs the FastAPI server and hits `GET /api/v1/funds` to extract the equivalent Python-computed values.

3. QA runs `reconcile.py` to perform element-wise comparison:

```python
import numpy as np
import pandas as pd

def reconcile_vectors(excel_path: str, python_array: np.ndarray, label: str):
    excel = pd.read_csv(excel_path, header=None).values.flatten()
    python = python_array.flatten()
    max_deviation = np.max(np.abs(excel - python))
    passed = max_deviation <= 1e-6
    print(f"[{'PASS' if passed else 'FAIL'}] {label}: max deviation = {max_deviation:.2e}")
    np.testing.assert_allclose(python, excel, atol=1e-6, rtol=0)
```

**Phase 2: Optimization Output Reconciliation**

For each of 5 test $A$ values ($A \in \{0.5, 2.0, 3.5, 6.0, 10.0\}$):

1. Excel Solver runs with the corresponding utility-maximization objective for each $A$ value and exports the optimal weights.
2. Python `POST /api/v1/optimize` called with the same $A$ value.
3. QA compares the 10 optimal weights element-wise.

**Phase 3: Sharpe Ratio & Statistics Reconciliation**

Independently compute in the reconciliation script:
- $E(r_p) = w^T \mu$ using NumPy
- $\sigma_p = \sqrt{w^T \Sigma w}$ using NumPy
- $S = (E(r_p) - 0.03) / \sigma_p$

Compare these against both the Excel-reported and Python-reported values. All three must agree within `1e-6`.

### 4.3 Tolerance Specifications

| Metric | Absolute Tolerance | Notes |
|--------|-------------------|-------|
| $\mu$ vector (all 10 elements) | `1e-6` | Annualized mean returns |
| $\Sigma$ matrix (all 100 elements) | `1e-6` | Annualized covariance matrix |
| GMVP weights (all 10) | `1e-6` | Closed-form vs. MMULT/MINVERSE |
| Optimal weights (all 10, per $A$) | `1e-6` | SLSQP vs. Excel Solver |
| $E(r_p)$ | `1e-6` | Portfolio expected return |
| $\sigma_p$ | `1e-6` | Portfolio volatility |
| Sharpe Ratio | `1e-4` | Relaxed due to $r_f$ rounding |
| Frontier points (all 100×10 weights) | `1e-5` | Parametric sweep; slightly relaxed |

### 4.4 Failure Protocol

If any reconciliation check fails:

1. **Identify the divergent component:** Check if $\mu$ matches (if not, data pipeline error). If $\mu$ matches but GMVP doesn't, it's a matrix algebra bug. If GMVP matches but optimal portfolio doesn't, it's an optimizer convergence issue.

2. **Root cause categories:**
   - `DATA_PIPELINE_ERROR`: Raw NAV CSVs differ between Excel and JSON (check decimal precision, date alignment)
   - `MATRIX_ALGEBRA_BUG`: NumPy `inv()` vs. Excel `MINVERSE()` precision mismatch (try `np.linalg.solve()` instead)
   - `OPTIMIZER_CONVERGENCE`: SLSQP tolerance too loose — tighten `ftol` to `1e-12`
   - `ANNUALIZATION_ERROR`: Monthly vs. annual factor mismatch (12 vs. 252)

3. **Escalation:** QA files a defect ticket with the reconciliation diff table. Data and backend owners have 24 hours to resolve. No deliverable ships until all checks pass.

### 4.5 Automated Reconciliation Report

`reconcile.py` must generate a machine-readable `reconciliation_report.json` and a human-readable `reconciliation_report.md` containing:

- Timestamp of the reconciliation run
- Git commit SHA of the Python backend
- Excel file version (date modified)
- Pass/Fail status per metric
- Maximum observed deviation per metric
- Side-by-side table of Python vs. Excel values for GMVP and optimal portfolios ($A = 3.5$)

This report is committed to `/reports/` and referenced in the academic Word document as Appendix material.

---

## Appendix A: Fund Universe & Data Schema

### A.1 Required Fund Diversity

| Slot | Asset Class | Rationale |
|------|-------------|-----------|
| 1–2 | Global Equity (Developed) | Core equity beta |
| 3 | Asia-Pacific / Regional Equity | Geographic diversification |
| 4 | Emerging Market Equity | Return enhancement |
| 5–6 | Investment Grade Fixed Income | Volatility dampener |
| 7 | High Yield / Corporate Bonds | Credit premium |
| 8 | Multi-Asset / Balanced | Diversification anchor |
| 9 | REIT / Real Estate | Inflation hedge |
| 10 | Commodity / Gold | Crisis hedge, low correlation |

### A.2 NAV Data Schema (CSV Standard)

```
date,nav,fund_code
2015-01-02,10.5230,LU0321462953
2015-02-02,10.6110,LU0321462953
...
```

Columns: `date` (ISO 8601), `nav` (float, 4 decimal places), `fund_code` (FSMOne string identifier).

---

## Appendix B: Glossary of Mathematical Notation

| Symbol | Definition |
|--------|-----------|
| $n$ | Number of assets (= 10) |
| $w \in \mathbb{R}^n$ | Portfolio weights vector |
| $\mu \in \mathbb{R}^n$ | Annualized mean return vector |
| $\Sigma \in \mathbb{R}^{n \times n}$ | Annualized covariance matrix (positive semi-definite) |
| $\mathbf{1} \in \mathbb{R}^n$ | Vector of ones |
| $E(r_p)$ | Portfolio expected return: $w^T \mu$ |
| $\sigma_p^2$ | Portfolio variance: $w^T \Sigma w$ |
| $\sigma_p$ | Portfolio volatility: $\sqrt{w^T \Sigma w}$ |
| $A$ | Investor risk aversion coefficient $\in [0.5, 10.0]$ |
| $U$ | Investor utility: $E(r_p) - \frac{1}{2} A \sigma_p^2$ |
| $r_f$ | Annual risk-free rate (= 0.03) |
| $S_p$ | Sharpe ratio: $(E(r_p) - r_f) / \sigma_p$ |
| GMVP | Global Minimum Variance Portfolio |
| CML | Capital Market Line |

---

*Document ends. Version 1.0.0. All module owners should acknowledge receipt before sprint commencement.*
