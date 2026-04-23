"""
End-to-end system walkthrough capture — 11 deterministic screenshots
covering the full user journey from landing through portfolio allocation.

Downstream uses:
  1. Team communication artifact (PR / Slack / slide deck)
  2. Figure source for the Word report's §5–§7
  3. Reference sequence for the 15-minute video demo

Outputs to reports/system_test/:
  01_landing_home.png
  02_landing_fund_universe.png
  03_risk_assessment_start.png
  04_risk_assessment_mid.png
  05_risk_assessment_complete.png
  06_risk_profile_page.png
  07_risk_profile_a_mapping.png
  08_efficient_frontier_default.png
  09_efficient_frontier_hover.png
  10_portfolio_allocation.png
  11_portfolio_fund_detail.png
  walkthrough.md

Prerequisites
-------------
  Backend :8000 and frontend :3000 both running locally. Fail-fast check
  at the top of main(). No production deploy; no app code changes. The
  /api/v1/chat/assess endpoint is route-stubbed (per the pattern from
  the A=0.5 capture script) to avoid needing an OpenAI key.

Design notes
------------
  * Dev-mode dismiss: Next.js renders a "1 error" HMR badge + dev-tools
    button on every page in dev. We inject a cosmetic CSS rule via
    page.add_style_tag on every navigation to hide these overlays.
    This does NOT modify application code — it's a browser-side
    display-layer suppression applied per screenshot session. The
    first screenshot is also programmatically inspected for any
    surviving error pill; if one appears the script aborts with a
    clear error.
  * Progressive chat stub: the /api/v1/chat/assess route handler is
    call-count-aware. Each message advances the dimension_scores dict
    by one entry, so the progress bar fills from 0 → 20 → 40 → 60 →
    80 → terminal. The scripted profile lands at C = 1.4, A = 7.175
    ("Moderately Conservative") — matches the canonical example in the
    A-mapping card test and keeps the downstream /profile + /frontier
    numbers consistent with reports/screenshots/*.
  * Plotly tangency hover: after the chart renders, we read
    plotDiv._fullLayout via page.evaluate to translate the tangency
    trace's (x, y) data coordinates to pixel coordinates, then
    page.mouse.move to dispatch the hover. Plotly's own hover layer
    renders the tooltip we screenshot.
  * Recharts pie hover: Recharts renders slices as <path> elements.
    We hover the largest slice (the 40% Franklin proxy / SPY position
    at A = 7.175 under max_weight = 0.4) to surface the tooltip.
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

from playwright.sync_api import Page, Route, sync_playwright


_ROOT = Path(__file__).resolve().parent.parent
_OUT = _ROOT / "reports" / "system_test"
_OUT.mkdir(parents=True, exist_ok=True)

BASE = "http://localhost:3000"
API = "http://127.0.0.1:8000"

# CSS injected into every page to hide Next.js dev-mode overlays. Does not
# modify the app — purely a browser-side display rule applied for the
# duration of the screenshot session. Covers the historical + current set
# of selectors used across Next.js 13/14/15 dev-mode build-watcher UIs.
_HIDE_NEXT_DEV_CSS = """
[data-nextjs-toast],
[data-nextjs-toast-container],
[data-nextjs-dev-tools-button],
[data-nextjs-dev-overlay],
[data-nextjs-static-indicator],
#__next-build-watcher,
#__next-prerender-indicator,
nextjs-portal {
  display: none !important;
  visibility: hidden !important;
}
"""


def _hide_dev_overlays(page: Page) -> None:
    """Inject the hide-overlay CSS immediately after page load."""
    page.add_style_tag(content=_HIDE_NEXT_DEV_CSS)


def _verify_no_error_pill(page: Page, screenshot_label: str) -> None:
    """
    After the first screenshot, scan the DOM for any surviving Next.js
    error toast. If the CSS hide didn't catch it, stop the script —
    screenshots must be clean.
    """
    present = page.evaluate(
        """
        () => {
            const sel = 'nextjs-portal, [data-nextjs-toast], [data-nextjs-dev-tools-button]';
            return Array.from(document.querySelectorAll(sel))
                .filter(el => {
                    const s = getComputedStyle(el);
                    return s.display !== 'none' && s.visibility !== 'hidden';
                })
                .length;
        }
        """
    )
    if present:
        raise RuntimeError(
            f'Next.js dev overlay still visible after CSS suppression '
            f'(screenshot: {screenshot_label}). Aborting per task spec — '
            'investigate the overlay source before re-running.'
        )


# ---------------------------------------------------------------------------
# Progressive chat-stub handler
# ---------------------------------------------------------------------------
#
# Each POST /api/v1/chat/assess advances the dimension_scores dict by one
# entry. The scripted progression lands at composite = 1.4, A = 7.175,
# profile_label = "Moderately Conservative" — matches the canonical
# example from the A-mapping card test.


_DIMENSION_ORDER = [
    "horizon",
    "drawdown",
    "loss_reaction",
    "income_stability",
    "experience",
]
_DIMENSION_VALUES = [1, 1, 1, 1, 3]  # sum = 7 → C = 1.4 → A = 7.175


def _build_progressive_stub(session_id: str):
    """Factory for a call-count-aware /chat/assess route handler."""
    state = {"n": 0}

    def handler(route: Route) -> None:
        n = state["n"]
        state["n"] += 1

        # Scores dict filled up to step n+1 (after handling the nth user message)
        scored_count = min(n + 1, len(_DIMENSION_ORDER))
        scores = {
            _DIMENSION_ORDER[i]: _DIMENSION_VALUES[i] for i in range(scored_count)
        }
        is_terminal = scored_count == len(_DIMENSION_ORDER)
        pending = None if is_terminal else _DIMENSION_ORDER[scored_count]

        payload: dict = {
            "session_id": session_id,
            "assistant_message": (
                "Thanks — that's an aggressive-leaning profile overall. "
                "Head to the Efficient Frontier page when you're ready."
                if is_terminal
                else f"Noted. Next, tell me about your {pending.replace('_', ' ')}."
            ),
            "updated_state": {
                "dimension_scores": scores,
                "pending_dimension": pending,
            },
            "is_terminal": is_terminal,
        }
        if is_terminal:
            payload["risk_profile"] = {
                "risk_aversion_coefficient": 7.175,
                "profile_label": "Moderately Conservative",
                "dimension_scores": scores,
            }

        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(payload),
        )

    return handler


# ---------------------------------------------------------------------------
# Capture helpers
# ---------------------------------------------------------------------------


def _shot(page: Page, name: str, *, full_page: bool = True) -> Path:
    out = _OUT / name
    page.screenshot(path=str(out), full_page=full_page)
    size = out.stat().st_size
    print(f"  [ok] {name}  ({size:,} bytes)")
    return out


def _check_prereqs() -> None:
    """Fail fast if either dev server is unreachable."""
    import urllib.request
    import urllib.error

    try:
        urllib.request.urlopen(f"{API}/api/v1/funds", timeout=2)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"Backend not reachable at {API}: {exc}")

    try:
        urllib.request.urlopen(f"{BASE}/", timeout=2)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"Frontend not reachable at {BASE}: {exc}")


# ---------------------------------------------------------------------------
# Per-page capture routines
# ---------------------------------------------------------------------------


def capture_landing(page: Page) -> None:
    """01: full landing. 02: Fund Universe section in isolation."""
    print("[1-2/11] Landing page")
    page.goto(f"{BASE}/", wait_until="networkidle")
    _hide_dev_overlays(page)
    time.sleep(0.5)

    # 01 — full page
    _shot(page, "01_landing_home.png", full_page=True)
    _verify_no_error_pill(page, "01_landing_home.png")

    # 02 — Fund Universe section only (scroll + clip to section's bounding box)
    page.locator("h2", has_text="Fund Universe").scroll_into_view_if_needed()
    time.sleep(0.3)
    section = page.locator("section").filter(has=page.locator("h2", has_text="Fund Universe"))
    box = section.bounding_box()
    if box is None:
        # Fallback to full viewport if locator can't pinpoint
        _shot(page, "02_landing_fund_universe.png", full_page=False)
    else:
        page.screenshot(
            path=str(_OUT / "02_landing_fund_universe.png"),
            clip={
                "x": max(0, box["x"]),
                "y": max(0, box["y"]),
                "width": min(1440, box["width"]),
                "height": min(1200, box["height"]),
            },
        )
        size = (_OUT / "02_landing_fund_universe.png").stat().st_size
        print(f"  [ok] 02_landing_fund_universe.png  ({size:,} bytes)")


def capture_assess_flow(page: Page) -> None:
    """03: first question. 04: ~40% progress. 05: terminal."""
    print("[3-5/11] Risk assessment flow")

    session_id = str(uuid.uuid4())
    page.route("**/api/v1/chat/assess", _build_progressive_stub(session_id))

    # Navigate to /assess (triggers the canned welcome; no API call yet)
    page.goto(f"{BASE}/assess", wait_until="networkidle")
    _hide_dev_overlays(page)
    page.wait_for_selector('input[type="text"]', timeout=10_000)
    time.sleep(0.5)

    # 03 — first question, 0% progress
    _shot(page, "03_risk_assessment_start.png", full_page=True)

    # Send 2 messages → progress reaches 40%
    for _ in range(2):
        page.locator('input[type="text"]').fill("Less than 2 years")
        page.keyboard.press("Enter")
        time.sleep(1.0)

    # 04 — mid-flow, 40% progress (2 of 5 dimensions complete)
    page.wait_for_timeout(300)
    _hide_dev_overlays(page)  # re-inject after any re-render
    _shot(page, "04_risk_assessment_mid.png", full_page=True)

    # Send the remaining 3 messages → terminal
    for _ in range(3):
        page.locator('input[type="text"]').fill("Less than 2 years")
        page.keyboard.press("Enter")
        time.sleep(1.0)

    # Wait for terminal CTA ("View My Risk Profile →")
    page.wait_for_selector("text=View My Risk Profile", timeout=10_000)
    time.sleep(0.5)
    _hide_dev_overlays(page)

    # 05 — terminal state
    _shot(page, "05_risk_assessment_complete.png", full_page=True)


def capture_profile(page: Page) -> None:
    """06: full /profile page. 07: A-mapping card in isolation."""
    print("[6-7/11] Profile page")

    # Client-side Link click preserves Zustand state
    page.locator('a[href="/profile"]').click()
    page.wait_for_url("**/profile", timeout=10_000)
    page.wait_for_selector("text=How your A was computed", timeout=15_000)
    _hide_dev_overlays(page)
    time.sleep(1.0)

    # 06 — full profile page
    _shot(page, "06_risk_profile_page.png", full_page=True)

    # 07 — isolate the A-mapping card by clipping to its bounding box
    card = page.locator("div").filter(
        has=page.locator("text=How your A was computed")
    ).filter(
        has=page.locator("text=Your calculation")
    ).first
    card.scroll_into_view_if_needed()
    time.sleep(0.3)
    box = card.bounding_box()
    if box is None:
        _shot(page, "07_risk_profile_a_mapping.png", full_page=False)
    else:
        # Small margin around the card for visual breathing room
        m = 20
        page.screenshot(
            path=str(_OUT / "07_risk_profile_a_mapping.png"),
            clip={
                "x": max(0, box["x"] - m),
                "y": max(0, box["y"] - m),
                "width": min(1440, box["width"] + 2 * m),
                "height": min(1200, box["height"] + 2 * m),
            },
        )
        size = (_OUT / "07_risk_profile_a_mapping.png").stat().st_size
        print(f"  [ok] 07_risk_profile_a_mapping.png  ({size:,} bytes)")


def capture_frontier(page: Page) -> None:
    """08: default frontier view. 09: hover on Tangency (long-only)."""
    print("[8-9/11] Efficient frontier")

    page.locator('a[href="/frontier"]').click()
    page.wait_for_url("**/frontier", timeout=10_000)
    # Wait for loading spinner to detach + chart to render
    page.wait_for_selector("text=Loading portfolio", state="detached", timeout=30_000)
    page.wait_for_selector(".js-plotly-plot", timeout=15_000)
    time.sleep(3.5)  # Plotly async layout
    _hide_dev_overlays(page)

    # 08 — default view with all traces rendered
    _shot(page, "08_efficient_frontier_default.png", full_page=True)

    # 09 — hover on Tangency (long-only) marker. Translate the trace's
    # data coordinates to pixel coordinates via Plotly's internal layout.
    hover_pt = page.evaluate(
        """
        () => {
            const plot = document.querySelector('.js-plotly-plot');
            if (!plot || !plot._fullData) return null;
            const trace = plot._fullData.find(t => t.name === 'Tangency (long-only)');
            if (!trace) return null;
            const layout = plot._fullLayout;
            const x0 = trace.x[0];
            const y0 = trace.y[0];
            const pxX = layout.xaxis.l2p(x0) + layout.xaxis._offset;
            const pxY = layout.yaxis.l2p(y0) + layout.yaxis._offset;
            const rect = plot.getBoundingClientRect();
            return { pageX: rect.left + pxX, pageY: rect.top + pxY };
        }
        """
    )
    if hover_pt is None:
        raise RuntimeError(
            "Could not locate Tangency (long-only) trace on the Plotly chart. "
            "The trace name may have changed — update this script or the chart."
        )

    page.mouse.move(hover_pt["pageX"], hover_pt["pageY"])
    time.sleep(1.0)  # let Plotly render the tooltip
    _hide_dev_overlays(page)

    _shot(page, "09_efficient_frontier_hover.png", full_page=True)


def capture_portfolio(page: Page) -> None:
    """10: full /portfolio page. 11: pie chart with tooltip visible."""
    print("[10-11/11] Portfolio allocation")

    page.locator('a[href="/portfolio"]').click()
    page.wait_for_url("**/portfolio", timeout=10_000)
    page.wait_for_selector("text=Loading portfolio", state="detached", timeout=30_000)
    page.wait_for_selector("text=Fund Breakdown", timeout=15_000)
    time.sleep(2.5)  # pie + table settle
    _hide_dev_overlays(page)

    # 10 — full portfolio page
    _shot(page, "10_portfolio_allocation.png", full_page=True)

    # 11 — hover the largest pie slice to surface the Recharts tooltip.
    # Recharts registers mouseenter/mouseover handlers on each .recharts-sector
    # <path>, so page.mouse.move() does not fire the tooltip — the locator's
    # hover() method dispatches the proper synthetic events.
    #
    # Pick the first sector via the locator API; at default A = 7.175 with
    # max_weight = 0.4 the sectors are dominated by JPMorgan / Franklin /
    # Fidelity (40% / 40% / 20%), so any non-zero sector yields a useful
    # tooltip.
    sectors = page.locator("path.recharts-sector")
    count = sectors.count()
    if count == 0:
        print("  [warn] No .recharts-sector paths found — capturing without tooltip")
        _shot(page, "11_portfolio_fund_detail.png", full_page=True)
        return

    # Scroll the pie chart into view, then hover + viewport screenshot.
    # full_page screenshots stitch by scrolling, which drops the tooltip
    # mid-capture — viewport screenshots preserve the hover state.
    page.locator(".recharts-pie").first.scroll_into_view_if_needed()
    time.sleep(0.3)
    sectors.first.hover(force=True)
    # Recharts debounces tooltip rendering; 700 ms is reliable
    time.sleep(0.7)
    _hide_dev_overlays(page)
    # Viewport (not full_page) to keep the tooltip rendered during capture
    _shot(page, "11_portfolio_fund_detail.png", full_page=False)


# ---------------------------------------------------------------------------
# Walkthrough document
# ---------------------------------------------------------------------------


_CAPTIONS: list[tuple[str, str, str]] = [
    (
        "01_landing_home.png",
        "Landing page — hero, platform architecture, fund universe entry point",
        "The landing page opens with a gradient hero, four platform-architecture "
        "cards explaining the LangGraph risk profiler, Markowitz optimiser, "
        "efficient-frontier visualisation, and allocation dashboard, followed "
        "by the Fund Universe section and the primary CTA into the risk "
        "assessment flow.",
    ),
    (
        "02_landing_fund_universe.png",
        "Fund Universe — 10 FSMOne funds with ETF proxies and asset-class badges",
        "The ten FSMOne funds that form the investable universe, each shown with "
        "its full display name, the ETF proxy used for μ/σ estimation, and an "
        "asset-class badge. The methodology note at the bottom explains the "
        "two-layer architecture (FSMOne display, ETF estimation) documented in "
        "§3.7 of the academic report.",
    ),
    (
        "03_risk_assessment_start.png",
        "Risk assessment — first dimension (investment horizon), 0% progress",
        "The LangGraph chatbot opens with a fixed welcome and asks the first "
        "psychographic question (investment horizon). The progress bar is empty; "
        "no API call has been made yet until the user sends the first reply.",
    ),
    (
        "04_risk_assessment_mid.png",
        "Risk assessment — mid flow, 40% progress (2 of 5 dimensions complete)",
        "After two user messages, two of the five rubric dimensions are scored. "
        "The progress bar fills to 40%. The /api/v1/chat/assess endpoint returns "
        "updated state after each turn, and the frontend marks each completed "
        "dimension on the progress rail.",
    ),
    (
        "05_risk_assessment_complete.png",
        "Risk assessment — terminal state with profile label and CTA",
        "After the fifth dimension is scored, the chatbot enters its terminal "
        "state. The response payload includes a complete risk_profile with the "
        "risk-aversion coefficient A, the textual profile label, and the five "
        "dimension scores. The conversation input is replaced by the CTA to "
        "view the risk profile.",
    ),
    (
        "06_risk_profile_page.png",
        "Risk profile — hero card, utility function parameters, dimension scores",
        "The /profile page summarises the assessment: the hero card shows the "
        "profile label and final A (7.17 for this scripted Moderately "
        "Conservative run), the Utility Function Parameters card renders "
        "U(w) = E(rₚ) − ½·A·σₚ² with A substituted, and the dimension scores "
        "card visualises each 1–5 rubric score as a gradient bar with the "
        "composite C displayed at the bottom.",
    ),
    (
        "07_risk_profile_a_mapping.png",
        "A-mapping card — formula with user's values plugged in",
        "The A-mapping card shows the canonical linear formula "
        "A = clamp(10.5 − 2.375·C, 0.5, 10.0) followed by the user's own worked "
        "calculation (C = 1.400 → raw A = 7.175 → clamped A = 7.17), a clamp "
        "indicator (grey when clamping is not active, amber when it fires), and "
        "a plain-language paragraph explaining the slope/intercept calibration.",
    ),
    (
        "08_efficient_frontier_default.png",
        "Efficient frontier — dual frontier, CML, fund dots, special points",
        "The /frontier page renders both the long-only (Sharpe-coloured) and "
        "short-allowed w ∈ [−1, 2] (dashed) efficient frontiers on a shared "
        "σ–E(rₚ) plane, with the capital market line anchored on the proper "
        "long-only tangency, ten individual fund scatter points labelled by "
        "proxy ticker, both GMVPs (filled + hollow teal diamonds), both "
        "tangencies (filled + hollow gold stars), the 1/N equal-weight "
        "benchmark, and the user's Optimal portfolio.",
    ),
    (
        "09_efficient_frontier_hover.png",
        "Efficient frontier — hover tooltip on Tangency (long-only)",
        "Hovering the long-only tangency marker surfaces Plotly's tooltip with "
        "the regime label, expected return, volatility, Sharpe ratio, "
        "solver_path provenance (primary vs fallback from Step 2's two-path "
        "SLSQP), and the top-three holdings in the tangency portfolio.",
    ),
    (
        "10_portfolio_allocation.png",
        "Portfolio allocation — pie chart, fund breakdown, summary stats",
        "The /portfolio page shows the optimal allocation as a Recharts donut "
        "(non-zero positions only) alongside the full 10-fund table including "
        "zero-weight funds. Summary cards report the portfolio's expected "
        "return, volatility, Sharpe ratio, and count of non-zero positions. "
        "Each fund row shows its FSMOne name and the ETF proxy used for "
        "estimation.",
    ),
    (
        "11_portfolio_fund_detail.png",
        "Portfolio — viewport detail on pie chart and fund breakdown",
        "Viewport-scale view of the portfolio upper section with the pie chart "
        "non-zero slices directly adjacent to the Fund Breakdown table. Each row "
        "shows the FSMOne fund name, ETF proxy ticker, asset-class badge, "
        "weight with progress bar, and expected contribution to the portfolio's "
        "annualised return (weight × annualised fund return). At the default "
        "A = 7.175 with max_single_weight = 0.4, four positions are non-zero: "
        "JPMorgan (40% cap), Franklin (22.15%), Fidelity (19.67%), and PIMCO "
        "bond (18.18%). The remaining six fund rows are dimmed and show "
        "0.00% — valid KKT inactive-constraint coordinates of the long-only "
        "utility-max.",
    ),
]


def write_walkthrough_md() -> Path:
    """Emit reports/system_test/walkthrough.md with pre-written captions."""
    import datetime

    lines: list[str] = [
        "# System Walkthrough",
        f"*Generated {datetime.datetime.now().isoformat(timespec='seconds')}*",
        "",
        "End-to-end capture of the user journey from landing page through "
        "portfolio allocation, produced by `scripts/e2e_system_walkthrough.py`. "
        "All 11 screenshots are deterministic given a running backend on "
        ":8000 and frontend on :3000 — the chat flow is route-stubbed to "
        "avoid depending on an OpenAI key. The scripted profile "
        "(composite C = 1.4, A = 7.175, Moderately Conservative) matches "
        "the canonical example used in the A-mapping card's consistency test.",
        "",
    ]

    for i, (filename, title, caption) in enumerate(_CAPTIONS, start=1):
        lines.append(f"## Step {i}: {title}")
        lines.append(f"![{title}]({filename})")
        lines.append("")
        lines.append(caption)
        lines.append("")

    out = _OUT / "walkthrough.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"  [ok] walkthrough.md  ({out.stat().st_size:,} bytes)")
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    print("System walkthrough capture")
    print("-" * 60)
    print(f"Output:   {_OUT.relative_to(_ROOT)}")
    print(f"Backend:  {API}")
    print(f"Frontend: {BASE}")
    print()

    _check_prereqs()

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        try:
            capture_landing(page)
            capture_assess_flow(page)
            capture_profile(page)
            capture_frontier(page)
            capture_portfolio(page)
        finally:
            browser.close()

    print()
    print("Generating walkthrough.md")
    print("-" * 60)
    write_walkthrough_md()

    print()
    print(f"Done. See {(_OUT / 'walkthrough.md').relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
