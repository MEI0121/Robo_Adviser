"""
Consistency test for the A-mapping formula displayed on /profile.

The frontend's AMappingCard recomputes A from the composite score C using
the same linear clamp formula that lives in
``backend/risk_chatbot/scoring.py``. If the two drift, users see a value
in the card that disagrees with the backend's reported A — and the
optimizer would run with a different A than the one explained to the
user. Both are bad outcomes.

This test pins the contract by verifying that ``compute_a_score`` (the
backend source of truth) produces the same numbers the frontend expects
for the four canonical cases listed in the task spec — mid-range,
low-boundary, clamp-active high, and the default-profile example.

The frontend component itself has no test runner configured (neither
Jest nor Vitest is installed). The math is extracted into a
TypeScript pure function (``frontend/components/profile/aMappingMath.ts``)
and verified-by-inspection against the backend formula. This Python
test anchors the shared contract.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest

from risk_chatbot.scoring import compute_a_score, _A_MIN, _A_MAX  # noqa: PLC0415


# Four spec cases from the task brief. Each tuple is:
#   (composite_score C, expected raw pre-clamp A, expected final clamped A,
#    whether clamping should fire).
_CANONICAL_CASES = [
    # (label,              C,    raw,     final,  clamped?)
    ("mid-range",           3.00,  3.375,   3.375, False),
    ("low-boundary C=1",    1.00,  8.125,   8.125, False),
    ("clamp-active C=5",    5.00, -1.375,   _A_MIN, True),   # raw < 0.5, clamp to A_MIN
    ("default-profile",     1.40,  7.175,   7.175, False),
]


@pytest.mark.parametrize("label,c,expected_raw,expected_final,should_clamp", _CANONICAL_CASES)
def test_backend_matches_frontend_formula(
    label: str, c: float, expected_raw: float, expected_final: float, should_clamp: bool
) -> None:
    """Backend's compute_a_score must agree with the frontend formula exactly."""
    # Re-derive raw the same way the frontend pure function does:
    #   raw = 10.5 − 2.375 · C
    # then clamp into [A_MIN, A_MAX].
    raw = 10.5 - 2.375 * c
    assert abs(raw - expected_raw) < 1e-9, (
        f"{label}: raw mismatch. Formula gives {raw!r}, spec says {expected_raw!r}"
    )

    clamp_fired = raw < _A_MIN or raw > _A_MAX
    assert clamp_fired == should_clamp, (
        f"{label}: clamp-active flag mismatch. Got {clamp_fired}, expected {should_clamp}"
    )

    # Now the real contract — backend scoring.py must produce the same final.
    backend_a = compute_a_score(c)
    assert abs(backend_a - expected_final) < 1e-9, (
        f"{label}: backend compute_a_score({c}) = {backend_a!r}, "
        f"spec says {expected_final!r}. The frontend card would show the "
        "wrong number; fix either scoring.py or aMappingMath.ts so they agree."
    )


def test_backend_slope_intercept_match_frontend_constants() -> None:
    """
    The frontend exports A_SLOPE=2.375 and A_INTERCEPT=10.5 as named
    constants in aMappingMath.ts. If someone changes either side of the
    pair without the other, the computation drifts silently. Pin both
    values here; if either is intentionally changed, this test must be
    updated in the same commit as the frontend constants.
    """
    # compute_a_score validates C ∈ [1, 5], so derive slope and intercept
    # from three interior points where clamping is known not to fire.
    a_at_one = compute_a_score(1.0)    # => 8.125
    a_at_two = compute_a_score(2.0)    # => 5.750
    a_at_three = compute_a_score(3.0)  # => 3.375
    # Slope between adjacent interior points.
    slope = a_at_two - a_at_three
    assert abs(slope - 2.375) < 1e-9, (
        f"Backend effective slope is {slope!r}, frontend constant is 2.375"
    )
    # Intercept from A(1) = intercept − 1 · slope, so intercept = A(1) + slope.
    intercept = a_at_one + slope
    assert abs(intercept - 10.5) < 1e-9, (
        f"Backend effective intercept is {intercept!r}, frontend constant is 10.5"
    )
