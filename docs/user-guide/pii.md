# PII Redaction

Personal Identifiable Information (PII) must never appear in logs, metric labels, or trace attributes. obskit provides automatic PII detection and redaction in its logging pipeline so compliance is the default, not an afterthought.

---

## Why PII Matters

### Regulatory requirements

| Regulation | Scope | Requirement |
|---|---|---|
| **GDPR** | EU residents | Data minimisation, purpose limitation, right to erasure |
| **CCPA** | California residents | Right to know, right to delete, right to opt-out |
| **PCI-DSS** | Payment card data | Card numbers must never appear in logs |
| **HIPAA** | US health data | PHI requires strict access controls and audit trails |

### Practical risks

- **Data breaches**: Log files are frequently less protected than databases. A leaked log archive can expose millions of users' PII.
- **Compliance fines**: GDPR fines can reach 4% of global annual turnover or €20M (whichever is higher).
- **Audit failures**: Logs containing PII make it impossible to grant compliant data access to third parties (e.g., security vendors).

!!! danger "The most common mistake"
    Logging exception messages verbatim. Exception messages routinely include user input — and user input routinely contains PII. Always log structured fields, never raw exception messages that may echo back user data.

---

## Configuring PII Redaction

### Using `obskit.logging.redaction` (recommended)

The `redaction` module provides a structlog processor with zero configuration required:

```python
import structlog
from obskit.logging.redaction import redact_sensitive_fields

structlog.configure(
    processors=[
        redact_sensitive_fields,    # default 11-field set, case-insensitive substring match
        structlog.processors.JSONRenderer(),
    ]
)
```

For custom fields:

```python
from obskit.logging.redaction import make_redaction_processor, DEFAULT_SENSITIVE_FIELDS

processor = make_redaction_processor(
    fields=DEFAULT_SENSITIVE_FIELDS | {"ssn", "credit_card", "dob"},
    placeholder="[REDACTED]",
)
```

The processor recurses into nested dicts (10 levels deep), detects circular references, and never mutates the original event dict.

### Using `configure_logging` (high-level API)

```python
from obskit.logging import configure_logging

configure_logging(
    pii_fields=["email", "password", "phone", "credit_card", "ssn", "token", "api_key"],
    pii_replacement="[REDACTED]",
)
```

Any log field whose **key** matches a name in `pii_fields` is replaced with `[REDACTED]` before the log line is written.

```python
from obskit.logging import get_logger

log = get_logger(__name__)

# Field "email" is in pii_fields → redacted automatically
log.info("user.registered", email="alice@example.com", plan="pro")
```

Output:
```json
{"event": "user.registered", "email": "[REDACTED]", "plan": "pro", ...}
```

### Pattern-based redaction

For PII that may appear in field values of any name (e.g., inside a `message` field or an exception string), use regex patterns:

```python
configure_logging(
    pii_patterns=[
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",   # Email addresses
        r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",                 # Credit card numbers
        r"\b\d{3}-\d{2}-\d{4}\b",                                     # US SSN
        r"\b(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b",  # Phone numbers
        r"\bsk_live_[A-Za-z0-9]{24,}\b",                              # Stripe live keys
        r"\bghp_[A-Za-z0-9]{36}\b",                                   # GitHub tokens
    ],
    pii_replacement="[REDACTED]",
)
```

Patterns are applied to **all string values** in the log record, including nested fields.

---

## Field-Level Redaction

### Named field list (exact match)

```python
configure_logging(
    pii_fields=[
        # Identity
        "email", "username", "full_name", "first_name", "last_name",
        # Contact
        "phone", "mobile", "phone_number", "address", "postcode", "zip_code",
        # Financial
        "credit_card", "card_number", "cvv", "expiry", "bank_account", "iban",
        # Authentication
        "password", "password_hash", "token", "api_key", "secret", "private_key",
        # Government IDs
        "ssn", "national_id", "passport_number", "driving_licence",
        # Health
        "dob", "date_of_birth", "diagnosis", "medical_record",
    ],
)
```

### Prefix-based field matching

Fields whose names start with a prefix:

```python
configure_logging(
    pii_field_prefixes=["pii_", "sensitive_", "private_"],
)
```

Any field named `pii_email`, `sensitive_phone`, or `private_ssn` is automatically redacted.

---

## Common PII Regex Patterns

