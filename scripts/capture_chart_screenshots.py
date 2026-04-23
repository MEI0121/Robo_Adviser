"""
Capture Step 4 verification screenshots of the Efficient Frontier chart.

Shot 1 — Default state (A=3.5): direct navigation to /frontier with an
         empty Zustand store. Fallback A=3.5 kicks in; Optimal coincides
         with long-only Tangency on this dataset under max_weight=0.4.

Shot 2 — Aggressive near-tangency (A=0.5): visits /assess, sends one
         trivial message, and stubs the backend's /api/v1/chat/assess
         response to return is_terminal=true with a full Aggressive
         risk profile (A=0.5). No backend key required; no frontend
         code modified. The page's real state-update path
         (setRiskProfile → Zustand → /frontier useEffect → /optimize
         refetch) runs as in production.

Outputs under reports/screenshots/.
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

FRONTIER_URL = "http://localhost:3000/frontier"
ASSESS_URL = "http://localhost:3000/assess"
CHART_SELECTOR = ".js-plotly-plot"


def _capture(page, filename: str) -> Path:
    path = _OUT / filename
    page.wait_for_selector(CHART_SELECTOR, timeout=20_000)
    # Plotly lays out async after data arrives
    time.sleep(3.5)
    page.screenshot(path=str(path), full_page=True)
    print(f"  wrote {path.relative_to(_ROOT)}  ({path.stat().st_size:,} bytes)")
    return path


def _aggressive_terminal_response(session_id: str) -> dict:
    """
    Minimal well-formed terminal /chat/assess payload for an Aggressive
    investor (A = 0.5, all dimension scores = 5). Matches the schema
    consumed by frontend/app/assess/page.tsx (is_terminal=true branch).
    """
    return {
        "session_id": session_id,
        "assistant_message": (
            "Thanks — based on your answers you look like an Aggressive "
            "investor. Head to the Efficient Frontier page to see your "
            "portfolio."
        ),
        "updated_state": {
            "dimension_scores": {
                "horizon": 5,
                "drawdown": 5,
                "loss_reaction": 5,
                "income_stability": 5,
                "experience": 5,
            },
            "pending_dimension": None,
        },
        "is_terminal": True,
        "risk_profile": {
            "risk_aversion_coefficient": 0.5,
            "profile_label": "Aggressive",
            "dimension_scores": {
                "horizon": 5,
                "drawdown": 5,
                "loss_reaction": 5,
                "income_stability": 5,
                "experience": 5,
            },
        },
    }


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # -------- Shot 1: default A=3.5 --------
        print("[1/2] Default state (A = 3.5, max_weight = 0.4)")
        page.goto(FRONTIER_URL, wait_until="networkidle")
        _capture(page, "frontier_default_A3.5.png")

        # -------- Shot 2: Aggressive A=0.5 --------
        print("[2/2] Aggressive state (A = 0.5) via route-stubbed chat flow")
        fresh = context.new_page()

        session_id = str(uuid.uuid4())

        def handle_chat(route: Route) -> None:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(_aggressive_terminal_response(session_id)),
            )

        # Intercept both the proxied dev-mode path and an absolute URL fallback.
        fresh.route("**/api/v1/chat/assess", handle_chat)

        fresh.goto(ASSESS_URL, wait_until="networkidle")

        # Type any text and press Enter to fire the POST /api/v1/chat/assess.
        # The textarea is the primary input on /assess; the button or Enter
        # will submit.
        fresh.wait_for_selector('input[type="text"]', timeout=10_000)
        fresh.locator('input[type="text"]').fill("Aggressive")
        fresh.keyboard.press("Enter")

        # Wait for setRiskProfile to settle — the is_terminal branch writes
        # the Zustand store synchronously after the POST resolves.
        time.sleep(1.5)

        # Navigate CLIENT-SIDE (Next.js Link) to preserve the in-memory
        # Zustand store. A full `page.goto(...)` reload would lose it.
        # The navbar has <Link href="/frontier">Efficient Frontier</Link>.
        fresh.locator('a[href="/frontier"]').click()
        fresh.wait_for_url("**/frontier", timeout=10_000)
        _capture(fresh, "frontier_aggressive_A0.5.png")

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
