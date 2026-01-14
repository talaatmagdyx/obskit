# Security Policy

## Supported Versions

The following versions of obskit are currently supported with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take the security of obskit seriously. If you believe you have found a security vulnerability, please report it to us responsibly.

### How to Report

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them via one of the following methods:

1. **Email**: Send details to [talaatmagdy75@gmail.com](mailto:talaatmagdy75@gmail.com)
2. **GitHub Private Vulnerability Reporting**: Use GitHub's [private vulnerability reporting](https://github.com/talaatmagdyx/obskit/security/advisories/new) feature

### What to Include

Please include the following information in your report:

- **Type of vulnerability** (e.g., buffer overflow, SQL injection, cross-site scripting)
- **Full paths of source file(s)** related to the vulnerability
- **Location of the affected source code** (tag/branch/commit or direct URL)
- **Step-by-step instructions** to reproduce the issue
- **Proof-of-concept or exploit code** (if possible)
- **Impact of the issue**, including how an attacker might exploit it

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Resolution Target**: Within 90 days (depending on complexity)

### What to Expect

1. **Acknowledgment**: We will acknowledge receipt of your vulnerability report
2. **Communication**: We will keep you informed of the progress toward a fix
3. **Credit**: We will credit you in the security advisory (unless you prefer to remain anonymous)
4. **Disclosure**: We follow responsible disclosure practices

## Security Best Practices for Users

### Configuration Security

```python
from obskit import configure

# Use environment variables for sensitive configuration
configure(
    service_name="my-service",
    # Don't hardcode credentials - use environment variables
    # OBSKIT_OTLP_ENDPOINT, OBSKIT_API_KEY, etc.
)
```

### PII Redaction

obskit includes built-in PII redaction. Always enable it in production:

```python
from obskit import configure_logging

logger = configure_logging(
    service_name="my-service",
    redact_pii=True,  # Enable PII redaction
)
```

### Metrics Endpoint Security

Protect your metrics endpoint in production:

```python
from obskit.metrics.auth import MetricsAuthMiddleware

# Add authentication to metrics endpoint
app.add_middleware(
    MetricsAuthMiddleware,
    api_key="your-secure-api-key",  # Use environment variable
)
```

### Rate Limiting

Enable rate limiting to prevent abuse:

```python
from obskit import configure

configure(
    metrics_rate_limit_enabled=True,
    metrics_rate_limit_requests=100,  # requests per minute
)
```

## Security Features

obskit includes several security features:

| Feature | Description |
|---------|-------------|
| **PII Redaction** | Automatic redaction of sensitive data in logs |
| **Metrics Auth** | Optional authentication for metrics endpoints |
| **Rate Limiting** | Built-in rate limiting for metrics endpoints |
| **No Eval/Exec** | No dynamic code execution |
| **Type Safety** | Full type hints with strict mypy checking |
| **Dependency Scanning** | Regular dependency vulnerability scanning |

## Security Scanning

We regularly scan for security issues using:

- **Dependabot**: Automated dependency updates
- **CodeQL**: Static code analysis
- **pip-audit**: Python package vulnerability scanning
- **bandit**: Python security linter

To run security scans locally:

```bash
# Install security tools
pip install obskit[security]

# Run pip-audit
pip-audit

# Run bandit
bandit -r src/obskit
```

## Known Security Considerations

### Log Data

- Logs may contain request/response data - ensure PII redaction is enabled
- Consider log retention policies for compliance

### Metrics Data

- Metrics endpoints should not be publicly accessible
- Use authentication in production environments

### Tracing Data

- Distributed traces may contain sensitive request data
- Configure sampling appropriately for sensitive services

## Security Updates

Security updates are released as patch versions (e.g., 1.0.1) and announced via:

- GitHub Security Advisories
- CHANGELOG.md
- GitHub Releases

Subscribe to repository notifications to stay informed about security updates.
