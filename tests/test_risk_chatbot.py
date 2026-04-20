"""
Unit tests for the psychographic risk assessment scoring engine.

Coverage targets (PRD Acceptance Criteria):
  - All 5 scoring rubric boundary conditions (score = 1, 3, 5 per dimension)
  - A score always in [0.5, 10.0]
  - Same dimension scores always yield the same A (determinism)
  - ValueError raised outside range
  - Profile label thresholds (all five buckets)
  - RiskProfileState Pydantic validation gates

Run with:
    pytest tests/test_risk_chatbot.py -v
"""

from __future__ import annotations

import math
import pytest

# The scoring module is pure Python — no LLM, no I/O.
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.risk_chatbot.scoring import (
    DIMENSION_KEYS,
    assign_profile_label,
    compute_a_score,
    compute_composite_score,
    score_to_risk_profile,
    all_dimensions_scored,
)
from backend.risk_chatbot.state import RiskProfileState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _all_scores(value: int) -> dict[str, int]:
    """Return a dict with every dimension set to `value`."""
    return {k: value for k in DIMENSION_KEYS}


# ---------------------------------------------------------------------------
# compute_composite_score
# ---------------------------------------------------------------------------

class TestCompositeScore:
    def test_all_ones(self):
        assert compute_composite_score(_all_scores(1)) == pytest.approx(1.0)

    def test_all_threes(self):
        assert compute_composite_score(_all_scores(3)) == pytest.approx(3.0)

    def test_all_fives(self):
        assert compute_composite_score(_all_scores(5)) == pytest.approx(5.0)

    def test_mixed_scores(self):
        # (1+2+3+4+5) / 5 = 3.0
        scores = {k: v for k, v in zip(DIMENSION_KEYS, [1, 2, 3, 4, 5])}
        assert compute_composite_score(scores) == pytest.approx(3.0)

    def test_missing_dimension_raises(self):
        incomplete = {"horizon": 3, "drawdown": 3}
        with pytest.raises(ValueError, match="Missing required dimension score"):
            compute_composite_score(incomplete)

    def test_score_below_range_raises(self):
        scores = _all_scores(3)
        scores["horizon"] = 0
        with pytest.raises(ValueError, match="must be an integer in \\[1, 5\\]"):
            compute_composite_score(scores)

    def test_score_above_range_raises(self):
        scores = _all_scores(3)
        scores["experience"] = 6
        with pytest.raises(ValueError, match="must be an integer in \\[1, 5\\]"):
            compute_composite_score(scores)

    def test_non_integer_raises(self):
        scores = dict(_all_scores(3))
        scores["horizon"] = 2.5  # type: ignore[assignment]
        with pytest.raises(ValueError):
            compute_composite_score(scores)


# ---------------------------------------------------------------------------
# compute_a_score
# ---------------------------------------------------------------------------

class TestAScore:
    """
    Formula: A = 10.5 - C × 2.375

    Boundary verification:
      C=1  →  A = 10.5 - 2.375 = 8.125
      C=3  →  A = 10.5 - 7.125 = 3.375
      C=5  →  A = 10.5 - 11.875 → clamped to 0.5 (raw = -1.375)
    """

    def test_c_equals_one(self):
        a = compute_a_score(1.0)
        assert a == pytest.approx(8.125, abs=1e-9)

    def test_c_equals_three(self):
        a = compute_a_score(3.0)
        assert a == pytest.approx(3.375, abs=1e-9)

    def test_c_equals_five_clamped(self):
        # Raw = 10.5 - 5×2.375 = -1.375 → PRD says clamp to 0.5
        a = compute_a_score(5.0)
        assert a == pytest.approx(0.5, abs=1e-9)

    def test_a_always_at_least_0_5(self):
        # For C ≥ ~4.22 the raw formula goes negative; all results clamp to 0.5
        for c in [4.0, 4.5, 5.0]:
            assert compute_a_score(c) >= 0.5

    def test_a_always_at_most_10_0(self):
        for c in [1.0, 1.5, 2.0]:
            assert compute_a_score(c) <= 10.0

    def test_monotonically_decreasing(self):
        """Higher composite score → lower A (more aggressive)."""
        prev = compute_a_score(1.0)
        for c in [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]:
            curr = compute_a_score(c)
            assert curr <= prev, f"A not decreasing at C={c}"
            prev = curr

    def test_determinism(self):
        """Calling the same input twice must return bit-identical output."""
        a1 = compute_a_score(2.6)
        a2 = compute_a_score(2.6)
        assert a1 == a2

    def test_extreme_composite_out_of_range(self):
        """composite_score vastly outside [1, 5] domain raises ValueError."""
        with pytest.raises(ValueError):
            compute_a_score(100.0)
        with pytest.raises(ValueError):
            compute_a_score(0.0)


