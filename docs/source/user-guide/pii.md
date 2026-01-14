# PII Redaction Guide

Personally Identifiable Information (PII) in logs and traces creates compliance
and security risks. obskit provides automatic PII redaction.

## Why PII Redaction?

### The Risks

Without PII redaction, your logs might contain:

```json
{
  "event": "User registered",
  "email": "john.doe@example.com",
  "phone": "+1-555-123-4567",
  "ssn": "123-45-6789",
  "credit_card": "4111-1111-1111-1111"
}
```

This creates:

| Risk | Impact |
|------|--------|
| **GDPR Violations** | Up to €20M or 4% of global revenue |
| **Data Breaches** | Logs often have weaker access controls |
| **Compliance Failures** | PCI-DSS, HIPAA, SOC 2 violations |
| **Privacy Lawsuits** | Class action potential |

### The Solution

With PII redaction:

```json
{
  "event": "User registered",
  "email": "[EMAIL REDACTED]",
  "phone": "[PHONE REDACTED]",
  "ssn": "[SSN REDACTED]",
  "credit_card": "[CREDIT_CARD REDACTED]"
}
```

## Basic Usage

### Automatic Redaction in Logs

```python
from obskit import configure_logging

# Enable PII redaction
logger = configure_logging(
    service_name="user-service",
    pii_redaction=True,
)

# PII is automatically redacted
logger.info("User signed up", email="john@example.com")
# Output: {"event": "User signed up", "email": "[EMAIL REDACTED]"}
```

### Manual Redaction

```python
from obskit.compliance import redact_pii

# Redact a single value
safe_email = redact_pii("john@example.com")
# Result: "[EMAIL REDACTED]"

# Redact a string with PII
message = redact_pii("Contact: john@example.com, +1-555-123-4567")
# Result: "Contact: [EMAIL REDACTED], [PHONE REDACTED]"

# Redact a dictionary
data = redact_pii({
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+1-555-123-4567",
})
# Result: {"name": "John Doe", "email": "[EMAIL REDACTED]", "phone": "[PHONE REDACTED]"}
```

## Supported PII Types

| Type | Pattern | Example | Redacted |
|------|---------|---------|----------|
| Email | `*@*.*` | john@example.com | [EMAIL REDACTED] |
| Phone | Various formats | +1-555-123-4567 | [PHONE REDACTED] |
| SSN | `XXX-XX-XXXX` | 123-45-6789 | [SSN REDACTED] |
| Credit Card | 13-19 digits | 4111111111111111 | [CREDIT_CARD REDACTED] |
| IP Address | IPv4/IPv6 | 192.168.1.1 | [IP REDACTED] |
| API Key | Common patterns | sk_live_xxx | [API_KEY REDACTED] |

## Configuration

### Custom Patterns

```python
from obskit.compliance import PIIRedactor, PIIPattern

# Create custom redactor with additional patterns
redactor = PIIRedactor(
    patterns=[
        PIIPattern(
            name="employee_id",
            pattern=r"EMP-\d{6}",
            replacement="[EMPLOYEE_ID REDACTED]",
        ),
        PIIPattern(
            name="internal_id",
            pattern=r"INT-[A-Z]{3}-\d{4}",
            replacement="[INTERNAL_ID REDACTED]",
        ),
    ],
    include_defaults=True,  # Include built-in patterns
)

# Use custom redactor
safe_data = redactor.redact("Employee EMP-123456 processed order")
# Result: "Employee [EMPLOYEE_ID REDACTED] processed order"
```

### Disable Specific Patterns

```python
from obskit.compliance import PIIRedactor

# Disable IP redaction (e.g., for internal services)
redactor = PIIRedactor(
    disabled_patterns=["ip_address"],
)
```

### Allow-Listed Values

```python
from obskit.compliance import PIIRedactor

# Don't redact specific values
redactor = PIIRedactor(
    allowlist=[
        "support@company.com",  # Public support email
        "1-800-COMPANY",        # Public phone number
    ],
)
```

## Context-Aware Redaction

### Field-Based Rules

```python
from obskit.compliance import FieldRedactor

# Redact specific fields regardless of content
field_redactor = FieldRedactor(
    sensitive_fields=[
        "password",
        "token",
        "secret",
        "api_key",
        "authorization",
    ],
)

data = {
    "username": "john",
    "password": "secret123",
    "token": "abc123xyz",
}

safe_data = field_redactor.redact(data)
# Result: {"username": "john", "password": "[REDACTED]", "token": "[REDACTED]"}
```

