# Test Organization

obskit uses a structured test organization for maintainability and clarity.

## Directory Structure

```
tests/
├── unit/              # Fast, isolated tests (no external deps)
├── integration/       # Component integration tests (testcontainers)
├── e2e/               # Full stack end-to-end tests
├── stress/            # Load and concurrency tests
├── conftest.py        # Shared fixtures
└── test_*.py          # Legacy tests (being migrated)
```

## Test Categories

### Unit Tests (`tests/unit/`)

- **Purpose**: Test individual functions/classes in isolation
- **Speed**: Fast (< 1 second each)
- **Dependencies**: Mocked
- **Run**: `pytest tests/unit/ -v`

```python
# Example: tests/unit/test_context.py
def test_correlation_id_generation():
    with correlation_context() as cid:
        assert cid is not None
        assert len(cid) == 36  # UUID format
```

### Integration Tests (`tests/integration/`)

- **Purpose**: Test component interactions
- **Speed**: Medium (< 30 seconds each)
- **Dependencies**: Testcontainers (Redis, etc.)
- **Run**: `pytest tests/integration/ -v -m integration`

```python
# Example: tests/integration/test_distributed_circuit_breaker.py
@pytest.mark.integration
async def test_circuit_breaker_with_redis(redis_container):
    breaker = DistributedCircuitBreaker(
        name="test",
        redis_client=redis_container.client,
    )
    # Test with real Redis
```

### E2E Tests (`tests/e2e/`)

- **Purpose**: Test complete user scenarios
- **Speed**: Slow (< 60 seconds each)
- **Dependencies**: Full Docker Compose stack
- **Run**: `pytest tests/e2e/ -v -m e2e`

```python
# Example: tests/e2e/test_full_observability.py
@pytest.mark.e2e
async def test_request_traced_and_metered(app_container):
    response = await client.get("/api/orders/123")
    # Verify metrics in Prometheus
    # Verify trace in Jaeger
```

### Stress Tests (`tests/stress/`)

- **Purpose**: Test under load and concurrency
- **Speed**: Variable
- **Run**: `pytest tests/stress/ -v -m slow`

## Running Tests

```bash
# All tests
pytest tests/ -v

# Unit tests only (fast)
pytest tests/unit/ -v

# Integration tests (requires Docker)
pytest tests/integration/ -v -m integration

# E2E tests (requires Docker Compose)
pytest tests/e2e/ -v -m e2e

# Stress tests
pytest tests/stress/ -v -m slow

# With coverage
pytest tests/ --cov=src/obskit --cov-report=html
```

## Test Markers

```python
@pytest.mark.unit        # Unit test
@pytest.mark.integration # Integration test
@pytest.mark.e2e         # End-to-end test
@pytest.mark.slow        # Slow test (stress/load)
```

## Fixtures

Common fixtures are in `conftest.py`:

- `reset_metrics`: Reset Prometheus registry
- `reset_context`: Clear correlation context
- `mock_logger`: Mock structlog logger
- `redis_container`: Testcontainers Redis (integration)
- `app_container`: Full app stack (e2e)

