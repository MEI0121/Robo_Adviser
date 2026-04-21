"""
Pydantic request/response models for the Robo-Adviser FastAPI backend.
All schemas adhere strictly to the API contract defined in PRD Section 2.
"""

from __future__ import annotations

import uuid
from typing import Literal, Optional

import numpy as np
from pydantic import BaseModel, Field, model_validator

from config import RISK_FREE_RATE


# ---------------------------------------------------------------------------
# Shared sub-models
# ---------------------------------------------------------------------------


class PortfolioStats(BaseModel):
    """Statistics for a single portfolio point (optimal or GMVP)."""

    weights: list[float] = Field(
        ...,
        min_length=10,
        max_length=10,
        description="Asset allocation weights. Sum = 1.0.",
    )
    expected_annual_return: float = Field(
        ..., description="E(r_p) = w^T * mu. Annualized, decimal form."
    )
    annual_volatility: float = Field(
        ..., description="sigma_p = sqrt(w^T * Sigma * w). Annualized, decimal form."
    )
    sharpe_ratio: float = Field(
        ..., description="(E(r_p) - r_f) / sigma_p. r_f = 0.03."
    )


class OptimalPortfolioStats(PortfolioStats):
    """Extended stats for the investor-specific optimal portfolio."""

    fund_codes: list[str] = Field(
        ...,
        min_length=10,
        max_length=10,
        description="FSMOne fund codes in the same order as weights.",
    )
    utility_score: float = Field(
        ...,
        description="U = E(r_p) - 0.5 * A * sigma_p^2. Maximized value.",
    )


class TangencyPortfolioStats(PortfolioStats):
    """
    Tangency (max-Sharpe) portfolio stats.

    Extends PortfolioStats with ``solver_path`` to surface which branch
    of compute_tangency_portfolio produced the result:
      - "primary"  — the scaled min-variance QP solution renormalised
      - "fallback" — direct Sharpe-max SLSQP

    On the current dataset, non-scale-invariant bounds (e.g. [-1, 2] or
    a long-only cap < 1) mean the fallback path is typically chosen.
    Exposed on the API so the reconciliation harness and methodology
    report can audit which branch was taken per regime.

    ``utility_score`` is not meaningful for a tangency portfolio (it is
    defined against a risk-aversion coefficient A, and the tangency is
    independent of any specific investor) — it is omitted from this model.
    """

    solver_path: Optional[str] = Field(
        default=None,
        description='"primary" or "fallback"; identifies which branch of '
        "compute_tangency_portfolio produced this result.",
    )


class FrontierPoint(BaseModel):
    """A single point on the efficient frontier."""

    expected_return: float
    volatility: float
    sharpe_ratio: float
    weights: list[float] = Field(..., min_length=10, max_length=10)


class OptimizationMetadata(BaseModel):
    """Metadata attached to every optimization response."""

    risk_aversion_coefficient: float
    risk_free_rate: float = RISK_FREE_RATE
    num_assets: int = 10
    data_start_date: str
    data_end_date: str
    optimization_method: str = "SLSQP"
    computation_time_ms: int


# ---------------------------------------------------------------------------
# POST /api/v1/optimize
# ---------------------------------------------------------------------------


class OptimizeConstraints(BaseModel):
    """Optional solver constraints forwarded from the frontend."""

    allow_short_selling: bool = Field(
        default=False,
        description="If False, enforces w_i >= 0 for all assets.",
    )
    max_single_weight: float = Field(
        default=1.0,
        ge=0.1,
        le=1.0,
        description="Upper bound on any single asset weight.",
    )


class OptimizeRequest(BaseModel):
    """Request body for POST /api/v1/optimize."""

    risk_aversion_coefficient: float = Field(
        ...,
        ge=0.5,
        le=10.0,
        description="Investor risk aversion parameter A from LangGraph chatbot.",
        examples=[3.5],
    )
    constraints: OptimizeConstraints = Field(default_factory=OptimizeConstraints)


