"""Additional coverage tests for debug/replay.py."""
from __future__ import annotations

import asyncio
import gzip
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from obskit.debug.replay import (
    CapturedRequest,
    FileStorage,
    MemoryStorage,
    RequestCapture,
    RequestCaptureStorage,
    _deserialize,
    _serialize,
)


class TestSerializeCoverage:
    def test_serialize_none(self):
        """Line 78: _serialize(None) returns None."""
        assert _serialize(None) is None

    def test_serialize_object_with_dict(self):
        """Lines 85-86: object with __dict__ is serialized."""
        class MyObj:
            def __init__(self):
                self.x = 1
                self.y = "hello"

        obj = MyObj()
        result = _serialize(obj)
        assert isinstance(result, dict)
        assert result["__class__"] == "MyObj"
        assert "__dict__" in result

    def test_serialize_fallback_to_str(self):
        """Lines 87-88: objects without __dict__ fallback to str()."""
        # frozenset has no __dict__
        fs = frozenset([1, 2, 3])
        result = _serialize(fs)
        assert isinstance(result, str)


class TestDeserializeCoverage:
    def test_deserialize_none(self):
        """Line 96: _deserialize(None) returns None."""
        assert _deserialize(None) is None

    def test_deserialize_class_dict(self):
        """Line 104: deserialize object with __class__ and __dict__ keys."""
        serialized = {"__class__": "MyObj", "__dict__": {"x": 1}}
        result = _deserialize(serialized)
        assert result == {"x": 1}

    def test_deserialize_non_dict_non_list(self):
        """Line 106: return raw value when not dict/list/None."""
        result = _deserialize(42.5)
        assert result == pytest.approx(42.5)


class TestRequestCaptureStorageAbstract:
    """Test that base class abstract methods raise NotImplementedError."""

    @pytest.mark.asyncio
    async def test_save_raises(self):
        storage = RequestCaptureStorage()
        with pytest.raises(NotImplementedError):
            await storage.save(None)

    @pytest.mark.asyncio
    async def test_load_raises(self):
        storage = RequestCaptureStorage()
        with pytest.raises(NotImplementedError):
            await storage.load("any-id")

    @pytest.mark.asyncio
    async def test_list_captures_raises(self):
        storage = RequestCaptureStorage()
        with pytest.raises(NotImplementedError):
            await storage.list_captures()

    @pytest.mark.asyncio
    async def test_delete_raises(self):
        storage = RequestCaptureStorage()
        with pytest.raises(NotImplementedError):
            await storage.delete("any-id")


class TestFileStorageCoverage:
    @pytest.mark.asyncio
    async def test_load_returns_none_when_neither_extension_exists(self):
        """Line 166: primary path doesn't exist, secondary path also doesn't -> None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_path=tmpdir, compress=False)
            result = await storage.load("nonexistent-capture")
            assert result is None

    @pytest.mark.asyncio
    async def test_load_exception_returns_none(self):
        """Lines 177-179: exception during load returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_path=tmpdir, compress=False)
            # Create a file with invalid JSON
            path = Path(tmpdir) / "bad-capture.json"
            path.write_text("not valid json")
            result = await storage.load("bad-capture")
            assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self):
        """Line 213: delete of nonexistent file returns False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_path=tmpdir)
            result = await storage.delete("does-not-exist")
            assert result is False

    @pytest.mark.asyncio
    async def test_list_captures_with_function_name_filter(self):
        """Lines 184-206: list_captures with function_name filter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_path=tmpdir, compress=False)

            cap1 = CapturedRequest(
                capture_id="c1", function_name="func_a", module="m",
                args=(), kwargs={}, timestamp=time.time()
            )
            cap2 = CapturedRequest(
                capture_id="c2", function_name="func_b", module="m",
                args=(), kwargs={}, timestamp=time.time() + 1
            )
            await storage.save(cap1)
            await storage.save(cap2)

            results = await storage.list_captures(function_name="func_a")
            assert "c1" in results
            assert "c2" not in results

    @pytest.mark.asyncio
    async def test_list_captures_with_since_filter(self):
        """Lines 201-202: list_captures with since filter skips old captures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_path=tmpdir, compress=False)

            cap = CapturedRequest(
                capture_id="old-cap", function_name="func", module="m",
                args=(), kwargs={}, timestamp=1000.0  # very old
            )
            await storage.save(cap)

            results = await storage.list_captures(since=time.time())
            assert "old-cap" not in results

    @pytest.mark.asyncio
    async def test_list_captures_respects_limit(self):
        """Line 188: list_captures stops at limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_path=tmpdir, compress=False)

            for i in range(5):
                cap = CapturedRequest(
                    capture_id=f"cap-{i}", function_name="func", module="m",
                    args=(), kwargs={}, timestamp=time.time() + i
                )
                await storage.save(cap)

            results = await storage.list_captures(limit=2)
            assert len(results) <= 2


