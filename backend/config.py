"""
Global configuration constants for the Robo-Adviser backend.

Any value that needs to stay consistent across the optimizer, API responses,
reconciliation harness, and frontend default props lives here.
"""

from __future__ import annotations


RISK_FREE_RATE: float = 0.03
"""
Annualized USD short-term risk-free rate used across all Sharpe, utility, and
tangency computations. Single source of truth — import this constant instead
of hard-coding 0.03 anywhere else. Matches PRD Appendix B (r_f).
"""
