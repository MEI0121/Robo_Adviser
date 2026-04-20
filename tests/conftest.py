"""
Shared pytest fixtures for the Robo-Adviser integration and reconciliation tests.

Provides:
  - sys.path injection so backend modules are importable without installation
  - Async ASGI test client wrapping the FastAPI app (httpx + ASGITransport)
  - Pre-loaded NumPy market data (mu, cov) straight from /data/processed/
  - Canonical fund-code list and risk-aversion test values
  - A tiny, fully deterministic 10-asset toy universe for unit-level checks
    that must work even before real processed fund data is available
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import AsyncGenerator

import numpy as np
import pytest
import pytest_asyncio

# ---------------------------------------------------------------------------
# Path setup — backend modules live two levels up from this file
# ---------------------------------------------------------------------------

_TESTS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _TESTS_DIR.parent
_BACKEND_DIR = _PROJECT_ROOT / "backend"
_PROCESSED_DIR = _PROJECT_ROOT / "data" / "processed"
_RECON_DIR = _PROJECT_ROOT / "data" / "reconciliation"  # Excel baseline CSV exports

# Ensure backend is importable
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# ---------------------------------------------------------------------------
# Async test mode — all async tests use asyncio event loop
# ---------------------------------------------------------------------------

pytest_plugins = ["pytest_asyncio"]


# ---------------------------------------------------------------------------
# ASGI test client (shared across the entire test session)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def client() -> AsyncGenerator:
    """
    Yield a live httpx.AsyncClient backed by the FastAPI ASGI app.

    httpx.ASGITransport does not trigger FastAPI's lifespan context manager
    automatically, so we manually pre-populate _app_state here, mirroring
    exactly what the lifespan handler does at server startup.  If the data
    files are absent, the app state remains None and endpoints return 503
    (which the integration tests handle with skipif guards).
    """
    import httpx
    from main import app, _app_state  # noqa: PLC0415

    # Pre-populate app state (mirrors lifespan handler in main.py)
    try:
        from data_loader import (  # noqa: PLC0415
            DataLoadError,
            MatrixConditionError,
            get_data_date_range,
            get_fund_codes,
            load_fund_metadata,
            load_market_data,
        )

        mu, cov = load_market_data()
        _app_state["mu"] = mu
        _app_state["cov"] = cov
        _app_state["fund_metadata"] = load_fund_metadata()
        _app_state["fund_codes"] = get_fund_codes()
        _app_state["date_range"] = get_data_date_range()
    except (DataLoadError, MatrixConditionError, Exception) as exc:  # noqa: BLE001
        # Leave app state as None — 503 tests will be handled by skipif guards
        _app_state.setdefault("mu", None)
        _app_state.setdefault("cov", None)
        _app_state.setdefault("fund_metadata", None)
        _app_state.setdefault("fund_codes", None)
        _app_state.setdefault("date_range", ("2015-01-02", "2025-12-31"))

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Real market data fixtures (require processed JSON outputs)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def mu_vector() -> np.ndarray:
    """Load the real annualised mean-return vector from data/processed."""
    path = _PROCESSED_DIR / "mu_vector.json"
    if not path.exists():
        pytest.skip(f"mu_vector.json not found at {path} — data pipeline output required.")
    from data_loader import parse_mu_vector_payload  # noqa: PLC0415

    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    mu = parse_mu_vector_payload(payload)
    assert mu.shape == (10,), f"Expected (10,) mu vector, got {mu.shape}"
    return mu


@pytest.fixture(scope="session")
def cov_matrix(mu_vector: np.ndarray) -> np.ndarray:  # noqa: ARG001 — ensures load order
    """Load the real annualised covariance matrix from data/processed."""
    path = _PROCESSED_DIR / "cov_matrix.json"
    if not path.exists():
        pytest.skip(f"cov_matrix.json not found at {path} — data pipeline output required.")
    from data_loader import parse_cov_matrix_payload  # noqa: PLC0415

    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    cov = parse_cov_matrix_payload(payload)
    assert cov.shape == (10, 10), f"Expected (10,10) cov matrix, got {cov.shape}"
    return cov


@pytest.fixture(scope="session")
def gmvp_reference() -> dict:
    """Load the GMVP reference data from gmvp_weights.json."""
    path = _PROCESSED_DIR / "gmvp_weights.json"
    if not path.exists():
        pytest.skip(f"gmvp_weights.json not found at {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def fund_codes(gmvp_reference: dict) -> list[str]:
    """Return the canonical 10-fund-code ordering from gmvp_weights.json."""
    return gmvp_reference["fund_codes"]


# ---------------------------------------------------------------------------
# Excel reconciliation CSV fixtures (optional — skip if not yet exported)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def excel_mu() -> np.ndarray:
    """Load Excel-exported mu vector CSV (10 rows × 1 column)."""
    path = _RECON_DIR / "excel_mu_vector.csv"
    if not path.exists():
        pytest.skip(
            f"Excel mu CSV not found at {path}. "
            "Export from the Excel audit model to /data/reconciliation/."
        )
    import pandas as pd  # noqa: PLC0415

    return pd.read_csv(path, header=None).values.flatten().astype(np.float64)


@pytest.fixture(scope="session")
def excel_cov() -> np.ndarray:
    """Load Excel-exported covariance matrix CSV (10 × 10)."""
    path = _RECON_DIR / "excel_cov_matrix.csv"
    if not path.exists():
        pytest.skip(f"Excel cov CSV not found at {path}.")
    import pandas as pd  # noqa: PLC0415

    return pd.read_csv(path, header=None).values.astype(np.float64)


@pytest.fixture(scope="session")
def excel_gmvp() -> np.ndarray:
    """Load Excel-exported GMVP weights CSV (10 rows × 1 column)."""
    path = _RECON_DIR / "excel_gmvp_weights.csv"
    if not path.exists():
        pytest.skip(f"Excel GMVP CSV not found at {path}.")
    import pandas as pd  # noqa: PLC0415

    return pd.read_csv(path, header=None).values.flatten().astype(np.float64)


@pytest.fixture(scope="session")
def excel_frontier() -> "pd.DataFrame":  # noqa: F821
    """
    Load Excel frontier CSV.
    Expected columns: target_return, min_variance, w0..w9 (50 rows).
    """
    path = _RECON_DIR / "excel_frontier.csv"
    if not path.exists():
        pytest.skip(f"Excel frontier CSV not found at {path}.")
    import pandas as pd  # noqa: PLC0415

    return pd.read_csv(path)


# ---------------------------------------------------------------------------
# PRD-canonical risk aversion test values (Phase 2 reconciliation)
# ---------------------------------------------------------------------------


@pytest.fixture(params=[0.5, 2.0, 3.5, 6.0, 10.0])
def risk_aversion_value(request) -> float:
    """Parametrised fixture yielding the 5 PRD-canonical A test values."""
    return float(request.param)


# ---------------------------------------------------------------------------
# Deterministic toy universe (unit tests — no disk I/O required)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def toy_universe() -> tuple[np.ndarray, np.ndarray]:
    """
    A well-conditioned 10-asset universe with known mathematical properties.

    Used for unit-level tests that must pass even before the project delivers
    real fund data.  Seed is fixed for reproducibility.
    """
    rng = np.random.default_rng(42)
    n = 10
    # Annualised returns: 4% to 13%
    mu = np.linspace(0.04, 0.13, n, dtype=np.float64)
    # Volatilities: 5% to 22%
    vols = np.linspace(0.05, 0.22, n, dtype=np.float64)
    # Uniform correlation 0.3 matrix
    rho = 0.30
    corr = np.full((n, n), rho, dtype=np.float64)
    np.fill_diagonal(corr, 1.0)
    D = np.diag(vols)
    cov = D @ corr @ D
    # Ensure strict positive definiteness
    cov += np.eye(n, dtype=np.float64) * 1e-6
    return mu, cov.astype(np.float64)