### Nested Data

```python
from obskit.compliance import redact_pii

nested_data = {
    "user": {
        "profile": {
            "email": "john@example.com",
            "preferences": {"notifications": True},
        },
    },
    "metadata": {
        "ip": "192.168.1.1",
    },
}

safe_data = redact_pii(nested_data)
# All PII is redacted at any nesting level
```

## Integration

### With Logging

```python
from obskit import configure_logging
from obskit.compliance import PIIRedactor

# Custom redactor
redactor = PIIRedactor(
    patterns=[...],
    allowlist=["support@company.com"],
)

logger = configure_logging(
    service_name="api",
    pii_redactor=redactor,
)
```

### With Tracing

```python
from obskit import configure_tracing
from obskit.compliance import redact_pii

configure_tracing(service_name="api")

# Redact span attributes
with tracer.start_as_current_span("process_user") as span:
    span.set_attribute("user.email", redact_pii(user.email))
    span.set_attribute("user.id", user.id)  # Not PII, keep as-is
```

### With Error Reporting

```python
from obskit.compliance import redact_pii

try:
    process_request()
except Exception as e:
    # Redact PII from error message
    safe_error = redact_pii(str(e))
    logger.error("Request failed", error=safe_error)
    
    # Or redact the full context
    error_context = redact_pii({
        "user_email": user.email,
        "request_data": request_data,
    })
    sentry.capture_exception(extra=error_context)
```

## Best Practices

### 1. Enable by Default

```python
# Good: PII redaction always on
logger = configure_logging(pii_redaction=True)

# Bad: Optional, might forget
logger = configure_logging()  # PII could leak
```

### 2. Redact at the Source

```python
# Good: Redact before logging
logger.info("Processing order", customer_email=redact_pii(email))

# Bad: Hope the logger catches it
logger.info("Processing order", customer_email=email)
```

### 3. Test Your Redaction

```python
def test_pii_redaction():
    """Ensure PII is properly redacted."""
    test_cases = [
        ("john@example.com", "[EMAIL REDACTED]"),
        ("+1-555-123-4567", "[PHONE REDACTED]"),
        ("4111111111111111", "[CREDIT_CARD REDACTED]"),
    ]
    
    for input_val, expected in test_cases:
        assert redact_pii(input_val) == expected
```

### 4. Audit Your Logs

```python
# Periodic audit script
import re

PII_PATTERNS = [
    r'\b[\w.-]+@[\w.-]+\.\w+\b',  # Email
    r'\b\d{3}-\d{2}-\d{4}\b',     # SSN
]

def audit_logs(log_file: str) -> list[str]:
    """Find potential PII leaks in logs."""
    leaks = []
    with open(log_file) as f:
        for line_num, line in enumerate(f, 1):
            for pattern in PII_PATTERNS:
                if re.search(pattern, line):
                    leaks.append(f"Line {line_num}: Potential PII found")
    return leaks
```

## Compliance Frameworks

### GDPR (EU)

- Requires "privacy by design"
- PII redaction helps demonstrate compliance
- Document your redaction approach

### HIPAA (Healthcare)

- PHI (Protected Health Information) must be secured
- Add healthcare-specific patterns:

```python
PHI_PATTERNS = [
    PIIPattern("mrn", r"MRN-\d{10}", "[MRN REDACTED]"),
    PIIPattern("npi", r"\d{10}", "[NPI REDACTED]"),
]
```

### PCI-DSS (Payments)

- Card numbers must never be logged
- obskit redacts by default
- Verify with compliance team

## Troubleshooting

### False Positives

If legitimate data is being redacted:

```python
# Add to allowlist
redactor = PIIRedactor(
    allowlist=["12345"],  # A product ID that looks like a number
)
```

### Missing Redactions

If PII is leaking through:

```python
# Add custom pattern
redactor = PIIRedactor(
    patterns=[
        PIIPattern("custom_id", r"YOUR-PATTERN", "[REDACTED]"),
    ],
)
```

### Performance

For high-throughput services:

```python
# Pre-compile patterns
redactor = PIIRedactor(precompile=True)

# Or sample redaction
if random.random() < 0.1:
    data = redact_pii(data)
```

## Next Steps

- **[Logging Guide](logging.md)** - Structured logging setup
- **[Tracing Guide](tracing.md)** - Secure distributed tracing
- **[Configuration](../config/index.md)** - Full configuration options

