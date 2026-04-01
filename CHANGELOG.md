# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0](https://github.com/talaatmagdyx/obskit/compare/v1.1.0...v2.0.0) (2026-04-01)


### ⚠ BREAKING CHANGES

* consolidate 16-package monorepo into single obskit package

### 🚀 Features

* release v3.0.0 — full mypy strict type coverage across all modules ([256ef42](https://github.com/talaatmagdyx/obskit/commit/256ef42507b969753bad0fa69658b2d27b3ed54d))
* release v3.1.0 — alerts builder, health router, CI hardening, full docs ([72b982c](https://github.com/talaatmagdyx/obskit/commit/72b982c4cdf615a67e648c88230349a89029e690))
* release v3.2.0 — 100% coverage, redaction module, multiprocess metrics, tracing fixes ([4e011df](https://github.com/talaatmagdyx/obskit/commit/4e011df231bc981ce696435efd89f2aff91cc073))
* **slo:** add with_slo_tracking decorators for sync/async SLO measurement v1.5.0 ([e860017](https://github.com/talaatmagdyx/obskit/commit/e8600173a7186c60a58e05213cb36a4a80d38fc4))
* **v1.4.0:** Add cardinality protection, sync circuit breaker, and enhanced queue tracking ([561cbc0](https://github.com/talaatmagdyx/obskit/commit/561cbc0dbe89a82fd99b3a0337b7d44f75fe638a))


### 🐛 Bug Fixes

* add noqa comment for CollectorRegistry import used in docstrings ([41db354](https://github.com/talaatmagdyx/obskit/commit/41db35473b5c97d046acbb511289f33c377541bf))
* apply 10 production-readiness bug fixes with full test coverage ([f09eaf5](https://github.com/talaatmagdyx/obskit/commit/f09eaf51f93e5a9069b42c19fa3606dbd074ce4e))
* **ci:** add obskit smoke tests and missing packages to CI matrix ([38e9480](https://github.com/talaatmagdyx/obskit/commit/38e9480901fc2d7032476f9eb25c35bac5dd7133))
* **ci:** add prometheus-client to integration test install step ([8330f7d](https://github.com/talaatmagdyx/obskit/commit/8330f7d08e52f7e265c5790452f3a9c61fef3af6))
* **ci:** fix all failing CI checks for v2.0.0 monorepo ([d2f1fd9](https://github.com/talaatmagdyx/obskit/commit/d2f1fd9cfc06302899b5f69612684ac9cd1e5873))
* **ci:** fix bandit format flag 'text' -&gt; 'txt' in security.yml ([a1a186c](https://github.com/talaatmagdyx/obskit/commit/a1a186c9a39d46dad9f17bfd89a1714d315817e2))
* **ci:** ignore unfixable pygments CVE-2026-4539 in pip-audit ([eb74be8](https://github.com/talaatmagdyx/obskit/commit/eb74be82cc250b2ebf514c5eb63b18dcb17c1181))
* **ci:** remove invalid pymdownx pin and fix docs build with auto_title ([c7d34dc](https://github.com/talaatmagdyx/obskit/commit/c7d34dc1a22f7084981027d5121b463ff1227bf6))
* **ci:** resolve ruff and mypy errors from bug-fix batch ([59f8659](https://github.com/talaatmagdyx/obskit/commit/59f865905ffa5c2c59f9f466c02d3b0dfa3b4d5e))
* code quality improvements ([8356ae9](https://github.com/talaatmagdyx/obskit/commit/8356ae90506afc59f45482c6254af5215a23dd5f))
* **deps:** add prometheus-client to dev extras and importlib mode to all packages ([a624b83](https://github.com/talaatmagdyx/obskit/commit/a624b835ecef86904a3d719edf6ae98c9cf0bac9))
* **docs:** pin pymdownx&lt;10.0.0 to fix mkdocs build crash ([f8e10f0](https://github.com/talaatmagdyx/obskit/commit/f8e10f0d6ba7d4a509db87935e21931a76b53a94))
* **lint:** replace (str, Enum) with StrEnum to fix UP042 ruff errors ([0ab9be8](https://github.com/talaatmagdyx/obskit/commit/0ab9be8b190b928ced27345ded12c624c8fc8aa7))
* **mypy:** suppress psycopg2 untyped-call via override instead of type: ignore ([cc6470a](https://github.com/talaatmagdyx/obskit/commit/cc6470a422ce3a4c41fb6e2a2540372f73dc8a5b))
* post-release CI, static analysis, deps and test fixes ([1c5578b](https://github.com/talaatmagdyx/obskit/commit/1c5578b425a390dc5e0e5acdafb7d64c6895bc87))
* **prod:** apply 8 production-readiness hardening fixes ([4c821e1](https://github.com/talaatmagdyx/obskit/commit/4c821e10b9f0700a836f37a6ecaf5c8662439da2))
* remove stale integration tests and restore psycopg2 type ignore ([d846442](https://github.com/talaatmagdyx/obskit/commit/d846442f6715b282ce874068d6e92d67a52b0788))
* remove unused local variables ([b2df28c](https://github.com/talaatmagdyx/obskit/commit/b2df28cd5de9978be505f7e768f83a5bc374a04a))
* remove unused TYPE_CHECKING import and fix django version check ([7d72164](https://github.com/talaatmagdyx/obskit/commit/7d72164dcaef74d9b49e740a0ecb6f38e4849bd1))
* resolve additional CodeQL alerts ([3710b0e](https://github.com/talaatmagdyx/obskit/commit/3710b0eee884dcc32b08ab01c4bff411cf7aa2af))
* resolve additional CodeQL alerts ([30f1d43](https://github.com/talaatmagdyx/obskit/commit/30f1d438b3cc832e67875d1ea8493c3d8584f2c1))
* resolve all CI failures — ruff, mypy, coverage, uv deprecation ([bb1042b](https://github.com/talaatmagdyx/obskit/commit/bb1042bbbac13f510b3aae8a0ae89fda78a410dd))
* resolve CI issues and add security policy ([5d35f85](https://github.com/talaatmagdyx/obskit/commit/5d35f85ca015b7e05af7c49a545ff1983aa80df0))
* resolve CodeQL alerts for unused imports, variables, and type issues ([ec43f17](https://github.com/talaatmagdyx/obskit/commit/ec43f17f362b03d6e4b3eb52e2a979f507284016))
* resolve CodeQL alerts for wrong arguments and loop variables ([fb95942](https://github.com/talaatmagdyx/obskit/commit/fb959421e4c9125e76eb85baeac9ebff03eedcf5))
* resolve CodeQL security alerts ([f6590be](https://github.com/talaatmagdyx/obskit/commit/f6590be7ea648474d5365de035c36678b8eeb024))
* resolve critical circular import bug in obskit.resilience (v1.3.3) ([b25dca8](https://github.com/talaatmagdyx/obskit/commit/b25dca8e50f2c233c031a99a7cf741baf3a04d61))
* resolve import conflicts and unused imports ([750f64c](https://github.com/talaatmagdyx/obskit/commit/750f64cbf69d585c572f2edafceb98700a4913b4))
* resolve more CodeQL alerts ([919f3c9](https://github.com/talaatmagdyx/obskit/commit/919f3c9406b1fcf924d24b42d9515f2ead6f89f5))
* resolve remaining CodeQL alerts ([f34231d](https://github.com/talaatmagdyx/obskit/commit/f34231d200c81cfa1194a8e1d34540375ebea79a))
* resolve ruff format and mypy strict errors ([933c313](https://github.com/talaatmagdyx/obskit/commit/933c3131deb9a5a46338ce798f265490fe522eea))
* restore 100% coverage after _error_details extraction ([1c9dff6](https://github.com/talaatmagdyx/obskit/commit/1c9dff60d5a40a7f7ef73ea7cd1c5ebdb299e660))
* restore loggers as _logger (private convention) ([47fec47](https://github.com/talaatmagdyx/obskit/commit/47fec4710f1f369a8a82abb49b070979b8999288))
* simplify Read the Docs configuration ([9fb5d49](https://github.com/talaatmagdyx/obskit/commit/9fb5d493fb623491abe7056ebe67dcb9c85fc881))
* **test:** patch redis.asyncio.Redis directly instead of sys.modules ([e6f7125](https://github.com/talaatmagdyx/obskit/commit/e6f712516d4fd718e3490bac9ec660e5c5a52947))
* **tests:** restore sys.modules properly in TestTenantGaps to prevent test pollution ([0d4e08c](https://github.com/talaatmagdyx/obskit/commit/0d4e08c4eb98628d86912f85facbb2a5a200e22e))
* **typecheck:** fix all mypy errors in CI type-check step ([7f136cb](https://github.com/talaatmagdyx/obskit/commit/7f136cbe974541a602c8ffc943c7fd685e4bfc7f))
* use local variables instead of discarding with underscore prefix ([2e6f116](https://github.com/talaatmagdyx/obskit/commit/2e6f116fc3879664ddb98ba0023f0e7592928aa1))
* use patch.dict(sys.modules, {...}) which auto-restores originals on exit. ([0d4e08c](https://github.com/talaatmagdyx/obskit/commit/0d4e08c4eb98628d86912f85facbb2a5a200e22e))


### 📚 Documentation

* add comprehensive CLAUDE.md and improve .gitignore ([d02415f](https://github.com/talaatmagdyx/obskit/commit/d02415f7ce3e30bbe67357a49ffb8d8db6423b64))
* add comprehensive feature reference documentation ([912a993](https://github.com/talaatmagdyx/obskit/commit/912a99388823d156bc01f57d1e82a67ffc5258cd))
* add Read the Docs configuration ([94988c2](https://github.com/talaatmagdyx/obskit/commit/94988c289226b15bf6d0d97655a05cf88c921f81))
* comprehensive Sphinx documentation with tech_docs ([a709bfb](https://github.com/talaatmagdyx/obskit/commit/a709bfb8d40776601337d3c7d2c63f803d460413))
* fix all remaining outdated 16-package references throughout documentation ([1ba2c99](https://github.com/talaatmagdyx/obskit/commit/1ba2c995177f885d804239fdf58ccae145b95f44))
* fix pip install commands for consolidated single-package ([14098a8](https://github.com/talaatmagdyx/obskit/commit/14098a8c8111e7ee6552c94e89bf23690b1f12bf))
* improve documentation and prepare for PyPI publishing ([fdb54db](https://github.com/talaatmagdyx/obskit/commit/fdb54db54bebde161ed408af5efe3421e895d094))
* include essential documentation inline in README for PyPI ([ecd4abe](https://github.com/talaatmagdyx/obskit/commit/ecd4abe6b2a45476f3f673b307fbeee793951200))
* remove staff engineer review documents ([4e05175](https://github.com/talaatmagdyx/obskit/commit/4e05175f1065a2429c51cfbe8b6a827e4342c57b))
* rewrite all 16 package READMEs with creative layout, real API examples and full feature coverage ([77a05d9](https://github.com/talaatmagdyx/obskit/commit/77a05d9acafe2701a59b90457b5537635bc4d5d5))
* rewrite README with creative layout, full package ecosystem and updated dev commands ([2c598f3](https://github.com/talaatmagdyx/obskit/commit/2c598f3f554dfe1b675ee8cee456c4486b3a073f))
* update all 2.2.0 version references to 3.0.0 ([e285bf9](https://github.com/talaatmagdyx/obskit/commit/e285bf90b5662ed5ea2e22c7822d8050fec83019))
* update all documentation for PyPI compatibility (v1.3.0) ([e7a2743](https://github.com/talaatmagdyx/obskit/commit/e7a2743655854d6489e7c8e1ba35b1dcf5a71cd0))
* update documentation for v3.2.0 ([9258e97](https://github.com/talaatmagdyx/obskit/commit/9258e97af3127e0b064f308b5ce8d6a23e17210f))
* update install commands for consolidated package ([9392ccb](https://github.com/talaatmagdyx/obskit/commit/9392ccbe8735bc66b8be7e43ea04ef2862fe6d4e))
* update README to reflect single-package-with-extras model ([93ff0c0](https://github.com/talaatmagdyx/obskit/commit/93ff0c06f2427fe9cfd0a89996839c1ffc4a3043))


### ♻️ Refactoring

* consolidate 16-package monorepo into single obskit package ([c908bd2](https://github.com/talaatmagdyx/obskit/commit/c908bd26fda9bfe65c694be12d582d889cf6aaf2))
* fix lint warnings and reduce cognitive complexity ([a6d9501](https://github.com/talaatmagdyx/obskit/commit/a6d95018517c3c4ad684f0fffb37bdd143165231))
* remove packages/ monorepo directories from git tracking ([8765e37](https://github.com/talaatmagdyx/obskit/commit/8765e374cbf9ddd47f3d9df4d07d5342f293af2b))


### 🔧 CI/CD

* add workflow_dispatch trigger to release workflow for manual PyPI publishes ([2c7c7ef](https://github.com/talaatmagdyx/obskit/commit/2c7c7efda4c2289e83afd876b37f78dab7006089))
* bump actions/checkout from 4 to 6 ([8c0b45f](https://github.com/talaatmagdyx/obskit/commit/8c0b45fbf29f80c57b31d5d3c681bb2d368d7786))
* bump actions/checkout from 4 to 6 ([b3f9d1b](https://github.com/talaatmagdyx/obskit/commit/b3f9d1b37d6335522f96542a47f9b0d44d9b8c64))
* bump actions/download-artifact from 4 to 7 ([85acbc2](https://github.com/talaatmagdyx/obskit/commit/85acbc2690ebd8e6412a4b5dfb5b4e416a8ad8f4))
* bump actions/download-artifact from 4 to 7 ([ad3476e](https://github.com/talaatmagdyx/obskit/commit/ad3476e80ea974d1c740a53935c460482a0612ca))
* bump actions/setup-python from 5 to 6 ([1310a30](https://github.com/talaatmagdyx/obskit/commit/1310a302dd0dfa89955f3c245d60ec115f4c0781))
* bump actions/setup-python from 5 to 6 ([86e12ac](https://github.com/talaatmagdyx/obskit/commit/86e12ace09e25f353f6fc6e0a6e964cd0c3f3310))
* bump actions/upload-artifact from 4 to 6 ([4fb0390](https://github.com/talaatmagdyx/obskit/commit/4fb0390f81403ab8657200a2772360f2b779630a))
* bump actions/upload-artifact from 4 to 6 ([f382687](https://github.com/talaatmagdyx/obskit/commit/f382687a3f39db690f78557d230e6e49a2bd2d6b))
* bump actions/upload-pages-artifact from 3 to 4 ([d3fc2a1](https://github.com/talaatmagdyx/obskit/commit/d3fc2a1d5082b3a08f1828ab8d4615cc0bc9d255))
* bump actions/upload-pages-artifact from 3 to 4 ([425031a](https://github.com/talaatmagdyx/obskit/commit/425031ae26bc4d63ae2f35e8f44891cdeab93a3f))
* fix cyclonedx-py v7 flags — --of JSON -o instead of --output-format/--outfile ([e624f94](https://github.com/talaatmagdyx/obskit/commit/e624f947307e672e46e8c3621c8c77124370552f))
* fix release-please version bumping for all 16 packages and cyclonedx-py SBOM command ([088d570](https://github.com/talaatmagdyx/obskit/commit/088d570b86246b65a8fbcc7adc59f230c401e314))
* migrate release-please to googleapis/release-please-action@v4 ([6fa7b4c](https://github.com/talaatmagdyx/obskit/commit/6fa7b4c97e02bb12753658a0a87be8db8f2351a8))
* pin sigstore action to v3.2.0 (v3 tag does not exist) ([1035379](https://github.com/talaatmagdyx/obskit/commit/1035379b46d53347859144b67385c0a7ea13e48f))
* simplify workflows for single-package build and publish ([6f7f745](https://github.com/talaatmagdyx/obskit/commit/6f7f745cc3b3cef5b220d52a85867189246d3020))


### 🔒 Security

* add nosec annotations for CodeQL/bandit alerts ([b826197](https://github.com/talaatmagdyx/obskit/commit/b82619717f5c50bbe9b73968f7104b04a7a402fd))

## [Unreleased]

## [1.1.0](https://github.com/talaatmagdyx/obskit/releases/tag/v1.1.0) (2026-04-01)

### Fixed

* **Critical: PII leakage** — `make_redaction_processor` was not wired into the default structlog processor chain; passwords, tokens, and secrets were logged in plaintext. Redaction now runs before sampling on every log record.
* **Critical: SQLAlchemy global instrumentation** — `instrument_sqlalchemy()` registered event listeners on the `Engine` class (process-global) instead of the engine instance, hijacking all SQLAlchemy engines created by third-party libraries. Listeners now attach to the passed instance only.
* **`OTLPLogHandler` silent log loss** — `_export_batch()` was a placeholder that silently discarded all log records. The handler now sets up a real `LoggerProvider` + `BatchLogRecordProcessor` + `OTLPLogExporter` pipeline in `__init__`, and `emit()` delegates to it for actual OTLP export.
* **Singleton return-inside-lock** — `get_observability()` and `get_settings()` returned inside the `with _lock:` block (double-checked locking anti-pattern). Moved `return` outside the lock.
* **async_ring emit errors silently swallowed** — exceptions in the background flush thread's emit function were caught and discarded. Now printed to `stderr` so operators can detect dropped records.
* **Sampling TOCTOU race** — `SmartSampler.should_log()` acquired `_dedup_lock` twice with a window between (check then update). Merged into a single atomic block.
* **Correlation ID regex over-permissive** — `_CORRELATION_ID_RE` allowed dots and up to 128 characters. Tightened to alphanumeric + hyphen + underscore, max 64 characters, to prevent header injection abuse.
* **SLO measurement buffer silent overflow** — `SLOTracker` silently dropped measurements when the deque reached capacity with no operator warning. Now emits a structured warning at 80% capacity (sampled every 10 000 measurements).
* **`_dropped` counter race in AsyncLogRing** — concurrent `enqueue()` callers could race on the read-modify-write of `_dropped`, producing duplicate 1000-drop warnings. Protected by a dedicated `threading.Lock`.
* **`CardinalityProtector.protect` double-lock** — two separate lock acquisitions (check, then add) created a TOCTOU window where the same new label value could be admitted twice under concurrent load. Replaced with a single `check_and_add()` atomic operation on `LRUCache`.
* **`SLOTracker.get_all_status` dict size change** — iterating `_targets` without snapshotting keys raised `RuntimeError` if `register_slo()` was called concurrently. Keys are now snapshot under the lock before iteration.

### Performance

* **`SLOTracker.get_status` O(n) → O(1)** — AVAILABILITY and ERROR_RATE status reads previously iterated all N measurements via `sum(1 for m in buf if m.success)`. Now maintained via incremental `_success_counts`/`_total_counts` dicts updated on every `record_measurement` append and window-eviction. Measured improvement: ~1000× at 100 k measurements.
* **Redaction processor `any()` → pre-compiled regex** — `_redact_value` called `any(s in key.lower() for s in _fields)` (11 Python generator steps per log field per event). Now uses a single `re.compile(pattern, IGNORECASE)` at processor-creation time; one C-level `re.search()` per field.
* **`MiddlewareCore.should_exclude` rstrip pre-computed** — `excluded.rstrip("/") + "/"` was recomputed on every request × every excluded path. Normalized prefixes are now pre-built in `__init__`, eliminating 400 k string allocations per 100 k requests.
* **`extract_correlation_id` miss: `uuid4` → `secrets.token_hex`** — `str(uuid.uuid4())` cost ~1.65 µs (UUID object construction + `os.urandom` + `__str__`). Replaced with `secrets.token_hex(16)` (~300 ns); 32-char hex string passes `_CORRELATION_ID_RE`.
* **`_HTPipeline.record()` metrics recorded synchronously** — RED metrics were silently dropped when the high-throughput pipeline was active because `observe_request()` was never called. Metrics are now recorded inline before enqueueing the log record.
* **`decorators/combined.py` `get_red_metrics()` cached at decoration time** — the hot `wrapper()` path called `get_red_metrics()` (a dict lookup + lock) on every request. The `REDMetrics` handle is now resolved once when the decorator is applied.

### Changed

* `integrations/` package — gRPC middleware, DB (SQLAlchemy/psycopg2/psycopg3), and queue (Kafka/RabbitMQ) integrations moved to `obskit.integrations` with per-extra import guards. Install via `obskit[grpc]`, `obskit[sqlalchemy]`, `obskit[psycopg2]`, `obskit[psycopg3]`, `obskit[kafka]`, `obskit[rabbitmq]`, or the bundle `obskit[integrations]`.
* Removed deprecated modules: `obskit.alerts`, `obskit.audit`, `obskit.batch`, `obskit.breakdown`, `obskit.budgets`, `obskit.annotations`, `obskit.alert_dedup`. These were experimental and never part of the stable API.

## [1.0.0](https://github.com/talaatmagdyx/obskit/releases/tag/v1.0.0) (2026-03-30)

Initial production release of obskit — a focused, single-wheel observability toolkit for Python
microservices. Install only what you need via pip extras.

### Features

* **Unified setup**: `configure_observability()` sets up tracing, metrics, and logging in one call,
  returning an `Observability` facade with `.tracer`, `.metrics`, `.logger`, `.config`, and `.shutdown()`
* **Framework instrumentation**: `instrument_fastapi(app)`, `instrument_flask(app)`, `instrument_django()` —
  one-line middleware setup with automatic metrics, traces, correlation IDs, and access logs
* **Structured config**: `ObservabilityConfig` frozen dataclasses grouping settings into `ServiceConfig`,
  `TracingConfig`, `MetricsConfig`, `LoggingConfig`, and `HealthConfig`
* **Structured logging**: JSON-first logging via structlog with automatic trace-log correlation,
  PII redaction (`make_redaction_processor`), and adaptive log sampling
* **RED metrics**: Prometheus-based Rate · Errors · Duration metrics with exemplar support,
  cardinality protection (label truncation + `"invalid_operation"` normalisation),
  multiprocess (Gunicorn) support, and OpenMetrics `/metrics` exposition
* **Distributed tracing**: OpenTelemetry SDK with W3C `traceparent` + `baggage` propagation,
  adaptive head-based sampling, and OTLP export
* **Health checks**: Kubernetes-style liveness/readiness probes with `HealthCheck`, `HealthChecker`,
  `build_health_router`, dependency aggregation, and optional SLO-based health (`obskit[health]`)
* **SLO tracking**: Error budget calculation and burn-rate status via `SLOTracker` (`obskit[slo]`);
  optional Prometheus metrics export (`obskit[slo-prometheus]`)
* **Shared middleware core**: `MiddlewareCore` — protocol-agnostic request instrumentation
  (path exclusion, correlation IDs, metrics recording, response headers)
* **Optional extras — granular installs**:
  - `obskit[prometheus]` — Prometheus client + `/metrics` HTTP server
  - `obskit[otlp]` — OpenTelemetry OTLP exporter
  - `obskit[fastapi]`, `obskit[flask]`, `obskit[django]` — framework middleware
  - `obskit[slo]`, `obskit[slo-prometheus]`, `obskit[slo-all]` — SLO tracking tiers
  - `obskit[health]`, `obskit[health-http]`, `obskit[health-all]` — health check tiers
  - `obskit[sqlalchemy]` — SQLAlchemy OTel auto-instrumentation
  - `obskit[psycopg2]` — psycopg2 OTel auto-instrumentation (sync)
  - `obskit[psycopg3]` — psycopg3 OTel auto-instrumentation (sync + async)
  - `obskit[db]` — all three DB drivers
  - `obskit[kafka]` — Kafka consumer tracing
  - `obskit[rabbitmq]` — RabbitMQ consumer tracing
  - `obskit[grpc]` — gRPC server/client interceptors
  - `obskit[integrations]` — db + kafka + rabbitmq + grpc bundle
  - `obskit[all]` — everything
* **`integrations/` namespace**: DB (`sqlalchemy`, `psycopg2`, `psycopg3`), queue (`kafka`, `rabbitmq`),
  and gRPC middleware live under `obskit.integrations.*` — each with import guards that name the
  exact extra required
* **Lazy top-level imports**: `HealthCheck`, `HealthChecker`, `build_health_router`,
  `instrument_fastapi/flask/django`, and multiprocess helpers are lazy-loaded in `__init__.py`
  via `__getattr__` to avoid `ImportError` when optional extras are not installed
* **Diagnostics**: `python -m obskit.core.diagnose` CLI for environment health checks
* **100% test coverage**: branch coverage enforced in CI (`--cov-fail-under=100`)
* **PEP 561 typed**: full mypy strict mode support

### Package structure

```
obskit/
  core/          context, config, observability, diagnostics
  logging/       structlog-based logger, redaction, sampling, trace correlation
  metrics/       RED metrics, exemplars, cardinality, OpenMetrics, multiprocess
  tracing/       OTel tracer, setup, auto-instrumentation helpers
  middleware/    fastapi, flask, django, core (MiddlewareCore), instrument
  health/        checker, checks, router, aggregator, slo_check
  slo/           tracker, types, prometheus export
  integrations/  grpc, db/(sqlalchemy, psycopg2, psycopg3), queue/(kafka, rabbitmq)
  decorators/    combined, context_managers
```