```python
PII_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "credit_card_visa_mc": r"\b4[0-9]{12}(?:[0-9]{3})?\b|\b5[1-5][0-9]{14}\b",
    "credit_card_generic": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    "us_ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "us_phone": r"\b(\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "uk_phone": r"\b(?:0|\+44)[0-9]{9,10}\b",
    "ipv4": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "stripe_key": r"\bsk_(?:live|test)_[A-Za-z0-9]{24,}\b",
    "github_token": r"\bghp_[A-Za-z0-9]{36}\b",
    "aws_key": r"\bAKIA[0-9A-Z]{16}\b",
    "jwt": r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b",
}
```

---

## Testing PII Redaction

Always write tests to verify that PII redaction works as configured:

```python
import pytest
from obskit.testing import ObskitTestCase
from obskit.logging import configure_logging, get_logger


class TestPIIRedaction(ObskitTestCase):
    def setup_method(self):
        configure_logging(
            pii_fields=["email", "password"],
            pii_patterns=[r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"],
        )
        self.log = get_logger("test")

    def test_email_field_is_redacted(self, caplog):
        self.log.info("test.event", email="alice@example.com", user_id="u_123")
        record = self.get_last_log_record()
        assert record["email"] == "[REDACTED]"
        assert record["user_id"] == "u_123"   # Non-PII field preserved

    def test_password_field_is_redacted(self, caplog):
        self.log.info("test.event", password="hunter2")
        record = self.get_last_log_record()
        assert record["password"] == "[REDACTED]"

    def test_credit_card_pattern_in_message(self, caplog):
        self.log.warning("payment.debug", message="Card 4111 1111 1111 1111 declined")
        record = self.get_last_log_record()
        assert "4111 1111 1111 1111" not in record["message"]
        assert "[REDACTED]" in record["message"]

    def test_non_pii_field_is_preserved(self, caplog):
        self.log.info("test.event", amount=9900, currency="USD")
        record = self.get_last_log_record()
        assert record["amount"] == 9900
        assert record["currency"] == "USD"
```

---

## Audit Logging for Compliance

Separate from application logging, obskit provides an **audit log** sink for compliance-relevant events (data access, authentication, configuration changes):

```python
from obskit.audit import AuditLogger

audit = AuditLogger(
    service="payment-service",
    sink="loki",                      # "loki" | "file" | "stdout"
    sink_config={"endpoint": "http://loki:3100"},
    immutable=True,                   # Disable dynamic log level changes for audit logs
)

# Record a data access event
audit.record(
    action="user.data_exported",
    actor_id="admin_user_xyz",        # Who performed the action
    subject_id="u_abc123",            # Whose data was accessed
    resource="user_profile",
    outcome="success",
    ip_address="10.0.1.45",
    reason="gdpr_data_request",       # Why the action was performed
)
```

Audit log output:
```json
{
  "timestamp": "2026-02-28T14:32:07.841Z",
  "type": "audit",
  "action": "user.data_exported",
  "actor_id": "admin_user_xyz",
  "subject_id": "u_abc123",
  "resource": "user_profile",
  "outcome": "success",
  "ip_address": "10.0.1.45",
  "reason": "gdpr_data_request",
  "service": "payment-service"
}
```

!!! tip "Audit logs must be immutable"
    Audit logs should be append-only and stored in a system that prevents modification or deletion (e.g., Loki with object storage backend, AWS CloudTrail, or a write-once S3 bucket). Compliance frameworks require that audit trails cannot be tampered with.

---

## PII in Traces and Metrics

PII in logs is the most common problem, but traces and metrics also need attention.

### Traces

Never put PII in span attributes or span names:

```python
# BAD
with trace_span("lookup_user", attributes={"email": user_email}):
    ...

# GOOD
with trace_span("lookup_user", attributes={"user_id": user_id}):
    ...
```

Configure OTel's span processor to scrub PII if needed:

```python
from obskit.tracing import setup_tracing

setup_tracing(
    exporter_endpoint="http://tempo:4317",
    scrub_span_attributes=["email", "password", "phone"],  # obskit extension
)
```

### Metrics

PII in metric labels causes cardinality explosion *and* compliance violations. Never use email, username, or any PII as a label value:

```python
# BAD — PII in label + cardinality explosion
counter.labels(user_email="alice@example.com").inc()

# GOOD — use internal ID if you need per-user tracking (rare)
counter.labels(user_id="u_abc123").inc()

# BEST — aggregate metrics, no user-level labels
counter.inc()  # track count globally
```
