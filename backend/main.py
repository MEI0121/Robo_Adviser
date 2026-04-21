"""
FastAPI application — Robo-Adviser backend.

Exposes three endpoints as defined in PRD Section 2:
  POST /api/v1/optimize    — core MPT optimization
  GET  /api/v1/funds       — fund universe manifest + covariance matrix
  POST /api/v1/chat/assess — LangGraph risk chatbot proxy

CORS is enabled for http://localhost:3000 (Next.js dev server).
Start with: uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

# Load secrets before any module that instantiates the LLM (e.g. risk_chatbot.graph).
_backend_dir = Path(__file__).resolve().parent
_project_root = _backend_dir.parent
load_dotenv(_project_root / ".env")
load_dotenv(_backend_dir / ".env")  # backend-local overrides project root

import time
from contextlib import asynccontextmanager
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import RISK_FREE_RATE
from data_loader import (
    DataLoadError,
    MatrixConditionError,
    get_data_date_range,
    get_fund_codes,
    load_fund_metadata,
    load_market_data,
)
from models import (
    ChatAssessRequest,
    ChatAssessResponse,
    ErrorResponse,
    FrontierPoint as FrontierPointModel,
    FundsResponse,
    FundInfo,
    OptimalPortfolioStats,
    OptimizeRequest,
    OptimizeResponse,
    OptimizationMetadata,
    PortfolioStats,
    RiskProfile,
    TangencyPortfolioStats,
)
from risk_chatbot.graph import sanitise_langgraph_state, step_graph
from optimizer import (
    OptimizationError,
    FrontierPoint,
    PortfolioResult,
    compute_efficient_frontier,
    compute_gmvp,
    compute_optimal_portfolio,
    compute_tangency_portfolio,
)
from market_cache import get_market_artifacts_cache
from portfolio_math import portfolio_return, portfolio_volatility, sharpe_ratio

# ---------------------------------------------------------------------------
# Application-level state (market data cached at startup)
# ---------------------------------------------------------------------------

_app_state: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load market data once at startup; fail loudly if files are missing."""
    try:
        mu, cov = load_market_data()
        _app_state["mu"] = mu
        _app_state["cov"] = cov
        _app_state["fund_metadata"] = load_fund_metadata()
        _app_state["fund_codes"] = get_fund_codes()
        _app_state["date_range"] = get_data_date_range()
        print(
            f"[startup] Market data loaded: mu.shape={mu.shape}, cov.shape={cov.shape}"
        )
    except (DataLoadError, MatrixConditionError) as exc:
        # Warn but don't crash — endpoints will return 503 if data is absent.
        print(f"[startup WARNING] Could not load market data: {exc}")
        _app_state["mu"] = None
        _app_state["cov"] = None
        _app_state["fund_metadata"] = None
        _app_state["fund_codes"] = None
        _app_state["date_range"] = ("2015-01-02", "2025-12-31")
    yield
    # Cleanup on shutdown (none required)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Robo-Adviser API",
    description=(
        "Modern Portfolio Theory optimization engine. "
        "Implements PRD v1.0.0 — backend optimization service."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow Next.js dev and prod origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://[::1]:3000",
        "https://robo-adviser.internal",
    ],
    # Dev-only: match Next on any localhost form / port (helps IPv6 [::1] vs 127.0.0.1)
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global exception handler — returns ErrorResponse envelope on unhandled errors
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    error = ErrorResponse(
        error_code="INTERNAL_SERVER_ERROR",
        message=str(exc),
        details={"type": type(exc).__name__},
    )
    return JSONResponse(status_code=500, content=error.model_dump())


# ---------------------------------------------------------------------------
# Utility: guard that data is loaded
# ---------------------------------------------------------------------------


def _require_market_data() -> tuple[np.ndarray, np.ndarray]:
    """
    Return (mu, cov) or raise HTTP 503 if the data files were not loaded.
    """
    mu: np.ndarray | None = _app_state.get("mu")
    cov: np.ndarray | None = _app_state.get("cov")
    if mu is None or cov is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Market data not available. "
                "Ensure mu_vector.json and cov_matrix.json are present in /data/processed/ "
                "(from the Excel/data pipeline) and restart the server."
            ),
        )
    return mu, cov


# ---------------------------------------------------------------------------
# POST /api/v1/optimize
# ---------------------------------------------------------------------------


