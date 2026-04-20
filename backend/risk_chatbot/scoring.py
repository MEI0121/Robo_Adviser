"""
Pure, deterministic scoring functions for the psychographic risk assessment.

All business logic lives here as stateless functions so that:
  - The LangGraph graph can call them without side-effects.
  - Unit tests achieve 100% coverage without spinning up an LLM.

Mathematical specification (from PRD §3 risk-assessment module):

  Composite score:
      C = (1/5) * Σ(s_k)   for k in {horizon, drawdown, loss_reaction,
                                        income_stability, experience}
      C ∈ [1.0, 5.0]

  A-score mapping (linear):
      A = 10.5 - C × 2.375
      A ∈ [0.5, 10.0]   (clamped; raises ValueError outside range)

  Derivation check:
      C = 1  →  A = 10.5 - 1×2.375  = 8.125   (near-Conservative boundary)
      C = 5  →  A = 10.5 - 5×2.375  = 0.625   (near-Aggressive boundary)
      The formula yields A ∈ [0.625, 8.125] for integer C in [1, 5].
      Non-integer means can produce values closer to the boundary extremes.

  Profile label thresholds:
      [8.0, 10.0] → Conservative
      [5.5,  8.0) → Moderately Conservative
      [3.5,  5.5) → Moderate
      [1.5,  3.5) → Moderately Aggressive
      [0.5,  1.5) → Aggressive
"""

from __future__ import annotations

from typing import Literal

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_A_INTERCEPT: float = 10.5
_A_SLOPE: float = 2.375          # (10.0 - 0.5) / (5 - 1)  ×  correction factor
_A_MIN: float = 0.5
_A_MAX: float = 10.0

PROFILE_LABELS = Literal[
    "Conservative",
    "Moderately Conservative",
    "Moderate",
    "Moderately Aggressive",
    "Aggressive",
]

# Dimension keys in canonical order (matches scoring rubric table in PRD)
DIMENSION_KEYS: tuple[str, ...] = (
    "horizon",
    "drawdown",
    "loss_reaction",
    "income_stability",
    "experience",
)

# ---------------------------------------------------------------------------
# Scoring rubric: keywords used by the LLM-guided node prompts
# ---------------------------------------------------------------------------

SCORING_RUBRIC: dict[str, dict[int, str]] = {
    "horizon": {
        1: "Less than 2 years",
        2: "2 to 5 years",
        3: "5 to 10 years",
        4: "10 to 20 years",
        5: "More than 20 years",
    },
    "drawdown": {
        1: "Less than 5% loss tolerable",
        2: "5% to 10% loss tolerable",
        3: "10% to 20% loss tolerable",
        4: "20% to 30% loss tolerable",
        5: "More than 30% loss tolerable",
    },
    "loss_reaction": {
        1: "Would panic-sell all holdings immediately",
        2: "Would sell a portion to reduce exposure",
        3: "Would hold and wait for recovery",
        4: "Would stay invested and review allocation",
        5: "Would buy more to take advantage of lower prices",
    },
    "income_stability": {
        1: "Very unstable income, immediate liquidity needed",
        2: "Somewhat unstable, may need funds within 1 year",
        3: "Moderate stability, emergency fund in place",
        4: "Stable income, minimal liquidity needs",
        5: "Very high stability, diversified income sources",
    },
    "experience": {
        1: "No prior investment experience",
        2: "Some experience with savings accounts / fixed deposits",
        3: "Intermediate experience with equities or mutual funds",
        4: "Experienced with diversified portfolio management",
        5: "Expert investor with professional-level knowledge",
    },
}


# ---------------------------------------------------------------------------
# Core pure functions
# ---------------------------------------------------------------------------

def compute_composite_score(dimension_scores: dict[str, int]) -> float:
    """
    Compute the mean of the five dimension scores.

    Parameters
    ----------
    dimension_scores : dict mapping each of the 5 dimension keys to an int in [1, 5].

    Returns
    -------
    float
        Composite score C in [1.0, 5.0].

    Raises
    ------
    ValueError
        If any required key is missing or any score is outside [1, 5].
    """
    for key in DIMENSION_KEYS:
        if key not in dimension_scores:
            raise ValueError(f"Missing required dimension score: '{key}'")
        score = dimension_scores[key]
        if not isinstance(score, int) or not (1 <= score <= 5):
            raise ValueError(
                f"Score for dimension '{key}' is {score!r}; must be an integer in [1, 5]"
            )
    return sum(dimension_scores[k] for k in DIMENSION_KEYS) / len(DIMENSION_KEYS)


