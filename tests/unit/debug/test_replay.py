"""Unit tests for request replay debugging."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from obskit.debug.replay import (
    CapturedRequest,
    FileStorage,
    MemoryStorage,
    RequestCapture,
)


class TestCapturedRequest:
    """Tests for CapturedRequest dataclass."""

    def test_init(self):
        """Test initialization."""
        capture = CapturedRequest(
            capture_id="cap-123",
            function_name="process_message",
            module="my_module",
            args=("arg1", "arg2"),
            kwargs={"key": "value"},
            timestamp=1234567890.0,
        )

        assert capture.capture_id == "cap-123"
        assert capture.function_name == "process_message"
        assert capture.args == ("arg1", "arg2")
        assert capture.kwargs == {"key": "value"}

    def test_init_with_error(self):
        """Test initialization with error info."""
        capture = CapturedRequest(
            capture_id="cap-123",
            function_name="failing_func",
            module="my_module",
            args=(),
            kwargs={},
            timestamp=1234567890.0,
            error="Connection failed",
            error_type="ConnectionError",
            traceback="Traceback...",
        )

        assert capture.error == "Connection failed"
        assert capture.error_type == "ConnectionError"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        capture = CapturedRequest(
            capture_id="cap-123",
            function_name="my_func",
            module="my_module",
            args=("arg1",),
            kwargs={"key": "value"},
            timestamp=1234567890.0,
            duration_seconds=0.5,
        )

        data = capture.to_dict()

        assert data["capture_id"] == "cap-123"
        assert data["function_name"] == "my_func"
        assert data["duration_seconds"] == 0.5

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "capture_id": "cap-456",
            "function_name": "restored_func",
            "module": "test_module",
            "args": ["a", "b"],
            "kwargs": {"x": 1},
            "timestamp": 1234567890.0,
            "error": None,
            "error_type": None,
            "traceback": None,
            "duration_seconds": 1.0,
            "metadata": {"request_id": "req-123"},
        }

        capture = CapturedRequest.from_dict(data)

        assert capture.capture_id == "cap-456"
        assert capture.function_name == "restored_func"
        assert capture.args == ("a", "b")
        assert capture.metadata["request_id"] == "req-123"


class TestMemoryStorage:
    """Tests for MemoryStorage class."""

    @pytest.mark.asyncio
    async def test_save_and_load(self):
        """Test saving and loading captures."""
        storage = MemoryStorage()

        capture = CapturedRequest(
            capture_id="mem-123",
            function_name="test_func",
            module="test",
            args=(),
            kwargs={},
            timestamp=1234567890.0,
        )

        await storage.save(capture)
        loaded = await storage.load("mem-123")

        assert loaded is not None
        assert loaded.capture_id == "mem-123"

    @pytest.mark.asyncio
    async def test_load_nonexistent(self):
        """Test loading non-existent capture."""
        storage = MemoryStorage()

        loaded = await storage.load("nonexistent")

        assert loaded is None

    @pytest.mark.asyncio
    async def test_list_captures(self):
        """Test listing captures."""
        storage = MemoryStorage()

        for i in range(5):
            capture = CapturedRequest(
                capture_id=f"cap-{i}",
                function_name="test_func",
                module="test",
                args=(),
                kwargs={},
                timestamp=1234567890.0 + i,
            )
            await storage.save(capture)

        captures = await storage.list_captures()

        assert len(captures) == 5

    @pytest.mark.asyncio
    async def test_list_captures_with_limit(self):
        """Test listing captures with limit."""
        storage = MemoryStorage()

        for i in range(10):
            capture = CapturedRequest(
                capture_id=f"cap-{i}",
                function_name="test_func",
                module="test",
                args=(),
                kwargs={},
                timestamp=1234567890.0 + i,
            )
            await storage.save(capture)

        captures = await storage.list_captures(limit=5)

        assert len(captures) == 5

    @pytest.mark.asyncio
    async def test_list_captures_filter_by_function(self):
        """Test listing captures filtered by function name."""
        storage = MemoryStorage()

        for i in range(5):
            func_name = "func_a" if i % 2 == 0 else "func_b"
            capture = CapturedRequest(
                capture_id=f"cap-{i}",
                function_name=func_name,
                module="test",
                args=(),
                kwargs={},
                timestamp=1234567890.0 + i,
            )
            await storage.save(capture)

        captures = await storage.list_captures(function_name="func_a")

        assert len(captures) == 3

    @pytest.mark.asyncio
    async def test_delete(self):
        """Test deleting a capture."""
        storage = MemoryStorage()

        capture = CapturedRequest(
            capture_id="to-delete",
            function_name="test_func",
            module="test",
            args=(),
            kwargs={},
            timestamp=1234567890.0,
        )
        await storage.save(capture)

        deleted = await storage.delete("to-delete")

        assert deleted is True
        assert await storage.load("to-delete") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self):
        """Test deleting non-existent capture."""
        storage = MemoryStorage()

        deleted = await storage.delete("nonexistent")

        assert deleted is False

    @pytest.mark.asyncio
    async def test_max_captures_eviction(self):
        """Test eviction when max captures reached."""
        storage = MemoryStorage(max_captures=5)

        for i in range(10):
            capture = CapturedRequest(
                capture_id=f"cap-{i}",
                function_name="test_func",
                module="test",
                args=(),
                kwargs={},
                timestamp=1234567890.0 + i,
            )
            await storage.save(capture)

        # Should only have 5 captures
        captures = await storage.list_captures()
        assert len(captures) == 5


class TestFileStorage:
    """Tests for FileStorage class."""

    @pytest.mark.asyncio
    async def test_save_and_load(self):
        """Test saving and loading captures to files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_path=tmpdir, compress=False)

            capture = CapturedRequest(
                capture_id="file-123",
                function_name="test_func",
                module="test",
                args=("arg1",),
                kwargs={"key": "value"},
                timestamp=1234567890.0,
            )

            await storage.save(capture)
            loaded = await storage.load("file-123")

            assert loaded is not None
            assert loaded.capture_id == "file-123"
            assert loaded.args == ("arg1",)

    @pytest.mark.asyncio
    async def test_save_and_load_compressed(self):
        """Test saving and loading compressed captures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_path=tmpdir, compress=True)

            capture = CapturedRequest(
                capture_id="compressed-123",
                function_name="test_func",
                module="test",
                args=(),
                kwargs={},
                timestamp=1234567890.0,
            )

            await storage.save(capture)
            loaded = await storage.load("compressed-123")

            assert loaded is not None
            assert loaded.capture_id == "compressed-123"

            # Verify file is compressed
            path = Path(tmpdir) / "compressed-123.json.gz"
            assert path.exists()

    @pytest.mark.asyncio
    async def test_load_nonexistent(self):
        """Test loading non-existent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_path=tmpdir)

            loaded = await storage.load("nonexistent")

            assert loaded is None

    @pytest.mark.asyncio
    async def test_delete(self):
        """Test deleting a capture file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = FileStorage(base_path=tmpdir, compress=False)

            capture = CapturedRequest(
                capture_id="to-delete",
                function_name="test_func",
                module="test",
                args=(),
                kwargs={},
                timestamp=1234567890.0,
            )
            await storage.save(capture)

            deleted = await storage.delete("to-delete")

            assert deleted is True
            assert await storage.load("to-delete") is None


class TestRequestCapture:
    """Tests for RequestCapture class."""

    def test_init_defaults(self):
        """Test default initialization."""
        capture = RequestCapture()

        assert capture.capture_on_error is True
        assert capture.capture_on_slow is False
        assert capture.slow_threshold == 5.0
        assert capture.sample_rate == 1.0

    def test_init_with_storage(self):
        """Test initialization with custom storage."""
        storage = MemoryStorage()
        capture = RequestCapture(storage=storage)

        assert capture.storage is storage

    def test_init_with_options(self):
        """Test initialization with custom options."""
        capture = RequestCapture(
            capture_on_error=True,
            capture_on_slow=True,
            slow_threshold_seconds=2.0,
            capture_sample_rate=0.5,
        )

        assert capture.capture_on_slow is True
        assert capture.slow_threshold == 2.0
        assert capture.sample_rate == 0.5

    @pytest.mark.asyncio
    async def test_capture_on_error(self):
        """Test capturing on error."""
        storage = MemoryStorage()
        capture = RequestCapture(storage=storage)

        async def failing_func():
            raise ValueError("Test error")

        capture_id = await capture.capture(
            func=failing_func, args=(), kwargs={}, error=ValueError("Test error")
        )

        assert capture_id is not None

        loaded = await storage.load(capture_id)
        assert loaded is not None
        assert "Test error" in loaded.error
        assert loaded.error_type == "ValueError"

    @pytest.mark.asyncio
    async def test_wrap_decorator_captures_errors(self):
        """Test wrap decorator captures errors."""
        storage = MemoryStorage()
        capture = RequestCapture(storage=storage, capture_on_error=True, capture_sample_rate=1.0)

        @capture.wrap
        async def failing_func(data):
            raise ValueError("Wrapped error")

        with pytest.raises(ValueError):
            await failing_func({"key": "value"})

        captures = await storage.list_captures()
        assert len(captures) == 1

    @pytest.mark.asyncio
    async def test_wrap_decorator_success_no_capture(self):
        """Test wrap decorator doesn't capture successful executions."""
        storage = MemoryStorage()
        capture = RequestCapture(storage=storage, capture_on_error=True, capture_on_slow=False)

        @capture.wrap
        async def success_func(data):
            return data

        result = await success_func({"key": "value"})

        assert result == {"key": "value"}

        captures = await storage.list_captures()
        assert len(captures) == 0

    @pytest.mark.asyncio
    async def test_wrap_decorator_captures_slow(self):
        """Test wrap decorator captures slow requests."""
        storage = MemoryStorage()
        capture = RequestCapture(
            storage=storage,
            capture_on_error=False,
            capture_on_slow=True,
            slow_threshold_seconds=0.05,
        )

        @capture.wrap
        async def slow_func():
            await asyncio.sleep(0.1)
            return "done"

        result = await slow_func()

        assert result == "done"

        captures = await storage.list_captures()
        assert len(captures) == 1

    @pytest.mark.asyncio
    async def test_replay_success(self):
        """Test replaying a captured request."""
        storage = MemoryStorage()
        capture = RequestCapture(storage=storage)

        # Define and wrap function
        @capture.wrap
        async def my_func(x, y):
            return x + y

        # Manually capture a request
        await capture.capture(
            func=my_func.__wrapped__,  # Get original function
            args=(1, 2),
            kwargs={},
        )

        captures = await storage.list_captures()
        capture_id = captures[0]

        # Replay
        result = await capture.replay(capture_id, func=my_func.__wrapped__)

        assert result["success"] is True
        assert result["output"] == 3

    @pytest.mark.asyncio
    async def test_replay_dry_run(self):
        """Test replay dry run mode."""
        storage = MemoryStorage()
        req_capture = RequestCapture(storage=storage)

        captured = CapturedRequest(
            capture_id="dry-run-123",
            function_name="my_func",
            module="test",
            args=(1, 2),
            kwargs={"z": 3},
            timestamp=1234567890.0,
        )
        await storage.save(captured)

        result = await req_capture.replay("dry-run-123", dry_run=True)

        assert result["success"] is True
        assert result["dry_run"] is True
        assert result["args"] == (1, 2)
        assert result["kwargs"] == {"z": 3}

    @pytest.mark.asyncio
    async def test_replay_not_found(self):
        """Test replaying non-existent capture."""
        storage = MemoryStorage()
        capture = RequestCapture(storage=storage)

        result = await capture.replay("nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_list_captures(self):
        """Test listing captured requests."""
        storage = MemoryStorage()
        req_capture = RequestCapture(storage=storage)

        for i in range(3):
            captured = CapturedRequest(
                capture_id=f"list-{i}",
                function_name="test_func",
                module="test",
                args=(),
                kwargs={},
                timestamp=1234567890.0 + i,
                error_type="ValueError" if i == 0 else None,
                duration_seconds=0.1 * i,
            )
            await storage.save(captured)

        captures = await req_capture.list_captures()

        assert len(captures) == 3
        assert all("capture_id" in c for c in captures)
        assert all("function_name" in c for c in captures)

    @pytest.mark.asyncio
    async def test_delete_capture(self):
        """Test deleting a capture."""
        storage = MemoryStorage()
        req_capture = RequestCapture(storage=storage)

        captured = CapturedRequest(
            capture_id="to-delete",
            function_name="test_func",
            module="test",
            args=(),
            kwargs={},
            timestamp=1234567890.0,
        )
        await storage.save(captured)

        deleted = await req_capture.delete_capture("to-delete")

        assert deleted is True

        captures = await req_capture.list_captures()
        assert len(captures) == 0

    def test_sample_rate(self):
        """Test sample rate affects capture decision."""
        # With sample_rate=0, should_capture should always return False
        capture = RequestCapture(capture_sample_rate=0.0)

        # Run multiple times
        results = [capture._should_capture() for _ in range(100)]

        assert all(r is False for r in results)

    def test_sample_rate_full(self):
        """Test full sample rate always captures."""
        capture = RequestCapture(capture_sample_rate=1.0)

        results = [capture._should_capture() for _ in range(100)]

        assert all(r is True for r in results)
