"""End-to-end tests for obskit.

E2E tests verify complete workflows from user perspective.
They test the full stack including external services.

Guidelines:
- Test complete user scenarios
- Use Docker Compose or testcontainers
- May take longer (< 60 seconds each)
- Mark with @pytest.mark.e2e
"""