class TestMemoryStorageCoverage:
    @pytest.mark.asyncio
    async def test_list_captures_since_filter(self):
        """Line 249: since filter skips old captures."""
        storage = MemoryStorage()

        old_cap = CapturedRequest(
            capture_id="old", function_name="func", module="m",
            args=(), kwargs={}, timestamp=1000.0
        )
        await storage.save(old_cap)

        results = await storage.list_captures(since=time.time())
        assert "old" not in results


class TestRequestCaptureCoverage:
    @pytest.mark.asyncio
    async def test_truncate_args_large_args(self):
        """Lines 336-344: _truncate_args truncates large arguments."""
        storage = MemoryStorage()
        capture = RequestCapture(storage=storage, max_arg_size=10)

        # Create args that are larger than max size
        large_arg = "x" * 10000
        truncated_args, _ = capture._truncate_args((large_arg,), {})

        # Should be truncated
        assert any(isinstance(a, str) and "truncated" in a for a in truncated_args)

    @pytest.mark.asyncio
    async def test_capture_with_metadata_extractor(self):
        """Lines 370-374: metadata extractor is called."""
        storage = MemoryStorage()
        metadata_captured = []

        def extractor(arg):
            metadata_captured.append(arg)
            return {"extracted": True}

        capture = RequestCapture(storage=storage, metadata_extractor=extractor)

        async def my_func(data):  # NOSONAR
            return data

        cap_id = await capture.capture(my_func, args=("test_data",), kwargs={})
        loaded = await storage.load(cap_id)
        assert loaded.metadata.get("extracted") is True

    @pytest.mark.asyncio
    async def test_capture_with_metadata_extractor_exception(self):
        """Lines 373-374: metadata extractor exception is silently ignored."""
        storage = MemoryStorage()

        def failing_extractor(arg):
            raise RuntimeError("extraction failed")

        capture = RequestCapture(storage=storage, metadata_extractor=failing_extractor)

        async def my_func(data):  # NOSONAR
            return data

        # Should not raise
        cap_id = await capture.capture(my_func, args=("data",), kwargs={})
        assert cap_id is not None

    @pytest.mark.asyncio
    async def test_replay_not_in_registry_returns_error(self):
        """Lines 436-440: function not in registry returns error dict."""
        storage = MemoryStorage()
        capture = RequestCapture(storage=storage)

        cap = CapturedRequest(
            capture_id="test-reg", function_name="unregistered_func",
            module="nonexistent_module", args=(), kwargs={}, timestamp=time.time()
        )
        await storage.save(cap)

        result = await capture.replay("test-reg")
        assert result["success"] is False
        assert "not in registry" in result["error"]

    @pytest.mark.asyncio
    async def test_replay_sync_function_via_replay(self):
        """Line 448: replay calls sync function."""
        storage = MemoryStorage()
        capture = RequestCapture(storage=storage)

        def sync_func(x, y):
            return x + y

        cap = CapturedRequest(
            capture_id="sync-test", function_name="sync_func",
            module=sync_func.__module__, args=(1, 2), kwargs={}, timestamp=time.time()
        )
        await storage.save(cap)

        result = await capture.replay("sync-test", func=sync_func)
        assert result["success"] is True
        assert result["output"] == 3

    @pytest.mark.asyncio
    async def test_replay_function_exception(self):
        """Lines 458-467: exception during replay is captured."""
        storage = MemoryStorage()
        capture = RequestCapture(storage=storage)

        def failing_func():
            raise ValueError("replay error")

        cap = CapturedRequest(
            capture_id="fail-test", function_name="failing_func",
            module="__main__", args=(), kwargs={}, timestamp=time.time()
        )
        await storage.save(cap)

        result = await capture.replay("fail-test", func=failing_func)
        assert result["success"] is False
        assert "replay error" in result["error"]
        assert result["error_type"] == "ValueError"

    @pytest.mark.asyncio
    async def test_wrap_passes_through_when_not_capturing(self):
        """Lines 515-517: wrap passes through when _should_capture() is False."""
        storage = MemoryStorage()
        capture = RequestCapture(storage=storage, capture_sample_rate=0.0)

        @capture.wrap
        async def my_async_func(x):
            return x * 2

        result = await my_async_func(5)
        assert result == 10

    def test_wrap_sync_function_passes_through_when_not_capturing(self):
        """Lines 544-554: wrap sync function that passes through via sync_wrapper."""
        storage = MemoryStorage()
        capture = RequestCapture(storage=storage, capture_sample_rate=0.0)

        @capture.wrap
        def sync_func(x):
            return x + 1

        result = sync_func(4)
        assert result == 5

    def test_wrap_sync_function_return_value(self):
        """Lines 525, 546-554: wrap sync function that runs via event loop."""
        storage = MemoryStorage()
        capture = RequestCapture(storage=storage, capture_sample_rate=1.0, capture_on_error=False)

        @capture.wrap
        def sync_func(x):
            return x * 3

        result = sync_func(3)
        assert result == 9


