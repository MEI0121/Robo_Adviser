"""
Capture a Step 4 verification screenshot of the Efficient Frontier chart.

The default /frontier page loads with A = 3.5 (fallback when no risk profile
is set). Captures that state to reports/screenshots/.

The near-tangency screenshot (A ≈ 0.5) requires a completed chat flow to
set the Zustand store — it's not driven by URL query params. Run the
chatbot manually (Aggressive profile) and screenshot yourself, or
extend this script once the store is exposed to ``window`` in dev mode.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "reports" / "screenshots"
_OUT.mkdir(parents=True, exist_ok=True)

FRONTEND_URL = "http://localhost:3000/frontier"
CHART_SELECTOR = ".js-plotly-plot"


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto(FRONTEND_URL, wait_until="networkidle")
        page.wait_for_selector(CHART_SELECTOR, timeout=20_000)
        # Plotly lays out async after the data prop arrives; wait a beat
        time.sleep(3.5)

        out = _OUT / "frontier_default_A3.5.png"
        page.screenshot(path=str(out), full_page=True)
        print(f"wrote {out.relative_to(_ROOT)} ({out.stat().st_size:,} bytes)")

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
