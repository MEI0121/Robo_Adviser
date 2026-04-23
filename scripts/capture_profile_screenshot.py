"""
Capture a screenshot of the /profile page with the AMappingCard visible.

Uses the same route-stubbed chat pattern as the other capture scripts to
put a canonical risk profile into the Zustand store without requiring an
OpenAI key. Canonical test case: composite_score = 1.40 → A = 7.175 →
label "Moderately Conservative". This matches the "default-profile"
entry in tests/test_a_mapping_consistency.py.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

from playwright.sync_api import sync_playwright, Route


_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "reports" / "screenshots"
_OUT.mkdir(parents=True, exist_ok=True)

BASE = "http://localhost:3000"


def _terminal_chat_payload(session_id: str) -> dict:
    """
    Terminal /chat/assess response with composite_score = 1.40 (A = 7.175).

    Dimension scores [1, 1, 1, 1, 3] have arithmetic mean 7/5 = 1.4.
    """
    scores = {
        "horizon": 1,
        "drawdown": 1,
        "loss_reaction": 1,
        "income_stability": 1,
        "experience": 3,
    }
    return {
        "session_id": session_id,
        "assistant_message": "Terminal — Moderately Conservative.",
        "updated_state": {"dimension_scores": scores, "pending_dimension": None},
        "is_terminal": True,
        "risk_profile": {
            "risk_aversion_coefficient": 7.175,
            "profile_label": "Moderately Conservative",
            "dimension_scores": scores,
        },
    }


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1600})
        page = context.new_page()

        session_id = str(uuid.uuid4())

        def handle_chat(route: Route) -> None:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(_terminal_chat_payload(session_id)),
            )

        page.route("**/api/v1/chat/assess", handle_chat)

        page.goto(f"{BASE}/assess", wait_until="networkidle")
        page.wait_for_selector('input[type="text"]', timeout=10_000)
        page.locator('input[type="text"]').fill("Conservative")
        page.keyboard.press("Enter")
        time.sleep(1.5)

        # Client-side Link click to preserve the Zustand store.
        page.locator('a[href="/profile"]').click()
        page.wait_for_url("**/profile", timeout=10_000)
        page.wait_for_selector("text=How your A was computed", timeout=10_000)
        time.sleep(1.5)

        out = _OUT / "profile_a_mapping_card.png"
        page.screenshot(path=str(out), full_page=True)
        print(f"wrote {out.relative_to(_ROOT)} ({out.stat().st_size:,} bytes)")

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