class TestSerializeCoverageExtra:
    def test_serialize_object_str_raises(self):
        """Lines 89-90: when str(obj) raises, return unserializable marker."""
        from obskit.debug.replay import _serialize

        class Unserializable:
            def __str__(self):
                raise RuntimeError('cannot stringify')
            # Remove __dict__ so we go through the try/str path
            __slots__ = []

        obj = Unserializable()
        result = _serialize(obj)
        assert 'unserializable' in result

    def test_deserialize_non_dict_non_list_non_none(self):
        """Line 106: _deserialize returns raw value for non-dict/list/None types."""
        from obskit.debug.replay import _deserialize

        # An integer that's not None, not list, not dict
        result = _deserialize(42)
        assert result == 42

        result = _deserialize(3.14)
        assert abs(result - 3.14) < 0.001


class TestFileStorageCoverageExtra:
    @pytest.mark.asyncio
    async def test_load_tries_other_extension(self):
        """Line 165-167: when primary path doesn't exist, tries other extension."""
        import tempfile
        import time
        from pathlib import Path

        from obskit.debug.replay import CapturedRequest, FileStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            # compress=False -> primary is .json, other is .json.gz
            storage = FileStorage(base_path=tmpdir, compress=False)

            # Save with compress=True storage (creates .json.gz)
            gz_storage = FileStorage(base_path=tmpdir, compress=True)
            cap = CapturedRequest(
                capture_id='ext-test', function_name='func', module='m',
                args=(), kwargs={}, timestamp=time.time()
            )
            await gz_storage.save(cap)

            # Now load with compress=False (primary .json doesn't exist, should find .json.gz)
            result = await storage.load('ext-test')
            assert result is not None
            assert result.capture_id == 'ext-test'

    @pytest.mark.asyncio
    async def test_list_captures_skips_non_json_files(self):
        """Line 191: files not ending in .json or .json.gz are skipped."""
        import tempfile
        from pathlib import Path

        from obskit.debug.replay import FileStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a non-JSON file
            (Path(tmpdir) / 'random_file.txt').write_text('not a capture')
            (Path(tmpdir) / 'another.log').write_text('log data')

            storage = FileStorage(base_path=tmpdir, compress=False)
            results = await storage.list_captures()
            # Should return empty since no json files
            assert results == []


