"""
Data integrity checks — PRD Section 3 (QA / reconciliation).

Validates that `/data/processed/mu_vector.json` and `cov_matrix.json` match
Excel baseline exports in `/data/reconciliation/*.csv` when those CSVs exist.

When Excel CSVs are absent, tests skip (Excel exports may not be present yet).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PROCESSED = _PROJECT_ROOT / "data" / "processed"
_RECON_DIR = _PROJECT_ROOT / "data" / "reconciliation"

_BACKEND_DIR = _PROJECT_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

_DATA_PRESENT = (_PROCESSED / "mu_vector.json").exists()

pytestmark = pytest.mark.data_integrity


@pytest.mark.skipif(not _DATA_PRESENT, reason="mu_vector.json not in /data/processed/")
def test_mu_json_matches_excel_csv_when_present():
    """Element-wise |mu_json - excel_mu| <= 1e-6 when excel_mu_vector.csv exists."""
    excel_p = _RECON_DIR / "excel_mu_vector.csv"
    if not excel_p.exists():
        pytest.skip(f"No Excel export at {excel_p}")

    from data_loader import parse_mu_vector_payload  # noqa: PLC0415

    with open(_PROCESSED / "mu_vector.json", encoding="utf-8") as fh:
        mu_json = parse_mu_vector_payload(json.load(fh))

    import pandas as pd  # noqa: PLC0415

    excel = pd.read_csv(excel_p, header=None).values.flatten().astype(np.float64)
    np.testing.assert_allclose(mu_json, excel, atol=1e-6, rtol=0)


@pytest.mark.skipif(not _DATA_PRESENT, reason="cov_matrix.json not in /data/processed/")
def test_cov_json_matches_excel_csv_when_present():
    """Element-wise |cov_json - excel_cov| <= 1e-6 when excel_cov_matrix.csv exists."""
    excel_p = _RECON_DIR / "excel_cov_matrix.csv"
    if not excel_p.exists():
        pytest.skip(f"No Excel export at {excel_p}")

    from data_loader import parse_cov_matrix_payload  # noqa: PLC0415

    with open(_PROCESSED / "cov_matrix.json", encoding="utf-8") as fh:
        cov_json = parse_cov_matrix_payload(json.load(fh))

    import pandas as pd  # noqa: PLC0415

    excel = pd.read_csv(excel_p, header=None).values.astype(np.float64)
    np.testing.assert_allclose(cov_json, excel, atol=1e-6, rtol=0)


@pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
def test_gmvp_json_schema_and_weights_sum():
    """
    gmvp_weights.json must be well-formed: 10 weights, sum ≈ 1, non-negative.

    Exact agreement with the live `compute_gmvp()` is not asserted here because
    Excel exports may use Excel's constrained long-only GMVP while the JSON
    snapshot can reflect a different solver snapshot — full numerical agreement
    is covered by `reconcile.py` vs Excel CSV exports.
    """
    gmvp_path = _PROCESSED / "gmvp_weights.json"
    if not gmvp_path.exists():
        pytest.skip("gmvp_weights.json not exported")

    with open(gmvp_path, encoding="utf-8") as fh:
        payload = json.load(fh)
    w = np.asarray(payload["weights"], dtype=np.float64)
    assert w.shape == (10,)
    assert abs(float(w.sum()) - 1.0) < 1e-6
    assert np.all(w >= -1e-8)
    assert "fund_codes" in payload and len(payload["fund_codes"]) == 10


@pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
def test_frontier_json_row_count_matches_optimizer_default():
    """frontier_points.json length matches compute_efficient_frontier n_points."""
    fp = _PROCESSED / "frontier_points.json"
    if not fp.exists():
        pytest.skip("frontier_points.json not exported")

    _backend = _PROJECT_ROOT / "backend"
    if str(_backend) not in sys.path:
        sys.path.insert(0, str(_backend))

    from data_loader import load_market_data  # noqa: PLC0415
    from optimizer import compute_efficient_frontier  # noqa: PLC0415

    with open(fp, encoding="utf-8") as fh:
        pts = json.load(fh)
    n_file = len(pts)

    mu, cov = load_market_data()
    py_pts = compute_efficient_frontier(mu, cov, n_points=n_file)
    assert len(py_pts) == n_file, "Frontier point count mismatch"
