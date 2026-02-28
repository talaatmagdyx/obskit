"""
Tests for obskit.metrics.presets module.

Tests cover:
- All bucket constants are present and correct types
- Buckets are ordered (ascending)
- Buckets contain sensible values
"""

import pytest

from obskit.metrics.presets import (
    API_SERVICE_BUCKETS,
    BATCH_SERVICE_BUCKETS,
    DATABASE_SERVICE_BUCKETS,
    DEFAULT_BUCKETS,
    FAST_SERVICE_BUCKETS,
)


class TestPresetBuckets:
    """Test that all preset bucket tuples are present and valid."""

    def test_fast_service_buckets_is_tuple(self):
        assert isinstance(FAST_SERVICE_BUCKETS, tuple)

    def test_api_service_buckets_is_tuple(self):
        assert isinstance(API_SERVICE_BUCKETS, tuple)

    def test_database_service_buckets_is_tuple(self):
        assert isinstance(DATABASE_SERVICE_BUCKETS, tuple)

    def test_batch_service_buckets_is_tuple(self):
        assert isinstance(BATCH_SERVICE_BUCKETS, tuple)

    def test_default_buckets_is_tuple(self):
        assert isinstance(DEFAULT_BUCKETS, tuple)

    def test_fast_service_buckets_not_empty(self):
        assert len(FAST_SERVICE_BUCKETS) > 0

    def test_api_service_buckets_not_empty(self):
        assert len(API_SERVICE_BUCKETS) > 0

    def test_database_service_buckets_not_empty(self):
        assert len(DATABASE_SERVICE_BUCKETS) > 0

    def test_batch_service_buckets_not_empty(self):
        assert len(BATCH_SERVICE_BUCKETS) > 0

    def test_default_buckets_not_empty(self):
        assert len(DEFAULT_BUCKETS) > 0

    def test_fast_service_buckets_all_floats(self):
        for b in FAST_SERVICE_BUCKETS:
            assert isinstance(b, float), f"Expected float, got {type(b)} for value {b}"

    def test_api_service_buckets_all_floats(self):
        for b in API_SERVICE_BUCKETS:
            assert isinstance(b, float)

    def test_database_service_buckets_all_floats(self):
        for b in DATABASE_SERVICE_BUCKETS:
            assert isinstance(b, float)

    def test_batch_service_buckets_all_floats(self):
        for b in BATCH_SERVICE_BUCKETS:
            assert isinstance(b, float)

    def test_default_buckets_all_floats(self):
        for b in DEFAULT_BUCKETS:
            assert isinstance(b, float)

    def test_fast_service_buckets_ascending(self):
        for i in range(len(FAST_SERVICE_BUCKETS) - 1):
            assert FAST_SERVICE_BUCKETS[i] < FAST_SERVICE_BUCKETS[i + 1]

    def test_api_service_buckets_ascending(self):
        for i in range(len(API_SERVICE_BUCKETS) - 1):
            assert API_SERVICE_BUCKETS[i] < API_SERVICE_BUCKETS[i + 1]

    def test_database_service_buckets_ascending(self):
        for i in range(len(DATABASE_SERVICE_BUCKETS) - 1):
            assert DATABASE_SERVICE_BUCKETS[i] < DATABASE_SERVICE_BUCKETS[i + 1]

    def test_batch_service_buckets_ascending(self):
        for i in range(len(BATCH_SERVICE_BUCKETS) - 1):
            assert BATCH_SERVICE_BUCKETS[i] < BATCH_SERVICE_BUCKETS[i + 1]

    def test_default_buckets_ascending(self):
        for i in range(len(DEFAULT_BUCKETS) - 1):
            assert DEFAULT_BUCKETS[i] < DEFAULT_BUCKETS[i + 1]

    def test_fast_service_buckets_all_positive(self):
        assert all(b > 0 for b in FAST_SERVICE_BUCKETS)

    def test_api_service_buckets_all_positive(self):
        assert all(b > 0 for b in API_SERVICE_BUCKETS)

    def test_batch_service_buckets_all_positive(self):
        assert all(b > 0 for b in BATCH_SERVICE_BUCKETS)

    def test_fast_service_buckets_max_is_sub_second_to_few_seconds(self):
        # Fast service should have a max bucket in a reasonable range
        assert max(FAST_SERVICE_BUCKETS) <= 10.0

    def test_batch_service_buckets_has_large_values(self):
        # Batch should have large buckets (minutes)
        assert max(BATCH_SERVICE_BUCKETS) >= 60.0

    def test_default_buckets_first_is_small(self):
        # Should start small (ms range)
        assert min(DEFAULT_BUCKETS) <= 0.01

    def test_fast_service_first_bucket(self):
        assert FAST_SERVICE_BUCKETS[0] == 0.001

    def test_api_service_buckets_count(self):
        assert len(API_SERVICE_BUCKETS) == 10

    def test_database_service_buckets_count(self):
        assert len(DATABASE_SERVICE_BUCKETS) == 11

    def test_batch_service_buckets_count(self):
        assert len(BATCH_SERVICE_BUCKETS) == 11

    def test_default_buckets_count(self):
        assert len(DEFAULT_BUCKETS) == 12

    def test_import_from_module(self):
        """Test that all exports are importable."""
        from obskit.metrics.presets import (
            API_SERVICE_BUCKETS,
            BATCH_SERVICE_BUCKETS,
            DATABASE_SERVICE_BUCKETS,
            DEFAULT_BUCKETS,
            FAST_SERVICE_BUCKETS,
        )
        assert all([
            FAST_SERVICE_BUCKETS,
            API_SERVICE_BUCKETS,
            DATABASE_SERVICE_BUCKETS,
            BATCH_SERVICE_BUCKETS,
            DEFAULT_BUCKETS,
        ])