class TestMemoryStorageCoverageExtra:
    @pytest.mark.asyncio
    async def test_list_captures_function_name_filter_no_match(self):
        """Lines 199-200: function_name filter skips non-matching captures."""
        import time

        from obskit.debug.replay import CapturedRequest, MemoryStorage

        storage = MemoryStorage()

        cap1 = CapturedRequest(
            capture_id='fn-match', function_name='matching_func', module='m',
            args=(), kwargs={}, timestamp=time.time()
        )
        cap2 = CapturedRequest(
            capture_id='fn-no-match', function_name='other_func', module='m',
            args=(), kwargs={}, timestamp=time.time()
        )
        await storage.save(cap1)
        await storage.save(cap2)

        results = await storage.list_captures(function_name='matching_func')
        assert 'fn-match' in results
        assert 'fn-no-match' not in results


class TestRequestCaptureCoverageExtra:
    @pytest.mark.asyncio
    async def test_capture_metadata_extractor_with_empty_args(self):
        """Lines 371-372: metadata_extractor not called when args is empty."""
        import time

        from obskit.debug.replay import MemoryStorage, RequestCapture

        storage = MemoryStorage()
        extractor_calls = []

        def extractor(arg):
            extractor_calls.append(arg)
            return {'extracted': True}

        capture = RequestCapture(storage=storage, metadata_extractor=extractor)

        async def func_no_args():  # NOSONAR
            return 42

        cap_id = await capture.capture(func_no_args, args=(), kwargs={})
        # extractor not called because args is empty
        assert len(extractor_calls) == 0
        assert cap_id is not None

    @pytest.mark.asyncio
    async def test_list_captures_with_load_returning_none(self):
        """Lines 481-482: list_captures skips captures that can't be loaded."""
        import time
        from unittest.mock import AsyncMock

        from obskit.debug.replay import MemoryStorage, RequestCapture

        storage = MemoryStorage()
        cap = __import__('obskit.debug.replay', fromlist=['CapturedRequest']).CapturedRequest(
            capture_id='load-none', function_name='func', module='m',
            args=(), kwargs={}, timestamp=time.time()
        )
        await storage.save(cap)

        capture_system = RequestCapture(storage=storage)

        # Mock storage.list_captures to return ID, but storage.load to return None
        async def mock_load(cid):  # NOSONAR
            return None

        with patch.object(storage, 'load', side_effect=mock_load):
            result = await capture_system.list_captures()

        assert result == []

    @pytest.mark.asyncio
    async def test_wrap_async_captures_on_error(self):
        """Lines 538-541: wrapped async func captures error and re-raises."""
        import time

        from obskit.debug.replay import MemoryStorage, RequestCapture

        storage = MemoryStorage()
        capture = RequestCapture(
            storage=storage,
            capture_on_error=True,
            capture_sample_rate=1.0
        )

        @capture.wrap
        async def failing_async(x):
            raise ValueError(f'error: {x}')

        with pytest.raises(ValueError):
            await failing_async('test')

        # Should have captured the error
        captures = list(storage._captures.values())
        assert len(captures) >= 1
        assert captures[0].error is not None


