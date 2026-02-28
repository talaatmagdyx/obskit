# Contributing to obskit

Thank you for considering a contribution to obskit!  This document covers everything
you need to know to develop, test, and submit a change.

---

## Development Setup

### Prerequisites

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/) (recommended) **or** pip
- Git

### Clone and install

```bash
git clone https://github.com/talaatmagdyx/obskit.git
cd obskit

# Option A — uv (recommended, fastest)
uv sync
pre-commit install

# Option B — pip editable installs
pip install -e "packages/obskit-core[dev]"
pip install -e "packages/obskit-logging[dev]"
pip install -e "packages/obskit-metrics[dev]"
pip install -e "packages/obskit-tracing[dev]"
pip install -e "packages/obskit-health[dev]"
pip install -e "packages/obskit-resilience[dev]"
pip install -e "packages/obskit-slo[dev]"
pip install -e "packages/obskit-decorators[dev]"
pip install -e "packages/obskit-db[dev]"
pip install -e "packages/obskit-queue[dev]"
pip install -e "packages/obskit-dashboards[dev]"
pip install -e "packages/obskit-middleware-fastapi[dev]"
pip install -e "packages/obskit-middleware-flask[dev]"
pip install -e "packages/obskit-middleware-django[dev]"
pip install -e "packages/obskit-middleware-grpc[dev]"
pip install pre-commit
pre-commit install
```

### Verify setup

```bash
python -m obskit.core.diagnose
```

All packages should show as installed and integrations should show as available.

---

## Project Structure

```
obskit/
├── packages/                    # One directory per installable package
│   ├── obskit-core/
│   │   ├── pyproject.toml       # Package metadata, deps, tool config
│   │   ├── README.md
│   │   ├── src/
│   │   │   └── obskit/
│   │   │       ├── config.py    # Public modules (no __init__.py at obskit/)
│   │   │       └── core/
│   │   │           └── ...
│   │   └── tests/
│   │       ├── conftest.py
│   │       └── unit/
│   └── ...
├── benchmarks/                  # Performance benchmarks
│   ├── bench_*.py               # pytest-benchmark microbenchmarks
│   ├── macro_runner.py          # End-to-end macro benchmarks
│   ├── bench_memory.py          # Memory profiling
│   ├── go_no_go.md              # Release gate thresholds
│   └── BENCHMARKING_STRATEGY.md
├── docs/                        # MkDocs documentation (you are here)
├── tests/
│   └── integration/             # Cross-package integration tests
├── .github/
│   └── workflows/               # CI/CD pipelines
├── mkdocs.yml
└── pyproject.toml               # uv workspace root + shared tool config
```

---

## Running Tests

### Single package

```bash
pytest packages/obskit-logging/tests -v
pytest packages/obskit-metrics/tests -v --cov=packages/obskit-metrics/src
```

### All packages

```bash
# With uv
uv run pytest packages/

# With pytest directly (after installing all packages)
pytest packages/ -v --tb=short
```

### Integration tests

```bash
pytest tests/integration/ -v
```

### With coverage

```bash
pytest packages/obskit-core/tests \
  --cov=packages/obskit-core/src \
  --cov-report=term-missing \
  --cov-fail-under=100
```

---

## Coverage Requirements

**All packages require 100% test coverage.**  A PR that drops coverage in any
package is blocked by CI.

The 100% requirement is enforced with `--cov-fail-under=100` in each package's
`pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "-v --cov=src/obskit --cov-report=term-missing --cov-fail-under=100"
```

When you add new code, add tests for every branch.  Use `# pragma: no cover` only
for code that is genuinely untestable (e.g., platform-specific paths on CI) and
document why.  See
[ADR-006](decisions/adr-006-coverage-pragma.md) for the full policy.

---

## Code Style

