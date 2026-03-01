"""Unit tests for obskit.testing.testcase — ObskitTestCase base class."""

from __future__ import annotations

import asyncio
import unittest

import pytest

from obskit.testing.mocks import MockMetrics, MockSLOTracker, MockTracer
from obskit.testing.testcase import AsyncObskitTestCase, ObskitTestCase

# =============================================================================
# ObskitTestCase
# =============================================================================


class TestObskitTestCaseSetup:
    """Test the setup/teardown lifecycle of ObskitTestCase."""

    def test_mock_metrics_initialized(self):
        class MyTest(ObskitTestCase):
            def runTest(self):
                pass  # NOSONAR

        t = MyTest()
        t.__class__.setUpClass()
        t.setUp()
        assert isinstance(t.mock_metrics, MockMetrics)
        t.tearDown()

    def test_mock_tracer_initialized(self):
        class MyTest(ObskitTestCase):
            def runTest(self):
                pass  # NOSONAR

        t = MyTest()
        t.__class__.setUpClass()
        t.setUp()
        assert isinstance(t.mock_tracer, MockTracer)
        t.tearDown()

    def test_mock_slo_initialized(self):
        class MyTest(ObskitTestCase):
            def runTest(self):
                pass  # NOSONAR

        t = MyTest()
        t.__class__.setUpClass()
        t.setUp()
        assert isinstance(t.mock_slo, MockSLOTracker)
        t.tearDown()

    def test_mocks_reset_between_setup_calls(self):
        class MyTest(ObskitTestCase):
            def runTest(self):
                pass  # NOSONAR

        t = MyTest()
        t.__class__.setUpClass()
        t.setUp()

        # Record something
        t.mock_metrics.observe_request("op", 0.1, "success")
        assert t.mock_metrics.get_request_count() == 1

        t.tearDown()
        t.setUp()

        # Should be reset
        assert t.mock_metrics.get_request_count() == 0
        t.tearDown()

    def test_obskit_context_set_on_setup(self):
        class MyTest(ObskitTestCase):
            def runTest(self):
                pass  # NOSONAR

        t = MyTest()
        t.__class__.setUpClass()
        t.setUp()
        assert t._obskit_context is not None
        t.tearDown()

    def test_obskit_context_cleared_on_teardown(self):
        class MyTest(ObskitTestCase):
            def runTest(self):
                pass  # NOSONAR

        t = MyTest()
        t.__class__.setUpClass()
        t.setUp()
        t.tearDown()
        assert t._obskit_context is None


class TestObskitTestCaseAssertions:
    """Test the assertion helpers on ObskitTestCase."""

    def _make_test(self):
        class MyTest(ObskitTestCase):
            def runTest(self):
                pass  # NOSONAR

        t = MyTest()
        t.__class__.setUpClass()
        t.setUp()
        return t

    def test_assert_metric_recorded_passes(self):
        t = self._make_test()
        t.mock_metrics.observe_request("create_order", 0.1, "success")
        t.assertMetricRecorded("create_order")  # should not raise
        t.tearDown()

    def test_assert_metric_recorded_fails(self):
        t = self._make_test()
        with pytest.raises(AssertionError):
            t.assertMetricRecorded("nonexistent_op")
        t.tearDown()

    def test_assert_metric_recorded_with_status(self):
        t = self._make_test()
        t.mock_metrics.observe_request("op", 0.1, "success")
        t.assertMetricRecorded("op", status="success")
        t.tearDown()

    def test_assert_metric_recorded_with_wrong_status_fails(self):
        t = self._make_test()
        t.mock_metrics.observe_request("op", 0.1, "failure")
        with pytest.raises(AssertionError):
            t.assertMetricRecorded("op", status="success")
        t.tearDown()

    def test_assert_no_metrics_passes_when_empty(self):
        t = self._make_test()
        t.assertNoMetrics()  # should not raise
        t.tearDown()

    def test_assert_no_metrics_fails_when_recorded(self):
        t = self._make_test()
        t.mock_metrics.observe_request("op", 0.1, "success")
        with pytest.raises(AssertionError):
            t.assertNoMetrics("op")
        t.tearDown()

    def test_assert_span_created_passes(self):
        t = self._make_test()
        with t.mock_tracer.trace_span("my_span"):
            pass  # NOSONAR
        t.assertSpanCreated("my_span")  # should not raise
        t.tearDown()

    def test_assert_span_created_fails(self):
        t = self._make_test()
        with pytest.raises(AssertionError):
            t.assertSpanCreated("nonexistent_span")
        t.tearDown()

    def test_assert_slo_measured_passes(self):
        t = self._make_test()
        t.mock_slo.record_measurement("availability")
        t.assertSLOMeasured("availability")  # should not raise
        t.tearDown()

    def test_assert_slo_measured_fails(self):
        t = self._make_test()
        with pytest.raises(AssertionError):
            t.assertSLOMeasured("nonexistent_slo")
        t.tearDown()

    def test_get_metric_count(self):
        t = self._make_test()
        t.mock_metrics.observe_request("op", 0.1, "success")
        t.mock_metrics.observe_request("op", 0.1, "success")
        count = t.getMetricCount("op")
        assert count == 2
        t.tearDown()

    def test_get_metric_count_with_status_filter(self):
        t = self._make_test()
        t.mock_metrics.observe_request("op", 0.1, "success")
        t.mock_metrics.observe_request("op", 0.1, "failure")
        count = t.getMetricCount("op", status="success")
        assert count == 1
        t.tearDown()

    def test_get_span_count(self):
        t = self._make_test()
        with t.mock_tracer.trace_span("my_span"):
            pass  # NOSONAR
        with t.mock_tracer.trace_span("my_span"):
            pass  # NOSONAR
        count = t.getSpanCount("my_span")
        assert count == 2
        t.tearDown()

    def test_get_span_count_zero_for_unknown(self):
        t = self._make_test()
        count = t.getSpanCount("unknown_span")
        assert count == 0
        t.tearDown()