class TestRemainingReplayCoverage:
    """Cover remaining uncovered lines in replay.py."""

    def test_deserialize_returns_raw_obj_for_primitive(self):
        """Line 106: _deserialize returns raw value for non-dict/list/None types (bool/int)."""
        from obskit.debug.replay import _deserialize
        # bool is a subclass of int, not dict/list/None
        assert _deserialize(True) is True
        assert _deserialize(False) is False

    @pytest.mark.asyncio
    async def test_file_storage_delete_existing_file(self):
        """Lines 211-212: delete existing file returns True."""
        import tempfile
        import time

        from obskit.debug.replay import CapturedRequest, FileStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_path=tmpdir, compress=False)
            cap = CapturedRequest(
                capture_id='del-test', function_name='func', module='m',
                args=(), kwargs={}, timestamp=time.time()
            )
            await storage.save(cap)
            result = await storage.delete('del-test')
            assert result is True

    @pytest.mark.asyncio
    async def test_memory_storage_evicts_oldest_when_at_limit(self):
        """Lines 226-227: MemoryStorage evicts oldest capture when at max_captures."""
        import time

        from obskit.debug.replay import CapturedRequest, MemoryStorage

        storage = MemoryStorage(max_captures=2)

        # Add 2 captures to reach the limit
        for i in range(2):
            cap = CapturedRequest(
                capture_id=f'cap-{i}', function_name='func', module='m',
                args=(), kwargs={}, timestamp=float(i + 1)
            )
            await storage.save(cap)

        assert len(storage._captures) == 2

        # Adding a 3rd should evict the oldest
        cap3 = CapturedRequest(
            capture_id='cap-new', function_name='func', module='m',
            args=(), kwargs={}, timestamp=100.0
        )
        await storage.save(cap3)

        # Still at 2 captures
        assert len(storage._captures) == 2
        # The oldest (cap-0 with timestamp=1) should be evicted
        assert 'cap-0' not in storage._captures
        assert 'cap-new' in storage._captures

    @pytest.mark.asyncio
    async def test_memory_storage_list_captures_limit_break(self):
        """Line 244: list_captures break when limit reached."""
        import time

        from obskit.debug.replay import CapturedRequest, MemoryStorage

        storage = MemoryStorage()
        for i in range(10):
            cap = CapturedRequest(
                capture_id=f'mem-cap-{i}', function_name='func', module='m',
                args=(), kwargs={}, timestamp=float(i + 1)
            )
            await storage.save(cap)

        results = await storage.list_captures(limit=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_memory_storage_delete_existing(self):
        """Lines 256-258: delete existing key in MemoryStorage returns True."""
        import time

        from obskit.debug.replay import CapturedRequest, MemoryStorage

        storage = MemoryStorage()
        cap = CapturedRequest(
            capture_id='del-mem', function_name='func', module='m',
            args=(), kwargs={}, timestamp=time.time()
        )
        await storage.save(cap)
        result = await storage.delete('del-mem')
        assert result is True
        assert 'del-mem' not in storage._captures

    @pytest.mark.asyncio
    async def test_replay_dry_run(self):
        """Lines 429-432: dry_run=True returns metadata without executing."""
        import time

        from obskit.debug.replay import CapturedRequest, MemoryStorage, RequestCapture

        storage = MemoryStorage()
        capture = RequestCapture(storage=storage)

        cap = CapturedRequest(
            capture_id='dry-run-test', function_name='func', module='m',
            args=(1, 2), kwargs={'z': 3}, timestamp=time.time()
        )
        await storage.save(cap)

        result = await capture.replay('dry-run-test', dry_run=True)
        assert result['success'] is True
        assert result['args'] == (1, 2)
        assert result['dry_run'] is True

    @pytest.mark.asyncio
    async def test_replay_async_function(self):
        """Line 446: replay calls async function."""
        import time

        from obskit.debug.replay import CapturedRequest, MemoryStorage, RequestCapture

        storage = MemoryStorage()
        capture = RequestCapture(storage=storage)

        async def async_add(x, y):  # NOSONAR
            return x + y

        cap = CapturedRequest(
            capture_id='async-replay', function_name='async_add', module='__main__',
            args=(3, 4), kwargs={}, timestamp=time.time()
        )
        await storage.save(cap)

        result = await capture.replay('async-replay', func=async_add)
        assert result['success'] is True
        assert result['output'] == 7

    @pytest.mark.asyncio
    async def test_list_captures_appends_valid_captures(self):
        """Lines 483-491: list_captures appends loaded captures."""
        import time

        from obskit.debug.replay import CapturedRequest, MemoryStorage, RequestCapture

        storage = MemoryStorage()
        cap = CapturedRequest(
            capture_id='lc-valid', function_name='func', module='m',
            args=(), kwargs={}, timestamp=time.time()
        )
        await storage.save(cap)

        capture_system = RequestCapture(storage=storage)
        result = await capture_system.list_captures()
        assert len(result) == 1
        assert result[0]['capture_id'] == 'lc-valid'

    @pytest.mark.asyncio
    async def test_delete_capture_delegates_to_storage(self):
        """Line 497: delete_capture delegates to storage.delete."""
        import time

        from obskit.debug.replay import CapturedRequest, MemoryStorage, RequestCapture

        storage = MemoryStorage()
        cap = CapturedRequest(
            capture_id='dc-test', function_name='func', module='m',
            args=(), kwargs={}, timestamp=time.time()
        )
        await storage.save(cap)

        capture_system = RequestCapture(storage=storage)
        result = await capture_system.delete_capture('dc-test')
        assert result is True

    @pytest.mark.asyncio
    async def test_wrap_captures_slow_requests(self):
        """Line 531: wrap captures slow requests."""
        import time

        from obskit.debug.replay import MemoryStorage, RequestCapture

        storage = MemoryStorage()
        capture = RequestCapture(
            storage=storage,
            capture_on_slow=True,
            slow_threshold_seconds=0.0,  # Always capture as slow
            capture_sample_rate=1.0,
            capture_on_error=False,
        )

        @capture.wrap
        async def slow_async_func(x):
            return x

        result = await slow_async_func(42)
        assert result == 42

        # Should have a capture due to slow threshold=0.0
        assert len(storage._captures) >= 1


class TestFinalReplayCoverage:
    """Final tests to hit the last missing lines."""

    def test_deserialize_non_standard_type(self):
        """Line 106: _deserialize returns raw object for non-standard types."""
        from obskit.debug.replay import _deserialize

        # A custom object that is not None, str, int, float, bool, list, or dict
        class CustomType:
            pass  # NOSONAR

        obj = CustomType()
        result = _deserialize(obj)
        assert result is obj

    @pytest.mark.asyncio
    async def test_file_storage_list_captures_filter_with_none_load(self):
        """Line 198->204 branch: when filter is active and load returns None, still appends capture_id."""
        import tempfile
        import time
        from pathlib import Path

        from obskit.debug.replay import CapturedRequest, FileStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_path=tmpdir, compress=False)

            # Create a valid capture file
            cap = CapturedRequest(
                capture_id='filter-none-test', function_name='func', module='m',
                args=(), kwargs={}, timestamp=time.time()
            )
            await storage.save(cap)

            # Patch load to return None (simulating corrupt file)
            async def patched_load(cid):  # NOSONAR
                return None

            with patch.object(storage, 'load', side_effect=patched_load):
                # function_name filter active, but load returns None
                # capture_id should still be appended (per code logic at line 204)
                results = await storage.list_captures(function_name='func')

            # The capture_id is appended even when load returns None (code behavior)
            assert 'filter-none-test' in results

    @pytest.mark.asyncio
    async def test_replay_not_found_in_storage(self):
        """Line 418: capture not found in storage returns error."""
        import time

        from obskit.debug.replay import MemoryStorage, RequestCapture

        storage = MemoryStorage()
        capture = RequestCapture(storage=storage)

        result = await capture.replay('nonexistent-id')
        assert result['success'] is False
        assert 'not found' in result['error'].lower()

    @pytest.mark.asyncio
    async def test_wrap_not_in_registry_via_wrap_replay(self):
        """Line 439->442 branch: func not in registry."""
        import time

        from obskit.debug.replay import CapturedRequest, MemoryStorage, RequestCapture

        storage = MemoryStorage()
        capture = RequestCapture(storage=storage)

        # Save a capture for an unregistered function (not wrapped)
        cap = CapturedRequest(
            capture_id='unregistered', function_name='unregistered_func',
            module='nonexistent_module', args=(), kwargs={}, timestamp=time.time()
        )
        await storage.save(cap)

        # replay without func= and not registered
        result = await capture.replay('unregistered')
        assert result['success'] is False
        assert 'registry' in result['error']

    @pytest.mark.asyncio
    async def test_wrap_async_captures_exception_and_reraises(self):
        """Lines 538-541: exception path in async_wrapper captures and re-raises."""
        import time

        from obskit.debug.replay import MemoryStorage, RequestCapture

        storage = MemoryStorage()
        capture = RequestCapture(
            storage=storage,
            capture_on_error=True,
            capture_sample_rate=1.0,
        )

        @capture.wrap
        async def async_failing(x):
            raise ValueError(f'async error: {x}')

        with pytest.raises(ValueError, match='async error'):
            await async_failing('test')

        # Check that the error was captured
        assert len(storage._captures) >= 1
        cap = list(storage._captures.values())[0]
        assert cap.error is not None


