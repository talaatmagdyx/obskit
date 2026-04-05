# HTTP Client Instrumentation

Prometheus metrics and OTel trace spans for outbound `httpx.AsyncClient` calls.  Every external API call made by the service becomes visible in Prometheus and in the distributed trace.

## Installation

```bash
pip install obskit httpx
```

## Quick Start

```python
import httpx
from obskit.integrations.http import instrument_httpx

# Wrap at construction time
client = instrument_httpx(httpx.AsyncClient(), name="twitter")

# All async methods are automatically instrumented
response = await client.get("https://api.twitter.com/endpoint")
```

## Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `http_client_requests_total` | Counter | `name`, `method`, `status_code` | Total outbound requests. `status_code` is the HTTP response code (`"200"`, `"404"`, …) or `"error"` for network exceptions. |
| `http_client_duration_seconds` | Histogram | `name`, `method` | End-to-end request latency. |

## Trace Spans

Each HTTP call creates an OTel span named `"HTTP <METHOD>"` with:

- `http.method` — e.g. `GET`, `POST`
- `http.client.name` — the `name` you passed to `instrument_httpx`

The W3C `traceparent` header is injected into every outgoing request so the upstream service can join the trace.

## Context Manager

```python
async with instrument_httpx(httpx.AsyncClient(), name="facebook") as client:
    response = await client.post(url, json=payload)
```

## Multiple Clients

```python
twitter_client  = instrument_httpx(httpx.AsyncClient(base_url="https://api.twitter.com"),  name="twitter")
facebook_client = instrument_httpx(httpx.AsyncClient(base_url="https://graph.facebook.com"), name="facebook")
whatsapp_client = instrument_httpx(httpx.AsyncClient(base_url="https://api.whatsapp.com"),  name="whatsapp")
```

Each `name` value appears as a distinct `name` label in Prometheus, keeping metrics for different platform adapters separate.

## API Reference

::: obskit.integrations.http.instrument_httpx

::: obskit.integrations.http.InstrumentedHttpxClient
