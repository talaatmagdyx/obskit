"""
Request Replay for Debugging.

Capture and replay failed requests for debugging.
"""

import asyncio
import functools
import gzip
import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

from ..logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class CapturedRequest:
    """Represents a captured request."""

    capture_id: str
    function_name: str
    module: str
    args: tuple
    kwargs: dict[str, Any]
    timestamp: float
    error: str | None = None
    error_type: str | None = None
    traceback: str | None = None
    duration_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "capture_id": self.capture_id,
            "function_name": self.function_name,
            "module": self.module,
            "args": _serialize(self.args),
            "kwargs": _serialize(self.kwargs),
            "timestamp": self.timestamp,
            "error": self.error,
            "error_type": self.error_type,
            "traceback": self.traceback,
            "duration_seconds": self.duration_seconds,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapturedRequest":
        return cls(
            capture_id=data["capture_id"],
            function_name=data["function_name"],
            module=data["module"],
            args=tuple(_deserialize(data["args"])),
            kwargs=_deserialize(data["kwargs"]),
            timestamp=data["timestamp"],
            error=data.get("error"),
            error_type=data.get("error_type"),
            traceback=data.get("traceback"),
            duration_seconds=data.get("duration_seconds"),
            metadata=data.get("metadata", {}),
        )


def _serialize(obj: Any) -> Any:
    """Serialize object for storage."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): _serialize(v) for k, v in obj.items()}
    if hasattr(obj, "__dict__"):
        return {"__class__": type(obj).__name__, "__dict__": _serialize(obj.__dict__)}
    try:
        return str(obj)
    except Exception:
        return f"<unserializable: {type(obj).__name__}>"


def _deserialize(obj: Any) -> Any:
    """Deserialize object from storage."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, list):
        return [_deserialize(item) for item in obj]
    if isinstance(obj, dict):
        if "__class__" in obj and "__dict__" in obj:
            # Return as dict since we can't reconstruct the class
            return _deserialize(obj["__dict__"])
        return {k: _deserialize(v) for k, v in obj.items()}
    return obj


class RequestCaptureStorage:
    """Base class for capture storage."""

    async def save(self, capture: CapturedRequest) -> str:
        """Save captured request."""
        raise NotImplementedError

    async def load(self, capture_id: str) -> CapturedRequest | None:
        """Load captured request."""
        raise NotImplementedError

    async def list_captures(
        self, function_name: str | None = None, since: float | None = None, limit: int = 100
    ) -> list[str]:
        """List capture IDs."""
        raise NotImplementedError

    async def delete(self, capture_id: str) -> bool:
        """Delete a capture."""
        raise NotImplementedError