class OptimizeResponse(BaseModel):
    """Success response body for POST /api/v1/optimize."""

    status: Literal["success"] = "success"
    optimal_portfolio: OptimalPortfolioStats
    gmvp: PortfolioStats
    efficient_frontier: list[FrontierPoint] = Field(
        ...,
        min_length=50,
        max_length=200,
        description=(
            "Long-only efficient frontier. Currently 100 points sorted by "
            "volatility ascending. Bounds are relaxed to [50, 200] to allow "
            "future adjustments without an API contract change; the server "
            "currently always emits 100."
        ),
    )

    # ----- New artifacts (PRD Part 1: short-sale + tangency + equal-weight) --
    gmvp_short_allowed: PortfolioStats = Field(
        ...,
        description=(
            "GMVP computed under relaxed constraints w_i in [-1, 2]. Same "
            "shape as `gmvp`; shorts are expected on the current dataset."
        ),
    )
    tangency: TangencyPortfolioStats = Field(
        ...,
        description=(
            "Max-Sharpe portfolio under the request's max_single_weight "
            "cap, long-only. Anchor point for the Capital Market Line."
        ),
    )
    tangency_short_allowed: TangencyPortfolioStats = Field(
        ...,
        description=(
            "Max-Sharpe portfolio under relaxed constraints w_i in [-1, 2]."
        ),
    )
    efficient_frontier_short_allowed: list[FrontierPoint] = Field(
        ...,
        min_length=50,
        max_length=200,
        description=(
            "Parallel 100-point efficient frontier with w_i in [-1, 2]. "
            "Same point count as `efficient_frontier` so the two curves "
            "can be compared directly in the σ-E(r) plane."
        ),
    )
    equal_weight: PortfolioStats = Field(
        ...,
        description=(
            "Naive 1/n benchmark. Computed server-side (replaces the "
            "frontend's previous incorrect average-of-frontier-points)."
        ),
    )

    metadata: OptimizationMetadata


# ---------------------------------------------------------------------------
# GET /api/v1/funds
# ---------------------------------------------------------------------------


class FundInfo(BaseModel):
    """
    Metadata for a single fund in the universe.

    ``fund_code`` and ``fund_name`` are the **display layer** — the FSMOne
    fund identifiers that users see and transact in. Expected returns and
    covariance, however, are estimated from a liquid ETF ``proxy_ticker``
    priced via ``proxy_provider``, because FSMOne does not expose 10-year
    daily historical data via API. The split is documented to users via a
    methodology tooltip on the fund-listing pages.
    """

    fund_code: str
    fund_name: str
    proxy_ticker: str = Field(
        ...,
        description="ETF ticker used to estimate mu and sigma for this fund.",
    )
    proxy_provider: str = Field(
        default="Yahoo Finance",
        description="Upstream price-series provider for the proxy ticker.",
    )
    asset_class: Literal[
        "Equity-Global",
        "Equity-Regional",
        "Fixed-Income",
        "Multi-Asset",
        "Commodity",
        "REIT",
    ]
    currency: str
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
    nav_history_years: int = Field(..., ge=10)


class FundsResponse(BaseModel):
    """Response body for GET /api/v1/funds."""

    funds: list[FundInfo] = Field(..., min_length=10, max_length=10)
    covariance_matrix: list[list[float]] = Field(
        ...,
        description="10x10 annualized covariance matrix Sigma. Row-major order.",
    )

    @model_validator(mode="after")
    def validate_cov_shape(self) -> "FundsResponse":
        if len(self.covariance_matrix) != 10 or any(
            len(row) != 10 for row in self.covariance_matrix
        ):
            raise ValueError("covariance_matrix must be 10x10.")
        return self


# ---------------------------------------------------------------------------
# POST /api/v1/chat/assess  (proxy passthrough — schema only)
# ---------------------------------------------------------------------------


class ChatAssessRequest(BaseModel):
    """Request body for POST /api/v1/chat/assess."""

    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="UUID for this session; generated server-side if omitted.",
    )
    user_message: Optional[str] = Field(
        default=None,
        description=(
            "Latest user reply. Omit or null on the first turn to receive the "
            "opening question."
        ),
    )
    current_state: Optional[dict] = Field(
        default=None,
        description="Opaque LangGraph state snapshot from the prior response.",
    )


class RiskProfile(BaseModel):
    """Terminal risk profile. Only present when is_terminal = True."""

    risk_aversion_coefficient: float = Field(..., ge=0.5, le=10.0)
    profile_label: Literal[
        "Conservative",
        "Moderately Conservative",
        "Moderate",
        "Moderately Aggressive",
        "Aggressive",
    ]
    dimension_scores: dict[str, int]


class ChatAssessResponse(BaseModel):
    """Response body for POST /api/v1/chat/assess."""

    session_id: str
    assistant_message: str
    updated_state: dict
    is_terminal: bool = Field(
        ...,
        description="True when the graph has reached the terminal RiskProfileState node.",
    )
    risk_profile: Optional[RiskProfile] = Field(
        default=None,
        description="Only present when is_terminal = True.",
    )


# ---------------------------------------------------------------------------
# Error schema (all endpoints)
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Standard error envelope returned on 400 / 422 / 500."""

    status: Literal["error"] = "error"
    error_code: str
    message: str
    details: dict = Field(default_factory=dict)
