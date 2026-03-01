"""Unit tests for Failover Coordinator."""

from obskit.failover import (
    Endpoint,
    EndpointRole,
    FailoverCoordinator,
    FailoverState,
    get_failover_coordinator,
)


class TestFailoverCoordinator:
    """Tests for FailoverCoordinator."""

    def test_register_primary(self):
        """Test registering primary endpoint."""
        coordinator = FailoverCoordinator("test")

        coordinator.register_primary(
            name="primary-db",
            address="localhost:5432",
        )

        active = coordinator.get_active()
        assert active is not None
        assert active.name == "primary-db"
        assert active.role == EndpointRole.PRIMARY

    def test_register_backup(self):
        """Test registering backup endpoint."""
        coordinator = FailoverCoordinator("test")

        coordinator.register_primary("primary", "localhost:5432")
        coordinator.register_backup("backup", "localhost:5433")

        status = coordinator.get_status()
        assert status["backup"] is not None
        assert status["backup"]["name"] == "backup"

    def test_get_active_address(self):
        """Test getting active endpoint address."""
        coordinator = FailoverCoordinator("test")

        coordinator.register_primary("primary", "localhost:5432")

        address = coordinator.get_active_address()
        assert address == "localhost:5432"

    def test_force_failover(self):
        """Test forced failover."""
        coordinator = FailoverCoordinator("test")

        coordinator.register_primary("primary", "localhost:5432")
        coordinator.register_backup("backup", "localhost:5433")

        coordinator.force_failover("Manual test")

        assert coordinator.get_state() == FailoverState.BACKUP
        active = coordinator.get_active()
        assert active.name == "backup"

    def test_force_recovery(self):
        """Test forced recovery."""
        coordinator = FailoverCoordinator("test")

        coordinator.register_primary("primary", "localhost:5432")
        coordinator.register_backup("backup", "localhost:5433")

        coordinator.force_failover()
        coordinator.force_recovery()

        assert coordinator.get_state() == FailoverState.PRIMARY

    def test_health_check_failover(self):
        """Test automatic failover on health check failure."""
        primary_healthy = True
        backup_healthy = True

        def check_primary():
            return primary_healthy

        def check_backup():
            return backup_healthy

        coordinator = FailoverCoordinator(
            "test",
            failure_threshold=1,
        )

        coordinator.register_primary(
            "primary",
            health_check=check_primary,
        )
        coordinator.register_backup(
            "backup",
            health_check=check_backup,
        )

        # Initial check - should stay on primary
        coordinator.check_health()
        assert coordinator.get_state() == FailoverState.PRIMARY

        # Make primary unhealthy
        primary_healthy = False
        coordinator.check_health()

        # Should failover
        assert coordinator.get_state() == FailoverState.BACKUP

    def test_get_events(self):
        """Test getting failover events."""
        coordinator = FailoverCoordinator("test")

        coordinator.register_primary("primary")
        coordinator.register_backup("backup")

        coordinator.force_failover("Test 1")
        coordinator.force_recovery()

        events = coordinator.get_events()
        assert len(events) >= 2

    def test_get_status(self):
        """Test getting full status."""
        coordinator = FailoverCoordinator("test")

        coordinator.register_primary("primary", "localhost:5432")
        coordinator.register_backup("backup", "localhost:5433")

        status = coordinator.get_status()

        assert status["coordinator"] == "test"
        assert status["state"] == "primary"
        assert status["primary"] is not None
        assert status["backup"] is not None


class TestEndpoint:
    """Tests for Endpoint."""

    def test_to_dict(self):
        """Test Endpoint serialization."""
        endpoint = Endpoint(
            name="test",
            role=EndpointRole.PRIMARY,
            address="localhost:5432",
            is_healthy=True,
        )

        data = endpoint.to_dict()
        assert data["name"] == "test"
        assert data["role"] == "primary"
        assert data["is_healthy"] is True


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_failover_coordinator(self):
        """Test coordinator singleton per name."""
        coord1 = get_failover_coordinator("test1")
        coord2 = get_failover_coordinator("test1")
        coord3 = get_failover_coordinator("test2")

        assert coord1 is coord2
        assert coord1 is not coord3
