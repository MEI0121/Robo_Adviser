"""
risk_chatbot package — psychographic risk assessment (multi-turn HTTP API).

Public surface:
    step_graph(...)    — advance the assessment by one client request (one dimension)
    RiskProfileState   — Pydantic terminal state model
    score_to_risk_profile(...)  — pure scoring pipeline
"""

from .graph import step_graph
from .scoring import (
    DIMENSION_KEYS,
    SCORING_RUBRIC,
    all_dimensions_scored,
    assign_profile_label,
    compute_a_score,
    compute_composite_score,
    score_to_risk_profile,
)
from .state import ChatState, DimensionScore, DimensionScores, RiskProfileState

__all__ = [
    # Stepping API
    "step_graph",
    # Scoring
    "DIMENSION_KEYS",
    "SCORING_RUBRIC",
    "all_dimensions_scored",
    "assign_profile_label",
    "compute_a_score",
    "compute_composite_score",
    "score_to_risk_profile",
    # State models
    "ChatState",
    "DimensionScore",
    "DimensionScores",
    "RiskProfileState",
]
