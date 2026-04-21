"""
Integration tests for the Step 3 additions to POST /api/v1/optimize.

Asserts:
  1. All new fields are present in the response at default inputs.
  2. gmvp_short_allowed has at least one weight < -0.001 (shorts engaged).
  3. tangency.sharpe_ratio ≥ max(long-only frontier.sharpe_ratio) - 1e-4.
  4. tangency_short_allowed.sharpe_ratio ≥ tangency.sharpe_ratio - 1e-6.
  5. efficient_frontier_short_allowed has exactly 100 points.
  6. equal_weight.weights == [0.1] * 10 exactly.
  7. solver_path is populated on both tangency entries; null on any
     portfolio that does not carry this distinction.
"""

from __future__ import annotations

from pathlib import Path

import pytest


_DATA_PRESENT = (
    Path(__file__).resolve().parent.parent / "data" / "processed" / "mu_vector.json"
).exists()


_REQUEST_BODY = {
    "risk_aversion_coefficient": 3.5,
    "constraints": {
        "allow_short_selling": False,
        "max_single_weight": 0.4,
    },
}


@pytest.fixture
async def optimize_response(client) -> dict:
    response = await client.post("/api/v1/optimize", json=_REQUEST_BODY)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
class TestStep3NewFields:
    # 1. All new fields present
    async def test_new_fields_are_present(self, optimize_response):
        for field in (
            "gmvp_short_allowed",
            "tangency",
            "tangency_short_allowed",
            "efficient_frontier_short_allowed",
            "equal_weight",
        ):
            assert field in optimize_response, f"missing top-level field: {field}"

    # 2. gmvp_short_allowed has meaningful shorts
    async def test_gmvp_short_allowed_has_shorts(self, optimize_response):
        weights = optimize_response["gmvp_short_allowed"]["weights"]
        assert any(w < -0.001 for w in weights), (
            f"expected at least one short (< -0.001) in gmvp_short_allowed; "
            f"got weights = {weights}"
        )

    # 3. Long-only tangency dominates the long-only frontier
    async def test_tangency_dominates_long_only_frontier(self, optimize_response):
        tan_sharpe = optimize_response["tangency"]["sharpe_ratio"]
        max_frontier_sharpe = max(
            p["sharpe_ratio"] for p in optimize_response["efficient_frontier"]
        )
        assert tan_sharpe >= max_frontier_sharpe - 1e-4, (
            f"tangency Sharpe {tan_sharpe:.6f} is below the best "
            f"long-only frontier sample Sharpe {max_frontier_sharpe:.6f}"
        )

    # 4. Short-allowed tangency weakly dominates long-only tangency
    async def test_short_allowed_tangency_weakly_dominates(self, optimize_response):
        s_long = optimize_response["tangency"]["sharpe_ratio"]
        s_short = optimize_response["tangency_short_allowed"]["sharpe_ratio"]
        assert s_short >= s_long - 1e-6, (
            f"short-allowed tangency Sharpe {s_short:.6f} below "
            f"long-only tangency Sharpe {s_long:.6f} — relaxing "
            "constraints should never reduce the max Sharpe"
        )

    # 5. Short-allowed frontier has exactly 100 points
    async def test_short_allowed_frontier_has_100_points(self, optimize_response):
        pts = optimize_response["efficient_frontier_short_allowed"]
        assert len(pts) == 100, f"expected 100 points, got {len(pts)}"
        for i, p in enumerate(pts):
            for field in ("expected_return", "volatility", "sharpe_ratio", "weights"):
                assert field in p, (
                    f"short-allowed frontier[{i}] missing field {field!r}"
                )
            assert len(p["weights"]) == 10

    # 6. equal_weight weights are exactly 0.1 each
    async def test_equal_weight_weights_are_uniform(self, optimize_response):
        weights = optimize_response["equal_weight"]["weights"]
        assert len(weights) == 10
        for i, w in enumerate(weights):
            assert w == 0.1, f"equal_weight.weights[{i}] = {w!r}, expected 0.1"

    # 7. solver_path populated on tangency entries, null elsewhere
    async def test_solver_path_populated_on_tangency_entries(self, optimize_response):
        for key in ("tangency", "tangency_short_allowed"):
            sp = optimize_response[key].get("solver_path")
            assert sp in ("primary", "fallback"), (
                f"{key}.solver_path = {sp!r}; expected 'primary' or 'fallback'"
            )

    async def test_solver_path_absent_or_null_on_non_tangency_portfolios(
        self, optimize_response
    ):
        # PortfolioStats (not TangencyPortfolioStats) should not carry
        # solver_path at all, or serialise it as null.
        for key in ("gmvp", "gmvp_short_allowed", "equal_weight", "optimal_portfolio"):
            sp = optimize_response[key].get("solver_path")
            assert sp is None, (
                f"{key} unexpectedly has solver_path = {sp!r}; expected None"
            )
