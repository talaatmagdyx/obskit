# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.0](https://github.com/talaatmagdyx/obskit/compare/v2.1.0...v2.2.0) (2026-03-01)


### 🚀 Features

* **slo:** add with_slo_tracking decorators for sync/async SLO measurement v1.5.0 ([234ff84](https://github.com/talaatmagdyx/obskit/commit/234ff84b536c0006bdc1b809108565bab0c3c715))
* **v1.4.0:** Add cardinality protection, sync circuit breaker, and enhanced queue tracking ([5025155](https://github.com/talaatmagdyx/obskit/commit/5025155a40236be351659ac8cc00d4491609c3bc))


### 🐛 Bug Fixes

* add noqa comment for CollectorRegistry import used in docstrings ([a294f0f](https://github.com/talaatmagdyx/obskit/commit/a294f0f0e464845a85a9d7cb6436f154141b489e))
* **ci:** add obskit smoke tests and missing packages to CI matrix ([e44e9d9](https://github.com/talaatmagdyx/obskit/commit/e44e9d9964de9c8582bc72ceb6e187fd512ad149))
* **ci:** add prometheus-client to integration test install step ([a9c5fe7](https://github.com/talaatmagdyx/obskit/commit/a9c5fe716c1a16ddaa7aec98a479cd1392616ade))
* **ci:** fix all failing CI checks for v2.0.0 monorepo ([05a2152](https://github.com/talaatmagdyx/obskit/commit/05a215279215ea8e359321899e0ab8dd83f5de56))
* **ci:** fix bandit format flag 'text' -&gt; 'txt' in security.yml ([f2fe9ae](https://github.com/talaatmagdyx/obskit/commit/f2fe9ae23670fe1a961847adb8224189ff52c203))
* code quality improvements ([234389d](https://github.com/talaatmagdyx/obskit/commit/234389daae7d103549bb6253ed3bb75fd111e93b))
* **deps:** add prometheus-client to dev extras and importlib mode to all packages ([d1b7c6c](https://github.com/talaatmagdyx/obskit/commit/d1b7c6c2069b8a39488b617a110434f6254dc27b))
* **lint:** replace (str, Enum) with StrEnum to fix UP042 ruff errors ([64c8ca2](https://github.com/talaatmagdyx/obskit/commit/64c8ca2c1620910c060082b37f202b5084b4928e))
* post-release CI, static analysis, deps and test fixes ([de01d08](https://github.com/talaatmagdyx/obskit/commit/de01d08c60b91f98eb5f1f72001e76358ec8f009))
* remove unused local variables ([908959e](https://github.com/talaatmagdyx/obskit/commit/908959ebb73b920f9053492a985bae2356b40a0d))
* remove unused TYPE_CHECKING import and fix django version check ([01639ed](https://github.com/talaatmagdyx/obskit/commit/01639edfa032347dd7411920f870a2c26c3ce880))
* resolve additional CodeQL alerts ([a1c6e4e](https://github.com/talaatmagdyx/obskit/commit/a1c6e4ef3dfce1602eef60fcac6e95298abf7348))
* resolve additional CodeQL alerts ([cc53984](https://github.com/talaatmagdyx/obskit/commit/cc539848551f58e148d015a6e4f1067799b68ca4))
* resolve CI issues and add security policy ([e67e28d](https://github.com/talaatmagdyx/obskit/commit/e67e28d17ca56540f7c2e3d23c53d99e5ede0e37))
* resolve CodeQL alerts for unused imports, variables, and type issues ([8d2730b](https://github.com/talaatmagdyx/obskit/commit/8d2730b75574aed25cf02ee872a95cb07b18b132))
* resolve CodeQL alerts for wrong arguments and loop variables ([c373568](https://github.com/talaatmagdyx/obskit/commit/c37356805448675252b9600b0ed9c5a8e9c1a263))
* resolve CodeQL security alerts ([defb33c](https://github.com/talaatmagdyx/obskit/commit/defb33cea96f873c28051bd56c4a4a97035ae657))
* resolve critical circular import bug in obskit.resilience (v1.3.3) ([5c86ad5](https://github.com/talaatmagdyx/obskit/commit/5c86ad5859eea720a12b9f10858d71b19c042c29))
* resolve import conflicts and unused imports ([4a0e1dd](https://github.com/talaatmagdyx/obskit/commit/4a0e1dd2579536c6f7045c62f82481700cf43130))
* resolve more CodeQL alerts ([5982b00](https://github.com/talaatmagdyx/obskit/commit/5982b00a83df7e935200c70c03ec651dd29273c5))
* resolve remaining CodeQL alerts ([d1b0c9f](https://github.com/talaatmagdyx/obskit/commit/d1b0c9f1c091816b12b460c424e5365496ca7c95))
* resolve ruff format and mypy strict errors ([5c75cb7](https://github.com/talaatmagdyx/obskit/commit/5c75cb751d70126761bb59d5010d52cac9961403))
* restore loggers as _logger (private convention) ([0ecaafc](https://github.com/talaatmagdyx/obskit/commit/0ecaafcddeb0e5db53577669f2a7c06d8bb67dc2))
* simplify Read the Docs configuration ([972a070](https://github.com/talaatmagdyx/obskit/commit/972a070b767de02a9c3390438d6bad8aa79d6960))
* **typecheck:** fix all mypy errors in CI type-check step ([238ada3](https://github.com/talaatmagdyx/obskit/commit/238ada34878834ba2aecd73de3565a8555c5706a))
* use local variables instead of discarding with underscore prefix ([d102662](https://github.com/talaatmagdyx/obskit/commit/d10266204ea550d4ee937b7bf18e9a6c7816feaf))


### 📚 Documentation

* add comprehensive feature reference documentation ([68bd3e6](https://github.com/talaatmagdyx/obskit/commit/68bd3e62630280adf5c6b52762bf68eef275a53a))
* add Read the Docs configuration ([15d803c](https://github.com/talaatmagdyx/obskit/commit/15d803ca635ff6a3166f5e412128061e6297bb9f))
* comprehensive Sphinx documentation with tech_docs ([b5fd27e](https://github.com/talaatmagdyx/obskit/commit/b5fd27e5ecbc2643a19cfd3f34b2500386b5125e))
* improve documentation and prepare for PyPI publishing ([fdcbf99](https://github.com/talaatmagdyx/obskit/commit/fdcbf992d55f5e399285b80c6d6e413f0d44adbc))
* include essential documentation inline in README for PyPI ([6281c26](https://github.com/talaatmagdyx/obskit/commit/6281c269fe73f6b75f95ebe903b15fb303638e93))
* remove staff engineer review documents ([29e9cfc](https://github.com/talaatmagdyx/obskit/commit/29e9cfcdd315b60259031ef9a20dee2f371865bd))
* rewrite all 16 package READMEs with creative layout, real API examples and full feature coverage ([f8a3ea0](https://github.com/talaatmagdyx/obskit/commit/f8a3ea083a9217c4bd44d0943dc838f9d81c2605))
* rewrite README with creative layout, full package ecosystem and updated dev commands ([c9470ef](https://github.com/talaatmagdyx/obskit/commit/c9470efae3bbdbbeaaa4277724943499836b4f0e))
* update all documentation for PyPI compatibility (v1.3.0) ([7e693d6](https://github.com/talaatmagdyx/obskit/commit/7e693d6554361969e8f3302517b5f5f3f0c8098c))


### 🔧 CI/CD

* bump actions/checkout from 4 to 6 ([3a4d1d8](https://github.com/talaatmagdyx/obskit/commit/3a4d1d846344e3bfc6b6cd4028fda221ce86cf83))
* bump actions/checkout from 4 to 6 ([eb44016](https://github.com/talaatmagdyx/obskit/commit/eb4401697f27d5dcd5dd67b6fca250764016452d))
* bump actions/download-artifact from 4 to 7 ([5484c25](https://github.com/talaatmagdyx/obskit/commit/5484c253dfd74c67a1439c3c81f1e48618da4531))
* bump actions/download-artifact from 4 to 7 ([adccbe8](https://github.com/talaatmagdyx/obskit/commit/adccbe8657684629a75cb770fc6098d3c5361f67))
* bump actions/setup-python from 5 to 6 ([6028579](https://github.com/talaatmagdyx/obskit/commit/60285794dd2da76c9eafa1155182452f2fe0dca6))
* bump actions/setup-python from 5 to 6 ([c8ee183](https://github.com/talaatmagdyx/obskit/commit/c8ee183dc1032d0d2b08ee594c04ed602f79afee))
* bump actions/upload-artifact from 4 to 6 ([51a68f5](https://github.com/talaatmagdyx/obskit/commit/51a68f5ee00d716adf1cb06d29f1a43fb3a728e0))
* bump actions/upload-artifact from 4 to 6 ([3f97e8f](https://github.com/talaatmagdyx/obskit/commit/3f97e8fb18e1904dca09c611eebd122883245b3a))
* bump actions/upload-pages-artifact from 3 to 4 ([4b35c97](https://github.com/talaatmagdyx/obskit/commit/4b35c977f30c11e8884b3ebc3214c837327c9f70))
* bump actions/upload-pages-artifact from 3 to 4 ([15fe9ac](https://github.com/talaatmagdyx/obskit/commit/15fe9ac250928a3b8c6cf1930b86b51d345ceb58))
* migrate release-please to googleapis/release-please-action@v4 ([4fe6a03](https://github.com/talaatmagdyx/obskit/commit/4fe6a03018e4bedb68eb0813c0345924fb9f5f9c))


### 🔒 Security

* add nosec annotations for CodeQL/bandit alerts ([16814e7](https://github.com/talaatmagdyx/obskit/commit/16814e78f066a552440c639f1be41d655bff9686))

## [2.1.0](https://github.com/talaatmagdyx/obskit/compare/v2.0.0...v2.1.0) (2026-02-28)


### 🚀 Features

* **slo:** add with_slo_tracking decorators for sync/async SLO measurement v1.5.0 ([234ff84](https://github.com/talaatmagdyx/obskit/commit/234ff84b536c0006bdc1b809108565bab0c3c715))
* **v1.4.0:** Add cardinality protection, sync circuit breaker, and enhanced queue tracking ([5025155](https://github.com/talaatmagdyx/obskit/commit/5025155a40236be351659ac8cc00d4491609c3bc))


### 🐛 Bug Fixes

* add noqa comment for CollectorRegistry import used in docstrings ([a294f0f](https://github.com/talaatmagdyx/obskit/commit/a294f0f0e464845a85a9d7cb6436f154141b489e))
* **ci:** add obskit smoke tests and missing packages to CI matrix ([f5d5579](https://github.com/talaatmagdyx/obskit/commit/f5d55792add4689f118bc384457cf86195544ae4))
* **ci:** add prometheus-client to integration test install step ([638b147](https://github.com/talaatmagdyx/obskit/commit/638b1471ebc0b2d92cb86eb12c7d60c92411f9d7))
* **ci:** fix all failing CI checks for v2.0.0 monorepo ([92fcfbd](https://github.com/talaatmagdyx/obskit/commit/92fcfbd2df71ef7e9ecc881ba085bce4fec4bc1a))
* **ci:** fix bandit format flag 'text' -&gt; 'txt' in security.yml ([f2f1d89](https://github.com/talaatmagdyx/obskit/commit/f2f1d899635be5c423d5ec3a2896ac1d863ab4aa))
* code quality improvements ([234389d](https://github.com/talaatmagdyx/obskit/commit/234389daae7d103549bb6253ed3bb75fd111e93b))
* **deps:** add prometheus-client to dev extras and importlib mode to all packages ([01b2da0](https://github.com/talaatmagdyx/obskit/commit/01b2da043ca821f5578d6b1d6f4f02064ae544ea))
* **lint:** replace (str, Enum) with StrEnum to fix UP042 ruff errors ([7dd0cb1](https://github.com/talaatmagdyx/obskit/commit/7dd0cb198ddc67469cf036aaa0e948bf46b10293))
* remove unused local variables ([908959e](https://github.com/talaatmagdyx/obskit/commit/908959ebb73b920f9053492a985bae2356b40a0d))
* remove unused TYPE_CHECKING import and fix django version check ([01639ed](https://github.com/talaatmagdyx/obskit/commit/01639edfa032347dd7411920f870a2c26c3ce880))
* resolve additional CodeQL alerts ([a1c6e4e](https://github.com/talaatmagdyx/obskit/commit/a1c6e4ef3dfce1602eef60fcac6e95298abf7348))
* resolve additional CodeQL alerts ([cc53984](https://github.com/talaatmagdyx/obskit/commit/cc539848551f58e148d015a6e4f1067799b68ca4))
* resolve CI issues and add security policy ([e67e28d](https://github.com/talaatmagdyx/obskit/commit/e67e28d17ca56540f7c2e3d23c53d99e5ede0e37))
* resolve CodeQL alerts for unused imports, variables, and type issues ([8d2730b](https://github.com/talaatmagdyx/obskit/commit/8d2730b75574aed25cf02ee872a95cb07b18b132))
* resolve CodeQL alerts for wrong arguments and loop variables ([c373568](https://github.com/talaatmagdyx/obskit/commit/c37356805448675252b9600b0ed9c5a8e9c1a263))
* resolve CodeQL security alerts ([defb33c](https://github.com/talaatmagdyx/obskit/commit/defb33cea96f873c28051bd56c4a4a97035ae657))
* resolve critical circular import bug in obskit.resilience (v1.3.3) ([5c86ad5](https://github.com/talaatmagdyx/obskit/commit/5c86ad5859eea720a12b9f10858d71b19c042c29))
* resolve import conflicts and unused imports ([4a0e1dd](https://github.com/talaatmagdyx/obskit/commit/4a0e1dd2579536c6f7045c62f82481700cf43130))
* resolve more CodeQL alerts ([5982b00](https://github.com/talaatmagdyx/obskit/commit/5982b00a83df7e935200c70c03ec651dd29273c5))
* resolve remaining CodeQL alerts ([d1b0c9f](https://github.com/talaatmagdyx/obskit/commit/d1b0c9f1c091816b12b460c424e5365496ca7c95))
* resolve ruff format and mypy strict errors ([5c75cb7](https://github.com/talaatmagdyx/obskit/commit/5c75cb751d70126761bb59d5010d52cac9961403))
* restore loggers as _logger (private convention) ([0ecaafc](https://github.com/talaatmagdyx/obskit/commit/0ecaafcddeb0e5db53577669f2a7c06d8bb67dc2))
* simplify Read the Docs configuration ([972a070](https://github.com/talaatmagdyx/obskit/commit/972a070b767de02a9c3390438d6bad8aa79d6960))
* **typecheck:** fix all mypy errors in CI type-check step ([5c443c0](https://github.com/talaatmagdyx/obskit/commit/5c443c0a636f3cc0ed4cbb89172710b3f7d56320))
* use local variables instead of discarding with underscore prefix ([d102662](https://github.com/talaatmagdyx/obskit/commit/d10266204ea550d4ee937b7bf18e9a6c7816feaf))


### 📚 Documentation

* add comprehensive feature reference documentation ([68bd3e6](https://github.com/talaatmagdyx/obskit/commit/68bd3e62630280adf5c6b52762bf68eef275a53a))
* add Read the Docs configuration ([15d803c](https://github.com/talaatmagdyx/obskit/commit/15d803ca635ff6a3166f5e412128061e6297bb9f))
* comprehensive Sphinx documentation with tech_docs ([b5fd27e](https://github.com/talaatmagdyx/obskit/commit/b5fd27e5ecbc2643a19cfd3f34b2500386b5125e))
* improve documentation and prepare for PyPI publishing ([fdcbf99](https://github.com/talaatmagdyx/obskit/commit/fdcbf992d55f5e399285b80c6d6e413f0d44adbc))
* include essential documentation inline in README for PyPI ([6281c26](https://github.com/talaatmagdyx/obskit/commit/6281c269fe73f6b75f95ebe903b15fb303638e93))
* remove staff engineer review documents ([29e9cfc](https://github.com/talaatmagdyx/obskit/commit/29e9cfcdd315b60259031ef9a20dee2f371865bd))
* update all documentation for PyPI compatibility (v1.3.0) ([7e693d6](https://github.com/talaatmagdyx/obskit/commit/7e693d6554361969e8f3302517b5f5f3f0c8098c))


### 🔧 CI/CD

* bump actions/checkout from 4 to 6 ([3a4d1d8](https://github.com/talaatmagdyx/obskit/commit/3a4d1d846344e3bfc6b6cd4028fda221ce86cf83))
* bump actions/checkout from 4 to 6 ([eb44016](https://github.com/talaatmagdyx/obskit/commit/eb4401697f27d5dcd5dd67b6fca250764016452d))
* bump actions/download-artifact from 4 to 7 ([5484c25](https://github.com/talaatmagdyx/obskit/commit/5484c253dfd74c67a1439c3c81f1e48618da4531))
* bump actions/download-artifact from 4 to 7 ([adccbe8](https://github.com/talaatmagdyx/obskit/commit/adccbe8657684629a75cb770fc6098d3c5361f67))
* bump actions/setup-python from 5 to 6 ([6028579](https://github.com/talaatmagdyx/obskit/commit/60285794dd2da76c9eafa1155182452f2fe0dca6))
* bump actions/setup-python from 5 to 6 ([c8ee183](https://github.com/talaatmagdyx/obskit/commit/c8ee183dc1032d0d2b08ee594c04ed602f79afee))
* bump actions/upload-artifact from 4 to 6 ([51a68f5](https://github.com/talaatmagdyx/obskit/commit/51a68f5ee00d716adf1cb06d29f1a43fb3a728e0))
* bump actions/upload-artifact from 4 to 6 ([3f97e8f](https://github.com/talaatmagdyx/obskit/commit/3f97e8fb18e1904dca09c611eebd122883245b3a))
* bump actions/upload-pages-artifact from 3 to 4 ([4b35c97](https://github.com/talaatmagdyx/obskit/commit/4b35c977f30c11e8884b3ebc3214c837327c9f70))
* bump actions/upload-pages-artifact from 3 to 4 ([15fe9ac](https://github.com/talaatmagdyx/obskit/commit/15fe9ac250928a3b8c6cf1930b86b51d345ceb58))
* migrate release-please to googleapis/release-please-action@v4 ([4fe6a03](https://github.com/talaatmagdyx/obskit/commit/4fe6a03018e4bedb68eb0813c0345924fb9f5f9c))


### 🔒 Security

* add nosec annotations for CodeQL/bandit alerts ([16814e7](https://github.com/talaatmagdyx/obskit/commit/16814e78f066a552440c639f1be41d655bff9686))

## [2.0.0] - 2026-02-27

### Breaking Changes

- **Monorepo split** — obskit is now a collection of focused packages. Each can be installed
  independently, and `pip install obskit` still installs everything as before.

  | Package | Contains |
  |---------|----------|
  | `obskit-core` | config, errors, interfaces, middleware base |
  | `obskit-logging` | structured logging, sampling, debug replay |
  | `obskit-metrics` | RED/Golden/USE metrics, Prometheus, fingerprint |
  | `obskit-tracing` | OpenTelemetry distributed tracing |
  | `obskit-health` | health-check framework |
  | `obskit-resilience` | circuit breaker, load shedding, failover |
  | `obskit-slo` | SLO tracking, alerting rules, error budgets |
  | `obskit-middleware-fastapi` | FastAPI ASGI middleware |
  | `obskit-middleware-flask` | Flask WSGI middleware |
  | `obskit-middleware-django` | Django middleware |
  | `obskit-middleware-grpc` | gRPC server/client interceptors |
  | `obskit` | meta-package (installs all of the above) |

  All existing `from obskit.X import Y` imports continue to work **unchanged** — namespace
  packages are used so Python merges all sub-packages into one `obskit.*` namespace.

- **13 out-of-scope modules removed** — the following modules have been permanently
  deleted because they belong in separate tools, not an observability toolkit:

  | Removed module | Domain |
  |---------------|--------|
  | `obskit.chaos` | Chaos engineering |
  | `obskit.capacity` | Capacity planning |
  | `obskit.compliance_reporter` | Compliance governance |
  | `obskit.compliance.pii` | PII / compliance tooling |
  | `obskit.runbook` | Incident runbooks |
  | `obskit.incident_timeline` | Incident management |
  | `obskit.secrets_detector` | Security scanning |
  | `obskit.feature_flags` | Platform engineering |
  | `obskit.deployment` | Platform engineering |
  | `obskit.resource_predictor` | AIOps / ML |
  | `obskit.root_cause` | AIOps / ML |
  | `obskit.self_healing` | AIOps / ML |
  | `obskit.flamegraph` | Profiling |

- **Build system changed** — sub-packages use `setuptools` (with `namespaces = true`)
  instead of hatchling. No end-user impact; only relevant if building from source.

### Added

- `packages/` directory with 12 independently installable packages.
- `pkgutil.extend_path` in `obskit/__init__.py` and `obskit/middleware/__init__.py`
  to enable namespace-package merging across sub-packages.

### Fixed

- **`ConsumerLagTracker` deadlock** (`packages/obskit-queue/src/obskit/consumer_lag.py`)
  - `get_stats()` held `self._lock` (non-reentrant `threading.Lock`) while calling
    `_calculate_growth_rate()` and `_calculate_velocity()`, which also attempted to
    acquire `self._lock` — causing a permanent deadlock on any `get_stats()` or
    `is_healthy()` call. All 51 consumer-lag tests hung indefinitely before this fix.
  - Fixed by changing `threading.Lock()` to `threading.RLock()` (reentrant lock).

### Migration Guide

```bash
# Before (monolith)
pip install obskit

# After (same — meta-package installs everything)
pip install obskit

# After (focused — only what you need)
pip install obskit-metrics obskit-logging
pip install obskit-middleware-fastapi
```

No import changes required. All `from obskit.X import Y` statements continue to work.

---

## [1.6.1] - 2026-02-27

### Security

- **MD5 — explicit non-security intent** (`alert_dedup.py`, `cache.py`, `fingerprint.py`, `logging/sampling.py`, `query_analyzer.py`)
  - Added `usedforsecurity=False` to all `hashlib.md5()` calls used for fingerprinting/cache-key generation
  - Silences bandit B324 (CWE-327); documents clearly these hashes are not used for cryptographic purposes

- **Health server: default bind address** (`health/server.py`)
  - `start_health_server()` now defaults to `host="127.0.0.1"` instead of `"0.0.0.0"`
  - Prevents `/health`, `/metrics`, and custom handler endpoints from being inadvertently exposed externally
  - Callers who need external binding must now opt-in explicitly

- **Timing-safe token comparison** (`metrics/auth.py`)
  - Replaced `token != self.auth_token` with `hmac.compare_digest()` to prevent timing-based token oracle attacks on the metrics endpoint

- **Thread safety: in-memory cache decorator** (`cache.py`)
  - Added `threading.Lock()` protecting all reads, writes, and deletes on the shared `_cache` dict
  - Eliminates TOCTOU race conditions (check-then-use) in multi-threaded deployments

- **Thread safety: custom health handler registry** (`health/server.py`)
  - `_custom_handlers` is now snapshot under `_server_lock` before dispatch, eliminating the check-then-call race condition

- **PII decorator: silent no-op removed** (`compliance/pii.py`)
  - `@redact_pii_decorator` now emits `UserWarning` at decoration time so callers know it performs no redaction
  - Prevents false confidence in automatic PII masking

- **`FileStorage` hardcoded `/tmp` removed** (`debug/replay.py`)
  - Default path changed from `/tmp/obskit_captures` to `Path(tempfile.gettempdir()) / "obskit_captures"`
  - Cross-platform; avoids world-readable directories on shared Linux systems

### Added

- **`.pre-commit-config.yaml` — bandit severity gate aligned with CI**
  - Bandit pre-commit hook now runs with `-ll` (MEDIUM+ only), matching the CI security job
  - Prevents false failures from the 34 intentional LOW findings (non-crypto `random.random()` for sampling)

- **CI: `security` job** (`.github/workflows/ci.yml`)
  - `bandit -r src/obskit -ll` — SAST gate on every push / PR
  - `pip-audit --desc` — CVE scan of the full dependency tree
  - `pip-licenses --fail-on="GPL-2.0;GPL-3.0;AGPL-3.0"` — copyleft license gate
  - `build` job now requires `security` to pass before packaging

- **Release pipeline: SBOM + Sigstore** (`.github/workflows/release.yml`)
  - `sbom` job generates CycloneDX JSON SBOM via `cyclonedx-py` and attaches it to the GitHub release
  - `publish-pypi` signs `dist/*.whl` and `dist/*.tar.gz` with Sigstore after upload; `.sigstore.json` files are attached to the release
  - `build` job now requires SBOM generation before packaging

- **Dependabot hardened** (`.github/dependabot.yml`)
  - Pip schedule changed from `weekly` to `daily` for faster security-patch delivery
  - Dev/test tooling batched into a single `dev-tooling` group to reduce noise
  - Production core dependencies (`structlog`, `pydantic-settings`, `PyYAML`, `opentelemetry-*`) left ungrouped so each advisory appears as a distinct PR

- **Dev dependencies** (`pyproject.toml`)
  - `pip-licenses>=5.0.0,<7.0.0` — license scanning
  - `cyclonedx-bom>=4.0.0,<6.0.0` — SBOM generation
  - `sigstore>=3.0.0,<4.0.0` — release artifact signing

---

## [1.6.0] - 2026-02-27

### Added

- **`observe` / `observe_sync` context managers** (`obskit.decorators.context_managers`)
  - `observe(...)` — async context manager that also works as an `@observe(...)` decorator on async functions
  - `observe_sync(...)` — sync context manager that also works as an `@observe_sync(...)` decorator on sync functions
  - Both support all standard parameters: `component`, `operation`, `threshold_ms`, `track_metrics`, `log_start`, `sample_rate`, `high_throughput`, plus arbitrary `**context` kwargs
  - Standard path mirrors `with_observability` (correlation context, RED metrics, structured logging)
  - High-throughput path routes through the `_HTPipeline` singleton for ~100 ns overhead
  - When `sample_rate < 1.0`, applies probabilistic sampling gate before pipeline entry

- **`_HTPipeline.configure()` — optional integrations for the HT pipeline** (`obskit.decorators.ht_runtime`)
  - `configure(statsd=..., slo_tracker=...)` — must be called before the first `high_throughput=True` invocation
  - Issues a `RuntimeWarning` if called after the pipeline has already started
  - **StatsD integration**: aggregated request counts and timings are emitted via `emit_counter` / `emit_timing` on every flush cycle (~1 s)
  - **SLO tracker integration**: every `record()` call posts a lock-free measurement to the attached `HighThroughputSLOTracker` (~100 ns overhead)

- **`configure_ht_pipeline()` module-level convenience function** (`obskit.decorators.ht_runtime`)
  - Wraps `_ht_pipeline.configure()` for ergonomic use without importing internal module paths

### Exports

- Added `observe`, `observe_sync`, `with_observability_sync` to top-level `obskit` package
- Added full HT pipeline API to top-level `obskit` package — no internal imports needed:
  - `configure_ht_pipeline` — attach StatsD / SLO tracker before first decorated call
  - `get_ht_pipeline` — access the singleton (e.g. to inspect state in tests)
  - `reset_ht_pipeline` — stop and replace the singleton (test teardown)
  - `StatsDEmitter` — parameter type for `configure_ht_pipeline(statsd=...)`
  - `HighThroughputSLOTracker` — parameter type for `configure_ht_pipeline(slo_tracker=...)`

---

## [1.5.0] - 2026-01-26

### Added

- **SLO Tracking Decorators** (`obskit.slo.tracker`)
  - `with_slo_tracking()` - Flexible decorator for SLO tracking with auto-detection of sync/async
  - `with_slo_tracking_sync()` - Synchronous decorator for SLO tracking
  - `with_slo_tracking_async()` - Asynchronous decorator for SLO tracking
  - Automatically records latency, availability, and error rate measurements
  - Lazy SLO registration on first use

### Exports

- Added `with_slo_tracking`, `with_slo_tracking_sync`, `with_slo_tracking_async` to `obskit.slo` module

---

## [1.4.0] - 2026-01-26

### Added

- **Cardinality Protection** (`obskit.metrics.cardinality`)
  - `CardinalityProtector` class to prevent high-cardinality label explosion
  - `CardinalityConfig` for customizable limits and TTL
  - `LRUCache` thread-safe cache for tracking unique values
  - `get_cardinality_protector()` singleton accessor
  - `protect_label()` and `protect_id()` convenience functions
  - Prometheus metrics: `obskit_cardinality_rejections_total`, `obskit_cardinality_current`, `obskit_cardinality_limit`

- **Sync Circuit Breaker Support** (`obskit.resilience.circuit_breaker`)
  - `with_circuit_breaker_sync()` decorator for sync functions
  - `CircuitBreaker.__enter__` / `__exit__` sync context manager
  - `CircuitBreaker.call_sync()` method for one-off protected calls
  - Internal sync methods: `_should_allow_request_sync()`, `_record_success_sync()`, `_record_failure_sync()`

- **Enhanced Queue Tracking** (`obskit.queue.tracker`)
  - `MessageContext` dataclass for rich business context (message_id, correlation_id, tenant_id, redelivered, etc.)
  - `QueueTracker.track_message()` context manager with mutable context
  - `QueueTracker.track_message_received()` for message receipt tracking
  - `QueueTracker.track_message_acked()` for acknowledgment tracking
  - `QueueTracker.track_message_nacked()` for negative acknowledgment tracking
  - Prometheus metrics: `obskit_queue_messages_received_total`, `obskit_queue_messages_acked_total`, `obskit_queue_messages_nacked_total`

### Fixed

- **Business Metrics `event` Parameter Conflict**
  - Fixed `TypeError: got multiple values for argument 'event'` in `BusinessMetrics.track_event()`
  - Changed log event name from `"business_event"` to `"business_event_tracked"`
  - Renamed log parameter from `event=event` to `event_type=event` to avoid structlog conflict

### Documentation

- Added `docs/source/features/cardinality-protection.md`
- Added `docs/source/features/sync-circuit-breaker.md`
- Added `docs/source/features/queue-tracking.md`

## [1.3.3] - 2026-01-20

### Fixed

- **Critical: Circular Import Bug in obskit.resilience**
  - Fixed circular import that prevented `from obskit.resilience import ...` from working
  - Root cause: `combined.py` and `factory.py` imported from `obskit.resilience` package instead of specific modules
  - Fix: Changed to direct imports from `obskit.resilience.circuit_breaker` and `obskit.resilience.rate_limiter`

- **Critical: ObskitSettings Class Indentation Bug**
  - Fixed class body being defined at module level instead of inside the class
  - This caused `model_fields` to be empty and all settings to fail validation
  - Fix: Corrected indentation of entire class body (lines 234-683)

- **Circular Import Handling in Logging**
  - Added defensive `try/except` for settings access during circular imports
  - Affected: `configure_logging()`, `add_service_info()`, `sample_log()` processors
  - Uses sensible defaults when settings attributes unavailable during import

- **MetricsMethod Import Cycle**
  - Moved `MetricsMethod` enum definition directly into `config.py`
  - Prevents import cycle: `config.py` → `obskit.core.types` → `obskit/__init__.py` → `config.py`

- **Flask Middleware Lazy Initialization**
  - Changed `obskit_flask` singleton to lazy initialization via `get_obskit_flask()`
  - Prevents settings access during module import

## [1.3.2] - 2026-01-20

### Fixed

- **CodeQL Alerts Resolution**
  - Fixed variable redefinition in `root_cause.py` by refactoring to single-assignment pattern
  - Removed unused `_logger` imports in `correlation.py`, `cost.py`, and `errors/responses.py`
  - Removed unused `TYPE_CHECKING` and `CollectorRegistry` imports in `metrics/types.py`
  - Standardized import patterns in test files to avoid import/from-import mixing
  - Fixed Django version check in `test_django.py` to avoid unused variable warnings

- **Import Consistency**
  - `test_self_metrics.py`: Use consistent module import pattern
  - `test_rate_limiter.py`: Use consistent module import pattern
  - `test_logger.py`: Use consistent module import pattern

## [1.3.1] - 2026-01-20

### Fixed

- Minor bug fixes and code quality improvements

## [1.3.0] - 2026-01-19

### 🚀 Major Release - 39 New Features!

This release brings obskit to **52+ total features** for enterprise-grade observability.

### Added - Debugging & Analysis

- **Flame Graph Profiler** (`FlameGraphProfiler`)
  - CPU and memory profiling with visualization
  - SVG and JSON export for flame graphs
  - Integration with py-spy/pyflame

- **Query Plan Analyzer** (`QueryAnalyzer`)
  - SQL query analysis and optimization suggestions
  - Slow query tracking with threshold alerts
  - Query type detection and cost estimation

- **Dependency Graph** (`DependencyGraph`)
  - Service dependency visualization
  - Health status propagation
  - DOT and Mermaid export formats

- **Root Cause Analyzer** (`RootCauseAnalyzer`)
  - Automated incident root cause analysis
  - Anomaly detection with severity levels
  - Contributing factor correlation

- **Error Fingerprinting** (`ErrorFingerprinter`)
  - Automatic error grouping by similarity
  - Stack trace normalization
  - Error occurrence tracking

- **Latency Breakdown** (`LatencyBreakdown`)
  - Phase-by-phase latency analysis
  - Percentage breakdown per phase
  - Automatic performance bottleneck detection

- **Hot Path Detector** (`HotPathDetector`)
  - Identify critical code paths
  - Call frequency and duration tracking
  - Performance optimization suggestions

### Added - Resilience & Reliability

- **Chaos Engineering** (`ChaosEngine`)
  - Latency injection experiments
  - Error injection with probability control
  - Timeout and resource exhaustion simulation
  - Network partition simulation

- **Graceful Degradation** (`DegradationManager`)
  - Feature priority-based degradation
  - Load-based automatic degradation
  - Fallback function support
  - Degradation level metrics

- **Self-Healing** (`SelfHealingEngine`)
  - Automatic remediation triggers
  - Cooldown and rate limiting
  - Execution tracking and metrics
  - Condition-based healing actions

- **Failover Coordinator** (`FailoverCoordinator`)
  - Primary/backup failover management
  - Health check-based automatic failover
  - Manual failover support
  - Failover event tracking

- **Load Shedding** (`LoadShedder`)
  - Priority-based request rejection
  - High/low water mark thresholds
  - Concurrent request tracking
  - Graceful rejection with retry-after

### Added - Performance

- **Adaptive Sampling** (`AdaptiveSampler`)
  - Dynamic trace/log sampling based on load
  - Error rate-based sampling adjustment
  - Configurable sampling strategies

- **Resource Predictor** (`ResourcePredictor`)
  - Predict resource exhaustion
  - Trend analysis and forecasting
  - Capacity planning recommendations

- **Auto-Scaling Metrics** (`AutoScalingMetrics`)
  - Kubernetes HPA metrics provider
  - Custom metric export for scaling
  - Scaling recommendation engine

### Added - Security & Compliance

- **Audit Trail** (`AuditTrail`)
  - Immutable audit logging
  - Chain verification for integrity
  - Query by actor, resource, time range

- **Secrets Detection** (`SecretsDetector`)
  - Detect secrets in logs and data
  - Automatic redaction of API keys, passwords
  - Support for custom secret patterns

- **Compliance Reporter** (`ComplianceReporter`)
  - GDPR compliance checks
  - SOC2 compliance checks
  - HIPAA compliance checks
  - Custom compliance framework support

### Added - Operations

- **Runbook Integration** (`RunbookManager`)
  - Link alerts to runbooks
  - Execution tracking and notes
  - Resolution documentation

- **Incident Timeline** (`IncidentManager`)
  - Build incident timelines
  - Event tracking with sources
  - Post-mortem generation

- **SLA Breach Predictor** (`SLAPredictor`)
  - Predict SLA violations
  - Time to breach estimation
  - Risk assessment and recommendations

- **Capacity Planner** (`CapacityPlanner`)
  - Resource usage tracking
  - Capacity projections (30/90 days)
  - Exhaustion date prediction

- **Alert Deduplication** (`AlertDeduplicator`)
  - Suppress redundant alerts
  - Configurable dedup windows
  - Group-by label support

- **Grafana Annotations** (`GrafanaAnnotator`)
  - Programmatic annotations
  - Deployment markers
  - Incident annotations

### Added - Infrastructure

- **Connection Pool Metrics** (`ConnectionPoolTracker`)
  - Database pool tracking
  - Redis pool tracking
  - RabbitMQ pool tracking
  - Wait time and utilization metrics

- **Dead Letter Queue Tracking** (`DLQTracker`)
  - DLQ message tracking
  - Reason categorization
  - Payload sampling

- **Consumer Lag Tracking** (`ConsumerLagTracker`)
  - Kafka consumer lag
  - RabbitMQ queue depth
  - SQS message age

- **External API SLA Tracking** (`ExternalAPISLATracker`)
  - External API availability
  - Latency P99 tracking
  - SLA compliance reporting

- **Executor Metrics** (`ExecutorTracker`)
  - ThreadPoolExecutor tracking
  - Active/queued task counts
  - Task duration metrics

- **Memory/GC Metrics** (`MemoryTracker`)
  - Heap usage tracking
  - GC collection metrics
  - Object count by type

- **Circuit Breaker Dashboard** (`CircuitBreakerDashboard`)
  - CB state visualization data
  - Multi-breaker overview
  - State change history

- **Distributed Locking** (`DistributedLock`)
  - Redis-based distributed locks
  - Leader election support
  - Lock timeout and extension

- **Tenant Quota Tracking** (`QuotaTracker`)
  - Per-tenant resource quotas
  - Usage tracking and limits
  - Quota period management

### Added - Deployment & Testing

- **Feature Flag Tracker** (`FeatureFlagTracker`)
  - Track flag usage and impact
  - A/B test metrics correlation
  - Flag change tracking

- **Deployment Tracker** (`DeploymentTracker`)
  - Canary deployment metrics
  - Blue-Green deployment tracking
  - Rollback detection

### Added - Documentation

- **Complete Feature Reference** (`docs/FEATURES.md`)
  - All 52+ features documented
  - Code examples for every feature
  - Best practices and configuration

### Changed

- Version bumped to 1.3.0
- README updated with all new features
- Documentation links now use absolute GitHub URLs for PyPI compatibility
- Tech docs updated with feature status tables

---

## [1.2.0] - 2026-01-15

### Added - Infrastructure Monitoring

- Connection Pool Metrics
- DLQ Tracking
- Consumer Lag Tracking
- External API SLA Tracking
- Executor Metrics
- Memory/GC Metrics
- Circuit Breaker Dashboard
- Distributed Locking
- Tenant Quota Tracking
- Error Fingerprinting
- Latency Breakdown

---

## [1.1.0] - 2026-01-10

### Added

- **Async Message Tracing** - Trace context propagation across RabbitMQ, Kafka, SQS
- **Batch Operation Tracking** - Track batch processing with success/failure rates
- **Cache Instrumentation** - Automatic cache hit/miss tracking
- **Business Metrics** - Easy business KPI tracking (conversions, funnels, revenue)
- **Performance Budgets** - Enforce latency/error rate constraints at code level
- **Correlation ID Manager** - Better correlation across async boundaries
- **Dependency Health Aggregator** - Single view of all dependencies' health
- **Smart Log Sampling** - Reduce log volume while keeping important events
- **Grafana Annotations** - Programmatic annotations for deployments/incidents
- **Cost Attribution** - Track resource usage per tenant for billing
- **Schema Validation Metrics** - Track data validation errors structured
- **Adaptive Retry** - Smarter retries that adapt to system load
- **Request Replay** - Capture and replay failed requests for debugging

---

## [1.0.0] - 2026-01-05

### 🎉 Production Stable Release

This release marks obskit as **fully production-ready** with all components stable.

### Stability Upgrades

- **Distributed Circuit Breaker** → ✅ **STABLE**
  - Full support for sync and async Redis clients
  - State persistence with configurable TTL
  - Graceful degradation on Redis failures
  - Multi-instance synchronization

- **SLO Tracking** → ✅ **STABLE**
  - Availability, Error Rate, Latency, Throughput SLOs
  - Error budget tracking with burn rate calculation
  - Alertmanager webhook integration
  - Prometheus metrics export

- **Self-Metrics** → ✅ **STABLE**
  - `obskit_async_queue_depth` gauge
  - `obskit_async_queue_capacity` gauge
  - `obskit_metrics_dropped_total` counter
  - `obskit_errors_total` counter
  - `obskit_info` version information

### Added

- **Built-in Health Checks**
  - `create_redis_check()` - Redis/Redis Cluster health
  - `create_memory_check()` - Memory utilization monitoring
  - `create_disk_check()` - Disk utilization monitoring
  - `create_http_check()` - External HTTP dependency checks

- **Rate Limiting for Metrics Endpoint**
  - `metrics_rate_limit_enabled` configuration
  - `metrics_rate_limit_requests` per minute limit
  - HTTP 429 response with Retry-After header

- **Configurable Async Queue**
  - `async_metric_queue_size` configuration
  - Self-monitoring of queue depth
  - Dropped metric tracking

- **Security Enhancements**
  - Complete security documentation
  - AWS Secrets Manager integration guide
  - HashiCorp Vault integration guide
  - Kubernetes External Secrets examples

- **Comprehensive Documentation**
  - `docs/PRODUCTION_GUIDE.md` - Complete production usage guide
  - `docs/API_STABILITY.md` - API stability guarantees
  - `docs/PERFORMANCE.md` - Performance tuning guide
  - `PRODUCTION_READINESS_REVIEW.md` - Production readiness review

### Changed

- Version bumped to 1.0.0 (production stable)
- Development Status classifier → "5 - Production/Stable"
- All dependencies now have upper bounds for predictability
- Improved thread safety in all singleton patterns

### Security

- All dependencies bounded to prevent unexpected breaking changes
- Security scanning tools available via `obskit[security]`
- Comprehensive PII redaction documentation

### Documentation

- Complete production deployment checklist (all items ✅)
- Kubernetes manifests with security best practices
- Prometheus alerting rules for obskit self-metrics
- Grafana dashboard examples

---

## [0.1.0] - 2024-01-15

### Added

- Initial release
- **Metrics**
  - RED Method (Rate, Errors, Duration)
  - Golden Signals (Latency, Traffic, Errors, Saturation)
  - USE Method (Utilization, Saturation, Errors)
  - Async metric recording
  - Tenant-aware metrics
  - Metrics sampling
- **Logging**
  - Structured logging with structlog
  - JSON and console formats
  - Correlation ID propagation
  - PII redaction
  - Dynamic log level adjustment
- **Tracing**
  - OpenTelemetry integration
  - OTLP export
  - W3C Trace Context propagation
  - Trace sampling
- **Health Checks**
  - Liveness probes
  - Readiness probes
  - Kubernetes-compatible endpoints
- **Resilience**
  - Circuit breaker pattern
  - Distributed circuit breaker (Redis) - Beta
  - Retry with exponential backoff
  - Rate limiting (token bucket, sliding window)
- **SLO**
  - SLO tracking - Beta
  - Error budget calculation
  - Prometheus alerting rules generation
- **Middleware**
  - FastAPI integration
  - Flask integration
  - Django integration
  - Automatic request tracking
- **Security**
  - Metrics endpoint authentication
  - PII redaction

### Fixed

- Thread safety in global singletons
- Metrics HTTP server lifecycle management
- Trace context propagation in async code

### Security

- PII redaction support
- Metrics endpoint authentication option
- Sensitive data filtering in traces
