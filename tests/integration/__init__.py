"""Integration tests for obskit.

Integration tests verify that components work together correctly.
They may use testcontainers for real external services.

Guidelines:
- Test API contracts between components
- Use testcontainers for Redis, etc.
- Tests may take longer (< 30 seconds each)
- Mark with @pytest.mark.integration
"""