@app.post(
    "/api/v1/optimize",
    response_model=OptimizeResponse,
    responses={
        400: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"description": "Market data not loaded"},
    },
    summary="Compute optimal portfolio for a given risk aversion coefficient.",
)
async def optimize(body: OptimizeRequest) -> OptimizeResponse:
    """
    Given an investor's risk aversion coefficient A, returns:
    - The utility-maximizing optimal portfolio (w*, E[r_p], σ_p, Sharpe, U)
    - The Global Minimum Variance Portfolio (GMVP)
    - The full efficient frontier (100 points, volatility-sorted)
    """
    mu, cov = _require_market_data()
    fund_codes: list[str] = _app_state["fund_codes"]
    start_date, end_date = _app_state["date_range"]

    A = body.risk_aversion_coefficient
    max_w = body.constraints.max_single_weight

    t_start = time.monotonic()

    # --- Optimal portfolio -----------------------------------------------
    try:
        opt: PortfolioResult = compute_optimal_portfolio(mu, cov, A, max_w)
    except OptimizationError as exc:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_code="OPTIMIZATION_INFEASIBLE",
                message=str(exc),
            ).model_dump(),
        ) from exc

    # --- GMVP (closed-form) -----------------------------------------------
    try:
        w_gmvp = compute_gmvp(cov)
    except OptimizationError as exc:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_code="GMVP_COMPUTATION_ERROR",
                message=str(exc),
            ).model_dump(),
        ) from exc

    gmvp_stats = PortfolioStats(
        weights=w_gmvp.tolist(),
        expected_annual_return=portfolio_return(w_gmvp, mu),
        annual_volatility=portfolio_volatility(w_gmvp, cov),
        sharpe_ratio=sharpe_ratio(w_gmvp, mu, cov),
    )

    # --- Efficient frontier (long-only) ----------------------------------
    try:
        frontier_points: list[FrontierPoint] = compute_efficient_frontier(
            mu, cov, n_points=100, max_weight=max_w
        )
    except OptimizationError as exc:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_code="FRONTIER_COMPUTATION_ERROR",
                message=str(exc),
            ).model_dump(),
        ) from exc

    # --- NEW artifacts (PRD Part 1) --------------------------------------
    # Request-dependent path: long-only tangency (depends on max_weight).
    # The short-circuit in compute_tangency_portfolio keeps this fast even
    # when max_weight < 1 makes the primary path infeasible.
    try:
        tangency_long = compute_tangency_portfolio(
            mu, cov, max_weight=max_w, allow_short_selling=False
        )
    except OptimizationError as exc:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_code="FRONTIER_COMPUTATION_ERROR",
                message=str(exc),
            ).model_dump(),
        ) from exc

    # Request-independent path: GMVP short-allowed, tangency short-allowed,
    # short-allowed frontier (100 points), equal-weight. Cached across calls
    # — invariant in A and max_weight.
    try:
        cached = get_market_artifacts_cache().get(mu, cov)
    except OptimizationError as exc:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_code="FRONTIER_COMPUTATION_ERROR",
                message=str(exc),
            ).model_dump(),
        ) from exc

    w_gmvp_short = cached.gmvp_short_allowed
    tangency_short = cached.tangency_short_allowed
    frontier_points_short = cached.efficient_frontier_short_allowed
    equal_weight_result = cached.equal_weight

    gmvp_short_stats = PortfolioStats(
        weights=w_gmvp_short.tolist(),
        expected_annual_return=portfolio_return(w_gmvp_short, mu),
        annual_volatility=portfolio_volatility(w_gmvp_short, cov),
        sharpe_ratio=sharpe_ratio(w_gmvp_short, mu, cov),
    )

    def _tangency_to_model(r: PortfolioResult) -> TangencyPortfolioStats:
        return TangencyPortfolioStats(
            weights=r.weights.tolist(),
            expected_annual_return=r.expected_return,
            annual_volatility=r.volatility,
            sharpe_ratio=r.sharpe,
            solver_path=r.solver_path or None,
        )

    equal_weight_stats = PortfolioStats(
        weights=equal_weight_result.weights.tolist(),
        expected_annual_return=equal_weight_result.expected_return,
        annual_volatility=equal_weight_result.volatility,
        sharpe_ratio=equal_weight_result.sharpe,
    )

    t_elapsed_ms = int((time.monotonic() - t_start) * 1000)

    # --- Assemble response ------------------------------------------------
    return OptimizeResponse(
        optimal_portfolio=OptimalPortfolioStats(
            weights=opt.weights.tolist(),
            fund_codes=fund_codes,
            expected_annual_return=opt.expected_return,
            annual_volatility=opt.volatility,
            sharpe_ratio=opt.sharpe,
            utility_score=opt.utility_score,
        ),
        gmvp=gmvp_stats,
        efficient_frontier=[
            FrontierPointModel(
                expected_return=fp.expected_return,
                volatility=fp.volatility,
                sharpe_ratio=fp.sharpe_ratio,
                weights=fp.weights.tolist(),
            )
            for fp in frontier_points
        ],
        gmvp_short_allowed=gmvp_short_stats,
        tangency=_tangency_to_model(tangency_long),
        tangency_short_allowed=_tangency_to_model(tangency_short),
        efficient_frontier_short_allowed=[
            FrontierPointModel(
                expected_return=fp.expected_return,
                volatility=fp.volatility,
                sharpe_ratio=fp.sharpe_ratio,
                weights=fp.weights.tolist(),
            )
            for fp in frontier_points_short
        ],
        equal_weight=equal_weight_stats,
        metadata=OptimizationMetadata(
            risk_aversion_coefficient=A,
            risk_free_rate=RISK_FREE_RATE,
            num_assets=10,
            data_start_date=start_date,
            data_end_date=end_date,
            optimization_method="SLSQP",
            computation_time_ms=t_elapsed_ms,
        ),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/funds
# ---------------------------------------------------------------------------


@app.get(
    "/api/v1/funds",
    response_model=FundsResponse,
    responses={
        503: {"description": "Market data not loaded"},
    },
    summary="Return fund universe manifest and covariance matrix.",
)
async def get_funds() -> FundsResponse:
    """
    Returns the static list of 10 funds with their metadata and the
    pre-computed annualized covariance matrix.
    """
    mu, cov = _require_market_data()
    raw_metadata: list[dict] = _app_state["fund_metadata"]

    funds = []
    for i, meta in enumerate(raw_metadata):
        # Pull per-fund return and vol from mu/cov diagonal
        w_single = np.zeros(10, dtype=np.float64)
        w_single[i] = 1.0
        ann_ret = float(mu[i])
        ann_vol = float(np.sqrt(cov[i, i]))
        sr = float((ann_ret - RISK_FREE_RATE) / ann_vol) if ann_vol > 1e-12 else 0.0

        funds.append(
            FundInfo(
                fund_code=meta["fund_code"],
                fund_name=meta["fund_name"],
                asset_class=meta["asset_class"],
                currency=meta.get("currency", "USD"),
                annualized_return=round(ann_ret, 6),
                annualized_volatility=round(ann_vol, 6),
                sharpe_ratio=round(sr, 6),
                nav_history_years=meta.get("nav_history_years", 10),
            )
        )

    return FundsResponse(
        funds=funds,
        covariance_matrix=cov.tolist(),
    )


# ---------------------------------------------------------------------------
# POST /api/v1/chat/assess — risk assessment stepper + HTTP surface
# ---------------------------------------------------------------------------


@app.post(
    "/api/v1/chat/assess",
    response_model=ChatAssessResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="LangGraph risk assessment chatbot proxy.",
)
async def chat_assess(body: ChatAssessRequest) -> ChatAssessResponse:
    """
    Stateless proxy: one HTTP request advances the LangGraph by one turn.

    The client persists ``updated_state`` and sends it back as ``current_state``.
    When ``is_terminal`` is true, ``risk_profile`` contains ``risk_aversion_coefficient``
    for ``POST /api/v1/optimize``.
    """
    # Normalise request: blank message / empty state snapshot behave like "not sent"
    user_message = body.user_message
    if user_message is not None and user_message.strip() == "":
        user_message = None

    current_state = body.current_state
    if current_state is not None and len(current_state) == 0:
        current_state = None

    try:
        result = step_graph(
            session_id=body.session_id,
            user_message=user_message,
            current_state=current_state,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error_code="INVALID_INPUT",
                message=str(exc),
            ).model_dump(),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error_code="GRAPH_EXECUTION_ERROR",
                message=str(exc),
            ).model_dump(),
        ) from exc

    risk_profile_out: RiskProfile | None = None
    if result["is_terminal"] and result.get("risk_profile"):
        rp = result["risk_profile"]
        risk_profile_out = RiskProfile(
            risk_aversion_coefficient=rp["risk_aversion_coefficient"],
            profile_label=rp["profile_label"],
            dimension_scores=rp["dimension_scores"],
        )

    updated_state = sanitise_langgraph_state(result["updated_state"])

    return ChatAssessResponse(
        session_id=body.session_id,
        assistant_message=result["assistant_message"],
        updated_state=updated_state,
        is_terminal=result["is_terminal"],
        risk_profile=risk_profile_out,
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    data_status = "loaded" if _app_state.get("mu") is not None else "missing"
    return {"status": "ok", "market_data": data_status}
