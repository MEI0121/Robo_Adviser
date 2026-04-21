"""
Regression test: the default /optimize response must remain byte-stable.

Before adding the short-sale / tangency / new-artifact work, we capture a
fixture of the /optimize response at the canonical default inputs
(A=7.17, max_weight=0.4) into tests/fixtures/optimize_baseline_response.json.

This test re-runs /optimize with the same inputs and asserts that the
pre-existing numeric fields — in particular optimal_portfolio.weights and
gmvp.weights — still match the baseline within 1e-10.

NEW fields appearing in the response are allowed (the upcoming work adds
tangency, short-allowed GMVP, short-allowed frontier, equal_weight). Any
CHANGE to an existing field value is a test failure.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "optimize_baseline_response.json"
)

_TOL = 1e-10

_REQUEST_BODY = {
    "risk_aversion_coefficient": 7.17,
    "constraints": {
        "allow_short_selling": False,
        "max_single_weight": 0.4,
    },
}

_DATA_PRESENT = (
    Path(__file__).resolve().parent.parent / "data" / "processed" / "mu_vector.json"
).exists()


def _load_baseline() -> dict:
    if not _FIXTURE_PATH.exists():
        pytest.skip(
            f"Baseline fixture missing at {_FIXTURE_PATH}. Regenerate with:\n"
            '  curl -X POST http://127.0.0.1:8000/api/v1/optimize '
            '-H "Content-Type: application/json" '
            "-d '" + json.dumps(_REQUEST_BODY) + "' "
            f"> {_FIXTURE_PATH.name}"
        )
    with open(_FIXTURE_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _assert_scalar_close(actual: float, expected: float, label: str) -> None:
    assert abs(actual - expected) <= _TOL, (
        f"{label}: drifted beyond tolerance.\n"
        f"  baseline = {expected!r}\n"
        f"  current  = {actual!r}\n"
        f"  |delta|  = {abs(actual - expected):.3e}  (tol = {_TOL:.0e})"
    )


def _assert_vector_close(
    actual: list[float], expected: list[float], label: str
) -> None:
    assert len(actual) == len(expected), (
        f"{label}: length changed {len(expected)} → {len(actual)}"
    )
    for i, (a, e) in enumerate(zip(actual, expected)):
        assert abs(a - e) <= _TOL, (
            f"{label}[{i}]: drifted beyond tolerance.\n"
            f"  baseline = {e!r}\n"
            f"  current  = {a!r}\n"
            f"  |delta|  = {abs(a - e):.3e}  (tol = {_TOL:.0e})"
        )


@pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
async def test_optimize_default_response_matches_baseline(client) -> None:
    """
    Re-run /optimize at the canonical defaults and assert every scalar /
    vector that was present in the baseline still matches within 1e-10.

    New fields in the live response are tolerated. Existing fields changing
    value is a regression — fails with a precise diff message.
    """
    baseline = _load_baseline()

    response = await client.post("/api/v1/optimize", json=_REQUEST_BODY)
    assert response.status_code == 200, response.text
    current = response.json()

    # --- Optimal portfolio weights (the headline assertion) -----------------
    _assert_vector_close(
        current["optimal_portfolio"]["weights"],
        baseline["optimal_portfolio"]["weights"],
        "optimal_portfolio.weights",
    )

    # --- GMVP weights -------------------------------------------------------
    _assert_vector_close(
        current["gmvp"]["weights"],
        baseline["gmvp"]["weights"],
        "gmvp.weights",
    )

    # --- Scalar stats on both portfolios ------------------------------------
    for field in ("expected_annual_return", "annual_volatility", "sharpe_ratio"):
        _assert_scalar_close(
            current["optimal_portfolio"][field],
            baseline["optimal_portfolio"][field],
            f"optimal_portfolio.{field}",
        )
        _assert_scalar_close(
            current["gmvp"][field],
            baseline["gmvp"][field],
            f"gmvp.{field}",
        )

    _assert_scalar_close(
        current["optimal_portfolio"]["utility_score"],
        baseline["optimal_portfolio"]["utility_score"],
        "optimal_portfolio.utility_score",
    )

    # --- Efficient frontier (100 × {er, vol, sharpe, weights}) --------------
    assert len(current["efficient_frontier"]) == len(baseline["efficient_frontier"]), (
        "efficient_frontier: point count changed "
        f"{len(baseline['efficient_frontier'])} → {len(current['efficient_frontier'])}"
    )
    for i, (cur_pt, base_pt) in enumerate(
        zip(current["efficient_frontier"], baseline["efficient_frontier"])
    ):
        for field in ("expected_return", "volatility", "sharpe_ratio"):
            _assert_scalar_close(
                cur_pt[field], base_pt[field], f"efficient_frontier[{i}].{field}"
            )
        _assert_vector_close(
            cur_pt["weights"],
            base_pt["weights"],
            f"efficient_frontier[{i}].weights",
        )

    # --- Metadata — only the invariants (timing is ignored) -----------------
    for field in (
        "risk_aversion_coefficient",
        "risk_free_rate",
        "num_assets",
        "data_start_date",
        "data_end_date",
        "optimization_method",
    ):
        assert current["metadata"][field] == baseline["metadata"][field], (
            f"metadata.{field}: {baseline['metadata'][field]!r} → "
            f"{current['metadata'][field]!r}"
        )