# ---------------------------------------------------------------------------
# assign_profile_label
# ---------------------------------------------------------------------------

class TestProfileLabel:
    def test_conservative_upper(self):
        assert assign_profile_label(10.0) == "Conservative"

    def test_conservative_lower_boundary(self):
        assert assign_profile_label(8.0) == "Conservative"

    def test_moderately_conservative(self):
        assert assign_profile_label(6.5) == "Moderately Conservative"

    def test_moderately_conservative_boundary(self):
        assert assign_profile_label(5.5) == "Moderately Conservative"

    def test_moderate(self):
        assert assign_profile_label(4.5) == "Moderate"

    def test_moderate_boundary(self):
        assert assign_profile_label(3.5) == "Moderate"

    def test_moderately_aggressive(self):
        assert assign_profile_label(2.5) == "Moderately Aggressive"

    def test_moderately_aggressive_boundary(self):
        assert assign_profile_label(1.5) == "Moderately Aggressive"

    def test_aggressive(self):
        assert assign_profile_label(0.8) == "Aggressive"

    def test_aggressive_lower_boundary(self):
        assert assign_profile_label(0.5) == "Aggressive"

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError):
            assign_profile_label(0.4)
        with pytest.raises(ValueError):
            assign_profile_label(10.1)

    def test_all_five_labels_reachable(self):
        """Ensure every label bucket is reachable via legal A values."""
        expected_labels = {
            "Conservative",
            "Moderately Conservative",
            "Moderate",
            "Moderately Aggressive",
            "Aggressive",
        }
        produced = {assign_profile_label(a) for a in [9.0, 6.5, 4.5, 2.5, 0.8]}
        assert produced == expected_labels


# ---------------------------------------------------------------------------
# score_to_risk_profile — full pipeline
# ---------------------------------------------------------------------------

class TestScoreToRiskProfile:
    def test_all_ones_gives_conservative(self):
        result = score_to_risk_profile(_all_scores(1), "sess-001", 5)
        assert result["profile_label"] == "Conservative"
        assert 0.5 <= result["risk_aversion_coefficient"] <= 10.0
        assert result["is_terminal"] is True

    def test_all_fives_gives_aggressive(self):
        # C=5.0 → raw A=-1.375 → clamped to 0.5 → "Aggressive"
        result = score_to_risk_profile(_all_scores(5), "sess-002", 7)
        assert result["profile_label"] == "Aggressive"
        assert result["risk_aversion_coefficient"] == pytest.approx(0.5, abs=1e-6)

    def test_mixed_scores_returns_valid_state(self):
        scores = {k: v for k, v in zip(DIMENSION_KEYS, [2, 3, 3, 4, 3])}
        # C = (2+3+3+4+3)/5 = 3.0  →  A = 10.5 - 3×2.375 = 3.375
        result = score_to_risk_profile(scores, "sess-003", 10)
        assert result["risk_aversion_coefficient"] == pytest.approx(3.375, abs=1e-6)
        assert result["profile_label"] == "Moderately Aggressive"

    def test_composite_score_stored_correctly(self):
        scores = _all_scores(3)
        result = score_to_risk_profile(scores, "sess-004", 6)
        assert result["composite_score"] == pytest.approx(3.0, abs=1e-9)

    def test_dimension_scores_preserved(self):
        scores = {k: v for k, v in zip(DIMENSION_KEYS, [1, 2, 3, 4, 5])}
        result = score_to_risk_profile(scores, "sess-005", 8)
        assert result["dimension_scores"] == scores

    def test_determinism_same_input_same_output(self):
        scores = _all_scores(3)
        r1 = score_to_risk_profile(scores, "sess-det", 5)
        r2 = score_to_risk_profile(scores, "sess-det", 5)
        assert r1["risk_aversion_coefficient"] == r2["risk_aversion_coefficient"]
        assert r1["profile_label"] == r2["profile_label"]


# ---------------------------------------------------------------------------
# RiskProfileState Pydantic validation
# ---------------------------------------------------------------------------