obskit uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting and
[mypy](https://mypy-lang.org/) for type checking.

```bash
# Format
ruff format packages/

# Lint (auto-fix safe issues)
ruff check packages/ --fix

# Type check
mypy packages/obskit-core/src
mypy packages/obskit-logging/src
# etc.
```

All of the above run automatically in the pre-commit hooks and CI.

### Style rules

- Maximum line length: 100 characters.
- All public APIs must have Google-style docstrings.
- All public APIs must have type annotations (mypy strict mode).
- Import order: stdlib → third-party → obskit packages (enforced by ruff/isort).
- No `TYPE_CHECKING` abuse — only for types that would cause circular imports.

---

## Pre-commit Hooks

Pre-commit runs automatically on `git commit`.  It applies the following checks:

| Hook | What it checks |
|---|---|
| `ruff-format` | Code formatting |
| `ruff` | Linting (E, W, F, I, B, UP, N, S rule sets) |
| `mypy` | Type checking (strict mode) |
| `trailing-whitespace` | No trailing spaces |
| `end-of-file-fixer` | Files end with a newline |
| `check-yaml` | Valid YAML syntax |
| `check-toml` | Valid TOML syntax |
| `detect-private-key` | No accidental private key commits |

To run pre-commit manually:

```bash
pre-commit run --all-files
```

---

## Adding a New Package

Follow these steps to add a new package (e.g., `obskit-cache`):

**1. Create the package directory structure**

```bash
mkdir -p packages/obskit-cache/src/obskit/cache
mkdir -p packages/obskit-cache/tests/unit/cache
touch packages/obskit-cache/src/obskit/cache/__init__.py
touch packages/obskit-cache/tests/__init__.py
touch packages/obskit-cache/tests/unit/__init__.py
touch packages/obskit-cache/tests/unit/cache/__init__.py
```

**2. Write `pyproject.toml`**

```toml
[project]
name = "obskit-cache"
version = "2.0.0"
description = "Cache instrumentation for the obskit observability toolkit"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
authors = [{ name = "Your Name", email = "you@example.com" }]
dependencies = ["obskit-core>=2.0.0,<3.0.0"]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0,<10.0.0",
    "pytest-asyncio>=0.23.0,<2.0.0",
    "pytest-cov>=4.1.0,<8.0.0",
    "mypy>=1.8.0,<2.0.0",
    "ruff>=0.3.0,<1.0.0",
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
namespaces = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-v --cov=src/obskit --cov-report=term-missing --cov-fail-under=100"
```

**3. Implement the package**

Write your code in `packages/obskit-cache/src/obskit/cache/`.  Add
`__all__` to `__init__.py`.

**4. Write tests**

Achieve 100% coverage from the start.

**5. Add the package to the meta-package**

Edit `packages/obskit/pyproject.toml` and add `obskit-cache` to `dependencies`.

**6. Add the package to `mkdocs.yml`**

Add an entry under the `Packages:` section.

**7. Write `README.md`**

A short README with installation and quick-start example.

**8. Write a `py.typed` marker**

```bash
touch packages/obskit-cache/src/obskit/cache/py.typed
```

This tells mypy and type checkers that the package ships type stubs.

---

## Pull Request Process

1. **Fork** the repository on GitHub.
2. **Create a branch** named `feat/short-description` or `fix/short-description`.
3. **Implement** the change with tests.
4. **Run** `pre-commit run --all-files` and `pytest packages/` locally.
5. **Open a PR** against `main`.
6. **Fill in** the PR template (summary, test plan, breaking changes).
7. **Request review** from a maintainer.

**PR requirements:**

- All CI checks must pass (lint, type check, tests, coverage).
- No coverage regression (any package touching `< 100%` fails CI).
- At least one maintainer approval.
- Changelog entry in `CHANGELOG.md` under the appropriate `[Unreleased]` section.

---

## ADR Process

An Architecture Decision Record (ADR) documents a significant technical decision
and the context behind it.  Write an ADR when:

- You are changing a dependency (e.g., switching from `loguru` to `structlog`).
- You are making a design choice that will be hard to reverse later.
- You are introducing a new pattern (e.g., how namespace packages are structured).
- A reviewer might reasonably ask "why did you do it this way?".

ADRs live in `docs/decisions/`.  Use the template:

```markdown
# ADR-NNN: Short title

**Date:** YYYY-MM-DD  
**Status:** Proposed | Accepted | Superseded by ADR-XXX

## Context
What problem are we solving?  What constraints exist?

## Decision
What did we decide?

## Consequences
What are the trade-offs?  What becomes easier / harder?
```

Reference the ADR in your PR description so reviewers can read the rationale.

---

## Releasing

obskit uses [release-please](https://github.com/google-github-actions/release-please-action)
for automated releases driven by [Conventional Commits](https://www.conventionalcommits.org/).

### Commit message convention

| Prefix | Version bump | Example |
|---|---|---|
| `feat:` | Minor (0.x+1) | `feat(metrics): add exemplar support` |
| `fix:` | Patch (0.0.x+1) | `fix(tracing): correct span status on timeout` |
| `perf:` | Patch | `perf(slo): reduce lock contention in record_measurement` |
| `docs:` | No bump | `docs(contributing): update ADR process` |
| `BREAKING CHANGE:` | Major (x+1) | Used in commit body for breaking changes |
| `feat!:` | Major | `feat!: remove experimental obskit.chaos module` |

### Release flow

1. Merge PR with conventional commits to `main`.
2. release-please opens a "Release PR" automatically — shows the changelog diff.
3. Maintainer reviews and merges the Release PR.
4. GitHub Actions builds wheels for all packages and publishes to PyPI.
5. A GitHub Release is created with the changelog.

---

## CI/CD Pipeline

| Workflow | Trigger | Steps |
|---|---|---|
| `ci.yml` | Push / PR | ruff lint → mypy → pytest (all packages) → coverage report |
| `docs.yml` | Push to main | mkdocs build → deploy to GitHub Pages |
| `release.yml` | Release PR merge | Build wheels → publish to PyPI → sign with sigstore |
| `security.yml` | Weekly | pip-audit → safety → bandit → detect-secrets |
| `mutation.yml` | Weekly | mutmut mutation testing on obskit-core |

### Local CI equivalent

```bash
# Matches what CI runs
pre-commit run --all-files
pytest packages/ --tb=short -q
python benchmarks/macro_runner.py --requests 1000 --workers 4
```
