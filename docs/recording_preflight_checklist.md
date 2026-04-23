# Recording Pre-Flight Checklist

Run through this 2-minute check immediately before hitting record. Every item must be green; stop and fix if anything fails. The video script is in [`docs/video_script_15min.md`](video_script_15min.md).

---

## 1. Backend server starts and responds (30 s)

```bash
cd backend
./.venv/Scripts/uvicorn.exe main:app --reload --port 8000
# (or: uvicorn main:app --reload --port 8000 on Linux/macOS)
```

In a second terminal:

```bash
curl -s http://localhost:8000/api/v1/funds | python -m json.tool | head -30
```

**Expect:** JSON array of 10 fund entries, each with `fund_code`, `fund_name`, `proxy_ticker`, `asset_class`. If you see fewer than 10 or the request 404s, the backend did not start cleanly — read the uvicorn logs.

## 2. Frontend dev server starts and renders (30 s)

```bash
cd frontend
npm run dev
```

Browse to `http://localhost:3000`.

**Expect:** Landing page renders with a Fund Universe section showing 10 FSMOne fund names (not ETF tickers). If you see tickers like `SPY`/`QQQ`/`BNDX` as the primary labels, the FSMOne display layer did not activate — verify the frontend fetched `/api/v1/funds` and is keyed on `fund_name`, not `proxy_ticker`.

## 3. `/profile` page shows canonical values (30 s)

Browse to `http://localhost:3000/profile`.

**Expect:**
- **Risk Aversion Score: 7.17** prominently displayed
- Profile label **Moderately Conservative**
- Five dimension cards (horizon, drawdown, loss reaction, income stability, experience) each with an integer score 1–5
- Composite score **C = 1.40** visible
- A-mapping formula card with `A = clamp(10.5 - 2.375·C, 0.5, 10.0)` and the worked calculation: **C = 1.40 → raw A = 7.175 → clamped A = 7.17**

**If any of this is missing:** the chat stepper has not been run yet for this session. Options to populate:
- Run the chat assessment once end-to-end with conservative-leaning answers that produce C = 1.40 (horizon=1, drawdown=1, loss_reaction=2, income_stability=1, experience=2 averages to 1.4). This requires a working OpenAI key in `.env` as `OPENAI_API_KEY=sk-...`.
- Or inject the canonical state via localStorage before the `/profile` route mounts. The pattern used by `tests/e2e/` helper scripts can seed the `riskProfile` key directly.

## 4. `/frontier` page renders correctly (20 s)

Browse to `http://localhost:3000/frontier` (or click **Proceed to portfolio** from `/profile`).

**Expect:**
- Both frontier curves visible (long-only solid, short-allowed dashed)
- 10 individual fund scatter dots annotated with fund names
- Dashed CML line extending from the y-axis through the tangency marker
- Tangency, GMVP, Optimal, and Equal-weight markers each labeled
- **No red "1 error" HMR badge in the bottom corner**

**If HMR error badge is visible:** kill the dev server and switch to a production build:

```bash
npm run build && npm run start
# then browse to http://localhost:3000/frontier
```

Production build does not display HMR badges.

## 5. Excel workbook accessible (10 s)

Open `A13_BMD5302_Robo.xlsm` on a second monitor or in an alt-tab–accessible window.

**Expect:**
- Workbook opens without a macro-disabled warning (enable macros if prompted)
- Default sheet view is `Frontier` (so the Segment 2 cutaway lands on a populated curve, not a blank intro sheet)
- Sheet tab bar visible across the bottom: `NAV_Data`, `Log_Returns`, `Cov_Matrix`, `GMVP`, `Frontier`, `Frontier_Short`, `Optimal`, `Tangency`

---

## Quick troubleshooting

| Symptom | Likely cause | Quick fix |
|---|---|---|
| `/funds` returns empty array | Market data not loaded | Check `data/processed/mu_vector.json` exists; re-run `python scripts/download_yfinance_data.py` if missing |
| `/optimize` 500s | Backend cache cold | Hit `/funds` first, then retry `/optimize` |
| Chatbot 401s during live demo | OpenAI key missing or wrong | **Script now bypasses live chatbot** — narrate over `/profile` instead (see Segment 3). If you must demo chatbot live, ensure `.env` has `OPENAI_API_KEY=sk-...` (not a Gemini key) |
| Chart shows only long-only frontier | Frontend ran an old cached bundle | Hard refresh (Ctrl+Shift+R) or restart `npm run dev` |
| Reconciliation report shows old counts | `reconcile.py` cached or not re-run | `backend/.venv/Scripts/python.exe reconcile.py` to regenerate `reports/reconciliation_report.{md,json,pdf}` |

---

## Last-minute housekeeping

- Close Slack, Discord, notification centers — no popups during recording
- Silence phone
- Browser zoom 100% (Ctrl+0 if unsure); close all tabs except the three demo tabs (`/profile`, `/frontier`, reconciliation report)
- DevTools closed unless the script's Network-tab cue calls for it (Segment 4)
- Screen recorder configured to capture the primary monitor at 1080p minimum

When all five numbered checks above are green: you are clear to record.
