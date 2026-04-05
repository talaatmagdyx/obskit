"""Unit tests for obskit.integrations.queue.retry_worker."""

from __future__ import annotations


class TestInstrumentRetryWorker:
    def test_returns_instrumentor(self):
        from obskit.integrations.queue.retry_worker import (
            RetryWorkerInstrumentor,
            instrument_retry_worker,
        )

        instr = instrument_retry_worker(name="my-worker")
        assert isinstance(instr, RetryWorkerInstrumentor)

    def test_default_name(self):
        from obskit.integrations.queue.retry_worker import instrument_retry_worker

        instr = instrument_retry_worker()
        assert instr._name == "default"

    def test_stores_name(self):
        from obskit.integrations.queue.retry_worker import instrument_retry_worker

        instr = instrument_retry_worker(name="event_retry")
        assert instr._name == "event_retry"


class TestRetryWorkerInstrumentorRecordEvent:
    def test_record_event_increments_counter(self):
        from obskit.integrations.queue.retry_worker import (
            RETRY_WORKER_EVENTS_TOTAL,
            instrument_retry_worker,
        )

        instr = instrument_retry_worker(name="w1")
        before = RETRY_WORKER_EVENTS_TOTAL.labels(name="w1", status="success")._value.get()
        instr.record_event("success")
        after = RETRY_WORKER_EVENTS_TOTAL.labels(name="w1", status="success")._value.get()
        assert after == before + 1.0

    def test_record_event_failure_increments_failure_counter(self):
        from obskit.integrations.queue.retry_worker import (
            RETRY_WORKER_EVENTS_TOTAL,
            instrument_retry_worker,
        )

        instr = instrument_retry_worker(name="w2")
        before = RETRY_WORKER_EVENTS_TOTAL.labels(name="w2", status="failure")._value.get()
        instr.record_event("failure")
        after = RETRY_WORKER_EVENTS_TOTAL.labels(name="w2", status="failure")._value.get()
        assert after == before + 1.0

    def test_record_event_skip_increments_skip_counter(self):
        from obskit.integrations.queue.retry_worker import (
            RETRY_WORKER_EVENTS_TOTAL,
            instrument_retry_worker,
        )

        instr = instrument_retry_worker(name="w3")
        before = RETRY_WORKER_EVENTS_TOTAL.labels(name="w3", status="skip")._value.get()
        instr.record_event("skip")
        after = RETRY_WORKER_EVENTS_TOTAL.labels(name="w3", status="skip")._value.get()
        assert after == before + 1.0

    def test_record_event_requeue_increments_requeue_counter(self):
        from obskit.integrations.queue.retry_worker import (
            RETRY_WORKER_EVENTS_TOTAL,
            instrument_retry_worker,
        )

        instr = instrument_retry_worker(name="w4")
        before = RETRY_WORKER_EVENTS_TOTAL.labels(name="w4", status="requeue")._value.get()
        instr.record_event("requeue")
        after = RETRY_WORKER_EVENTS_TOTAL.labels(name="w4", status="requeue")._value.get()
        assert after == before + 1.0

    def test_record_event_multiple_calls_accumulate(self):
        from obskit.integrations.queue.retry_worker import (
            RETRY_WORKER_EVENTS_TOTAL,
            instrument_retry_worker,
        )

        instr = instrument_retry_worker(name="w5")
        before = RETRY_WORKER_EVENTS_TOTAL.labels(name="w5", status="success")._value.get()
        instr.record_event("success")
        instr.record_event("success")
        instr.record_event("success")
        after = RETRY_WORKER_EVENTS_TOTAL.labels(name="w5", status="success")._value.get()
        assert after == before + 3.0

    def test_record_event_custom_status(self):
        """Any non-empty string is accepted as a status label."""
        from obskit.integrations.queue.retry_worker import (
            RETRY_WORKER_EVENTS_TOTAL,
            instrument_retry_worker,
        )

        instr = instrument_retry_worker(name="w6")
        before = RETRY_WORKER_EVENTS_TOTAL.labels(name="w6", status="expired")._value.get()
        instr.record_event("expired")
        after = RETRY_WORKER_EVENTS_TOTAL.labels(name="w6", status="expired")._value.get()
        assert after == before + 1.0


