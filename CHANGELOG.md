# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0](https://github.com/talaatmagdyx/obskit/compare/v1.1.0...v2.0.0) (2026-04-06)


### ⚠ BREAKING CHANGES

* consolidate 16-package monorepo into single obskit package

### 🚀 Features

* release v2.0.0 — trace sampling, WorkerHealthServer, integrations expansion ([8d3b12f](https://github.com/talaatmagdyx/obskit/commit/8d3b12f02a7f3f1edcb48b560cde2a087276da86))
* release v3.0.0 — full mypy strict type coverage across all modules ([256ef42](https://github.com/talaatmagdyx/obskit/commit/256ef42507b969753bad0fa69658b2d27b3ed54d))
* release v3.1.0 — alerts builder, health router, CI hardening, full docs ([72b982c](https://github.com/talaatmagdyx/obskit/commit/72b982c4cdf615a67e648c88230349a89029e690))
* release v3.2.0 — 100% coverage, redaction module, multiprocess metrics, tracing fixes ([4e011df](https://github.com/talaatmagdyx/obskit/commit/4e011df231bc981ce696435efd89f2aff91cc073))
* **slo:** add with_slo_tracking decorators for sync/async SLO measurement v1.5.0 ([e860017](https://github.com/talaatmagdyx/obskit/commit/e8600173a7186c60a58e05213cb36a4a80d38fc4))
* **v1.4.0:** Add cardinality protection, sync circuit breaker, and enhanced queue tracking ([561cbc0](https://github.com/talaatmagdyx/obskit/commit/561cbc0dbe89a82fd99b3a0337b7d44f75fe638a))


### 🐛 Bug Fixes

* add noqa comment for CollectorRegistry import used in docstrings ([41db354](https://github.com/talaatmagdyx/obskit/commit/41db35473b5c97d046acbb511289f33c377541bf))
* apply 10 production-readiness bug fixes with full test coverage ([f09eaf5](https://github.com/talaatmagdyx/obskit/commit/f09eaf51f93e5a9069b42c19fa3606dbd074ce4e))
* break cyclic import between health/__init__ and health/slo_check ([c94ea0c](https://github.com/talaatmagdyx/obskit/commit/c94ea0c8dbb9158b57b2224fe9755f61c1e13c01))
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
* **sonar:** replace asyncio.wait_for timeout param with asyncio.timeout() ctx manager and fix async stubs in tests ([8eeb814](https://github.com/talaatmagdyx/obskit/commit/8eeb814024bf7135de7923692d0f901987688cce))
* **sonar:** resolve 17 security hotspots and reliability C rating ([ee69b4c](https://github.com/talaatmagdyx/obskit/commit/ee69b4ccd65c43f23884e41f61c76f10c6063dac))
* **sonar:** resolve 40+ code smell issues across source and test files ([a02a480](https://github.com/talaatmagdyx/obskit/commit/a02a480677d4812685d6eeceac53bb433e0bd722))
* **test:** patch redis.asyncio.Redis directly instead of sys.modules ([e6f7125](https://github.com/talaatmagdyx/obskit/commit/e6f712516d4fd718e3490bac9ec660e5c5a52947))
* **tests:** replace asyncio.get_event_loop() with asyncio.run() for Python 3.12 and cover tracer.py sampling_cfg branch ([07e3f8d](https://github.com/talaatmagdyx/obskit/commit/07e3f8d0c2cab6f6a45e249732b275ccefc0a3c7))
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

## [2.0.0] (2026-04-04)

### Added

* **`configure_trace_sampling(head_rate, *, always_sample_errors=True)` — production trace volume control**
  (`obskit.tracing.sampling`) — configures head-based sampling on the active (or future)
  ``TracerProvider``.  Accepts either a ``Retrying``/``AsyncRetrying`` instance or the
  ``tenacity.retry(...)`` factory shorthand (tenacity 9.x) — both paths are handled.

  * ``head_rate`` controls what fraction of traces is exported (e.g. ``0.1`` → 10 %).
    Uses ``ParentBased(TraceIdRatioBased)`` so the decision propagates across services.
  * ``always_sample_errors=True`` (default) uses ``RECORD_ONLY`` instead of ``DROP`` for
    non-sampled spans and exports them via :class:`ErrorPromotionSpanProcessor` when their
    status is ``StatusCode.ERROR``.  Only the error span is force-exported; parent spans
    that were already discarded are not recovered (use the OTel Collector for full
    tail-based sampling).

  Can be called **before** or **after** ``configure_observability()``.

  ```python
  from obskit import configure_trace_sampling

  configure_trace_sampling(head_rate=0.1, always_sample_errors=True)
  configure_observability(service_name="worker", otlp_endpoint="http://tempo:4317")
  ```

* **`WorkerHealthServer(port, checks, *, max_silence_seconds=None)` — Kubernetes liveness probe for worker processes**
  (`obskit.health.server`) — runs a minimal HTTP server in a daemon thread so that
  Kubernetes liveness probes can reach non-HTTP services (RabbitMQ consumers, cron workers,
  async pipeline workers) without requiring FastAPI or Flask.

  * ``GET /health``, ``GET /live``, ``GET /ready`` — returns ``200 OK`` when all checks pass,
    ``503 Service Unavailable`` when any check fails or silence exceeds ``max_silence_seconds``.
  * ``record_activity()`` — resets the silence timer; call after every message processed.

  ```python
  from obskit.health import WorkerHealthServer

  health = WorkerHealthServer(
      port=8002,
      checks={
          "consumer": lambda: consumer.is_alive(),
          "retry_worker": lambda: retry_worker.is_running,
      },
      max_silence_seconds=120,
  )
  await health.start()

  # In the message loop:
  health.record_activity()
  ```

### Changed

* **`instrument_tenacity`** now handles both ``tenacity.Retrying``/``AsyncRetrying`` instances
  (instance path) and the decorator factory returned by ``tenacity.retry(...)`` in tenacity 9.x
  (factory path).  Both are detected automatically via ``hasattr(retry_obj, "stop")``.

## [1.9.0] (2026-04-04)

### Added

* **`instrument_tenacity(retry_obj, name)` — tenacity retry Prometheus metrics**
  (`obskit.integrations.resilience.tenacity`) — patches a tenacity ``Retrying``
  or ``AsyncRetrying`` decorator in-place to emit:

  * ``retry_attempts_total{name, attempt_number}`` — incremented via the
    ``before_sleep`` hook on every failed attempt that schedules a retry.
    The ``attempt_number`` label identifies which attempt failed.
  * ``retry_exhausted_total{name}`` — incremented via the ``after`` hook when
    the stop condition is reached on a failed attempt (all retries spent).

  Pre-existing ``before_sleep`` and ``after`` hooks are preserved.
  Also exported as ``obskit.instrument_tenacity``.

  ```python
  from obskit import instrument_tenacity
  import tenacity

  platform_retry = instrument_tenacity(
      tenacity.retry(
          retry=tenacity.retry_if_exception_type(IOError),
          stop=tenacity.stop_after_attempt(3),
          wait=tenacity.wait_exponential_jitter(initial=0.5, max=8),
          reraise=True,
      ),
      name="platform_http",
  )

  @platform_retry
  async def call_api(): ...
  ```

* **`instrument_redis_client(client, name)` — dedicated Redis error counter**
  (`obskit.integrations.cache`) — identical to `instrument_redis` but uses
  a positional `name` parameter, matching the common calling convention.
  Adds a new **`redis_command_errors_total{name, command}`** dedicated counter
  to all instrumented Redis clients (both `instrument_redis` and
  `instrument_redis_client`) for simpler alerting without label filtering.
  Also exported as ``obskit.instrument_redis_client``.

* **`@instrument_event_handler(name)` — OTel span + metrics for event handlers**
  (`obskit.decorators.event_handler`) — wraps async event handler methods with a
  child OTel span (``event_handler.<name>``) so the full pipeline
  ``HTTP → publish → consume → handler → use_case → DB`` is a connected trace.
  Emits:

  * ``event_handler_duration_seconds{name}`` — wall-time histogram (always
    recorded, including on exception).
  * ``event_handler_errors_total{name}`` — counter incremented before re-raise.

  Place this as the **outermost** decorator so the span wraps all inner
  decorators including ``with_event_context``:

  ```python
  from obskit import instrument_event_handler, with_event_context

  class EngagementInsertHandler:
      @instrument_event_handler(name="engagement_insert")
      @with_event_context(lambda e: {"company_id": str(e.get("company_id", ""))})
      async def handle(self, event_data: dict) -> None:
          await self._use_case.execute(event_data)
  ```

  Also exported as ``obskit.instrument_event_handler``.

## [1.8.0] (2026-04-04)

### Added

* **`extract_trace_context_from_headers(headers)` — RabbitMQ consumer trace extraction**
  (`obskit.integrations.queue.rabbitmq`) — public counterpart to `inject_trace_context_to_headers`.
  Extracts a W3C `traceparent` from an AMQP message headers dict and returns an OTel
  `Context` object that can be passed to `use_span_context`, completing the
  publisher→consumer trace linkage:
  ```python
  from obskit import extract_trace_context_from_headers, use_span_context
  ctx = extract_trace_context_from_headers(message.properties.headers or {})
  with use_span_context(ctx):
      async with async_trace_span("orders.process"):
          await handle(message.body)
  ```
  Also exported as `obskit.extract_trace_context_from_headers`.

* **`use_span_context(ctx)` — activate an extracted trace context**
  (`obskit.tracing.tracer`) — synchronous context manager that attaches a previously
  extracted OTel context for the duration of a `with` block.  When `ctx` is `None`
  (no `traceparent` found) it is a no-op, so callers never need an explicit None check.
  Also exported as `obskit.use_span_context`.

* **`instrument_pybreaker(breaker, name)` — circuit breaker Prometheus metrics**
  (`obskit.integrations.resilience.pybreaker`) — attaches an
  `ObskitCircuitBreakerListener` to any pybreaker `CircuitBreaker` instance and starts
  recording state, call outcomes, and **state transitions** (`circuit_breaker_transitions_total{name,from_state,to_state}`).
  Also exported as `obskit.instrument_pybreaker`.

* **`instrument_rate_limiter(limiter, platform)` — rate-limiter Prometheus metrics**
  (`obskit.integrations.resilience.rate_limiter`) — wraps `check()` and `record_limit()`
  on any rate-limiter object and emits `rate_limit_hits_total`, `rate_limit_recorded_total`,
  and `rate_limit_reset_seconds` counters/gauge.  Exception `retry_after`/`reset_after`
  attributes are read automatically to populate the reset gauge.
  Also exported as `obskit.instrument_rate_limiter`.

* **`circuit_breaker_transitions_total{name,from_state,to_state}` counter** added to
  `ObskitCircuitBreakerListener` and `instrument_circuit_breaker` — tracks every
  closed→open, open→half-open, and half-open→closed transition with full label context.

## [1.7.0] (2026-04-04)

### Added

* **`context_extractor` parameter for `instrument_fastapi()` and `configure_app_observability()`**
  — optional callable `(scope, receive) -> dict` that extracts per-request attributes
  (tenant ID, region, etc.) from the ASGI scope.  The returned dict is merged into the
  request log and span automatically.

* **`instrument_psycopg_pool(pool, name)` — connection pool Prometheus metrics**
  (`obskit.integrations.db.psycopg_pool`) — instruments a `psycopg_pool.ConnectionPool`
  or `AsyncConnectionPool` with `db_pool_size`, `db_pool_available`,
  `db_pool_waiting_requests` gauges and a `db_connection_acquisition_seconds` histogram.
  `PsycopgPoolInstrumentor.collect_stats()` updates the pool-state gauges on demand.

* **`slow_threshold_ms` parameter for `instrument_repo()`** — emit a `slow_repo_operation`
  structured warning log when any decorated async method exceeds the threshold.  The
  warning fires in a `finally` block so it triggers even when the method raises:
  ```python
  @instrument_repo(component="postgres", slow_threshold_ms=200.0)
  class OrderRepo: ...
  ```

* **`get_slo_readiness_check(name)` — retrieve a registered SLO readiness check**
  (`obskit.health.slo_check`) — returns the `SLOReadinessCheck` registered under the
  given name.  `add_slo_readiness_check` is now idempotent — repeated calls with the
  same name return the existing check.  Also exported as `obskit.get_slo_readiness_check`.

* **`baggage_context` / `async_baggage_context` — W3C baggage context managers**
  (`obskit.tracing.baggage`) — set arbitrary W3C baggage key-value pairs for the
  duration of a `with`/`async with` block; exported as `obskit.baggage_context` and
  `obskit.async_baggage_context`.

## [1.6.0] (2026-04-03)

### Added

* **`inject_trace_context_to_headers(headers)` — RabbitMQ publisher trace propagation**
  (`obskit.integrations.queue.rabbitmq`) — injects the active W3C ``traceparent`` (and
  ``tracestate``) into a plain ``dict`` before publishing to RabbitMQ, enabling end-to-end
  distributed traces across async message boundaries:
  ```python
  from obskit.integrations.queue.rabbitmq import inject_trace_context_to_headers
  headers: dict = {}
  inject_trace_context_to_headers(headers)
  channel.basic_publish(exchange="", routing_key="orders", body=body,
                        properties=pika.BasicProperties(headers=headers))
  ```
  Also exported as `obskit.inject_trace_context_to_headers`.

* **`instrument_rabbitmq` enhanced** — consumer callback now automatically extracts the
  ``traceparent`` header from incoming AMQP message properties and runs the user callback
  inside a child OTel span (`rabbitmq.consume.<queue>`), linking every consumed message
  to the publisher's trace. Falls back gracefully when OTel is not installed.

* **`observe_with_exemplar(metric, value)` — trace exemplar injection** now exported at
  the top-level `obskit` namespace (`obskit.observe_with_exemplar`).  Links a Prometheus
  histogram observation to the active Tempo/Jaeger trace so Grafana can display a
  "jump to trace" link directly from a latency spike.  Also exports `get_trace_exemplar`.

* **`DLQTracker` / `DLQReason` / `get_dlq_tracker` — Dead Letter Queue metrics** now
  exported from `obskit` top-level.  Record messages sent to DLQ (with reason, age, and
  retry count), track reprocessing success/failure, and alert on size thresholds:
  ```python
  from obskit import DLQTracker, DLQReason
  dlq = DLQTracker("orders_dlq")
  dlq.track_message_sent("orders", DLQReason.MAX_RETRIES.value, retry_count=5)
  ```

* **`add_slo_readiness_check(slo_name, critical_threshold)` — SLO-backed readiness probe**
  now exported from `obskit` top-level.  Registers a readiness health check that fails
  (HTTP 503) when the named SLO's error budget falls below *critical_threshold* (default
  10 %), keeping Kubernetes from routing traffic to a service burning through its budget.

* **`AdaptiveSampledLogger` — adaptive log volume control** now exported from `obskit`
  top-level.  Automatically adjusts per-level sampling rates to stay within a
  *target_logs_per_second* budget while always preserving warnings, errors, and
  critical events:
  ```python
  from obskit import AdaptiveSampledLogger
  logger = AdaptiveSampledLogger("retry_worker", target_logs_per_second=50)
  logger.info("event_retried")  # rate throttled automatically under load
  ```

## [1.5.0] (2026-04-03)

### Added

* **`instrument_httpx(client, name)` — outbound HTTP instrumentation** (`obskit.integrations.http`) —
  wraps any `httpx.AsyncClient` with:
  - `http_client_requests_total{name, method, status_code}` (counter — status is HTTP code or `"error"`)
  - `http_client_duration_seconds{name, method}` (histogram)
  - W3C `traceparent` injected into every outgoing request
  - One OTel span per request (`"HTTP GET"`, `"HTTP POST"`, …) with `http.method` and `http.client.name` attributes
  Works with `async with` context manager pattern.  Also exported as `obskit.instrument_httpx`.

* **`with_event_context(extractor)` — event handler context decorator** (`obskit.logging.event_context`) —
  decorator factory that binds structlog context-vars (company_id, company_schema, …) for the duration
  of an async event handler and unbinds them on exit (even on exceptions).  The `extractor` callable
  maps the incoming event dict to the bindings:
  ```python
  @with_event_context(lambda event: {
      "company_id": str(event.get("company_id")),
      "company_schema": event.get("company_schema"),
  })
  async def handle(self, event: dict) -> None: ...
  ```
  Also exported as `obskit.with_event_context`.

* **`instrument_repo(component)` — repository auto-tracing decorator** (`obskit.decorators.repo`) —
  class decorator that auto-wraps every public async method with an OTel span.  Span names follow the
  `"ClassName.method_name"` pattern (customisable via `span_prefix`).  Static methods, class methods,
  private methods, and synchronous methods are left unchanged:
  ```python
  @instrument_repo(component="postgres")
  class NotesRepo:
      async def insert_note(self, ...): ...
      async def get_notes(self, ...): ...
  # Spans: "NotesRepo.insert_note", "NotesRepo.get_notes"
  ```
  Also exported as `obskit.instrument_repo`.

* **`configure_app_observability(app, ...)` — one-call FastAPI setup** (`obskit.middleware.instrument`) —
  adds `ObskitMiddleware` *and* a Prometheus `/metrics` endpoint to a FastAPI app in a single call.
  Accepts `exclude_paths`, `track_metrics`, `track_logging`, `track_tracing`, and `metrics_path` params.
  Ideal for multi-app deployments where each app needs its own observability stack:
  ```python
  from obskit.middleware.instrument import configure_app_observability
  upload_app = FastAPI()
  configure_app_observability(upload_app, exclude_paths=["/v2/_healthy"])
  ```
  Also exported as `obskit.configure_app_observability`.

* **`instrument_psycopg3` / `instrument_psycopg3_connection`** now exported from the top-level `obskit`
  namespace (`obskit.instrument_psycopg3`, `obskit.instrument_psycopg3_connection`) for discoverability.
  The underlying implementation in `obskit.integrations.db.psycopg3` is unchanged.

## [1.4.0] (2026-04-03)

### Added

* **`patch_threading()` — context-propagating thread replacement** (`obskit.threading`) —
  calling `patch_threading()` (or passing `patch_threads=True` to `configure_observability()`)
  replaces `threading.Thread` globally with `_ContextThread`, which automatically copies
  structlog context-vars (`request_id`, `company_id`, …) and the active OpenTelemetry trace
  context into every child thread at `start()` time and cleans up on exit.
  Use `reset_threading_patch()` to restore the original `threading.Thread`.
  Also exported as `obskit.patch_threading` / `obskit.reset_threading_patch`.

* **`instrument_redis(client, name)` — Redis Prometheus instrumentation** (`obskit.integrations.cache`) —
  wraps any async Redis client (redis-py, aioredis) with three Prometheus metrics:
  `redis_commands_total{name, command, status}` (counter),
  `redis_command_duration_seconds{name, command}` (histogram), and
  `redis_pool_connections{name, state}` (gauge, populated via `update_pool_stats()`).
  Also exported as `obskit.instrument_redis`.

* **`scoped_context(**kw)` — duration-scoped log context manager** (`obskit.logging.context`) —
  binds structlog context-vars for the duration of a `with` / `async with` block and
  unbinds them automatically on exit (even if an exception is raised).  Keys bound
  *inside* the block by the caller's own code are not affected.
  Also exported as `obskit.scoped_context`.

* **`configure_observability(redis_url=...)` — auto Redis SLO init** — when `redis_url` is
  provided (or set via `OBSKIT_REDIS_URL`), `configure_observability()` automatically creates
  and registers a global `AsyncRedisSLOTracker`.  Access it via `get_redis_slo_tracker()`.
  Gracefully skips (with a warning log) if the `redis` package is not installed.

* **`configure_observability(redact_fields=[...])` — custom PII redaction** — user-supplied
  field-name substrings are merged with the built-in `DEFAULT_SENSITIVE_FIELDS` set
  (password, token, secret, …) in the structlog processor chain.

* **`instrument_retry_worker(name)` — retry loop Prometheus instrumentation**
  (`obskit.integrations.queue.retry_worker`) — returns a `RetryWorkerInstrumentor` handle
  with two methods:
  - `record_event(status)` — increments `retry_worker_events_total{name, status}`
    (conventional statuses: `"success"`, `"failure"`, `"skip"`, `"requeue"`)
  - `set_queue_depth(n)` — sets `retry_worker_queue_depth{name}` gauge
  Also exported as `obskit.instrument_retry_worker`.

## [1.3.0] (2026-04-03)

### Added

* **`obskit.integrations.gunicorn.ObskitGunicornConfig`** — base class for Gunicorn config files
  that eliminates multiprocess Prometheus boilerplate.  Inherit from it and gunicorn's
  `on_starting` / `child_exit` hooks are wired automatically:
  ```python
  from obskit.integrations.gunicorn import ObskitGunicornConfig

  class Config(ObskitGunicornConfig):
      bind = "0.0.0.0:8000"
      workers = 4
      worker_class = "uvicorn.workers.UvicornWorker"
  ```
  Also exported from the top-level `obskit` namespace as `obskit.ObskitGunicornConfig`.

* **`obskit.slo.redis_tracker.AsyncRedisSLOTracker`** — fleet-wide SLO tracker that stores
  measurements in Redis sorted sets so all Gunicorn/uvicorn workers share a single,
  consistent SLO view.  Supports all four SLO types (AVAILABILITY, ERROR_RATE, LATENCY,
  THROUGHPUT), rolling time windows, and TTL-based automatic eviction.
  Also exported as `obskit.AsyncRedisSLOTracker`.

* **Structured startup validation in `configure_observability()`** — emits structured log events
  at startup so misconfiguration surfaces immediately:
  - `obskit_configured` — service name, environment, version, log level/format, tracing state,
    sample rates
  - `otlp_endpoint_is_localhost` warning — hints to set a real collector in production
  - `otlp_endpoint_not_configured` warning — tracing enabled but no endpoint means spans are dropped
  - `log_sampling_active` info — reminds operators that non-error logs are sampled

## [1.2.0] (2026-04-03)

### Added

* **`obskit.resilience.circuit_breaker`** — Prometheus instrumentation for circuit breakers.
  `instrument_circuit_breaker(cb, name="redis_commands")` attaches an `ObskitCircuitBreakerListener`
  to any pybreaker `CircuitBreaker`, emitting three metrics:
  `circuit_breaker_state{name}` (0=closed/1=open/2=half-open),
  `circuit_breaker_failures_total{name}`, and
  `circuit_breaker_calls_total{name, outcome}`.
  Standalone helpers (`record_success`, `record_failure`, `record_state_change`) work without pybreaker.

* **`configure_observability()` now wires the log pipeline implicitly** — calling
  `configure_observability()` no longer requires a separate `configure_logging()` call at startup.
  The structlog processor chain is configured automatically, eliminating silent misconfiguration.

* **`obskit.logging.context`** — first-party context-binding API so application code never
  needs to import structlog directly.  Provides `bind_context(**kw)`, `unbind_context(*keys)`,
  `clear_context()`, `get_context()`, and `reset_context(token)`.
  Also exported from the top-level `obskit` namespace.

* **`ObskitMiddleware` `context_extractor` hook** — optional callable that receives the decoded
  request headers and returns a dict of extra fields to bind into the structured log context
  for the duration of the request.  Designed for multi-tenant services:
  ```python
  ObskitMiddleware(app, context_extractor=lambda h: {"company_id": h.get("x-company-id")})
  ```
  All log lines emitted during that request automatically carry `company_id`.

* **`check_psycopg3(dsn)`** health check helper in `obskit.health.aggregator` — uses
  `psycopg.AsyncConnection` (psycopg v3) to verify the PostgreSQL connection.

* **`check_pika(url)`** health check helper in `obskit.health.aggregator` — uses
  `pika.BlockingConnection` (sync AMQP client) run in a thread-pool executor.

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