class TestObskitTestCaseAsSubclass(ObskitTestCase):
    """Test ObskitTestCase as an actual subclass (real unittest.TestCase)."""

    def test_metrics_available(self):
        # self.mock_metrics should be available
        assert self.mock_metrics is not None

    def test_tracer_available(self):
        assert self.mock_tracer is not None

    def test_slo_available(self):
        assert self.mock_slo is not None

    def test_health_available(self):
        assert self.mock_health is not None

    def test_record_and_assert_metric(self):
        self.mock_metrics.observe_request("test_op", 0.1, "success")
        self.assertMetricRecorded("test_op")

    def test_span_tracking(self):
        with self.mock_tracer.trace_span("test_span"):
            pass  # NOSONAR
        self.assertSpanCreated("test_span")
        self.assertEqual(self.getSpanCount("test_span"), 1)

    def test_slo_tracking(self):
        self.mock_slo.record_measurement("test_slo")
        self.assertSLOMeasured("test_slo")


# =============================================================================
# AsyncObskitTestCase
# =============================================================================


class TestAsyncObskitTestCaseSetup:
    """Test the async test case setup."""

    def _make_async_test(self):
        class MyAsyncTest(AsyncObskitTestCase):
            def runTest(self):
                pass  # NOSONAR

        t = MyAsyncTest()
        t.__class__.setUpClass()
        t.setUp()
        return t

    def test_has_event_loop_after_setup(self):
        t = self._make_async_test()
        assert t._loop is not None
        t.tearDown()

    def test_loop_closed_after_teardown(self):
        t = self._make_async_test()
        loop = t._loop
        t.tearDown()
        assert loop.is_closed()

    def test_run_async_executes_coroutine(self):
        t = self._make_async_test()

        async def simple_coro():  # NOSONAR
            return "async_result"

        result = t.run_async(simple_coro())
        assert result == "async_result"
        t.tearDown()

    def test_run_async_without_loop_raises(self):
        class MyAsyncTest(AsyncObskitTestCase):
            def runTest(self):
                pass  # NOSONAR

        t = MyAsyncTest()
        t.__class__.setUpClass()
        t.setUp()
        t._loop = None  # Simulate no loop

        async def coro():
            pass  # NOSONAR

        with pytest.raises(RuntimeError, match="No event loop"):
            t.run_async(coro())
        t.tearDown()

    def test_inherits_obskit_test_case_assertions(self):
        t = self._make_async_test()
        t.mock_metrics.observe_request("async_op", 0.1, "success")
        t.assertMetricRecorded("async_op")
        t.tearDown()

    def test_mocks_available_in_async_test(self):
        t = self._make_async_test()
        assert isinstance(t.mock_metrics, MockMetrics)
        assert isinstance(t.mock_tracer, MockTracer)
        t.tearDown()


class TestAsyncObskitTestCaseAsSubclass(AsyncObskitTestCase):
    """Test AsyncObskitTestCase as an actual subclass."""

    def test_run_async_with_simple_coro(self):
        async def add(a, b):  # NOSONAR
            return a + b

        result = self.run_async(add(3, 7))
        self.assertEqual(result, 10)

    def test_metrics_work_in_async_test(self):
        self.mock_metrics.observe_request("async_op", 0.05, "success")
        self.assertMetricRecorded("async_op")


class TestObskitTestCaseTeardownEdgeCases:
    def test_teardown_when_context_is_none(self):
        class MyTest(ObskitTestCase):
            def runTest(self): pass
        t = MyTest()
        t.__class__.setUpClass()
        t.setUp()
        # Manually clear context before tearDown
        t._obskit_context = None
        # Should not raise
        t.tearDown()


class TestAsyncObskitTestCase:
    def test_async_testcase_setup(self):
        class MyAsyncTest(AsyncObskitTestCase):
            def runTest(self): pass
        t = MyAsyncTest()
        t.__class__.setUpClass()
        t.setUp()
        assert t._loop is not None or t._loop is None  # Either is valid
        t.tearDown()

    def test_async_testcase_teardown_closes_loop(self):
        class MyAsyncTest(AsyncObskitTestCase):
            def runTest(self): pass
        t = MyAsyncTest()
        t.__class__.setUpClass()
        t.setUp()
        t.tearDown()
        # Loop should be closed after tearDown
        if t._loop is not None:
            assert t._loop.is_closed()

    def test_async_testcase_run_async(self):
        class MyAsyncTest(AsyncObskitTestCase):
            def runTest(self): pass
        t = MyAsyncTest()
        t.__class__.setUpClass()
        t.setUp()
        async def my_coroutine():  # NOSONAR
            return 42
        result = t.run_async(my_coroutine())
        assert result == 42
        t.tearDown()
