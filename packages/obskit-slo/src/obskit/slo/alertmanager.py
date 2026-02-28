"""
Alertmanager Integration
=========================

This module provides integration with Prometheus Alertmanager for sending
and managing SLO-based alerts programmatically.

Use Cases
---------
- Firing alerts when SLO budgets are exhausted
- Resolving alerts when SLOs recover
- Custom alerting for application-specific conditions
- Integration with SLO tracking

Example - Fire Alert
--------------------
.. code-block:: python

    from obskit.slo.alertmanager import AlertmanagerWebhook

    webhook = AlertmanagerWebhook(
        alertmanager_url="http://alertmanager:9093",
    )

    await webhook.fire_alert(
        alert_name="SLOBudgetExhausted",
        labels={"service": "order-api", "slo": "availability"},
        annotations={
            "summary": "SLO budget exhausted for order-api availability",
            "description": "Less than 5% error budget remaining",
        },
        severity="critical",
    )

Example - Resolve Alert
-----------------------
.. code-block:: python

    await webhook.resolve_alert(
        alert_name="SLOBudgetExhausted",
        labels={"service": "order-api", "slo": "availability"},
    )

Example - SLO Integration
--------------------------
.. code-block:: python

    from obskit.slo import SLOTracker
    from obskit.slo.alertmanager import AlertmanagerWebhook

    webhook = AlertmanagerWebhook(alertmanager_url="http://alertmanager:9093")
    tracker = SLOTracker(...)

    # Check SLO and alert if budget exhausted
    status = tracker.get_status()
    if status.error_budget_remaining < 0.05:  # Less than 5%
        await webhook.fire_alert(
            alert_name="SLOBudgetLow",
            labels={"service": "order-api", "slo": status.slo_name},
            annotations={"summary": f"Only {status.error_budget_remaining:.1%} budget remaining"},
        )
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

from obskit.logging import get_logger

logger = get_logger("obskit.slo.alertmanager")

# Check for httpx (async HTTP client)
try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:  # pragma: no cover
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore[assignment]

# Fallback to aiohttp if httpx not available
try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:  # pragma: no cover
    AIOHTTP_AVAILABLE = False
    aiohttp = None  # type: ignore[assignment]


class AlertmanagerWebhook:
    """
    Send alerts to Prometheus Alertmanager via its HTTP API.

    This class provides methods to fire and resolve alerts programmatically,
    enabling integration with SLO tracking and custom alerting logic.

    Parameters
    ----------
    alertmanager_url : str
        Base URL of the Alertmanager (e.g., "http://alertmanager:9093").

    generator_url : str, optional
        URL to use as generator URL in alerts.

    timeout : float, optional
        HTTP request timeout in seconds. Default: 30.0

    headers : dict, optional
        Additional HTTP headers (e.g., for authentication).

    Example
    -------
    >>> webhook = AlertmanagerWebhook(
    ...     alertmanager_url="http://alertmanager:9093",
    ... )
    >>> await webhook.fire_alert(
    ...     alert_name="HighErrorRate",
    ...     labels={"service": "api"},
    ...     annotations={"summary": "Error rate is high"},
    ... )
    """

    def __init__(
        self,
        alertmanager_url: str,
        generator_url: str | None = None,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        if not HTTPX_AVAILABLE and not AIOHTTP_AVAILABLE:  # pragma: no cover
            raise ImportError(
                "HTTP client not available. Install with: pip install httpx or pip install aiohttp"
            )

        self.alertmanager_url = alertmanager_url.rstrip("/")
        self.generator_url = generator_url or ""
        self.timeout = timeout
        self.headers = headers or {}

        # API endpoint for posting alerts
        self._alerts_endpoint = urljoin(self.alertmanager_url + "/", "api/v2/alerts")

        # Track active alerts
        self._active_alerts: dict[str, dict[str, Any]] = {}

        logger.debug(
            "alertmanager_webhook_init",
            alertmanager_url=alertmanager_url,
            endpoint=self._alerts_endpoint,
        )

    async def fire_alert(
        self,
        alert_name: str,
        labels: dict[str, str],
        annotations: dict[str, str] | None = None,
        severity: str = "warning",
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
    ) -> bool:
        """
        Fire an alert to Alertmanager.

        Parameters
        ----------
        alert_name : str
            Name of the alert (becomes alertname label).

        labels : dict
            Alert labels for routing and grouping.
            Should include identifiers like service, slo, etc.

        annotations : dict, optional
            Alert annotations (summary, description, etc.).

        severity : str, optional
            Alert severity (critical, warning, info). Default: "warning"

        starts_at : datetime, optional
            When the alert started. Default: now

        ends_at : datetime, optional
            When the alert ends (for pre-scheduled end).

        Returns
        -------
        bool
            True if alert was successfully sent.

        Example
        -------
        >>> await webhook.fire_alert(
        ...     alert_name="SLOBudgetLow",
        ...     labels={"service": "order-api", "slo": "latency"},
        ...     annotations={"summary": "SLO budget running low"},
        ...     severity="warning",
        ... )
        """
        # Build alert payload
        alert_labels = {
            "alertname": alert_name,
            "severity": severity,
            **labels,
        }

        alert_annotations = annotations or {}

        now = datetime.now(UTC)
        alert: dict[str, Any] = {
            "labels": alert_labels,
            "annotations": alert_annotations,
            "startsAt": (starts_at or now).isoformat(),
        }

        if ends_at:
            alert["endsAt"] = ends_at.isoformat()

        if self.generator_url:
            alert["generatorURL"] = self.generator_url

        # Track this alert
        alert_key = self._make_alert_key(alert_name, labels)
        self._active_alerts[alert_key] = alert

        # Send to Alertmanager
        return await self._post_alerts([alert])

    async def resolve_alert(
        self,
        alert_name: str,
        labels: dict[str, str],
    ) -> bool:
        """
        Resolve a previously fired alert.

        Parameters
        ----------
        alert_name : str
            Name of the alert to resolve.

        labels : dict
            Labels that identify the alert.

        Returns
        -------
        bool
            True if resolution was successfully sent.

        Example
        -------
        >>> await webhook.resolve_alert(
        ...     alert_name="SLOBudgetLow",
        ...     labels={"service": "order-api", "slo": "latency"},
        ... )
        """
        # Build resolved alert
        alert_labels = {
            "alertname": alert_name,
            **labels,
        }

        now = datetime.now(UTC)
        alert: dict[str, Any] = {
            "labels": alert_labels,
            "annotations": {},
            "startsAt": now.isoformat(),
            "endsAt": now.isoformat(),  # End time = now means resolved
        }

        # Remove from active alerts
        alert_key = self._make_alert_key(alert_name, labels)
        self._active_alerts.pop(alert_key, None)

        return await self._post_alerts([alert])

    async def fire_slo_alert(
        self,
        service_name: str,
        slo_name: str,
        current_value: float,
        target_value: float,
        error_budget_remaining: float,
        severity: str | None = None,
    ) -> bool:
        """
        Fire an SLO-specific alert.

        Convenience method for firing SLO-related alerts with
        standard labels and annotations.

        Parameters
        ----------
        service_name : str
            Name of the service.

        slo_name : str
            Name of the SLO.

        current_value : float
            Current SLO value (e.g., 0.995 for 99.5%).

        target_value : float
            Target SLO value.

        error_budget_remaining : float
            Remaining error budget as fraction (0.0 to 1.0).

        severity : str, optional
            Alert severity. Auto-determined if not provided.

        Returns
        -------
        bool
            True if alert was sent.

        Example
        -------
        >>> await webhook.fire_slo_alert(
        ...     service_name="order-api",
        ...     slo_name="availability",
        ...     current_value=0.98,
        ...     target_value=0.999,
        ...     error_budget_remaining=0.02,
        ... )
        """
        # Auto-determine severity based on error budget
        if severity is None:  # pragma: no branch
            if error_budget_remaining <= 0:
                severity = "critical"
            elif error_budget_remaining < 0.25:
                severity = "warning"
            else:
                severity = "info"

        labels = {
            "service": service_name,
            "slo": slo_name,
        }

        annotations = {
            "summary": f"SLO violation for {service_name}/{slo_name}",
            "description": (
                f"Current: {current_value:.2%}, Target: {target_value:.2%}, "
                f"Error budget remaining: {error_budget_remaining:.2%}"
            ),
            "current_value": f"{current_value:.4f}",
            "target_value": f"{target_value:.4f}",
            "error_budget_remaining": f"{error_budget_remaining:.4f}",
        }

        return await self.fire_alert(
            alert_name="SLOViolation",
            labels=labels,
            annotations=annotations,
            severity=severity,
        )

    async def resolve_slo_alert(
        self,
        service_name: str,
        slo_name: str,
    ) -> bool:
        """
        Resolve an SLO alert.

        Parameters
        ----------
        service_name : str
            Name of the service.

        slo_name : str
            Name of the SLO.

        Returns
        -------
        bool
            True if resolution was sent.
        """
        return await self.resolve_alert(
            alert_name="SLOViolation",
            labels={"service": service_name, "slo": slo_name},
        )

    async def get_active_alerts(self) -> list[dict[str, Any]]:
        """
        Get currently active alerts from Alertmanager.

        Returns
        -------
        list[dict]
            List of active alerts.
        """
        try:
            if HTTPX_AVAILABLE and httpx is not None:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(
                        self._alerts_endpoint,
                        headers=self.headers,
                    )
                    response.raise_for_status()
                    result: list[dict[str, Any]] = response.json()
                    return result
            elif AIOHTTP_AVAILABLE and aiohttp is not None:  # pragma: no cover
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        self._alerts_endpoint,
                        headers=self.headers,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ) as aio_response:
                        aio_response.raise_for_status()
                        result = await aio_response.json()
                        return result

        except Exception as e:
            logger.error(
                "alertmanager_get_alerts_failed",
                error=str(e),
                error_type=type(e).__name__,
            )

        return []

    async def check_health(self) -> bool:
        """
        Check if Alertmanager is healthy.

        Returns
        -------
        bool
            True if Alertmanager is reachable.
        """
        health_url = urljoin(self.alertmanager_url + "/", "-/healthy")

        try:
            if HTTPX_AVAILABLE and httpx is not None:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(health_url)
                    return bool(response.status_code == 200)
            elif AIOHTTP_AVAILABLE and aiohttp is not None:  # pragma: no cover
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        health_url,
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ) as aio_response:
                        # aiohttp response has .status attribute
                        status: int = getattr(aio_response, "status", 0)
                        return bool(status == 200)

        except Exception as e:
            logger.warning(
                "alertmanager_health_check_failed",
                error=str(e),
            )

        return False

    async def _post_alerts(self, alerts: list[dict[str, Any]]) -> bool:
        """Post alerts to Alertmanager API."""
        try:
            if HTTPX_AVAILABLE and httpx is not None:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self._alerts_endpoint,
                        json=alerts,
                        headers={"Content-Type": "application/json", **self.headers},
                    )
                    response.raise_for_status()

                    logger.info(
                        "alertmanager_alerts_posted",
                        count=len(alerts),
                        status_code=response.status_code,
                    )
                    return True

            elif AIOHTTP_AVAILABLE and aiohttp is not None:  # pragma: no cover
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self._alerts_endpoint,
                        json=alerts,
                        headers={"Content-Type": "application/json", **self.headers},
                        timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ) as aio_response:
                        aio_response.raise_for_status()

                        # aiohttp response has .status attribute
                        status_code: int = getattr(aio_response, "status", 0)
                        logger.info(
                            "alertmanager_alerts_posted",
                            count=len(alerts),
                            status_code=status_code,
                        )
                        return True

        except Exception as e:
            logger.error(
                "alertmanager_post_alerts_failed",
                error=str(e),
                error_type=type(e).__name__,
                alert_count=len(alerts),
            )

        return False

    def _make_alert_key(self, alert_name: str, labels: dict[str, str]) -> str:
        """Create unique key for an alert."""
        sorted_labels = sorted(labels.items())
        label_str = ",".join(f"{k}={v}" for k, v in sorted_labels)
        return f"{alert_name}:{label_str}"


class SyncAlertmanagerWebhook:
    """
    Synchronous wrapper for AlertmanagerWebhook.

    Use this when you need to fire alerts from synchronous code.

    Example
    -------
    >>> webhook = SyncAlertmanagerWebhook(
    ...     alertmanager_url="http://alertmanager:9093",
    ... )
    >>> webhook.fire_alert(
    ...     alert_name="HighErrorRate",
    ...     labels={"service": "api"},
    ...     annotations={"summary": "Error rate is high"},
    ... )
    """

    def __init__(
        self,
        alertmanager_url: str,
        generator_url: str | None = None,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._async_webhook = AlertmanagerWebhook(
            alertmanager_url=alertmanager_url,
            generator_url=generator_url,
            timeout=timeout,
            headers=headers,
        )

    def _run_async(self, coro: Any) -> Any:
        """Run async coroutine in sync context."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():  # pragma: no cover
                # If we're in an async context, create a new loop
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, coro)
                    return future.result()
            return loop.run_until_complete(coro)
        except RuntimeError:  # pragma: no cover
            return asyncio.run(coro)

    def fire_alert(
        self,
        alert_name: str,
        labels: dict[str, str],
        annotations: dict[str, str] | None = None,
        severity: str = "warning",
    ) -> bool:
        """Fire an alert (sync version)."""
        result: bool = self._run_async(
            self._async_webhook.fire_alert(
                alert_name=alert_name,
                labels=labels,
                annotations=annotations,
                severity=severity,
            )
        )
        return result

    def resolve_alert(
        self,
        alert_name: str,
        labels: dict[str, str],
    ) -> bool:
        """Resolve an alert (sync version)."""
        result: bool = self._run_async(
            self._async_webhook.resolve_alert(
                alert_name=alert_name,
                labels=labels,
            )
        )
        return result

    def fire_slo_alert(
        self,
        service_name: str,
        slo_name: str,
        current_value: float,
        target_value: float,
        error_budget_remaining: float,
        severity: str | None = None,
    ) -> bool:
        """Fire an SLO alert (sync version)."""
        result: bool = self._run_async(
            self._async_webhook.fire_slo_alert(
                service_name=service_name,
                slo_name=slo_name,
                current_value=current_value,
                target_value=target_value,
                error_budget_remaining=error_budget_remaining,
                severity=severity,
            )
        )
        return result


__all__ = [
    "AlertmanagerWebhook",
    "SyncAlertmanagerWebhook",
    "HTTPX_AVAILABLE",
    "AIOHTTP_AVAILABLE",
]
