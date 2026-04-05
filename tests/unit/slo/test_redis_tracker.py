"""Unit tests for obskit.slo.redis_tracker.AsyncRedisSLOTracker."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from obskit.slo.redis_tracker import AsyncRedisSLOTracker
from obskit.slo.types import SLOStatus, SLOType


def _make_redis(*, zcount_total=10, zcount_success=9, zrangebyscore=None,
                zrangebyscore_scores=None):
    """Build a mock async Redis client with sensible defaults."""
    r = MagicMock()
    r.zadd = AsyncMock(return_value=1)
    r.zremrangebyscore = AsyncMock(return_value=0)
    r.expire = AsyncMock(return_value=True)
    r.zcount = AsyncMock(side_effect=lambda key, *a, **kw: (
        AsyncMock(return_value=zcount_success)()
        if "success" in key
        else AsyncMock(return_value=zcount_total)()
    ))
    r.zrangebyscore = AsyncMock(return_value=zrangebyscore or [])
    return r


class TestAsyncRedisSLOTrackerInit:
    def test_defaults(self):
        r = MagicMock()
        tracker = AsyncRedisSLOTracker(r)
        assert tracker._service == "default"
        assert tracker._key_prefix == "obskit:slo"

    def test_custom_params(self):
        r = MagicMock()
        tracker = AsyncRedisSLOTracker(r, service="my-svc", key_prefix="custom")
        assert tracker._service == "my-svc"
        assert tracker._key_prefix == "custom"

    def test_key_format(self):
        r = MagicMock()
        tracker = AsyncRedisSLOTracker(r, service="svc", key_prefix="pfx")
        assert tracker._key("api_avail", "total") == "pfx:svc:api_avail:total"


class TestRegisterSlo:
    def test_register_stores_target(self):
        tracker = AsyncRedisSLOTracker(MagicMock(), service="svc")
        tracker.register_slo("avail", SLOType.AVAILABILITY, target_value=0.999)
        assert "avail" in tracker._targets
        t = tracker._targets["avail"]
        assert t.target_value == 0.999
        assert t.slo_type == SLOType.AVAILABILITY

    def test_register_with_window(self):
        tracker = AsyncRedisSLOTracker(MagicMock())
        tracker.register_slo("err", SLOType.ERROR_RATE, target_value=0.01, window_seconds=1800)
        assert tracker._targets["err"].window_seconds == 1800

    def test_register_latency_requires_percentile(self):
        tracker = AsyncRedisSLOTracker(MagicMock())
        with pytest.raises(ValueError, match="percentile"):
            tracker.register_slo("lat", SLOType.LATENCY, target_value=200.0)

    def test_register_latency_with_percentile(self):
        tracker = AsyncRedisSLOTracker(MagicMock())
        tracker.register_slo("lat", SLOType.LATENCY, target_value=200.0, percentile=99)
        assert tracker._targets["lat"].percentile == 99


class TestRecordMeasurement:
    @pytest.mark.asyncio
    async def test_availability_success(self):
        r = MagicMock()
        r.zadd = AsyncMock(return_value=1)
        r.zremrangebyscore = AsyncMock(return_value=0)
        r.expire = AsyncMock(return_value=True)

        tracker = AsyncRedisSLOTracker(r, service="svc")
        tracker.register_slo("avail", SLOType.AVAILABILITY, target_value=0.999)

        await tracker.record_measurement("avail", value=1.0, success=True)

        # ZADD should be called for both total and success keys
        assert r.zadd.call_count == 2
        calls = [c.args[0] for c in r.zadd.call_args_list]
        assert any("total" in k for k in calls)
        assert any("success" in k for k in calls)

    @pytest.mark.asyncio
    async def test_availability_failure_only_writes_total(self):
        r = MagicMock()
        r.zadd = AsyncMock(return_value=1)
        r.zremrangebyscore = AsyncMock(return_value=0)
        r.expire = AsyncMock(return_value=True)

        tracker = AsyncRedisSLOTracker(r, service="svc")
        tracker.register_slo("avail", SLOType.AVAILABILITY, target_value=0.999)

        await tracker.record_measurement("avail", value=0.0, success=False)

        calls = [c.args[0] for c in r.zadd.call_args_list]
        assert any("total" in k for k in calls)
        # success key should NOT be written
        assert not any("success" in k for k in calls)

    @pytest.mark.asyncio
    async def test_error_rate_measurement(self):
        r = MagicMock()
        r.zadd = AsyncMock(return_value=1)
        r.zremrangebyscore = AsyncMock(return_value=0)
        r.expire = AsyncMock(return_value=True)

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("err", SLOType.ERROR_RATE, target_value=0.05)

        await tracker.record_measurement("err", value=1.0, success=True)
        assert r.zadd.call_count >= 1

    @pytest.mark.asyncio
    async def test_latency_writes_latencies_key(self):
        r = MagicMock()
        r.zadd = AsyncMock(return_value=1)
        r.zremrangebyscore = AsyncMock(return_value=0)
        r.expire = AsyncMock(return_value=True)

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("lat", SLOType.LATENCY, target_value=200.0, percentile=99)

        await tracker.record_measurement("lat", value=150.0, success=True)

        calls = [c.args[0] for c in r.zadd.call_args_list]
        assert any("latencies" in k for k in calls)

    @pytest.mark.asyncio
    async def test_throughput_writes_total_key(self):
        r = MagicMock()
        r.zadd = AsyncMock(return_value=1)
        r.zremrangebyscore = AsyncMock(return_value=0)
        r.expire = AsyncMock(return_value=True)

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("tput", SLOType.THROUGHPUT, target_value=100.0)

        await tracker.record_measurement("tput", value=1.0)

        calls = [c.args[0] for c in r.zadd.call_args_list]
        assert any("total" in k for k in calls)

    @pytest.mark.asyncio
    async def test_unregistered_slo_is_ignored(self):
        r = MagicMock()
        r.zadd = AsyncMock(return_value=1)
        tracker = AsyncRedisSLOTracker(r)

        # No exception, no Redis calls
        await tracker.record_measurement("nonexistent", value=1.0)
        r.zadd.assert_not_called()

    @pytest.mark.asyncio
    async def test_eviction_zremrangebyscore_called(self):
        r = MagicMock()
        r.zadd = AsyncMock(return_value=1)
        r.zremrangebyscore = AsyncMock(return_value=0)
        r.expire = AsyncMock(return_value=True)

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("avail", SLOType.AVAILABILITY, target_value=0.999,
                             window_seconds=3600)
        await tracker.record_measurement("avail", value=1.0, success=True)

        assert r.zremrangebyscore.call_count >= 1

    @pytest.mark.asyncio
    async def test_expire_called_with_ttl(self):
        r = MagicMock()
        r.zadd = AsyncMock(return_value=1)
        r.zremrangebyscore = AsyncMock(return_value=0)
        r.expire = AsyncMock(return_value=True)

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("avail", SLOType.AVAILABILITY, target_value=0.999,
                             window_seconds=3600)
        await tracker.record_measurement("avail", value=1.0, success=True)

        # TTL = window_seconds + 60
        expire_calls = [c.args for c in r.expire.call_args_list]
        ttls = [args[1] for args in expire_calls]
        assert all(t == 3660 for t in ttls)


class TestGetStatusAvailability:
    @pytest.mark.asyncio
    async def test_availability_compliant(self):
        async def _zcount(key, *a, **kw):
            if "success" in key:
                return 990
            return 1000

        r = MagicMock()
        r.zcount = _zcount

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("avail", SLOType.AVAILABILITY, target_value=0.999)

        status = await tracker.get_status("avail")
        assert status is not None
        assert isinstance(status, SLOStatus)
        assert status.current_value == pytest.approx(0.99)
        assert status.compliance is False  # 0.99 < 0.999
        assert status.measurement_count == 1000

    @pytest.mark.asyncio
    async def test_availability_met(self):
        async def _zcount(key, *a, **kw):
            if "success" in key:
                return 1000
            return 1000

        r = MagicMock()
        r.zcount = _zcount

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("avail", SLOType.AVAILABILITY, target_value=0.999)

        status = await tracker.get_status("avail")
        assert status.current_value == pytest.approx(1.0)
        assert status.compliance is True

    @pytest.mark.asyncio
    async def test_availability_empty_window_defaults_to_1(self):
        async def _zcount(*a, **kw):
            return 0

        r = MagicMock()
        r.zcount = _zcount

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("avail", SLOType.AVAILABILITY, target_value=0.999)

        status = await tracker.get_status("avail")
        assert status.current_value == pytest.approx(1.0)
        assert status.measurement_count == 0

    @pytest.mark.asyncio
    async def test_returns_none_for_unregistered(self):
        tracker = AsyncRedisSLOTracker(MagicMock())
        result = await tracker.get_status("unknown")
        assert result is None


class TestGetStatusErrorRate:
    @pytest.mark.asyncio
    async def test_error_rate_below_target(self):
        """2% errors, target ≤ 5% → compliant."""

        async def _zcount(key, *a, **kw):
            if "success" in key:
                return 98
            return 100

        r = MagicMock()
        r.zcount = _zcount

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("err", SLOType.ERROR_RATE, target_value=0.05)

        status = await tracker.get_status("err")
        assert status.current_value == pytest.approx(0.02)
        assert status.compliance is True

    @pytest.mark.asyncio
    async def test_error_rate_empty_defaults_to_zero(self):
        async def _zcount(*a, **kw):
            return 0

        r = MagicMock()
        r.zcount = _zcount

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("err", SLOType.ERROR_RATE, target_value=0.05)

        status = await tracker.get_status("err")
        assert status.current_value == pytest.approx(0.0)


class TestGetStatusLatency:
    @pytest.mark.asyncio
    async def test_latency_p99_below_target(self):
        # 100 measurements: values 1..100 ms → P99 = 99 ms < 200 ms target
        members = [f"{i}.0:uid{i}" for i in range(1, 101)]

        r = MagicMock()
        r.zrangebyscore = AsyncMock(return_value=members)

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("lat", SLOType.LATENCY, target_value=200.0, percentile=99)

        status = await tracker.get_status("lat")
        assert status is not None
        assert status.current_value == pytest.approx(99.0)
        assert status.compliance is True

    @pytest.mark.asyncio
    async def test_latency_empty_returns_default_status(self):
        r = MagicMock()
        r.zrangebyscore = AsyncMock(return_value=[])

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("lat", SLOType.LATENCY, target_value=200.0, percentile=99)

        status = await tracker.get_status("lat")
        assert status is not None
        assert status.current_value == pytest.approx(0.0)
        assert status.compliance is True
        assert status.measurement_count == 0

    @pytest.mark.asyncio
    async def test_latency_bytes_decoded(self):
        """Redis binary client returns bytes — they must be decoded."""
        members = [b"150.0:uid1", b"200.0:uid2", b"250.0:uid3"]

        r = MagicMock()
        r.zrangebyscore = AsyncMock(return_value=members)

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("lat", SLOType.LATENCY, target_value=300.0, percentile=99)

        status = await tracker.get_status("lat")
        assert status.current_value == pytest.approx(250.0)


class TestGetStatusThroughput:
    @pytest.mark.asyncio
    async def test_throughput_computed(self):
        import time

        now = time.time()
        # 11 measurements over 10 seconds = 1.1 req/s (> 1.0 target)
        members_with_scores = [(f"uid{i}", now - 10 + i) for i in range(11)]

        r = MagicMock()
        r.zrangebyscore = AsyncMock(return_value=members_with_scores)

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("tput", SLOType.THROUGHPUT, target_value=1.0)

        status = await tracker.get_status("tput")
        assert status is not None
        assert status.current_value == pytest.approx(1.1)
        assert status.compliance is True

    @pytest.mark.asyncio
    async def test_throughput_less_than_2_returns_zero(self):
        r = MagicMock()
        r.zrangebyscore = AsyncMock(return_value=[("uid1", 1.0)])

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("tput", SLOType.THROUGHPUT, target_value=1.0)

        status = await tracker.get_status("tput")
        assert status.current_value == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_throughput_empty_returns_zero(self):
        r = MagicMock()
        r.zrangebyscore = AsyncMock(return_value=[])

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("tput", SLOType.THROUGHPUT, target_value=1.0)

        status = await tracker.get_status("tput")
        assert status.current_value == pytest.approx(0.0)


class TestGetAllStatus:
    @pytest.mark.asyncio
    async def test_returns_all_registered(self):
        async def _zcount(key, *a, **kw):
            if "success" in key:
                return 100
            return 100

        r = MagicMock()
        r.zcount = _zcount

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("a", SLOType.AVAILABILITY, target_value=0.99)
        tracker.register_slo("b", SLOType.ERROR_RATE, target_value=0.01)

        result = await tracker.get_all_status()
        assert set(result.keys()) == {"a", "b"}

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_slos(self):
        tracker = AsyncRedisSLOTracker(MagicMock())
        result = await tracker.get_all_status()
        assert result == {}


class TestComplianceAndBudget:
    def test_availability_compliance(self):
        from obskit.slo.types import SLOTarget, SLOType

        target = SLOTarget(slo_type=SLOType.AVAILABILITY, target_value=0.999)
        assert AsyncRedisSLOTracker._check_compliance(target, 0.999) is True
        assert AsyncRedisSLOTracker._check_compliance(target, 0.998) is False

    def test_error_rate_compliance(self):
        from obskit.slo.types import SLOTarget, SLOType

        target = SLOTarget(slo_type=SLOType.ERROR_RATE, target_value=0.05)
        assert AsyncRedisSLOTracker._check_compliance(target, 0.04) is True
        assert AsyncRedisSLOTracker._check_compliance(target, 0.06) is False

    def test_latency_compliance(self):
        from obskit.slo.types import SLOTarget, SLOType

        target = SLOTarget(slo_type=SLOType.LATENCY, target_value=200.0, percentile=99)
        assert AsyncRedisSLOTracker._check_compliance(target, 199.0) is True
        assert AsyncRedisSLOTracker._check_compliance(target, 201.0) is False

    def test_throughput_compliance(self):
        from obskit.slo.types import SLOTarget, SLOType

        target = SLOTarget(slo_type=SLOType.THROUGHPUT, target_value=100.0)
        assert AsyncRedisSLOTracker._check_compliance(target, 100.0) is True
        assert AsyncRedisSLOTracker._check_compliance(target, 99.0) is False

    def test_error_budget_availability(self):
        from obskit.slo.types import SLOTarget, SLOType

        target = SLOTarget(slo_type=SLOType.AVAILABILITY, target_value=0.99)
        remaining, burn_rate = AsyncRedisSLOTracker._calculate_error_budget(target, 0.99)
        assert remaining == pytest.approx(0.0)
        assert burn_rate == pytest.approx(1.0)

    def test_error_budget_availability_unused(self):
        from obskit.slo.types import SLOTarget, SLOType

        target = SLOTarget(slo_type=SLOType.AVAILABILITY, target_value=0.99)
        remaining, burn_rate = AsyncRedisSLOTracker._calculate_error_budget(target, 1.0)
        assert remaining == pytest.approx(0.01)
        assert burn_rate == pytest.approx(0.0)

    def test_error_budget_error_rate(self):
        from obskit.slo.types import SLOTarget, SLOType

        target = SLOTarget(slo_type=SLOType.ERROR_RATE, target_value=0.05)
        remaining, burn_rate = AsyncRedisSLOTracker._calculate_error_budget(target, 0.025)
        assert remaining == pytest.approx(0.025)
        assert burn_rate == pytest.approx(0.5)

    def test_error_budget_latency_throughput_returns_defaults(self):
        from obskit.slo.types import SLOTarget, SLOType

        for slo_type, extra in [
            (SLOType.LATENCY, {"percentile": 99}),
            (SLOType.THROUGHPUT, {}),
        ]:
            target = SLOTarget(slo_type=slo_type, target_value=200.0, **extra)
            remaining, burn_rate = AsyncRedisSLOTracker._calculate_error_budget(target, 150.0)
            assert remaining == pytest.approx(1.0)
            assert burn_rate == pytest.approx(0.0)


class TestDecodeHelper:
    """Tests for the _decode() bytes/str helper."""

    def test_decode_str_passthrough(self):
        from obskit.slo.redis_tracker import _decode

        assert _decode("hello:world") == "hello:world"

    def test_decode_bytes_to_str(self):
        from obskit.slo.redis_tracker import _decode

        assert _decode(b"150.0:uid123") == "150.0:uid123"


class TestKeyNaming:
    """Key format and custom prefix tests."""

    def test_default_prefix_and_service(self):
        tracker = AsyncRedisSLOTracker(MagicMock())
        assert tracker._key("my_slo", "total") == "obskit:slo:default:my_slo:total"
        assert tracker._key("my_slo", "success") == "obskit:slo:default:my_slo:success"
        assert tracker._key("my_slo", "latencies") == "obskit:slo:default:my_slo:latencies"

    def test_custom_prefix_and_service(self):
        tracker = AsyncRedisSLOTracker(MagicMock(), service="checkout", key_prefix="myapp:slos")
        assert tracker._key("avail", "total") == "myapp:slos:checkout:avail:total"

    @pytest.mark.asyncio
    async def test_record_uses_correct_key(self):
        r = MagicMock()
        r.zadd = AsyncMock(return_value=1)
        r.zremrangebyscore = AsyncMock(return_value=0)
        r.expire = AsyncMock(return_value=True)

        tracker = AsyncRedisSLOTracker(r, service="svc", key_prefix="ns")
        tracker.register_slo("avail", SLOType.AVAILABILITY, target_value=0.99)
        await tracker.record_measurement("avail", value=1.0, success=True)

        keys = [c.args[0] for c in r.zadd.call_args_list]
        assert "ns:svc:avail:total" in keys
        assert "ns:svc:avail:success" in keys


class TestRegisterOverwrite:
    """Re-registering an SLO replaces the previous target."""

    def test_register_overwrites_existing(self):
        tracker = AsyncRedisSLOTracker(MagicMock())
        tracker.register_slo("avail", SLOType.AVAILABILITY, target_value=0.99)
        tracker.register_slo("avail", SLOType.AVAILABILITY, target_value=0.999, window_seconds=7200)

        t = tracker._targets["avail"]
        assert t.target_value == pytest.approx(0.999)
        assert t.window_seconds == 7200


class TestThroughputEdgeCases:
    """Edge cases for THROUGHPUT computation."""

    @pytest.mark.asyncio
    async def test_throughput_same_timestamps_returns_zero(self):
        """When all measurements have the same timestamp, time_span=0 → rate=0."""
        import time

        now = time.time()
        members = [(f"uid{i}", now) for i in range(5)]  # all at same timestamp

        r = MagicMock()
        r.zrangebyscore = AsyncMock(return_value=members)

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("tput", SLOType.THROUGHPUT, target_value=10.0)

        status = await tracker.get_status("tput")
        assert status.current_value == pytest.approx(0.0)

    @pytest.mark.asyncio
    async def test_throughput_two_measurements_computes_rate(self):
        """Minimum viable throughput: 2 measurements, known time span."""
        import time

        now = time.time()
        members = [("uid0", now - 2.0), ("uid1", now)]  # 2 events over 2 s = 1 req/s

        r = MagicMock()
        r.zrangebyscore = AsyncMock(return_value=members)

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("tput", SLOType.THROUGHPUT, target_value=0.5)

        status = await tracker.get_status("tput")
        assert status.current_value == pytest.approx(1.0)
        assert status.compliance is True


class TestSLOStatusFields:
    """Verify SLOStatus fields populated correctly by the Redis tracker."""

    @pytest.mark.asyncio
    async def test_status_has_window_timestamps(self):
        from datetime import UTC, datetime

        async def _zcount(key, *a, **kw):
            return 100 if "success" in key else 100

        r = MagicMock()
        r.zcount = _zcount

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("avail", SLOType.AVAILABILITY, target_value=0.99, window_seconds=600)

        before = datetime.now(UTC)
        status = await tracker.get_status("avail")
        after = datetime.now(UTC)

        assert before <= status.window_end <= after
        assert (status.window_end - status.window_start).total_seconds() == pytest.approx(600, abs=1)

    @pytest.mark.asyncio
    async def test_status_to_dict_round_trip(self):
        async def _zcount(key, *a, **kw):
            return 50

        r = MagicMock()
        r.zcount = _zcount

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("avail", SLOType.AVAILABILITY, target_value=0.99)

        status = await tracker.get_status("avail")
        d = status.to_dict()

        assert d["slo_type"] == "availability"
        assert d["target_value"] == pytest.approx(0.99)
        assert d["measurement_count"] == 50
        assert "window_start" in d
        assert "window_end" in d


class TestLatencyPercentileEdges:
    """P50 and P100 percentile edge cases."""

    @pytest.mark.asyncio
    async def test_p50_latency(self):
        """P50 of [10, 20, 30, 40, 50] = 30."""
        members = [f"{v}.0:uid{v}" for v in [10, 20, 30, 40, 50]]

        r = MagicMock()
        r.zrangebyscore = AsyncMock(return_value=members)

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("lat", SLOType.LATENCY, target_value=40.0, percentile=50)

        status = await tracker.get_status("lat")
        assert status.current_value == pytest.approx(30.0)
        assert status.compliance is True

    @pytest.mark.asyncio
    async def test_p100_returns_max(self):
        """P100 returns the maximum value."""
        members = ["10.0:uid1", "50.0:uid2", "200.0:uid3"]

        r = MagicMock()
        r.zrangebyscore = AsyncMock(return_value=members)

        tracker = AsyncRedisSLOTracker(r)
        tracker.register_slo("lat", SLOType.LATENCY, target_value=300.0, percentile=100)

        status = await tracker.get_status("lat")
        assert status.current_value == pytest.approx(200.0)