class FileStorage(RequestCaptureStorage):
    """Store captures to local filesystem."""

    def __init__(self, base_path: str = "/tmp/obskit_captures", compress: bool = True):
        self.base_path = Path(base_path)
        self.compress = compress
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_path(self, capture_id: str) -> Path:
        ext = ".json.gz" if self.compress else ".json"
        return self.base_path / f"{capture_id}{ext}"

    async def save(self, capture: CapturedRequest) -> str:
        path = self._get_path(capture.capture_id)
        data = json.dumps(capture.to_dict(), indent=2)

        if self.compress:
            with gzip.open(path, "wt", encoding="utf-8") as f:
                f.write(data)
        else:
            path.write_text(data)

        return capture.capture_id

    async def load(self, capture_id: str) -> CapturedRequest | None:
        path = self._get_path(capture_id)
        if not path.exists():
            # Try other extension
            other_ext = ".json" if self.compress else ".json.gz"
            path = self.base_path / f"{capture_id}{other_ext}"
            if not path.exists():
                return None

        try:
            if path.suffix == ".gz":
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = json.loads(path.read_text())

            return CapturedRequest.from_dict(data)
        except Exception as e:
            logger.error("capture_load_failed", capture_id=capture_id, error=str(e))
            return None

    async def list_captures(
        self, function_name: str | None = None, since: float | None = None, limit: int = 100
    ) -> list[str]:
        captures = []

        for path in sorted(self.base_path.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if len(captures) >= limit:
                break

            if not path.name.endswith((".json", ".json.gz")):
                continue

            capture_id = path.stem.replace(".json", "")

            # Apply filters if we can load the capture
            if function_name or since:
                capture = await self.load(capture_id)
                if capture:
                    if function_name and capture.function_name != function_name:
                        continue
                    if since and capture.timestamp < since:
                        continue

            captures.append(capture_id)

        return captures

    async def delete(self, capture_id: str) -> bool:
        path = self._get_path(capture_id)
        if path.exists():
            path.unlink()
            return True
        return False


class MemoryStorage(RequestCaptureStorage):
    """Store captures in memory (for testing)."""

    def __init__(self, max_captures: int = 1000):
        self.max_captures = max_captures
        self._captures: dict[str, CapturedRequest] = {}

    async def save(self, capture: CapturedRequest) -> str:
        # Evict old captures if at limit
        while len(self._captures) >= self.max_captures:
            oldest_id = min(self._captures.keys(), key=lambda k: self._captures[k].timestamp)
            del self._captures[oldest_id]

        self._captures[capture.capture_id] = capture
        return capture.capture_id

    async def load(self, capture_id: str) -> CapturedRequest | None:
        return self._captures.get(capture_id)

    async def list_captures(
        self, function_name: str | None = None, since: float | None = None, limit: int = 100
    ) -> list[str]:
        captures = []

        for capture_id, capture in sorted(
            self._captures.items(), key=lambda x: x[1].timestamp, reverse=True
        ):
            if len(captures) >= limit:
                break

            if function_name and capture.function_name != function_name:
                continue
            if since and capture.timestamp < since:
                continue

            captures.append(capture_id)

        return captures

    async def delete(self, capture_id: str) -> bool:
        if capture_id in self._captures:
            del self._captures[capture_id]
            return True
        return False


class RequestCapture:
    """
    Captures and replays failed requests for debugging.

    Example:
        capture = RequestCapture(
            storage=FileStorage("/tmp/captures"),
            capture_on_error=True,
            capture_on_slow=True,
            slow_threshold_seconds=5.0
        )

        @capture.wrap
        async def process_request(data: dict):
            # On failure, request is captured
            pass

        # Later: replay captured request
        await capture.replay("capture-123")

        # List captures
        captures = await capture.list_captures()
    """

    def __init__(
        self,
        storage: RequestCaptureStorage | None = None,
        capture_on_error: bool = True,
        capture_on_slow: bool = False,
        slow_threshold_seconds: float = 5.0,
        capture_sample_rate: float = 1.0,
        max_arg_size: int = 10000,
        include_traceback: bool = True,
        metadata_extractor: Callable[[Any], dict[str, Any]] | None = None,
    ):
        """
        Initialize request capture.

        Args:
            storage: Storage backend
            capture_on_error: Capture requests that raise exceptions
            capture_on_slow: Capture slow requests
            slow_threshold_seconds: Threshold for slow requests
            capture_sample_rate: Sampling rate (0.0 to 1.0)
            max_arg_size: Maximum size for serialized arguments
            include_traceback: Include traceback in captures
            metadata_extractor: Function to extract additional metadata
        """
        self.storage = storage or MemoryStorage()
        self.capture_on_error = capture_on_error
        self.capture_on_slow = capture_on_slow
        self.slow_threshold = slow_threshold_seconds
        self.sample_rate = capture_sample_rate
        self.max_arg_size = max_arg_size
        self.include_traceback = include_traceback
        self.metadata_extractor = metadata_extractor

        # Registry of wrapped functions for replay
        self._function_registry: dict[str, Callable] = {}

    def _should_capture(self) -> bool:
        """Determine if we should capture based on sample rate."""
        import random

        return random.random() < self.sample_rate

    def _truncate_args(self, args: tuple, kwargs: dict) -> tuple:
        """Truncate arguments if too large."""
        serialized = json.dumps(_serialize((args, kwargs)))

        if len(serialized) <= self.max_arg_size:
            return args, kwargs

        # Truncate and add marker
        truncated_args = tuple(
            f"<truncated: {type(a).__name__}>" if len(str(a)) > 1000 else a for a in args
        )
        truncated_kwargs = {
            k: f"<truncated: {type(v).__name__}>" if len(str(v)) > 1000 else v
            for k, v in kwargs.items()
        }

        return truncated_args, truncated_kwargs

    async def capture(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        error: Exception | None = None,
        duration: float | None = None,
    ) -> str:
        """
        Capture a request.

        Returns:
            Capture ID
        """
        import traceback as tb

        capture_id = f"capture-{uuid.uuid4().hex[:12]}"

        # Truncate large arguments
        truncated_args, truncated_kwargs = self._truncate_args(args, kwargs)

        # Extract metadata
        metadata = {}
        if self.metadata_extractor:
            try:
                if args:
                    metadata = self.metadata_extractor(args[0]) or {}
            except Exception:
                pass  # Metadata extraction failed - continue without metadata

        capture = CapturedRequest(
            capture_id=capture_id,
            function_name=func.__name__,
            module=func.__module__,
            args=truncated_args,
            kwargs=truncated_kwargs,
            timestamp=time.time(),
            error=str(error) if error else None,
            error_type=type(error).__name__ if error else None,
            traceback=tb.format_exc() if error and self.include_traceback else None,
            duration_seconds=duration,
            metadata=metadata,
        )

        await self.storage.save(capture)

        logger.info(
            "request_captured",
            capture_id=capture_id,
            function=func.__name__,
            error_type=capture.error_type,
            duration=duration,
        )

        return capture_id

    async def replay(
        self, capture_id: str, func: Callable | None = None, dry_run: bool = False
    ) -> dict[str, Any]:
        """
        Replay a captured request.

        Args:
            capture_id: ID of capture to replay
            func: Function to call (uses registry if not provided)
            dry_run: If True, don't actually execute

        Returns:
            Replay result
        """
        capture = await self.storage.load(capture_id)
        if not capture:
            return {"success": False, "error": f"Capture {capture_id} not found"}

        # Find function
        if not func:
            key = f"{capture.module}.{capture.function_name}"
            func = self._function_registry.get(key)

            if not func:
                return {"success": False, "error": f"Function {key} not in registry"}

        result = {
            "capture_id": capture_id,
            "function": capture.function_name,
            "original_error": capture.error,
            "dry_run": dry_run,
        }

        if dry_run:
            result["success"] = True
            result["args"] = capture.args
            result["kwargs"] = capture.kwargs
            return result

        start_time = time.time()

        try:
            if asyncio.iscoroutinefunction(func):
                output = await func(*capture.args, **capture.kwargs)
            else:
                output = func(*capture.args, **capture.kwargs)

            result["success"] = True
            result["output"] = _serialize(output)
            result["duration"] = time.time() - start_time

            logger.info(
                "request_replayed", capture_id=capture_id, success=True, duration=result["duration"]
            )

        except Exception as e:
            import traceback as tb

            result["success"] = False
            result["error"] = str(e)
            result["error_type"] = type(e).__name__
            result["traceback"] = tb.format_exc()
            result["duration"] = time.time() - start_time

            logger.warning("request_replay_failed", capture_id=capture_id, error=str(e))

        return result

    async def list_captures(
        self, function_name: str | None = None, since: float | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """List captured requests."""
        capture_ids = await self.storage.list_captures(
            function_name=function_name, since=since, limit=limit
        )

        captures = []
        for cid in capture_ids:
            capture = await self.storage.load(cid)
            if capture:
                captures.append(
                    {
                        "capture_id": capture.capture_id,
                        "function_name": capture.function_name,
                        "timestamp": datetime.fromtimestamp(capture.timestamp).isoformat(),
                        "error_type": capture.error_type,
                        "duration": capture.duration_seconds,
                    }
                )

        return captures

    async def delete_capture(self, capture_id: str) -> bool:
        """Delete a capture."""
        return await self.storage.delete(capture_id)

    def wrap(self, func: F) -> F:
        """
        Decorator to wrap function with capture.

        Example:
            @capture.wrap
            async def my_function(data):
                pass
        """
        # Register function for replay
        key = f"{func.__module__}.{func.__name__}"
        self._function_registry[key] = func

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not self._should_capture():
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                return func(*args, **kwargs)

            start_time = time.time()

            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                duration = time.time() - start_time

                # Capture slow requests
                if self.capture_on_slow and duration >= self.slow_threshold:
                    await self.capture(func, args, kwargs, duration=duration)

                return result

            except Exception as e:
                duration = time.time() - start_time

                if self.capture_on_error:
                    await self.capture(func, args, kwargs, error=e, duration=duration)

                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, run in event loop
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(async_wrapper(*args, **kwargs))
            finally:
                loop.close()

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore


__all__ = [
    "RequestCapture",
    "CapturedRequest",
    "RequestCaptureStorage",
    "FileStorage",
    "MemoryStorage",
]
