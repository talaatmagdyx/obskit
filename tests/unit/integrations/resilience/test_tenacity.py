"""Unit tests for obskit.integrations.resilience.tenacity.

Two usage paths are supported:

* **Instance path** — pass a ``tenacity.Retrying`` / ``tenacity.AsyncRetrying``
  instance directly; hooks are patched in-place and the same object is returned.

* **Factory path** — pass the decorator factory returned by ``tenacity.retry(...)``
  (a plain function in tenacity 9.x); a new factory is returned that patches hooks
  on the ``Retrying``/``AsyncRetrying`` object created at decoration time.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

tenacity = pytest.importorskip("tenacity")


class TestInstrumentTenacityReturnsRetryObj:
    def test_returns_same_retry_obj(self):
        from obskit.integrations.resilience.tenacity import instrument_tenacity

        retry_obj = tenacity.Retrying(stop=tenacity.stop_after_attempt(3))
        result = instrument_tenacity(retry_obj, name="t_ret")
        assert result is retry_obj

    def test_patches_before_sleep(self):
        from obskit.integrations.resilience.tenacity import instrument_tenacity

        retry_obj = tenacity.Retrying(stop=tenacity.stop_after_attempt(3))
        instrument_tenacity(retry_obj, name="t_patch_bs")
        assert callable(retry_obj.before_sleep)

    def test_patches_after(self):
        from obskit.integrations.resilience.tenacity import instrument_tenacity

        retry_obj = tenacity.Retrying(stop=tenacity.stop_after_attempt(3))
        instrument_tenacity(retry_obj, name="t_patch_after")
        assert callable(retry_obj.after)

    def test_works_with_async_retrying(self):
        from obskit.integrations.resilience.tenacity import instrument_tenacity

        retry_obj = tenacity.AsyncRetrying(stop=tenacity.stop_after_attempt(3))
        result = instrument_tenacity(retry_obj, name="t_async_ret")
        assert result is retry_obj
        assert callable(retry_obj.before_sleep)


class TestRetryAttemptsCounter:
    def test_before_sleep_increments_attempt_counter(self):
        from obskit.integrations.resilience.tenacity import (
            RETRY_ATTEMPTS_TOTAL,
            instrument_tenacity,
        )

        retry_obj = tenacity.Retrying(stop=tenacity.stop_after_attempt(3))
        instrument_tenacity(retry_obj, name="t_bs_inc")

        retry_state = MagicMock()
        retry_state.attempt_number = 1

        before = RETRY_ATTEMPTS_TOTAL.labels(
            name="t_bs_inc", attempt_number="1"
        )._value.get()
        retry_obj.before_sleep(retry_state)
        after = RETRY_ATTEMPTS_TOTAL.labels(
            name="t_bs_inc", attempt_number="1"
        )._value.get()
        assert after == before + 1.0

    def test_before_sleep_uses_attempt_number_label(self):
        from obskit.integrations.resilience.tenacity import (
            RETRY_ATTEMPTS_TOTAL,
            instrument_tenacity,
        )

        retry_obj = tenacity.Retrying(stop=tenacity.stop_after_attempt(3))
        instrument_tenacity(retry_obj, name="t_bs_label")

        for attempt in (1, 2):
            retry_state = MagicMock()
            retry_state.attempt_number = attempt
            before = RETRY_ATTEMPTS_TOTAL.labels(
                name="t_bs_label", attempt_number=str(attempt)
            )._value.get()
            retry_obj.before_sleep(retry_state)
            after = RETRY_ATTEMPTS_TOTAL.labels(
                name="t_bs_label", attempt_number=str(attempt)
            )._value.get()
            assert after == before + 1.0

    def test_preserves_original_before_sleep(self):
        from obskit.integrations.resilience.tenacity import instrument_tenacity

        original_bs = MagicMock()
        retry_obj = tenacity.Retrying(
            stop=tenacity.stop_after_attempt(3),
            before_sleep=original_bs,
        )
        instrument_tenacity(retry_obj, name="t_orig_bs")

        retry_state = MagicMock()
        retry_state.attempt_number = 1
        retry_obj.before_sleep(retry_state)
        original_bs.assert_called_once_with(retry_state)

    def test_before_sleep_none_original_is_safe(self):
        """No original before_sleep — patched hook must not raise."""
        from obskit.integrations.resilience.tenacity import instrument_tenacity

        retry_obj = tenacity.Retrying(stop=tenacity.stop_after_attempt(2))
        assert retry_obj.before_sleep is None
        instrument_tenacity(retry_obj, name="t_bs_none")

        retry_state = MagicMock()
        retry_state.attempt_number = 1
        # Should not raise
        retry_obj.before_sleep(retry_state)


class TestRetryExhaustedCounter:
    def test_after_increments_exhausted_when_stop_met(self):
        from obskit.integrations.resilience.tenacity import (
            RETRY_EXHAUSTED_TOTAL,
            instrument_tenacity,
        )

        retry_obj = tenacity.Retrying(stop=tenacity.stop_after_attempt(3))
        instrument_tenacity(retry_obj, name="t_exh")

        retry_state = MagicMock()
        retry_state.attempt_number = 3  # at max → stop returns True
        retry_state.outcome.failed = True

        before = RETRY_EXHAUSTED_TOTAL.labels(name="t_exh")._value.get()
        retry_obj.after(retry_state)
        after = RETRY_EXHAUSTED_TOTAL.labels(name="t_exh")._value.get()
        assert after == before + 1.0

    def test_after_does_not_increment_exhausted_when_stop_not_met(self):
        from obskit.integrations.resilience.tenacity import (
            RETRY_EXHAUSTED_TOTAL,
            instrument_tenacity,
        )

        retry_obj = tenacity.Retrying(stop=tenacity.stop_after_attempt(3))
        instrument_tenacity(retry_obj, name="t_no_exh")

        retry_state = MagicMock()
        retry_state.attempt_number = 1  # below max → stop returns False
        retry_state.outcome.failed = True

        before = RETRY_EXHAUSTED_TOTAL.labels(name="t_no_exh")._value.get()
        retry_obj.after(retry_state)
        after = RETRY_EXHAUSTED_TOTAL.labels(name="t_no_exh")._value.get()
        assert after == before  # NOT exhausted yet

    def test_after_does_not_increment_when_outcome_not_failed(self):
        """Successful attempt at stop boundary should not count as exhausted."""
        from obskit.integrations.resilience.tenacity import (
            RETRY_EXHAUSTED_TOTAL,
            instrument_tenacity,
        )

        retry_obj = tenacity.Retrying(stop=tenacity.stop_after_attempt(3))
        instrument_tenacity(retry_obj, name="t_success_at_stop")

        retry_state = MagicMock()
        retry_state.attempt_number = 3
        retry_state.outcome.failed = False  # success — not exhausted

        before = RETRY_EXHAUSTED_TOTAL.labels(name="t_success_at_stop")._value.get()
        retry_obj.after(retry_state)
        after = RETRY_EXHAUSTED_TOTAL.labels(name="t_success_at_stop")._value.get()
        assert after == before

    def test_after_does_not_increment_when_outcome_is_none(self):
        from obskit.integrations.resilience.tenacity import (
            RETRY_EXHAUSTED_TOTAL,
            instrument_tenacity,
        )

        retry_obj = tenacity.Retrying(stop=tenacity.stop_after_attempt(3))
        instrument_tenacity(retry_obj, name="t_no_outcome")

        retry_state = MagicMock()
        retry_state.attempt_number = 3
        retry_state.outcome = None

        before = RETRY_EXHAUSTED_TOTAL.labels(name="t_no_outcome")._value.get()
        retry_obj.after(retry_state)
        after = RETRY_EXHAUSTED_TOTAL.labels(name="t_no_outcome")._value.get()
        assert after == before

    def test_preserves_original_after(self):
        from obskit.integrations.resilience.tenacity import instrument_tenacity

        original_after = MagicMock()
        retry_obj = tenacity.Retrying(
            stop=tenacity.stop_after_attempt(3),
            after=original_after,
        )
        instrument_tenacity(retry_obj, name="t_orig_after")

        retry_state = MagicMock()
        retry_state.outcome = None
        retry_obj.after(retry_state)
        original_after.assert_called_once_with(retry_state)


class TestEndToEndRetry:
    def test_async_retry_attempts_and_exhaustion(self):
        """Full async retry with 3 attempts: 2 attempt labels + 1 exhausted."""
        from obskit.integrations.resilience.tenacity import (
            RETRY_ATTEMPTS_TOTAL,
            RETRY_EXHAUSTED_TOTAL,
            instrument_tenacity,
        )

        retry_obj = instrument_tenacity(
            tenacity.AsyncRetrying(
                stop=tenacity.stop_after_attempt(3),
                wait=tenacity.wait_none(),
                reraise=True,
            ),
            name="e2e_async",
        )

        @retry_obj.wraps
        async def always_fails():
            raise RuntimeError("boom")

        before_a1 = RETRY_ATTEMPTS_TOTAL.labels(
            name="e2e_async", attempt_number="1"
        )._value.get()
        before_a2 = RETRY_ATTEMPTS_TOTAL.labels(
            name="e2e_async", attempt_number="2"
        )._value.get()
        before_exh = RETRY_EXHAUSTED_TOTAL.labels(name="e2e_async")._value.get()

        with pytest.raises(RuntimeError, match="boom"):
            asyncio.run(always_fails())

        assert (
            RETRY_ATTEMPTS_TOTAL.labels(
                name="e2e_async", attempt_number="1"
            )._value.get()
            == before_a1 + 1.0
        )
        assert (
            RETRY_ATTEMPTS_TOTAL.labels(
                name="e2e_async", attempt_number="2"
            )._value.get()
            == before_a2 + 1.0
        )
        assert (
            RETRY_EXHAUSTED_TOTAL.labels(name="e2e_async")._value.get()
            == before_exh + 1.0
        )

    def test_async_retry_success_no_exhaustion(self):
        """Function succeeds on 2nd attempt: 1 attempt label, 0 exhausted."""
        from obskit.integrations.resilience.tenacity import (
            RETRY_ATTEMPTS_TOTAL,
            RETRY_EXHAUSTED_TOTAL,
            instrument_tenacity,
        )

        retry_obj = instrument_tenacity(
            tenacity.AsyncRetrying(
                stop=tenacity.stop_after_attempt(3),
                wait=tenacity.wait_none(),
                reraise=True,
            ),
            name="e2e_success",
        )

        call_count = [0]

        @retry_obj.wraps
        async def fails_once():
            call_count[0] += 1
            if call_count[0] < 2:
                raise RuntimeError("first fail")

        before_a1 = RETRY_ATTEMPTS_TOTAL.labels(
            name="e2e_success", attempt_number="1"
        )._value.get()
        before_exh = RETRY_EXHAUSTED_TOTAL.labels(name="e2e_success")._value.get()

        asyncio.run(fails_once())

        assert (
            RETRY_ATTEMPTS_TOTAL.labels(
                name="e2e_success", attempt_number="1"
            )._value.get()
            == before_a1 + 1.0
        )
        assert (
            RETRY_EXHAUSTED_TOTAL.labels(name="e2e_success")._value.get()
            == before_exh  # not exhausted — succeeded on 2nd attempt
        )


class TestFactoryPath:
    """Tests for the tenacity.retry() shorthand (factory) usage in tenacity 9.x."""

    def test_factory_returns_callable(self):
        """instrument_tenacity with a factory returns a callable decorator."""
        from obskit.integrations.resilience.tenacity import instrument_tenacity

        factory = tenacity.retry(stop=tenacity.stop_after_attempt(3))
        result = instrument_tenacity(factory, name="t_factory_callable")
        assert callable(result)

    def test_factory_result_is_not_original(self):
        """The returned factory is a new wrapper, not the original function."""
        from obskit.integrations.resilience.tenacity import instrument_tenacity

        factory = tenacity.retry(stop=tenacity.stop_after_attempt(3))
        result = instrument_tenacity(factory, name="t_factory_new")
        assert result is not factory

    def test_factory_wraps_async_function(self):
        """Applying the factory to an async function produces an async callable."""
        import asyncio

        from obskit.integrations.resilience.tenacity import instrument_tenacity

        decorated = instrument_tenacity(
            tenacity.retry(stop=tenacity.stop_after_attempt(3), reraise=True),
            name="t_factory_async_wrap",
        )

        @decorated
        async def handle():
            pass

        assert asyncio.iscoroutinefunction(handle)

    def test_factory_preserves_function_result(self):
        """The factory wrapper does not alter the return value of the wrapped function."""
        import asyncio

        from obskit.integrations.resilience.tenacity import instrument_tenacity

        @instrument_tenacity(
            tenacity.retry(stop=tenacity.stop_after_attempt(2), reraise=True),
            name="t_factory_result",
        )
        async def produce():
            return "value"

        assert asyncio.run(produce()) == "value"

    def test_factory_patches_hooks_on_wrapped_retry(self):
        """After decoration, the underlying .retry object has patched hooks."""
        from obskit.integrations.resilience.tenacity import instrument_tenacity

        instrumented = instrument_tenacity(
            tenacity.retry(stop=tenacity.stop_after_attempt(3), reraise=True),
            name="t_factory_hooks",
        )

        async def fn():
            pass

        wrapped = instrumented(fn)
        assert callable(wrapped.retry.before_sleep)
        assert callable(wrapped.retry.after)

    def test_factory_preserves_before_sleep_callback(self):
        """A before_sleep= callback passed to retry() is still called."""
        from unittest.mock import MagicMock

        from obskit.integrations.resilience.tenacity import instrument_tenacity

        original_bs = MagicMock()
        instrumented = instrument_tenacity(
            tenacity.retry(
                stop=tenacity.stop_after_attempt(3),
                before_sleep=original_bs,
                reraise=True,
            ),
            name="t_factory_preserve_bs",
        )

        async def fn():
            pass

        wrapped = instrumented(fn)
        retry_state = MagicMock()
        retry_state.attempt_number = 1
        wrapped.retry.before_sleep(retry_state)
        original_bs.assert_called_once_with(retry_state)

    def test_factory_end_to_end_attempts_and_exhaustion(self):
        """Full async retry via retry() shorthand: 2 attempt labels + 1 exhausted."""
        import asyncio

        from obskit.integrations.resilience.tenacity import (
            RETRY_ATTEMPTS_TOTAL,
            RETRY_EXHAUSTED_TOTAL,
            instrument_tenacity,
        )

        @instrument_tenacity(
            tenacity.retry(
                stop=tenacity.stop_after_attempt(3),
                wait=tenacity.wait_none(),
                reraise=True,
            ),
            name="factory_e2e_fail",
        )
        async def always_fails():
            raise RuntimeError("boom")

        before_a1 = RETRY_ATTEMPTS_TOTAL.labels(
            name="factory_e2e_fail", attempt_number="1"
        )._value.get()
        before_a2 = RETRY_ATTEMPTS_TOTAL.labels(
            name="factory_e2e_fail", attempt_number="2"
        )._value.get()
        before_exh = RETRY_EXHAUSTED_TOTAL.labels(name="factory_e2e_fail")._value.get()

        with pytest.raises(RuntimeError, match="boom"):
            asyncio.run(always_fails())

        assert (
            RETRY_ATTEMPTS_TOTAL.labels(
                name="factory_e2e_fail", attempt_number="1"
            )._value.get()
            == before_a1 + 1.0
        )
        assert (
            RETRY_ATTEMPTS_TOTAL.labels(
                name="factory_e2e_fail", attempt_number="2"
            )._value.get()
            == before_a2 + 1.0
        )
        assert (
            RETRY_EXHAUSTED_TOTAL.labels(name="factory_e2e_fail")._value.get()
            == before_exh + 1.0
        )

    def test_factory_end_to_end_success_no_exhaustion(self):
        """Succeeds on 2nd attempt: 1 attempt label, 0 exhausted."""
        import asyncio

        from obskit.integrations.resilience.tenacity import (
            RETRY_ATTEMPTS_TOTAL,
            RETRY_EXHAUSTED_TOTAL,
            instrument_tenacity,
        )

        call_count = [0]

        @instrument_tenacity(
            tenacity.retry(
                stop=tenacity.stop_after_attempt(3),
                wait=tenacity.wait_none(),
                reraise=True,
            ),
            name="factory_e2e_ok",
        )
        async def fails_once():
            call_count[0] += 1
            if call_count[0] < 2:
                raise RuntimeError("first fail")

        before_a1 = RETRY_ATTEMPTS_TOTAL.labels(
            name="factory_e2e_ok", attempt_number="1"
        )._value.get()
        before_exh = RETRY_EXHAUSTED_TOTAL.labels(name="factory_e2e_ok")._value.get()

        asyncio.run(fails_once())

        assert (
            RETRY_ATTEMPTS_TOTAL.labels(
                name="factory_e2e_ok", attempt_number="1"
            )._value.get()
            == before_a1 + 1.0
        )
        assert (
            RETRY_EXHAUSTED_TOTAL.labels(name="factory_e2e_ok")._value.get()
            == before_exh  # not exhausted
        )


class TestPublicAPI:
    def test_all_exports_present(self):
        import obskit.integrations.resilience.tenacity as m

        for name in (
            "instrument_tenacity",
            "RETRY_ATTEMPTS_TOTAL",
            "RETRY_EXHAUSTED_TOTAL",
        ):
            assert hasattr(m, name), f"missing: {name}"

    def test_top_level_export(self):
        import obskit

        assert "instrument_tenacity" in obskit.__all__
