"""
Cache for market-data-dependent optimizer artifacts that are invariant
across /optimize request parameters.

The short-allowed GMVP, short-allowed tangency, short-allowed efficient
frontier, and the 1/n equal-weight portfolio depend only on ``(mu, cov)``
— they are independent of the investor's risk-aversion coefficient A and
of ``max_single_weight``. Recomputing them on every request wastes ~2s
on the 10-ETF dataset.

The cache is:
  - Lazy-initialised (first .get() call populates).
  - Keyed by the SHA-1 fingerprint of ``mu.tobytes() || cov.tobytes()``,
    so swapping (mu, cov) for a different market snapshot
    stale-invalidates automatically.
  - Explicit: no decorators, no module-level mutation outside the
    singleton accessor. ``invalidate()`` and ``.hits`` / ``.misses``
    counters are part of the public surface so tests can pin behaviour.
  - Thread-safe (FastAPI serves requests via asyncio, but we still
    guard against accidental concurrent access in the lifespan hook
    / background tasks).

Usage:
    cache = get_market_artifacts_cache()
    artifacts = cache.get(mu, cov)
    artifacts.gmvp_short_allowed        # np.ndarray
    artifacts.tangency_short_allowed    # PortfolioResult
    artifacts.efficient_frontier_short_allowed  # list[FrontierPoint]
    artifacts.equal_weight              # PortfolioResult

Reset (tests only):
    cache.invalidate()
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from threading import Lock
from typing import Optional

import numpy as np

from optimizer import (
    FrontierPoint,
    PortfolioResult,
    _compute_constrained_gmvp,
    compute_efficient_frontier,
    compute_equal_weight_portfolio,
    compute_tangency_portfolio,
)


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MarketIndependentArtifacts:
    """
    The four artifacts that depend only on ``(mu, cov)``.

    Frozen so that downstream code (main.py /optimize handler) cannot
    accidentally mutate cached state. The numpy arrays inside are not
    automatically immutable, but the FastAPI handler converts them to
    plain Python lists (``.tolist()``) before serialisation, which does
    not mutate the source.
    """

    gmvp_short_allowed: np.ndarray                          # shape (n,)
    tangency_short_allowed: PortfolioResult
    efficient_frontier_short_allowed: list[FrontierPoint]
    equal_weight: PortfolioResult


# ---------------------------------------------------------------------------
# Cache class
# ---------------------------------------------------------------------------


def _fingerprint(mu: np.ndarray, cov: np.ndarray) -> bytes:
    """
    Content hash of (mu, cov). Stable across ndarray re-instantiations of
    the same underlying values — needed because conftest.py and the
    FastAPI lifespan may load the same JSON into distinct arrays.
    """
    h = hashlib.sha1()
    h.update(np.ascontiguousarray(mu, dtype=np.float64).tobytes())
    h.update(np.ascontiguousarray(cov, dtype=np.float64).tobytes())
    return h.digest()


class MarketArtifactsCache:
    """Explicit, test-friendly cache for request-independent artifacts."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._key: Optional[bytes] = None
        self._payload: Optional[MarketIndependentArtifacts] = None
        self._hits: int = 0
        self._misses: int = 0

    # ---- public API ------------------------------------------------------

    def get(self, mu: np.ndarray, cov: np.ndarray) -> MarketIndependentArtifacts:
        """Return cached artifacts for (mu, cov), recomputing on miss."""
        key = _fingerprint(mu, cov)
        with self._lock:
            if self._key == key and self._payload is not None:
                self._hits += 1
                return self._payload
            # Miss: stale key, first call, or different (mu, cov)
            self._misses += 1
            self._payload = self._compute(mu, cov)
            self._key = key
            return self._payload

    def invalidate(self) -> None:
        """Drop all cached state and reset counters. Tests use this between cases."""
        with self._lock:
            self._key = None
            self._payload = None
            self._hits = 0
            self._misses = 0

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def is_populated(self) -> bool:
        return self._payload is not None

    # ---- internals -------------------------------------------------------

    @staticmethod
    def _compute(mu: np.ndarray, cov: np.ndarray) -> MarketIndependentArtifacts:
        return MarketIndependentArtifacts(
            gmvp_short_allowed=_compute_constrained_gmvp(
                cov, allow_short_selling=True
            ),
            tangency_short_allowed=compute_tangency_portfolio(
                mu, cov, max_weight=1.0, allow_short_selling=True
            ),
            efficient_frontier_short_allowed=compute_efficient_frontier(
                mu, cov, n_points=100, max_weight=1.0, allow_short_selling=True
            ),
            equal_weight=compute_equal_weight_portfolio(mu, cov),
        )


# ---------------------------------------------------------------------------
# Lazy module-level singleton — accessed only via get_market_artifacts_cache()
# ---------------------------------------------------------------------------


_SINGLETON: Optional[MarketArtifactsCache] = None
_SINGLETON_LOCK = Lock()


def get_market_artifacts_cache() -> MarketArtifactsCache:
    """Return the process-wide cache instance, creating it on first access."""
    global _SINGLETON
    if _SINGLETON is None:
        with _SINGLETON_LOCK:
            if _SINGLETON is None:
                _SINGLETON = MarketArtifactsCache()
    return _SINGLETON