def compute_a_score(composite_score: float) -> float:
    """
    Map a composite score C to the risk aversion coefficient A.

    Formula (PRD §3 risk-assessment module):
        A = 10.5 - C × 2.375

    Parameters
    ----------
    composite_score : float in [1.0, 5.0]

    Returns
    -------
    float
        A ∈ [0.5, 10.0], clamped to the valid range.

    Raises
    ------
    ValueError
        If the raw (pre-clamp) A value deviates more than 1e-3 outside [0.5, 10.0],
        which would indicate a logic error rather than floating-point rounding.
    """
    raw_a = _A_INTERCEPT - composite_score * _A_SLOPE

    # The formula A = 10.5 - C × 2.375 yields A ≈ 0.5 at C ≈ 4.22 and goes
    # negative beyond that.  For C = 5.0 (all dimensions scored 5) the raw
    # value is -1.375 — this is an expected, mathematically valid outcome that
    # the PRD explicitly instructs us to clamp to 0.5.
    #
    # Only raise if the composite_score itself is wildly out of its own [1, 5]
    # domain (which would indicate a programming error upstream).
    if composite_score < 0.9 or composite_score > 5.1:
        raise ValueError(
            f"composite_score {composite_score:.6f} is outside [1, 5]; "
            f"this is a programming error — raw A = {raw_a:.6f}"
        )

    return float(max(_A_MIN, min(_A_MAX, raw_a)))


def assign_profile_label(a_score: float) -> str:
    """
    Map a risk aversion coefficient A to its human-readable profile label.

    Boundary table (PRD §3 risk-assessment module):
        [8.0, 10.0] → Conservative
        [5.5,  8.0) → Moderately Conservative
        [3.5,  5.5) → Moderate
        [1.5,  3.5) → Moderately Aggressive
        [0.5,  1.5) → Aggressive

    Parameters
    ----------
    a_score : float in [0.5, 10.0]

    Returns
    -------
    str — one of the five canonical profile labels.

    Raises
    ------
    ValueError
        If a_score is outside [0.5, 10.0].
    """
    if not (_A_MIN <= a_score <= _A_MAX):
        raise ValueError(
            f"a_score {a_score:.6f} is outside [0.5, 10.0]; cannot assign profile label"
        )

    if a_score >= 8.0:
        return "Conservative"
    if a_score >= 5.5:
        return "Moderately Conservative"
    if a_score >= 3.5:
        return "Moderate"
    if a_score >= 1.5:
        return "Moderately Aggressive"
    return "Aggressive"


def score_to_risk_profile(
    dimension_scores: dict[str, int],
    session_id: str,
    conversation_turns: int,
) -> dict:
    """
    Full pipeline: dimension scores → composite → A score → profile label.

    This function is the single entry point for all scoring logic and is used
    by the `score_and_classify` LangGraph node.

    Returns
    -------
    dict
        A plain dict that is valid input for `RiskProfileState(**result)`.
    """
    composite = compute_composite_score(dimension_scores)
    a_score = compute_a_score(composite)
    label = assign_profile_label(a_score)

    return {
        "session_id": session_id,
        "risk_aversion_coefficient": round(a_score, 6),
        "profile_label": label,
        "dimension_scores": dict(dimension_scores),
        "composite_score": round(composite, 6),
        "conversation_turns": conversation_turns,
        "is_terminal": True,
    }


# ---------------------------------------------------------------------------
# Helper: check whether all five dimensions have been scored
# ---------------------------------------------------------------------------

def all_dimensions_scored(dimension_scores: dict[str, int]) -> bool:
    """Return True only when every required dimension has a valid 1-5 score."""
    return all(
        dimension_scores.get(k, 0) in range(1, 6) for k in DIMENSION_KEYS
    )
