"""
State definitions for the LangGraph risk assessment chatbot.

Two layers of state:
  1. ChatState (TypedDict) — mutable working state passed between graph nodes.
  2. RiskProfileState (Pydantic BaseModel) — immutable terminal output emitted
     when all five dimensions have been scored and the graph exits.
"""

from __future__ import annotations

from typing import Annotated, Literal, NotRequired, Optional
from typing_extensions import TypedDict

from pydantic import BaseModel, Field, field_validator
import operator


# ---------------------------------------------------------------------------
# Intermediate / Working State  (TypedDict — used inside the LangGraph graph)
# ---------------------------------------------------------------------------

class DimensionScores(TypedDict, total=False):
    """Raw 1-5 integer scores for each psychographic dimension."""
    horizon: int            # investment horizon
    drawdown: int           # max acceptable drawdown tolerance
    loss_reaction: int      # emotional / behavioural response to portfolio loss
    income_stability: int   # income reliability and liquidity needs
    experience: int         # prior investment experience level


class ChatState(TypedDict):
    """
    Session state returned by ``POST /api/v1/chat/assess`` as ``updated_state``.

    `messages` is the server-side transcript (may differ from the UI if the client
    shows a static opening line). ``pending_dimension`` records which rubric
    dimension the last assistant prompt belongs to — the next user reply is
    scored for that dimension only.
    """
    session_id: str
    messages: Annotated[list[dict], operator.add]
    dimension_scores: DimensionScores
    conversation_turns: int
    current_node: str       # tracks which dimension node is active
    is_terminal: bool
    pending_dimension: NotRequired[str | None]


# ---------------------------------------------------------------------------
# Terminal Output State  (Pydantic BaseModel — the final emitted artefact)
# ---------------------------------------------------------------------------

PROFILE_LABELS = Literal[
    "Conservative",
    "Moderately Conservative",
    "Moderate",
    "Moderately Aggressive",
    "Aggressive",
]


class RiskProfileState(BaseModel):
    """
    Strictly-typed terminal state emitted by the `score_and_classify` node.
    This object is serialised to JSON and returned to the frontend via the
    POST /api/v1/chat/assess response under the `risk_profile` key.
    """

    session_id: str = Field(..., description="UUID of the chat session")

    risk_aversion_coefficient: float = Field(
        ...,
        ge=0.5,
        le=10.0,
        description="Investor risk aversion parameter A in [0.5, 10.0]",
    )

    profile_label: PROFILE_LABELS = Field(
        ...,
        description="Human-readable risk profile bucket",
    )

    dimension_scores: dict[str, int] = Field(
        ...,
        description=(
            "Raw 1-5 scores per dimension: "
            "{'horizon': int, 'drawdown': int, 'loss_reaction': int, "
            "'income_stability': int, 'experience': int}"
        ),
    )

    composite_score: float = Field(
        ...,
        ge=1.0,
        le=5.0,
        description="Mean of the five dimension scores (1–5 scale)",
    )

    conversation_turns: int = Field(
        ...,
        ge=1,
        description="Total number of user turns taken to complete the assessment",
    )

    is_terminal: bool = Field(default=True)

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("risk_aversion_coefficient")
    @classmethod
    def clamp_a_score(cls, v: float) -> float:
        """Raise if A falls outside the allowed range — never silently clamp."""
        if not (0.5 <= v <= 10.0):
            raise ValueError(
                f"risk_aversion_coefficient {v:.6f} is outside [0.5, 10.0]"
            )
        return round(v, 6)

    @field_validator("dimension_scores")
    @classmethod
    def validate_dimension_scores(cls, v: dict[str, int]) -> dict[str, int]:
        required_keys = {"horizon", "drawdown", "loss_reaction", "income_stability", "experience"}
        missing = required_keys - v.keys()
        if missing:
            raise ValueError(f"Missing dimension scores: {missing}")
        for key, score in v.items():
            if not (1 <= score <= 5):
                raise ValueError(f"Score for '{key}' is {score}; must be in [1, 5]")
        return v


# ---------------------------------------------------------------------------
# Per-node structured output models  (used with model.with_structured_output)
# ---------------------------------------------------------------------------

class DimensionScore(BaseModel):
    """LLM structured output for a single dimension extraction node."""
    score: int = Field(..., ge=1, le=5, description="Dimension score 1–5")
    reasoning: str = Field(..., description="Brief justification for the score")
    follow_up_needed: bool = Field(
        default=False,
        description="True if the user's answer was ambiguous and a clarifying question should be asked",
    )


class AssistantMessage(BaseModel):
    """LLM structured output for generating the next conversational prompt."""
    message: str = Field(..., description="The assistant's next message to the user")
