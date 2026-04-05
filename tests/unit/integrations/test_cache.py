"""Unit tests for obskit.integrations.cache — Redis instrumentation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestInstrumentRedis:
    def test_returns_instrumented_redis(self):
        from obskit.integrations.cache import InstrumentedRedis, instrument_redis

        client = MagicMock()
        wrapped = instrument_redis(client, name="test-cache")
        assert isinstance(wrapped, InstrumentedRedis)

    def test_default_name(self):
        from obskit.integrations.cache import InstrumentedRedis, instrument_redis

        wrapped = instrument_redis(MagicMock())
        assert isinstance(wrapped, InstrumentedRedis)
        assert wrapped._name == "default"

    def test_stores_name(self):
        from obskit.integrations.cache import instrument_redis

        wrapped = instrument_redis(MagicMock(), name="my-cache")
        assert wrapped._name == "my-cache"

    def test_non_async_attrs_passed_through(self):
        """Sync attributes are returned unchanged without wrapping."""
        from obskit.integrations.cache import instrument_redis

        client = MagicMock()
        client.sync_attr = "hello"
        wrapped = instrument_redis(client, name="t")
        assert wrapped.sync_attr == "hello"

    def test_non_callable_passed_through(self):
        from obskit.integrations.cache import instrument_redis

        client = MagicMock()
        client.connection_pool = object()
        wrapped = instrument_redis(client, name="t")
        # Should not raise and should return the pool
        pool = wrapped.connection_pool
        assert pool is client.connection_pool


class TestInstrumentedRedisAsync:
    @pytest.mark.asyncio
    async def test_async_command_success_increments_counter(self):
        from obskit.integrations.cache import (
            REDIS_COMMANDS_TOTAL,
            instrument_redis,
        )

        client = MagicMock()
        client.get = AsyncMock(return_value="val")
        wrapped = instrument_redis(client, name="c1")

        before = REDIS_COMMANDS_TOTAL.labels(name="c1", command="get", status="success")._value.get()
        await wrapped.get("key")
        after = REDIS_COMMANDS_TOTAL.labels(name="c1", command="get", status="success")._value.get()
        assert after == before + 1.0

    @pytest.mark.asyncio
    async def test_async_command_error_increments_error_counter(self):
        from obskit.integrations.cache import (
            REDIS_COMMANDS_TOTAL,
            instrument_redis,
        )

        client = MagicMock()
        client.get = AsyncMock(side_effect=ConnectionError("down"))
        wrapped = instrument_redis(client, name="c2")

        before = REDIS_COMMANDS_TOTAL.labels(name="c2", command="get", status="error")._value.get()
        with pytest.raises(ConnectionError):
            await wrapped.get("key")
        after = REDIS_COMMANDS_TOTAL.labels(name="c2", command="get", status="error")._value.get()
        assert after == before + 1.0

    @pytest.mark.asyncio
    async def test_async_command_records_duration(self):
        from obskit.integrations.cache import (
            REDIS_COMMAND_DURATION_SECONDS,
            instrument_redis,
        )

        client = MagicMock()
        client.set = AsyncMock(return_value=True)
        wrapped = instrument_redis(client, name="c3")

        hist = REDIS_COMMAND_DURATION_SECONDS.labels(name="c3", command="set")
        before_count = hist._sum.get()
        await wrapped.set("k", "v")
        after_count = hist._sum.get()
        assert after_count > before_count

    @pytest.mark.asyncio
    async def test_result_passed_through(self):
        from obskit.integrations.cache import instrument_redis

        client = MagicMock()
        client.hget = AsyncMock(return_value=b"data")
        wrapped = instrument_redis(client, name="c4")

        result = await wrapped.hget("myhash", "field")
        assert result == b"data"

    @pytest.mark.asyncio
    async def test_multiple_different_commands(self):
        from obskit.integrations.cache import (
            REDIS_COMMANDS_TOTAL,
            instrument_redis,
        )

        client = MagicMock()
        client.get = AsyncMock(return_value=None)
        client.set = AsyncMock(return_value=True)
        client.delete = AsyncMock(return_value=1)
        wrapped = instrument_redis(client, name="c5")

        await wrapped.get("k")
        await wrapped.set("k", "v")
        await wrapped.delete("k")

        assert REDIS_COMMANDS_TOTAL.labels(name="c5", command="get", status="success")._value.get() >= 1.0
        assert REDIS_COMMANDS_TOTAL.labels(name="c5", command="set", status="success")._value.get() >= 1.0
        assert REDIS_COMMANDS_TOTAL.labels(name="c5", command="delete", status="success")._value.get() >= 1.0


class TestInstrumentRedisClient:
    def test_returns_instrumented_redis(self):
        from obskit.integrations.cache import InstrumentedRedis, instrument_redis_client

        client = MagicMock()
        wrapped = instrument_redis_client(client, name="rc-basic")
        assert isinstance(wrapped, InstrumentedRedis)

    def test_default_name(self):
        from obskit.integrations.cache import instrument_redis_client

        wrapped = instrument_redis_client(MagicMock())
        assert wrapped._name == "default"

    def test_stores_name(self):
        from obskit.integrations.cache import instrument_redis_client

        wrapped = instrument_redis_client(MagicMock(), name="engagement-cache")
        assert wrapped._name == "engagement-cache"

    def test_stores_client_reference(self):
        from obskit.integrations.cache import instrument_redis_client

        client = MagicMock()
        wrapped = instrument_redis_client(client, name="rc-ref")
        assert wrapped._client is client

    @pytest.mark.asyncio
    async def test_error_increments_dedicated_error_counter(self):
        from obskit.integrations.cache import (
            REDIS_COMMAND_ERRORS_TOTAL,
            instrument_redis_client,
        )

        client = MagicMock()
        client.get = AsyncMock(side_effect=ConnectionError("down"))
        wrapped = instrument_redis_client(client, name="rc_err")

        before = REDIS_COMMAND_ERRORS_TOTAL.labels(
            name="rc_err", command="get"
        )._value.get()
        with pytest.raises(ConnectionError):
            await wrapped.get("key")
        after = REDIS_COMMAND_ERRORS_TOTAL.labels(
            name="rc_err", command="get"
        )._value.get()
        assert after == before + 1.0

    @pytest.mark.asyncio
    async def test_success_does_not_increment_error_counter(self):
        from obskit.integrations.cache import (
            REDIS_COMMAND_ERRORS_TOTAL,
            instrument_redis_client,
        )

        client = MagicMock()
        client.get = AsyncMock(return_value="val")
        wrapped = instrument_redis_client(client, name="rc_ok")

        before = REDIS_COMMAND_ERRORS_TOTAL.labels(
            name="rc_ok", command="get"
        )._value.get()
        await wrapped.get("key")
        after = REDIS_COMMAND_ERRORS_TOTAL.labels(
            name="rc_ok", command="get"
        )._value.get()
        assert after == before

    @pytest.mark.asyncio
    async def test_duration_recorded(self):
        from obskit.integrations.cache import (
            REDIS_COMMAND_DURATION_SECONDS,
            instrument_redis_client,
        )

        client = MagicMock()
        client.set = AsyncMock(return_value=True)
        wrapped = instrument_redis_client(client, name="rc_dur")

        hist = REDIS_COMMAND_DURATION_SECONDS.labels(name="rc_dur", command="set")
        before = hist._sum.get()
        await wrapped.set("k", "v")
        after = hist._sum.get()
        assert after > before


class TestRedisCommandErrorsTotal:
    @pytest.mark.asyncio
    async def test_errors_total_incremented_via_instrument_redis(self):
        """REDIS_COMMAND_ERRORS_TOTAL is also emitted by the original instrument_redis."""
        from obskit.integrations.cache import (
            REDIS_COMMAND_ERRORS_TOTAL,
            instrument_redis,
        )

        client = MagicMock()
        client.hset = AsyncMock(side_effect=RuntimeError("redis error"))
        wrapped = instrument_redis(client, name="ir_err")

        before = REDIS_COMMAND_ERRORS_TOTAL.labels(
            name="ir_err", command="hset"
        )._value.get()
        with pytest.raises(RuntimeError):
            await wrapped.hset("h", "f", "v")
        after = REDIS_COMMAND_ERRORS_TOTAL.labels(
            name="ir_err", command="hset"
        )._value.get()
        assert after == before + 1.0

    @pytest.mark.asyncio
    async def test_errors_total_not_incremented_on_success(self):
        from obskit.integrations.cache import (
            REDIS_COMMAND_ERRORS_TOTAL,
            instrument_redis,
        )

        client = MagicMock()
        client.get = AsyncMock(return_value="ok")
        wrapped = instrument_redis(client, name="ir_ok2")

        before = REDIS_COMMAND_ERRORS_TOTAL.labels(
            name="ir_ok2", command="get"
        )._value.get()
        await wrapped.get("k")
        after = REDIS_COMMAND_ERRORS_TOTAL.labels(
            name="ir_ok2", command="get"
        )._value.get()
        assert after == before


class TestUpdatePoolStats:
    def test_pool_stats_updated(self):
        from obskit.integrations.cache import REDIS_POOL_CONNECTIONS, instrument_redis

        pool = MagicMock()
        pool._available_connections = ["c1", "c2", "c3"]
        pool._in_use_connections = {"c4"}

        client = MagicMock()
        client.connection_pool = pool
        wrapped = instrument_redis(client, name="pool-test")

        wrapped.update_pool_stats()

        avail = REDIS_POOL_CONNECTIONS.labels(name="pool-test", state="available")._value.get()
        in_use = REDIS_POOL_CONNECTIONS.labels(name="pool-test", state="in_use")._value.get()
        assert avail == 3.0
        assert in_use == 1.0

    def test_pool_stats_no_pool_attr(self):
        """update_pool_stats() is a no-op when there is no connection_pool."""
        from obskit.integrations.cache import instrument_redis

        client = MagicMock(spec=[])  # no connection_pool
        wrapped = instrument_redis(client, name="no-pool")
        # Should not raise
        wrapped.update_pool_stats()

    def test_pool_stats_missing_internal_attrs(self):
        """update_pool_stats() handles pools that lack _available/_in_use attrs."""
        from obskit.integrations.cache import instrument_redis

        pool = MagicMock(spec=[])  # no _available_connections / _in_use_connections
        client = MagicMock()
        client.connection_pool = pool
        wrapped = instrument_redis(client, name="sparse-pool")
        # Should not raise
        wrapped.update_pool_stats()
