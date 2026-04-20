"""
Data loading module for the Robo-Adviser backend.

Loads pre-computed market statistics (mu vector and covariance matrix) from
the JSON files in /data/processed/ (Excel/data pipeline output).  Also exposes fund
metadata for the GET /api/v1/funds endpoint.

All NumPy arrays are cast to float64 to satisfy the PRD requirement.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np


def parse_mu_vector_payload(raw: Any) -> np.ndarray:
    """
    Normalise mu JSON payload into a (10,) float64 vector.

    Accepts either:
      - A bare list of 10 floats (legacy format), or
      - A dict with key ``mu_vector`` (and optional ``fund_codes``, metadata).
    """
    if isinstance(raw, dict):
        if "mu_vector" not in raw:
            raise DataLoadError(
                "mu_vector.json dict must contain a 'mu_vector' key with 10 floats."
            )
        raw = raw["mu_vector"]
    mu = np.asarray(raw, dtype=np.float64)
    if mu.shape != (10,):
        raise DataLoadError(
            f"μ vector must have length 10; got shape {mu.shape}."
        )
    return mu


def parse_cov_matrix_payload(raw: Any) -> np.ndarray:
    """
    Normalise covariance JSON payload into a (10, 10) float64 matrix.

    Accepts either:
      - A bare 10×10 nested list (legacy format), or
      - A dict with key ``cov_matrix`` (and optional ``fund_codes``, metadata).
    """
    if isinstance(raw, dict):
        if "cov_matrix" not in raw:
            raise DataLoadError(
                "cov_matrix.json dict must contain a 'cov_matrix' key with a 10×10 array."
            )
        raw = raw["cov_matrix"]
    cov = np.asarray(raw, dtype=np.float64)
    if cov.shape != (10, 10):
        raise DataLoadError(
            f"Σ matrix must be 10×10; got shape {cov.shape}."
        )
    return cov

# ---------------------------------------------------------------------------
# Path resolution — data/processed/ is two directories above this file
# ---------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _BACKEND_DIR.parent
_PROCESSED_DIR = _PROJECT_ROOT / "data" / "processed"

MU_VECTOR_PATH = _PROCESSED_DIR / "mu_vector.json"
COV_MATRIX_PATH = _PROCESSED_DIR / "cov_matrix.json"
FUND_METADATA_PATH = _PROCESSED_DIR / "fund_metadata.json"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DataLoadError(RuntimeError):
    """Raised when market data cannot be loaded or fails shape validation."""


class MatrixConditionError(ValueError):
    """Raised when the covariance matrix is numerically ill-conditioned."""


# ---------------------------------------------------------------------------
# Core loader
# ---------------------------------------------------------------------------


def load_market_data() -> tuple[np.ndarray, np.ndarray]:
    """
    Load the annualized mean return vector and covariance matrix.

    Returns
    -------
    mu : np.ndarray, shape (10,), dtype float64
        Annualized mean returns vector.
    cov : np.ndarray, shape (10, 10), dtype float64
        Annualized covariance matrix (positive semi-definite).

    Raises
    ------
    DataLoadError
        If either JSON file is missing or has the wrong shape.
    MatrixConditionError
        If the covariance matrix fails condition-number or PSD checks.
    """
    mu = _load_mu_vector()
    cov = _load_cov_matrix()
    _validate_matrix_properties(cov)
    return mu, cov


def _load_mu_vector() -> np.ndarray:
    """Read mu_vector.json and return a (10,) float64 array."""
    if not MU_VECTOR_PATH.exists():
        raise DataLoadError(
            f"mu_vector.json not found at {MU_VECTOR_PATH}. "
            "Add this file under data/processed/ before the backend can start."
        )
    with open(MU_VECTOR_PATH, "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    return parse_mu_vector_payload(payload)


def _load_cov_matrix() -> np.ndarray:
    """Read cov_matrix.json and return a (10, 10) float64 array."""
    if not COV_MATRIX_PATH.exists():
        raise DataLoadError(
            f"cov_matrix.json not found at {COV_MATRIX_PATH}. "
            "Add this file under data/processed/ before the backend can start."
        )
    with open(COV_MATRIX_PATH, "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    return parse_cov_matrix_payload(payload)


def _validate_matrix_properties(cov: np.ndarray) -> None:
    """
    Assert that the covariance matrix is positive semi-definite and
    numerically well-conditioned (condition number < 1e10).

    Raises
    ------
    MatrixConditionError
    """
    eigenvalues = np.linalg.eigvals(cov)
    if not np.all(eigenvalues >= -1e-10):  # allow tiny floating-point negatives
        raise MatrixConditionError(
            f"Covariance matrix is not positive semi-definite. "
            f"Min eigenvalue: {eigenvalues.min():.4e}. "
            "Check annualization and the covariance construction in the Excel model."
        )

    cond = np.linalg.cond(cov)
    if cond > 1e10:
        raise MatrixConditionError(
            f"Covariance matrix is ill-conditioned (condition number = {cond:.2e}). "
            "Matrix inversion results will be unreliable. "
            "Consider adding a small regularization term or reviewing fund selection."
        )


# ---------------------------------------------------------------------------
# Fund metadata loader
# ---------------------------------------------------------------------------


def load_fund_metadata() -> list[dict[str, Any]]:
    """
    Load fund metadata from fund_metadata.json.

    Returns a list of 10 fund descriptor dicts conforming to the FundInfo
    schema in models.py.  If the file is absent the backend raises
    DataLoadError so the gap is immediately visible at startup.
    """
    if not FUND_METADATA_PATH.exists():
        raise DataLoadError(
            f"fund_metadata.json not found at {FUND_METADATA_PATH}. "
            "Add fund_metadata.json under data/processed/."
        )
    with open(FUND_METADATA_PATH, "r", encoding="utf-8") as fh:
        funds: list[dict[str, Any]] = json.load(fh)

    if len(funds) != 10:
        raise DataLoadError(
            f"fund_metadata.json must contain exactly 10 fund entries; got {len(funds)}."
        )
    return funds


# ---------------------------------------------------------------------------
# Convenience: get fund codes in canonical order
# ---------------------------------------------------------------------------


def get_fund_codes() -> list[str]:
    """Return the list of 10 fund codes in the same order as mu / cov rows."""
    funds = load_fund_metadata()
    return [f["fund_code"] for f in funds]


# ---------------------------------------------------------------------------
# Metadata helpers (dates, etc.)
# ---------------------------------------------------------------------------


def get_data_date_range() -> tuple[str, str]:
    """
    Return (start_date, end_date) strings from fund_metadata.json, or
    reasonable defaults if the keys are absent.
    """
    try:
        funds = load_fund_metadata()
        start = funds[0].get("data_start_date", "2015-01-02")
        end = funds[0].get("data_end_date", "2025-12-31")
        return start, end
    except DataLoadError:
        return "2015-01-02", "2025-12-31"