class TestRegistryReplayCoverage:
    """Tests for registry-based replay paths."""

    @pytest.mark.asyncio
    async def test_replay_via_registry_found_path(self):
        """Line 439->442: func is found in registry (condition False -> skip to 442)."""
        import time

        from obskit.debug.replay import CapturedRequest, MemoryStorage, RequestCapture

        storage = MemoryStorage()
        capture_system = RequestCapture(storage=storage, capture_sample_rate=1.0)

        # Register a function via wrap
        @capture_system.wrap
        async def registered_func(x, y):
            return x * y

        # Manually save a capture for this function
        cap = CapturedRequest(
            capture_id='registry-test',
            function_name='registered_func',
            module=registered_func.__module__,
            args=(3, 4),
            kwargs={},
            timestamp=time.time()
        )
        await storage.save(cap)

        # Replay without providing func= - should find it in registry
        result = await capture_system.replay('registry-test')
        assert result['success'] is True
        assert result['output'] == 12

    def test_wrap_sync_captures_exception_and_reraises(self):
        """Lines 538-541 via sync_wrapper: wrap sync func captures error and re-raises."""
        import time

        from obskit.debug.replay import MemoryStorage, RequestCapture

        storage = MemoryStorage()
        capture_system = RequestCapture(
            storage=storage,
            capture_on_error=True,
            capture_sample_rate=1.0,
        )

        @capture_system.wrap
        def sync_failing(x):
            raise ValueError(f'sync error: {x}')

        with pytest.raises(ValueError, match='sync error'):
            sync_failing('test')

        # Check that the error was captured
        assert len(storage._captures) >= 1
        cap = list(storage._captures.values())[0]
        assert cap.error is not None


class TestCaptureOnErrorFalseCoverage:
    @pytest.mark.asyncio
    async def test_wrap_async_no_capture_on_error(self):
        """Line 538->541: when capture_on_error=False, exception is re-raised without capturing."""
        from obskit.debug.replay import MemoryStorage, RequestCapture

        storage = MemoryStorage()
        capture_system = RequestCapture(
            storage=storage,
            capture_on_error=False,  # Do NOT capture on error
            capture_sample_rate=1.0,
        )

        @capture_system.wrap
        async def no_capture_on_fail(x):
            raise ValueError(f'uncaptured error: {x}')

        with pytest.raises(ValueError, match='uncaptured error'):
            await no_capture_on_fail('test')

        # No capture should have been made
        assert len(storage._captures) == 0