class TestRiskProfileStateValidation:
    def _valid_payload(self) -> dict:
        return {
            "session_id": "test-session-uuid",
            "risk_aversion_coefficient": 3.5,
            "profile_label": "Moderate",
            "dimension_scores": {
                "horizon": 3,
                "drawdown": 3,
                "loss_reaction": 3,
                "income_stability": 3,
                "experience": 3,
            },
            "composite_score": 3.0,
            "conversation_turns": 5,
            "is_terminal": True,
        }

    def test_valid_payload_constructs(self):
        state = RiskProfileState(**self._valid_payload())
        assert state.risk_aversion_coefficient == pytest.approx(3.5)
        assert state.is_terminal is True

    def test_a_below_range_raises(self):
        payload = self._valid_payload()
        payload["risk_aversion_coefficient"] = 0.3
        with pytest.raises(Exception):  # Pydantic ValidationError
            RiskProfileState(**payload)

    def test_a_above_range_raises(self):
        payload = self._valid_payload()
        payload["risk_aversion_coefficient"] = 11.0
        with pytest.raises(Exception):
            RiskProfileState(**payload)

    def test_invalid_profile_label_raises(self):
        payload = self._valid_payload()
        payload["profile_label"] = "Reckless"  # not in Literal
        with pytest.raises(Exception):
            RiskProfileState(**payload)

    def test_missing_dimension_key_raises(self):
        payload = self._valid_payload()
        del payload["dimension_scores"]["horizon"]
        with pytest.raises(Exception):
            RiskProfileState(**payload)

    def test_dimension_score_out_of_range_raises(self):
        payload = self._valid_payload()
        payload["dimension_scores"]["horizon"] = 7
        with pytest.raises(Exception):
            RiskProfileState(**payload)


# ---------------------------------------------------------------------------
# all_dimensions_scored helper
# ---------------------------------------------------------------------------

class TestAllDimensionsScored:
    def test_all_present_returns_true(self):
        assert all_dimensions_scored(_all_scores(4)) is True

    def test_missing_dimension_returns_false(self):
        scores = _all_scores(3)
        del scores["experience"]
        assert all_dimensions_scored(scores) is False

    def test_zero_score_returns_false(self):
        scores = _all_scores(3)
        scores["horizon"] = 0
        assert all_dimensions_scored(scores) is False

    def test_score_six_returns_false(self):
        scores = _all_scores(3)
        scores["drawdown"] = 6
        assert all_dimensions_scored(scores) is False


# ---------------------------------------------------------------------------
# Boundary conditions per dimension (PRD requirement: score = 1, 3, 5)
# ---------------------------------------------------------------------------

class TestDimensionBoundaryConditions:
    """
    For each dimension, verify that the most conservative (1) and most
    aggressive (5) scores are correctly handled and that the overall
    pipeline remains valid when a single dimension takes its extreme values
    while others are held at 3.
    """

    @pytest.mark.parametrize("dimension", DIMENSION_KEYS)
    def test_dimension_score_1_valid_pipeline(self, dimension: str):
        scores = _all_scores(3)
        scores[dimension] = 1
        result = score_to_risk_profile(scores, f"sess-{dimension}-1", 5)
        assert 0.5 <= result["risk_aversion_coefficient"] <= 10.0
        assert result["profile_label"] in {
            "Conservative",
            "Moderately Conservative",
            "Moderate",
            "Moderately Aggressive",
            "Aggressive",
        }

    @pytest.mark.parametrize("dimension", DIMENSION_KEYS)
    def test_dimension_score_3_valid_pipeline(self, dimension: str):
        scores = _all_scores(3)
        result = score_to_risk_profile(scores, f"sess-{dimension}-3", 5)
        assert 0.5 <= result["risk_aversion_coefficient"] <= 10.0

    @pytest.mark.parametrize("dimension", DIMENSION_KEYS)
    def test_dimension_score_5_valid_pipeline(self, dimension: str):
        scores = _all_scores(3)
        scores[dimension] = 5
        result = score_to_risk_profile(scores, f"sess-{dimension}-5", 5)
        assert 0.5 <= result["risk_aversion_coefficient"] <= 10.0

    @pytest.mark.parametrize("score_value", [1, 3, 5])
    def test_all_dimensions_same_score_pipeline(self, score_value: int):
        """All dimensions at the same extreme — complete pipeline still valid."""
        scores = _all_scores(score_value)
        result = score_to_risk_profile(scores, f"sess-all-{score_value}", 5)
        assert 0.5 <= result["risk_aversion_coefficient"] <= 10.0
        state = RiskProfileState(**result)
        assert state.is_terminal is True