class TestRetryWorkerInstrumentorSetQueueDepth:
    def test_set_queue_depth_updates_gauge(self):
        from obskit.integrations.queue.retry_worker import (
            RETRY_WORKER_QUEUE_DEPTH,
            instrument_retry_worker,
        )

        instr = instrument_retry_worker(name="d1")
        instr.set_queue_depth(42)
        val = RETRY_WORKER_QUEUE_DEPTH.labels(name="d1")._value.get()
        assert val == 42.0

    def test_set_queue_depth_zero(self):
        from obskit.integrations.queue.retry_worker import (
            RETRY_WORKER_QUEUE_DEPTH,
            instrument_retry_worker,
        )

        instr = instrument_retry_worker(name="d2")
        instr.set_queue_depth(10)
        instr.set_queue_depth(0)
        val = RETRY_WORKER_QUEUE_DEPTH.labels(name="d2")._value.get()
        assert val == 0.0

    def test_set_queue_depth_overrides_previous(self):
        from obskit.integrations.queue.retry_worker import (
            RETRY_WORKER_QUEUE_DEPTH,
            instrument_retry_worker,
        )

        instr = instrument_retry_worker(name="d3")
        instr.set_queue_depth(100)
        instr.set_queue_depth(7)
        val = RETRY_WORKER_QUEUE_DEPTH.labels(name="d3")._value.get()
        assert val == 7.0


import pytest


class TestRetryWorkerInstrumentorRecordBackoff:
    def test_record_backoff_accumulates_sum(self):
        from obskit.integrations.queue.retry_worker import (
            RETRY_WORKER_BACKOFF_SECONDS,
            instrument_retry_worker,
        )

        instr = instrument_retry_worker(name="b2")
        before_sum = RETRY_WORKER_BACKOFF_SECONDS.labels(name="b2")._sum.get()
        instr.record_backoff(2.0)
        instr.record_backoff(3.0)
        after_sum = RETRY_WORKER_BACKOFF_SECONDS.labels(name="b2")._sum.get()
        assert after_sum == pytest.approx(before_sum + 5.0)

    def test_record_backoff_single_call_adds_to_sum(self):
        """A single record_backoff(v) adds exactly v to the histogram sum."""
        from obskit.integrations.queue.retry_worker import (
            RETRY_WORKER_BACKOFF_SECONDS,
            instrument_retry_worker,
        )

        instr = instrument_retry_worker(name="b1")
        before_sum = RETRY_WORKER_BACKOFF_SECONDS.labels(name="b1")._sum.get()
        instr.record_backoff(1.5)
        after_sum = RETRY_WORKER_BACKOFF_SECONDS.labels(name="b1")._sum.get()
        assert after_sum == pytest.approx(before_sum + 1.5)

    def test_record_backoff_zero_seconds(self):
        """record_backoff(0.0) is accepted without error."""
        from obskit.integrations.queue.retry_worker import instrument_retry_worker

        instr = instrument_retry_worker(name="b3")
        instr.record_backoff(0.0)  # should not raise


class TestRetryWorkerPublicAPI:
    def test_all_exports_present(self):
        import obskit.integrations.queue.retry_worker as rw

        for name in (
            "RetryWorkerInstrumentor",
            "instrument_retry_worker",
            "RETRY_WORKER_EVENTS_TOTAL",
            "RETRY_WORKER_QUEUE_DEPTH",
            "RETRY_WORKER_BACKOFF_SECONDS",
        ):
            assert hasattr(rw, name), f"missing export: {name}"
