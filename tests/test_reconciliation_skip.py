"""
Tests for the PASS / FAIL / SKIP semantics of the reconciliation harness.

Step 5 replaces the earlier binary pass/fail with three-valued status.
A check is:
  - PASS when Excel reference exists AND deviation ≤ tolerance (or the
    check is a pure Python self-consistency recomputation that matched)
  - FAIL when Excel reference exists AND deviation > tolerance
  - SKIP when no Excel reference CSV exists for that check

Previously the missing-CSV case was silently dropped from results, so
"18/18 passed" could mean "18 Python self-checks passed, Excel never
consulted". The SKIP row makes the reconciliation gap explicit.

These tests exercise all three states via synthetic Excel CSVs written
into temporary fixture directories.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import numpy as np
import pytest


_ROOT = Path(__file__).resolve().parent.parent
_DATA_PRESENT = (_ROOT / "data" / "processed" / "mu_vector.json").exists()

pytestmark = pytest.mark.skipif(
    not _DATA_PRESENT, reason="Market data required for reconciliation"
)


# Import reconcile.py only once (top-level sys.path already adjusted for
# backend/; reconcile.py lives at project root).
sys.path.insert(0, str(_ROOT))
import reconcile  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _status_of(report: dict, label_contains: str) -> str:
    """Return the status of the first check whose label contains the substring."""
    for c in report["checks"]:
        if label_contains in c["label"]:
            return c["status"]
    raise AssertionError(
        f"No check row found matching substring {label_contains!r} "
        f"in labels: {[c['label'] for c in report['checks']]}"
    )


def _write_csv(path: Path, array: np.ndarray) -> None:
    """Write a 1-D or 2-D numpy array as a headerless CSV (matches the harness's reader)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(path, np.atleast_2d(array), delimiter=",", fmt="%.18e")


# ---------------------------------------------------------------------------
# 1. No Excel CSVs → every Excel-gated check reports SKIP
# ---------------------------------------------------------------------------


class TestAllSkippedWhenNoExcelCSVs:
    def test_all_excel_gated_checks_report_skip(self, tmp_path):
        """
        Run reconcile against an empty Excel dir. Phase 3 Python
        self-consistency checks still PASS (legitimately), but every
        check that depends on an Excel CSV must be SKIP — not PASS.
        """
        empty_dir = tmp_path / "empty_recon"
        empty_dir.mkdir()

        report = reconcile.run_reconciliation(excel_dir=empty_dir, project_root=tmp_path)

        # Every Excel-gated label should be SKIP
        for label in (
            "μ vector (10 elements)",
            "Σ matrix (100 elements)",
            "GMVP weights (10 elements)",
            "Optimal weights (A=0.5)",
            "Optimal weights (A=3.5)",
            "Frontier weights (long-only",
            "GMVP (short-allowed) weights",
            "Tangency (long-only) weights",
            "Tangency (short-allowed) weights",
            "Frontier weights (short-allowed",
            "Equal-weight (E[r], σ, Sharpe)",
        ):
            assert _status_of(report, label) == "SKIP", (
                f"Check '{label}' should be SKIP when CSV absent; "
                f"got {_status_of(report, label)!r}"
            )

        # Python self-consistency recomputations are NOT Excel-gated;
        # they should still PASS.
        assert _status_of(report, "GMVP E(r_p)") == "PASS"
        assert _status_of(report, "Optimal A=3.5 Sharpe") == "PASS"

    def test_summary_counts_split_correctly(self, tmp_path):
        empty_dir = tmp_path / "empty_recon"
        empty_dir.mkdir()

        report = reconcile.run_reconciliation(excel_dir=empty_dir, project_root=tmp_path)

        # Sums reconcile to total
        assert (
            report["passed_checks"] + report["failed_checks"] + report["skipped_checks"]
            == report["total_checks"]
        )
        # No failures in an empty-CSV run
        assert report["failed_checks"] == 0
        # At least some skips — this is the whole point
        assert report["skipped_checks"] > 0
        # And at least some passes — the Python self-checks still succeed
        assert report["passed_checks"] > 0

    def test_overall_status_pass_with_skips(self, tmp_path):
        """Overall PASS is fine when there are passes + skips but no fails."""
        empty_dir = tmp_path / "empty_recon"
        empty_dir.mkdir()

        report = reconcile.run_reconciliation(excel_dir=empty_dir, project_root=tmp_path)
        assert report["overall_status"] == "PASS"


# ---------------------------------------------------------------------------
# 2. Matching Excel CSV → corresponding check reports PASS
# ---------------------------------------------------------------------------


class TestPassWhenExcelMatches:
    def test_matching_mu_vector_csv_produces_pass(self, tmp_path, mu_vector):
        """
        Writing an Excel μ CSV with values equal to Python's μ (copy of
        the loaded mu_vector) must flip the μ check from SKIP to PASS.
        """
        excel_dir = tmp_path / "matching_recon"
        _write_csv(excel_dir / "excel_mu_vector.csv", mu_vector.reshape(-1, 1))

        report = reconcile.run_reconciliation(excel_dir=excel_dir, project_root=tmp_path)

        assert _status_of(report, "μ vector (10 elements)") == "PASS"
        # Other checks that still lack CSVs remain SKIP
        assert _status_of(report, "Σ matrix (100 elements)") == "SKIP"

    def test_matching_gmvp_csv_produces_pass(self, tmp_path, cov_matrix):
        """GMVP weights CSV with Python's GMVP values → PASS."""
        from optimizer import compute_gmvp  # noqa: PLC0415

        w_gmvp = compute_gmvp(cov_matrix)
        excel_dir = tmp_path / "gmvp_recon"
        _write_csv(excel_dir / "excel_gmvp_weights.csv", w_gmvp.reshape(-1, 1))

        report = reconcile.run_reconciliation(excel_dir=excel_dir, project_root=tmp_path)

        assert _status_of(report, "GMVP weights (10 elements)") == "PASS"


# ---------------------------------------------------------------------------
# 3. Deviating Excel CSV → corresponding check reports FAIL
# ---------------------------------------------------------------------------


class TestFailWhenExcelDeviates:
    def test_mu_csv_with_large_deviation_fails(self, tmp_path, mu_vector):
        """Perturbed μ CSV with deviation >> tolerance → FAIL (not SKIP, not PASS)."""
        bad_mu = mu_vector.copy()
        bad_mu[0] += 0.01  # 1% perturbation; tolerance is 1e-6
        excel_dir = tmp_path / "deviating_recon"
        _write_csv(excel_dir / "excel_mu_vector.csv", bad_mu.reshape(-1, 1))

        report = reconcile.run_reconciliation(excel_dir=excel_dir, project_root=tmp_path)

        assert _status_of(report, "μ vector (10 elements)") == "FAIL"
        assert report["overall_status"] == "FAIL"
        assert report["failed_checks"] >= 1


# ---------------------------------------------------------------------------
# 4. solver_path metadata is attached to tangency rows only
# ---------------------------------------------------------------------------


class TestSolverPathProvenance:
    def test_tangency_rows_carry_solver_path(self, tmp_path):
        empty_dir = tmp_path / "empty_recon"
        empty_dir.mkdir()

        report = reconcile.run_reconciliation(excel_dir=empty_dir, project_root=tmp_path)

        tangency_rows = [
            c for c in report["checks"]
            if "Tangency" in c["label"] and "weights" in c["label"]
        ]
        assert len(tangency_rows) >= 2, "Expected at least 2 tangency rows"
        for c in tangency_rows:
            assert c.get("solver_path") in ("primary", "fallback"), (
                f"Tangency row missing solver_path provenance: {c}"
            )

    def test_non_tangency_rows_have_no_solver_path(self, tmp_path):
        empty_dir = tmp_path / "empty_recon"
        empty_dir.mkdir()

        report = reconcile.run_reconciliation(excel_dir=empty_dir, project_root=tmp_path)

        for c in report["checks"]:
            if "Tangency" in c["label"]:
                continue  # skip tangency rows — they legitimately have solver_path
            assert "solver_path" not in c, (
                f"Non-tangency row unexpectedly has solver_path: {c['label']}"
            )
