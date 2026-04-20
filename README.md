# Robo-Adviser Platform

A quantitative robo-adviser demo built on **Modern Portfolio Theory (MPT)**. The stack uses **FastAPI** with **NumPy/SciPy** for portfolio optimization and the efficient frontier, and **Next.js 14** for the landing page, risk assessment chat, frontier charts, and allocation views. Processed moments and matrices live under `data/processed/`. The full product spec and API contract are in [`PRD.md`](./PRD.md) at the repo root.

---

## Features

- **Risk assessment** — Multi-turn dialogue captures preferences, maps them to a risk aversion coefficient \(A\), and assigns a profile label.
- **Portfolio optimization** — Maximizes mean–variance utility \(U = E(r_p) - \frac{1}{2} A \sigma_p^2\) under long-only and optional weight caps; returns optimal weights, GMVP, and efficient-frontier points.
- **Frontend** — Plotly efficient frontier, Recharts pie chart and table; in development, Next.js rewrites proxy `/api/v1/*` to the backend to avoid browser CORS issues.
- **Reconciliation & tests** — Unit tests, API integration, and reconciliation scripts under `tests/`; reports under `reports/`.

---

## Tech stack

| Layer | Technologies |
|-------|----------------|
| Frontend | Next.js 14 (App Router), TypeScript, TailwindCSS, Plotly.js, Recharts, Zustand, Axios |
| Backend | Python 3.11+, FastAPI, Uvicorn, Pydantic v2, NumPy, SciPy |
| Data | Static JSON/CSV (`data/raw/`, `data/processed/`) |
| Assessment / LLM | LangChain (OpenAI or Ollama — see environment variables) |

---

## Repository layout (excerpt)

```
├── backend/           # FastAPI app (optimizer, chat routes)
├── frontend/          # Next.js UI
├── data/
│   ├── raw/           # Raw NAV CSVs
│   └── processed/     # μ, Σ, frontier JSON, etc.
├── tests/             # Pytest (reconciliation, E2E markers)
├── reports/           # Reconciliation outputs
├── docs/              # Academic draft, demo script, equation notes
├── PRD.md             # Requirements & API contract
└── README.md          # This file
```

---

## Prerequisites

- **Node.js** 18+ (LTS recommended)
- **Python** 3.11–3.13 (see `backend/requirements.txt`)
- Optional: **OpenAI API key** for cloud models, or local **Ollama**

---

## Quick start

### 1. Clone and install dependencies

```bash
# Backend (use a virtual environment in the repo root or under backend/)
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

```bash
cd frontend
npm install
```

### 2. Environment variables

Copy the example file and add your secrets (**do not commit real keys**):

```bash
# Windows (cmd/PowerShell from repo root)
copy backend\.env.example backend\.env

# macOS/Linux
cp backend/.env.example backend/.env
```

You can also place `.env` at the project root; see `backend/.env.example` for variables the app reads.

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI key (required when using GPT) |
| `OPENAI_MODEL` / `CHATBOT_MODEL` | Model name, e.g. `gpt-4o` |
| `CHATBOT_BACKEND` | `openai` (default) or `ollama` |
| `OLLAMA_BASE_URL` | When using Ollama, e.g. `http://localhost:11434` |

By default the frontend **rewrites** `/api/v1/*` to `http://127.0.0.1:8000`. To call the API directly from the browser, set:

```bash
# frontend/.env.local (optional)
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api/v1
```

### 3. Run the services

**Terminal A — backend (port 8000)**

```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Terminal B — frontend (port 3000)**

```bash
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). If you change the proxy target in `next.config.mjs`, restart `npm run dev`.

---

## API summary (matches PRD)

Base URL (development): `http://localhost:8000/api/v1`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/funds` | Fund list and covariance matrix |
| `POST` | `/optimize` | Body includes `risk_aversion_coefficient`; returns optimal portfolio, GMVP, frontier |
| `POST` | `/chat/assess` | Single-step risk assessment (session state carried by the client) |

Full JSON schemas: [`PRD.md`](./PRD.md), Section 2.

---

## Data & Excel reconciliation

- Processed expected returns and covariance are in `data/processed/` (e.g. `mu_vector.json`, `cov_matrix.json`).
- Excel audit model build notes: [`data/README_EXCEL_MODEL.md`](./data/README_EXCEL_MODEL.md).
- Optional: use `requirements-data.txt` and scripts under `data/` to fetch or refresh market data.

---

## Tests

From the repository root (with test deps from `backend/requirements.txt` installed):

```bash
# Skip browser-based E2E by default:
pytest -m "not e2e"
```

Full E2E requires FastAPI and Next.js running; see `pytest.ini` and `tests/test_e2e.py`.

---

## Documentation & deliverables

- **Requirements & API** — [`PRD.md`](./PRD.md)
- **Academic draft / demo script** — [`docs/`](./docs/)
- **Reconciliation output** — [`reports/`](./reports/)

---

## Disclaimer

This project is for coursework and engineering demos only; **it is not investment advice**. Results depend on historical data and model assumptions. Real investing involves fees, taxes, liquidity, and regulatory constraints.

---

## License

If no `LICENSE` file is present, all rights are reserved. Before publishing to GitHub, add a license and a `.gitignore` that excludes `.env`, `node_modules/`, `.venv/`, etc.
