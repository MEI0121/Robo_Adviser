"""
Tests for backend.market_cache.MarketArtifactsCache.

Pins three behaviours the handler relies on:
  1. First .get() on new (mu, cov) populates and counts as a miss.
  2. Second .get() with the same (mu, cov) returns the same payload
     without recomputing (hit; misses unchanged).
  3. .get() with different (mu, cov) content stale-invalidates: a new
     miss is counted and a fresh payload is produced.

Also verifies:
  - .invalidate() resets both state and counters.
  - ``is_populated`` flips False → True → False across lifecycle.
  - The fingerprint is content-based, not identity-based: two distinct
    ndarrays with equal contents hit the cache.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import numpy as np
import pytest

from market_cache import (
    MarketArtifactsCache,
    MarketIndependentArtifacts,
    get_market_artifacts_cache,
)


_DATA_PRESENT = (
    Path(__file__).resolve().parent.parent / "data" / "processed" / "mu_vector.json"
).exists()

pytestmark = pytest.mark.skipif(
    not _DATA_PRESENT, reason="Market data required for cache tests"
)


@pytest.fixture
def fresh_cache() -> MarketArtifactsCache:
    """Give each test a pristine cache (invalidate the singleton)."""
    cache = get_market_artifacts_cache()
    cache.invalidate()
    return cache


class TestCacheLifecycle:
    def test_first_call_populates_and_counts_a_miss(
        self, fresh_cache, mu_vector, cov_matrix
    ):
        assert not fresh_cache.is_populated
        assert fresh_cache.hits == 0
        assert fresh_cache.misses == 0

        payload = fresh_cache.get(mu_vector, cov_matrix)

        assert isinstance(payload, MarketIndependentArtifacts)
        assert fresh_cache.is_populated
        assert fresh_cache.misses == 1
        assert fresh_cache.hits == 0

    def test_second_call_hits_cache_without_recompute(
        self, fresh_cache, mu_vector, cov_matrix
    ):
        first = fresh_cache.get(mu_vector, cov_matrix)
        second = fresh_cache.get(mu_vector, cov_matrix)

        # Same object identity proves no recomputation happened.
        assert second is first
        assert fresh_cache.hits == 1
        assert fresh_cache.misses == 1

    def test_five_sequential_calls_have_one_miss_and_four_hits(
        self, fresh_cache, mu_vector, cov_matrix
    ):
        for _ in range(5):
            fresh_cache.get(mu_vector, cov_matrix)

        assert fresh_cache.misses == 1
        assert fresh_cache.hits == 4

    def test_invalidate_resets_state_and_counters(
        self, fresh_cache, mu_vector, cov_matrix
    ):
        fresh_cache.get(mu_vector, cov_matrix)
        fresh_cache.get(mu_vector, cov_matrix)
        assert fresh_cache.is_populated
        assert fresh_cache.hits == 1
        assert fresh_cache.misses == 1

        fresh_cache.invalidate()

        assert not fresh_cache.is_populated
        assert fresh_cache.hits == 0
        assert fresh_cache.misses == 0


class TestContentBasedKeying:
    def test_same_content_different_ndarray_objects_hit_cache(
        self, fresh_cache, mu_vector, cov_matrix
    ):
        """
        The FastAPI lifespan and test conftest both load the same JSON
        into separate ndarrays. id() would mismatch. A correct cache
        keys by content and registers a hit.
        """
        mu_copy = np.array(mu_vector, copy=True)
        cov_copy = np.array(cov_matrix, copy=True)
        assert mu_copy is not mu_vector
        assert cov_copy is not cov_matrix

        first = fresh_cache.get(mu_vector, cov_matrix)
        second = fresh_cache.get(mu_copy, cov_copy)

        assert second is first
        assert fresh_cache.hits == 1
        assert fresh_cache.misses == 1

    def test_different_mu_stale_invalidates(
        self, fresh_cache, mu_vector, cov_matrix
    ):
        """Simulate the ``mu changed`` scenario the design must survive."""
        first = fresh_cache.get(mu_vector, cov_matrix)

        mu_perturbed = mu_vector.copy()
        mu_perturbed[0] += 1e-6
        second = fresh_cache.get(mu_perturbed, cov_matrix)

        assert second is not first
        assert fresh_cache.misses == 2
        assert fresh_cache.hits == 0

    def test_different_cov_stale_invalidates(
        self, fresh_cache, mu_vector, cov_matrix
    ):
        """And the ``cov changed`` scenario."""
        first = fresh_cache.get(mu_vector, cov_matrix)

        cov_perturbed = cov_matrix.copy()
        cov_perturbed[0, 0] += 1e-6
        second = fresh_cache.get(mu_vector, cov_perturbed)

        assert second is not first
        assert fresh_cache.misses == 2
        assert fresh_cache.hits == 0


class TestCachePayloadShape:
    def test_payload_contains_all_four_fields(
        self, fresh_cache, mu_vector, cov_matrix
    ):
        payload = fresh_cache.get(mu_vector, cov_matrix)

        assert hasattr(payload, "gmvp_short_allowed")
        assert hasattr(payload, "tangency_short_allowed")
        assert hasattr(payload, "efficient_frontier_short_allowed")
        assert hasattr(payload, "equal_weight")

        assert payload.gmvp_short_allowed.shape == (10,)
        assert len(payload.efficient_frontier_short_allowed) == 100
        assert payload.equal_weight.weights.shape == (10,)
        assert abs(payload.equal_weight.weights.sum() - 1.0) < 1e-12
