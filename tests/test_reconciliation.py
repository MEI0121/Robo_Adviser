"""
Financial Reconciliation Tests — pytest test suite wrapper.

Bridges reconcile.py's assertion functions into the standard pytest test
collection so that `pytest tests/` runs all reconciliation checks alongside
unit and API integration tests.

Each test corresponds to a PRD Section 4.3 tolerance check.
Tests that require Excel baseline CSV exports will skip automatically
if the files are not present in /data/reconciliation/.

Run:
    pytest tests/test_reconciliation.py -v -m reconciliation
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _PROJECT_ROOT / "backend"
_RECON_DIR = _PROJECT_ROOT / "data" / "reconciliation"

if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Import reconcile.py at project root (not inside a package)
import importlib.util

_recon_spec = importlib.util.spec_from_file_location(
    "reconcile", _PROJECT_ROOT / "reconcile.py"
)
_recon_mod = importlib.util.module_from_spec(_recon_spec)  # type: ignore[arg-type]
_recon_spec.loader.exec_module(_recon_mod)  # type: ignore[union-attr]

reconcile = _recon_mod

pytestmark = pytest.mark.reconciliation

_DATA_PRESENT = (_PROJECT_ROOT / "data" / "processed" / "mu_vector.json").exists()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_python_data():
    """Load mu and cov from backend; skip if not available."""
    if not _DATA_PRESENT:
        pytest.skip("Processed market data not present in /data/processed/")
    return reconcile._load_python_market_data()


# ---------------------------------------------------------------------------
# Phase 1: Static Data
# ---------------------------------------------------------------------------


class TestPhase1StaticData:
    """PRD Phase 1 reconciliation: μ, Σ, and GMVP weights vs Excel."""

    def test_mu_vector_reconciliation(self):
        """
        μ vector: Python backend vs Excel export.
        Tolerance: atol=1e-6 (PRD Section 4.3).
        """
        reconcile.assert_mu_reconciliation(_RECON_DIR)

    def test_cov_matrix_reconciliation(self):
        """
        Σ matrix (100 elements): Python backend vs Excel export.
        Tolerance: atol=1e-6 (PRD Section 4.3).
        """
        reconcile.assert_cov_reconciliation(_RECON_DIR)

    def test_gmvp_weights_reconciliation(self):
        """
        GMVP weights (10 elements): Python closed-form vs Excel MMULT/MINVERSE.
        Tolerance: atol=1e-6 — this is the critical QA sign-off check.
        """
        reconcile.assert_gmvp_reconciliation(_RECON_DIR)

    @pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
    def test_gmvp_weights_sum_to_one(self):
        """GMVP weights must sum to 1.0 within 1e-8 (no Excel required)."""
        mu, cov = _load_python_data()
        w_gmvp = reconcile._compute_python_gmvp(cov)
        assert abs(w_gmvp.sum() - 1.0) < 1e-8, (
            f"GMVP weights sum = {w_gmvp.sum():.10f}"
        )

    @pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
    def test_gmvp_weights_non_negative(self):
        """All GMVP weights must be ≥ 0 (long-only constraint)."""
        mu, cov = _load_python_data()
        w_gmvp = reconcile._compute_python_gmvp(cov)
        assert np.all(w_gmvp >= -1e-8), (
            f"Negative GMVP weight: min={w_gmvp.min():.6e}"
        )

    @pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
    def test_cov_matrix_is_positive_definite(self):
        """
        det(Σ) must be strictly positive (PRD mirrors Excel =MDETERM check).

        For a 10×10 monthly-return covariance matrix the determinant can be
        very small in absolute terms (e.g. 1e-22) while still being strictly
        positive and the matrix being invertible.  We therefore assert det > 0
        and separately verify positive-definiteness via all eigenvalues ≥ 0
        (which is the mathematically correct PD test).
        """
        mu, cov = _load_python_data()
        det = float(np.linalg.det(cov))
        assert det > 0, (
            f"Covariance matrix determinant = {det:.4e} — not positive definite"
        )
        eigenvalues = np.linalg.eigvals(cov)
        assert np.all(eigenvalues >= -1e-10), (
            f"Covariance matrix has negative eigenvalue: {eigenvalues.min():.4e}"
        )

    @pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
    def test_cov_matrix_condition_number(self):
        """Condition number of Σ must be < 1e10 for reliable inversion."""
        mu, cov = _load_python_data()
        cond = float(np.linalg.cond(cov))
        assert cond < 1e10, (
            f"Covariance matrix condition number = {cond:.4e} — ill-conditioned"
        )

    @pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
    def test_cov_matrix_symmetry(self):
        """Σ must be symmetric: Σ[i,j] == Σ[j,i] to within 1e-10."""
        mu, cov = _load_python_data()
        np.testing.assert_allclose(
            cov, cov.T, atol=1e-10, rtol=0,
            err_msg="Covariance matrix is not symmetric"
        )

    @pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
    def test_mu_vector_all_finite(self):
        """All μ values must be finite (no NaN or Inf)."""
        mu, _ = _load_python_data()
        assert np.all(np.isfinite(mu)), f"Non-finite values in μ: {mu}"

    @pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
    def test_cov_matrix_all_finite(self):
        """All Σ values must be finite."""
        _, cov = _load_python_data()
        assert np.all(np.isfinite(cov)), "Non-finite values in covariance matrix"


# ---------------------------------------------------------------------------
# Phase 2: Optimization Output
# ---------------------------------------------------------------------------


class TestPhase2OptimizationOutput:
    """
    PRD Phase 2: For each of 5 canonical A values, compare Python SLSQP
    optimal portfolio weights against Excel Solver exports.
    """

    @pytest.mark.parametrize("A", [0.5, 2.0, 3.5, 6.0, 10.0])
    def test_optimal_weights_reconciliation(self, A: float):
        """
        Optimal weights for A={A}: SLSQP vs Excel Solver.
        Tolerance: atol=1e-6 (PRD Section 4.3).
        """
        reconcile.assert_optimal_reconciliation(A, _RECON_DIR)

    @pytest.mark.parametrize("A", [0.5, 2.0, 3.5, 6.0, 10.0])
    @pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
    def test_optimal_weights_sum_to_one(self, A: float):
        """Optimal weights for A={A} must sum to 1.0 within 1e-8."""
        mu, cov = _load_python_data()
        w = reconcile._compute_python_optimal(mu, cov, A)
        assert abs(w.sum() - 1.0) < 1e-8, (
            f"A={A}: weights sum = {w.sum():.10f}"
        )

    @pytest.mark.parametrize("A", [0.5, 2.0, 3.5, 6.0, 10.0])
    @pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
    def test_optimal_weights_non_negative(self, A: float):
        """All optimal weights for A={A} must be ≥ 0 (long-only)."""
        mu, cov = _load_python_data()
        w = reconcile._compute_python_optimal(mu, cov, A)
        assert np.all(w >= -1e-8), (
            f"A={A}: negative weight detected, min={w.min():.6e}"
        )


# ---------------------------------------------------------------------------
# Phase 3: Statistics Independent Recomputation
# ---------------------------------------------------------------------------


class TestPhase3StatisticsIndependent:
    """
    PRD Phase 3: Independently recompute E(r_p), σ_p, and Sharpe Ratio
    from NumPy primitives and verify they agree with API-reported values.
    """

    @pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
    def test_gmvp_return_matches_formula(self):
        """E(r_p) = w^T μ must equal portfolio_return(w, μ) to within 1e-6."""
        mu, cov = _load_python_data()
        w_gmvp = reconcile._compute_python_gmvp(cov)
        er_formula = float(np.dot(w_gmvp, mu))
        # Verify self-consistency
        from portfolio_math import portfolio_return  # noqa: PLC0415
        er_module = portfolio_return(w_gmvp, mu)
        assert abs(er_formula - er_module) < 1e-12, (
            f"GMVP return: formula={er_formula:.10f}, module={er_module:.10f}"
        )

    @pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
    def test_gmvp_volatility_matches_formula(self):
        """σ_p = sqrt(w^T Σ w) self-consistency check."""
        mu, cov = _load_python_data()
        w_gmvp = reconcile._compute_python_gmvp(cov)
        vol_formula = float(np.sqrt(np.maximum(w_gmvp @ cov @ w_gmvp, 0.0)))
        from portfolio_math import portfolio_volatility  # noqa: PLC0415
        vol_module = portfolio_volatility(w_gmvp, cov)
        assert abs(vol_formula - vol_module) < 1e-12, (
            f"GMVP vol: formula={vol_formula:.10f}, module={vol_module:.10f}"
        )

    @pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
    def test_gmvp_sharpe_matches_formula(self):
        """Sharpe = (E(r_p) − 0.03) / σ_p self-consistency check."""
        mu, cov = _load_python_data()
        w_gmvp = reconcile._compute_python_gmvp(cov)
        from portfolio_math import portfolio_return, portfolio_volatility, sharpe_ratio  # noqa: PLC0415
        er = portfolio_return(w_gmvp, mu)
        vol = portfolio_volatility(w_gmvp, cov)
        sr_formula = (er - 0.03) / vol if vol > 1e-12 else 0.0
        sr_module = sharpe_ratio(w_gmvp, mu, cov)
        # Sharpe tolerance is 1e-4 per PRD
        assert abs(sr_formula - sr_module) < 1e-4, (
            f"GMVP Sharpe: formula={sr_formula:.8f}, module={sr_module:.8f}"
        )

    @pytest.mark.parametrize("A", [0.5, 2.0, 3.5, 6.0, 10.0])
    @pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
    def test_optimal_utility_score_matches_formula(self, A: float):
        """U = E(r_p) − 0.5 · A · σ_p² self-consistency for each A value."""
        mu, cov = _load_python_data()
        w = reconcile._compute_python_optimal(mu, cov, A)
        from portfolio_math import portfolio_return, portfolio_variance, utility  # noqa: PLC0415
        er = portfolio_return(w, mu)
        var = portfolio_variance(w, cov)
        u_formula = er - 0.5 * A * var
        u_module = utility(w, mu, cov, A)
        assert abs(u_formula - u_module) < 1e-10, (
            f"A={A}: utility formula={u_formula:.10f}, module={u_module:.10f}"
        )

    @pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
    def test_gmvp_has_minimum_variance_among_random_portfolios(self):
        """
        Sanity check: no random long-only portfolio should have lower variance
        than the GMVP.  Tests 200 random Dirichlet portfolios.
        """
        mu, cov = _load_python_data()
        w_gmvp = reconcile._compute_python_gmvp(cov)
        from portfolio_math import portfolio_variance  # noqa: PLC0415
        var_gmvp = portfolio_variance(w_gmvp, cov)

        rng = np.random.default_rng(seed=2026)
        for trial in range(200):
            w_rand = rng.dirichlet(np.ones(10))
            var_rand = portfolio_variance(w_rand, cov)
            assert var_gmvp <= var_rand + 1e-6, (
                f"Trial {trial}: GMVP variance {var_gmvp:.8f} > "
                f"random portfolio variance {var_rand:.8f}"
            )


# ---------------------------------------------------------------------------
# Full pipeline smoke test (runs reconcile.run_reconciliation directly)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
def test_reconciliation_pipeline_runs_without_exception():
    """
    The reconcile.run_reconciliation() function must complete without
    raising an exception, even if Excel CSVs are absent (which causes
    individual checks to skip rather than fail).
    """
    report = reconcile.run_reconciliation(excel_dir=_RECON_DIR)
    assert isinstance(report, dict)
    assert "overall_status" in report
    assert report["overall_status"] in ("PASS", "FAIL", "SKIP")
    assert "checks" in report
    assert isinstance(report["checks"], list)


@pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
def test_reconciliation_report_files_generated():
    """
    After running reconcile.run_reconciliation(), both the JSON and Markdown
    report files must exist in /reports/.
    """
    reconcile.run_reconciliation(excel_dir=_RECON_DIR)
    json_path = _PROJECT_ROOT / "reports" / "reconciliation_report.json"
    md_path = _PROJECT_ROOT / "reports" / "reconciliation_report.md"
    pdf_path = _PROJECT_ROOT / "reports" / "reconciliation_report.pdf"
    assert json_path.exists(), f"JSON report not generated at {json_path}"
    assert md_path.exists(), f"Markdown report not generated at {md_path}"
    assert pdf_path.exists(), f"PDF report not generated at {pdf_path}"


@pytest.mark.skipif(not _DATA_PRESENT, reason="Market data not present")
def test_reconciliation_json_report_schema():
    """The generated JSON report must conform to the expected schema."""
    import json  # noqa: PLC0415

    reconcile.run_reconciliation(excel_dir=_RECON_DIR)
    json_path = _PROJECT_ROOT / "reports" / "reconciliation_report.json"
    with open(json_path, encoding="utf-8") as fh:
        report = json.load(fh)

    required_keys = {
        "timestamp",
        "git_commit_sha",
        "excel_file_version",
        "overall_status",
        "total_checks",
        "passed_checks",
        "failed_checks",
        "skipped_checks",
        "elapsed_seconds",
        "checks",
        "gmvp_side_by_side",
        "optimal_side_by_side_A3_5",
    }
    missing = required_keys - set(report.keys())
    assert not missing, f"JSON report missing keys: {missing}"

    for check in report["checks"]:
        assert "label" in check
        assert "status" in check
        assert check["status"] in ("PASS", "FAIL", "SKIP")
        assert "max_deviation" in check  # may be None for SKIP
        assert "tolerance" in check
