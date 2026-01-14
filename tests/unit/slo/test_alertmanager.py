"""Tests for obskit.slo.alertmanager module."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAlertmanagerWebhook:
    """Tests for AlertmanagerWebhook class."""

    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx", MagicMock())
    def test_init(self):
        """Test AlertmanagerWebhook initialization."""
        from obskit.slo.alertmanager import AlertmanagerWebhook

        webhook = AlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        assert webhook.alertmanager_url == "http://alertmanager:9093"
        assert webhook.timeout == 30.0
        assert webhook._alerts_endpoint == "http://alertmanager:9093/api/v2/alerts"

    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx", MagicMock())
    def test_init_with_custom_params(self):
        """Test initialization with custom parameters."""
        from obskit.slo.alertmanager import AlertmanagerWebhook

        webhook = AlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093/",  # Trailing slash
            generator_url="http://my-app.com",
            timeout=60.0,
            headers={"Authorization": "Bearer token"},
        )

        assert webhook.alertmanager_url == "http://alertmanager:9093"  # Trailing slash removed
        assert webhook.generator_url == "http://my-app.com"
        assert webhook.timeout == 60.0
        assert webhook.headers == {"Authorization": "Bearer token"}

    @pytest.mark.asyncio
    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx")
    async def test_fire_alert(self, mock_httpx):
        """Test firing an alert."""
        from obskit.slo.alertmanager import AlertmanagerWebhook

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        webhook = AlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        result = await webhook.fire_alert(
            alert_name="TestAlert",
            labels={"service": "test"},
            annotations={"summary": "Test alert"},
            severity="warning",
        )

        assert result is True
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx")
    async def test_fire_alert_tracks_active(self, mock_httpx):
        """Test that firing alert tracks it as active."""
        from obskit.slo.alertmanager import AlertmanagerWebhook

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        webhook = AlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        await webhook.fire_alert(
            alert_name="TestAlert",
            labels={"service": "test"},
        )

        assert len(webhook._active_alerts) == 1

    @pytest.mark.asyncio
    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx")
    async def test_resolve_alert(self, mock_httpx):
        """Test resolving an alert."""
        from obskit.slo.alertmanager import AlertmanagerWebhook

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        webhook = AlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        # Fire first
        await webhook.fire_alert(
            alert_name="TestAlert",
            labels={"service": "test"},
        )

        # Resolve
        result = await webhook.resolve_alert(
            alert_name="TestAlert",
            labels={"service": "test"},
        )

        assert result is True
        assert len(webhook._active_alerts) == 0

    @pytest.mark.asyncio
    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx")
    async def test_fire_slo_alert(self, mock_httpx):
        """Test firing SLO-specific alert."""
        from obskit.slo.alertmanager import AlertmanagerWebhook

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        webhook = AlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        result = await webhook.fire_slo_alert(
            service_name="order-api",
            slo_name="availability",
            current_value=0.98,
            target_value=0.999,
            error_budget_remaining=0.02,
        )

        assert result is True

    @pytest.mark.asyncio
    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx")
    async def test_fire_slo_alert_auto_severity(self, mock_httpx):
        """Test SLO alert auto-determines severity."""
        from obskit.slo.alertmanager import AlertmanagerWebhook

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        webhook = AlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        # Critical when budget is exhausted
        await webhook.fire_slo_alert(
            service_name="api",
            slo_name="latency",
            current_value=0.90,
            target_value=0.99,
            error_budget_remaining=-0.1,
        )

        # Should have called post
        mock_client.post.assert_called()

    @pytest.mark.asyncio
    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx")
    async def test_resolve_slo_alert(self, mock_httpx):
        """Test resolving SLO alert."""
        from obskit.slo.alertmanager import AlertmanagerWebhook

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        webhook = AlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        result = await webhook.resolve_slo_alert(
            service_name="order-api",
            slo_name="availability",
        )

        assert result is True

    @pytest.mark.asyncio
    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx")
    async def test_get_active_alerts(self, mock_httpx):
        """Test getting active alerts from Alertmanager."""
        from obskit.slo.alertmanager import AlertmanagerWebhook

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = [{"labels": {"alertname": "Test"}}]
        mock_client.get.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        webhook = AlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        alerts = await webhook.get_active_alerts()

        assert len(alerts) == 1
        assert alerts[0]["labels"]["alertname"] == "Test"

    @pytest.mark.asyncio
    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx")
    async def test_check_health(self, mock_httpx):
        """Test health check."""
        from obskit.slo.alertmanager import AlertmanagerWebhook

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        webhook = AlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        result = await webhook.check_health()

        assert result is True

    @pytest.mark.asyncio
    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx")
    async def test_check_health_failure(self, mock_httpx):
        """Test health check failure."""
        from obskit.slo.alertmanager import AlertmanagerWebhook

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection refused")
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        webhook = AlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        result = await webhook.check_health()

        assert result is False

    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx", MagicMock())
    def test_make_alert_key(self):
        """Test alert key generation."""
        from obskit.slo.alertmanager import AlertmanagerWebhook

        webhook = AlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        key = webhook._make_alert_key("TestAlert", {"a": "1", "b": "2"})

        assert key == "TestAlert:a=1,b=2"


class TestSyncAlertmanagerWebhook:
    """Tests for SyncAlertmanagerWebhook class."""

    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx", MagicMock())
    def test_init(self):
        """Test SyncAlertmanagerWebhook initialization."""
        from obskit.slo.alertmanager import SyncAlertmanagerWebhook

        webhook = SyncAlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        assert webhook._async_webhook is not None

    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx")
    def test_fire_alert_sync(self, mock_httpx):
        """Test firing alert synchronously."""
        from obskit.slo.alertmanager import SyncAlertmanagerWebhook

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        webhook = SyncAlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        result = webhook.fire_alert(
            alert_name="TestAlert",
            labels={"service": "test"},
        )

        assert result is True

    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx")
    def test_resolve_alert_sync(self, mock_httpx):
        """Test resolving alert synchronously."""
        from obskit.slo.alertmanager import SyncAlertmanagerWebhook

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        webhook = SyncAlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        result = webhook.resolve_alert(
            alert_name="TestAlert",
            labels={"service": "test"},
        )

        assert result is True

    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx")
    def test_fire_slo_alert_sync(self, mock_httpx):
        """Test firing SLO alert synchronously."""
        from obskit.slo.alertmanager import SyncAlertmanagerWebhook

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        webhook = SyncAlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        result = webhook.fire_slo_alert(
            service_name="api",
            slo_name="latency",
            current_value=0.95,
            target_value=0.99,
            error_budget_remaining=0.5,
        )

        assert result is True


class TestAiohttpPath:
    """Tests for aiohttp fallback path."""

    @pytest.mark.asyncio
    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", False)
    @patch("obskit.slo.alertmanager.httpx", None)
    @patch("obskit.slo.alertmanager.AIOHTTP_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.aiohttp")
    async def test_fire_alert_aiohttp(self, mock_aiohttp):
        """Test firing alert via aiohttp."""
        from obskit.slo.alertmanager import AlertmanagerWebhook

        mock_response = MagicMock()
        mock_response.status = 200
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response
        mock_session = MagicMock()
        mock_session.post.return_value = mock_cm
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_aiohttp.ClientSession.return_value = mock_session
        mock_aiohttp.ClientTimeout = MagicMock()

        webhook = AlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        result = await webhook.fire_alert(
            alert_name="TestAlert",
            labels={"service": "test"},
        )

        assert result is True

    @pytest.mark.asyncio
    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", False)
    @patch("obskit.slo.alertmanager.httpx", None)
    @patch("obskit.slo.alertmanager.AIOHTTP_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.aiohttp")
    async def test_get_active_alerts_aiohttp(self, mock_aiohttp):
        """Test getting alerts via aiohttp."""
        from obskit.slo.alertmanager import AlertmanagerWebhook

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[{"labels": {"alertname": "Test"}}])
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response
        mock_session = MagicMock()
        mock_session.get.return_value = mock_cm
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_aiohttp.ClientSession.return_value = mock_session
        mock_aiohttp.ClientTimeout = MagicMock()

        webhook = AlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        alerts = await webhook.get_active_alerts()

        assert len(alerts) == 1

    @pytest.mark.asyncio
    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", False)
    @patch("obskit.slo.alertmanager.httpx", None)
    @patch("obskit.slo.alertmanager.AIOHTTP_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.aiohttp")
    async def test_check_health_aiohttp(self, mock_aiohttp):
        """Test health check via aiohttp."""
        from obskit.slo.alertmanager import AlertmanagerWebhook

        mock_response = MagicMock()
        mock_response.status = 200
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_response
        mock_session = MagicMock()
        mock_session.get.return_value = mock_cm
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_aiohttp.ClientSession.return_value = mock_session
        mock_aiohttp.ClientTimeout = MagicMock()

        webhook = AlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        result = await webhook.check_health()

        assert result is True

    @pytest.mark.asyncio
    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx")
    async def test_post_alerts_exception(self, mock_httpx):
        """Test _post_alerts handles exception."""
        from obskit.slo.alertmanager import AlertmanagerWebhook

        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection error")
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        webhook = AlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        result = await webhook.fire_alert(
            alert_name="TestAlert",
            labels={"service": "test"},
        )

        assert result is False

    @pytest.mark.asyncio
    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx")
    async def test_get_active_alerts_exception(self, mock_httpx):
        """Test get_active_alerts handles exception."""
        from obskit.slo.alertmanager import AlertmanagerWebhook

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection error")
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        webhook = AlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        alerts = await webhook.get_active_alerts()

        assert alerts == []

    @pytest.mark.asyncio
    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx")
    async def test_fire_alert_with_ends_at(self, mock_httpx):
        """Test fire_alert with ends_at timestamp."""
        from obskit.slo.alertmanager import AlertmanagerWebhook

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        webhook = AlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        ends_at = datetime.now(UTC)
        result = await webhook.fire_alert(
            alert_name="TestAlert",
            labels={"service": "test"},
            ends_at=ends_at,
        )

        assert result is True

    @pytest.mark.asyncio
    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx")
    async def test_fire_alert_with_generator_url(self, mock_httpx):
        """Test fire_alert with generator_url set."""
        from obskit.slo.alertmanager import AlertmanagerWebhook

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        webhook = AlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
            generator_url="http://my-app.com/alerts",
        )

        result = await webhook.fire_alert(
            alert_name="TestAlert",
            labels={"service": "test"},
        )

        assert result is True


class TestSyncAlertmanagerWebhookEdgeCases:
    """Edge case tests for SyncAlertmanagerWebhook."""

    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx")
    def test_sync_webhook_fire_alert(self, mock_httpx):
        """Test SyncAlertmanagerWebhook fire_alert."""
        from obskit.slo.alertmanager import SyncAlertmanagerWebhook

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        webhook = SyncAlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        result = webhook.fire_alert(
            alert_name="TestAlert",
            labels={"service": "test"},
        )

        assert result is True

    @patch("obskit.slo.alertmanager.HTTPX_AVAILABLE", True)
    @patch("obskit.slo.alertmanager.httpx")
    def test_sync_webhook_resolve_alert(self, mock_httpx):
        """Test SyncAlertmanagerWebhook resolve_alert."""
        from obskit.slo.alertmanager import SyncAlertmanagerWebhook

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.post.return_value = mock_response
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client

        webhook = SyncAlertmanagerWebhook(
            alertmanager_url="http://alertmanager:9093",
        )

        result = webhook.resolve_alert(
            alert_name="TestAlert",
            labels={"service": "test"},
        )

        assert result is True
