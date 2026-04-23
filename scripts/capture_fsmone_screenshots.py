"""
Capture the two verification screenshots required by the FSMOne remap PR:

  1. Landing page Fund Universe section — shows the 10 FSMOne fund names as
     primary labels with ``proxy: TICKER`` secondary labels and asset-class
     badges. Methodology tooltip visible at the bottom of the section.
  2. Portfolio Allocation page — table shows FSMOne fund names with
     ``proxy: TICKER`` beneath each row.

The portfolio shot uses the same stubbed-chat trick as
``capture_chart_screenshots.py`` to skip the real chatbot flow (no OpenAI
key required), defaulting to A=3.5 so the non-zero allocation rows are
populated.

Outputs under ``reports/screenshots/``.
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


def _terminal_chat_payload(session_id: str, A: float = 3.5) -> dict:
    """Minimal /chat/assess terminal response at a moderate profile."""
    scores = {
        "horizon": 3, "drawdown": 3, "loss_reaction": 3,
        "income_stability": 3, "experience": 3,
    }
    return {
        "session_id": session_id,
        "assistant_message": "Terminal — Moderate profile.",
        "updated_state": {"dimension_scores": scores, "pending_dimension": None},
        "is_terminal": True,
        "risk_profile": {
            "risk_aversion_coefficient": A,
            "profile_label": "Moderate",
            "dimension_scores": scores,
        },
    }


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1200})

        # -------- Shot 1: Landing page Fund Universe ----------------------
        print("[1/2] Landing page / Fund Universe section")
        page = context.new_page()
        page.goto(f"{BASE}/", wait_until="networkidle")
        # Scroll the Fund Universe heading into view
        page.locator("h2", has_text="Fund Universe").scroll_into_view_if_needed()
        time.sleep(1.0)
        out1 = _OUT / "fsmone_fund_universe.png"
        page.screenshot(path=str(out1), full_page=True)
        print(f"  wrote {out1.relative_to(_ROOT)} ({out1.stat().st_size:,} bytes)")

        # -------- Shot 2: Portfolio Allocation with FSMOne + proxy --------
        print("[2/2] Portfolio Allocation page")
        p2 = context.new_page()
        session_id = str(uuid.uuid4())

        def handle_chat(route: Route) -> None:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(_terminal_chat_payload(session_id, A=3.5)),
            )

        p2.route("**/api/v1/chat/assess", handle_chat)

        p2.goto(f"{BASE}/assess", wait_until="networkidle")
        p2.wait_for_selector('input[type="text"]', timeout=10_000)
        p2.locator('input[type="text"]').fill("Moderate")
        p2.keyboard.press("Enter")
        time.sleep(1.5)

        # Client-side navigate to /portfolio (full page.goto would lose the
        # Zustand-backed risk profile — same trap as the A=0.5 shot).
        p2.locator('a[href="/portfolio"]').click()
        p2.wait_for_url("**/portfolio", timeout=10_000)
        # Wait for the loading spinner to disappear, then for the real
        # content (Fund Breakdown heading only renders post-load).
        p2.wait_for_selector(
            "text=Loading portfolio", state="detached", timeout=30_000,
        )
        p2.wait_for_selector("text=Fund Breakdown", timeout=15_000)
        # Pie + table animations settle
        time.sleep(3.0)

        out2 = _OUT / "fsmone_portfolio_allocation.png"
        p2.screenshot(path=str(out2), full_page=True)
        print(f"  wrote {out2.relative_to(_ROOT)} ({out2.stat().st_size:,} bytes)")

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
