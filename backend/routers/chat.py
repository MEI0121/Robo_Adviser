"""
FastAPI router: POST /api/v1/chat/assess

Implements the LangGraph risk chatbot proxy endpoint specified in PRD §2.4.

Request  → forwards `user_message` + `current_state` to the LangGraph graph runner.
Response → returns `assistant_message`, `updated_state`, `is_terminal`, and
           (when is_terminal=true) a fully populated `risk_profile` object.

The endpoint is stateless: the caller is responsible for persisting
`updated_state` between turns and passing it back as `current_state`.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..risk_chatbot.graph import sanitise_langgraph_state, step_graph

router = APIRouter(prefix="/chat", tags=["Risk Assessment Chatbot"])


# ---------------------------------------------------------------------------
# Request / Response Pydantic models (match PRD §2.4 contract exactly)
# ---------------------------------------------------------------------------

class ChatAssessRequest(BaseModel):
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="UUID identifying the chat session; auto-generated if not provided",
    )
    user_message: Optional[str] = Field(
        default=None,
        description=(
            "The user's latest message. "
            "Pass null / omit on the very first turn to receive the opening question."
        ),
    )
    current_state: Optional[dict[str, Any]] = Field(
        default=None,
        description="Opaque LangGraph state snapshot returned by the previous response",
    )


class RiskProfileResponse(BaseModel):
    """Inline risk profile — only present when is_terminal=true."""
    risk_aversion_coefficient: float
    profile_label: str
    dimension_scores: dict[str, int]
    composite_score: float


class ChatAssessResponse(BaseModel):
    session_id: str
    assistant_message: str
    updated_state: dict[str, Any]
    is_terminal: bool
    risk_profile: Optional[RiskProfileResponse] = None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/assess",
    response_model=ChatAssessResponse,
    summary="Risk Assessment Chatbot — step the LangGraph forward by one turn",
    responses={
        400: {"description": "Invalid session or message payload"},
        500: {"description": "LangGraph execution error"},
    },
)
def assess(request: ChatAssessRequest) -> ChatAssessResponse:
    """
    Stateless proxy to the LangGraph risk assessment graph.

    ### Flow
    1. Receive `session_id`, optional `user_message`, and optional `current_state`.
    2. Inject the user message into the graph and advance by one turn.
    3. Return the assistant's next question (or terminal summary) plus the
       updated state snapshot for the client to persist.

    ### Terminal condition
    When `is_terminal` is `true`, `risk_profile` is populated with the
    computed `risk_aversion_coefficient` and `profile_label`.  The frontend
    should read `risk_aversion_coefficient` and POST it to `/api/v1/optimize`.
    """
    try:
        result = step_graph(
            session_id=request.session_id,
            user_message=request.user_message,
            current_state=request.current_state,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_INPUT", "message": str(exc)},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "GRAPH_EXECUTION_ERROR",
                "message": str(exc),
            },
        )

    risk_profile_response: Optional[RiskProfileResponse] = None
    if result["is_terminal"] and result.get("risk_profile"):
        rp = result["risk_profile"]
        risk_profile_response = RiskProfileResponse(
            risk_aversion_coefficient=rp["risk_aversion_coefficient"],
            profile_label=rp["profile_label"],
            dimension_scores=rp["dimension_scores"],
            composite_score=rp["composite_score"],
        )

    updated_state = sanitise_langgraph_state(result["updated_state"])

    return ChatAssessResponse(
        session_id=request.session_id,
        assistant_message=result["assistant_message"],
        updated_state=updated_state,
        is_terminal=result["is_terminal"],
        risk_profile=risk_profile_response,
    )


