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

# Option B — pip editable install
pip install -e ".[all]"
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
├── src/
│   └── obskit/              # Single package
│       ├── config.py        # ObskitSettings
│       ├── core/            # Context, diagnose, deprecation
│       ├── logging/         # Structured logging
│       ├── metrics/         # Prometheus metrics
│       ├── tracing/         # OpenTelemetry
│       ├── health/          # Health checks
│       ├── resilience/      # Circuit breaker, retry
│       ├── slo/             # SLO tracking
│       ├── middleware/      # Framework middlewares
│       └── testing/         # Test helpers
├── tests/
│   └── unit/                # All unit tests
├── benchmarks/              # Performance benchmarks
├── docs/                    # MkDocs documentation
├── .github/
│   └── workflows/           # CI/CD pipelines
├── mkdocs.yml
└── pyproject.toml           # Package metadata + tool config
```

---

## Running Tests

### Single module

```bash
pytest tests/unit/logging/ -v
pytest tests/unit/metrics/ -v --cov=src/obskit
```

### All tests

```bash
# With uv
uv run pytest tests/unit/

# With pytest directly (after installing all packages)
pytest tests/unit/ -v --tb=short
```

### Integration tests

```bash
pytest tests/integration/ -v
```

### With coverage

```bash
pytest tests/unit/ \
  --cov=src/obskit \
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
ruff format src/ tests/

# Lint (auto-fix safe issues)
ruff check src/ tests/ --fix

# Type check
mypy src/
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

## Adding New Functionality

Follow these steps to add a new module (e.g., `obskit.cache`):

**1. Create the module directory**

```bash
mkdir -p src/obskit/cache
touch src/obskit/cache/__init__.py
touch src/obskit/cache/py.typed
```

**2. Implement the module**

Write your code in `src/obskit/cache/`. Add `__all__` to `__init__.py`.

**3. Add tests**

```bash
mkdir -p tests/unit/cache
touch tests/unit/cache/__init__.py
```

Achieve 100% coverage from the start.

**4. Add to extras if it needs heavy dependencies**

Edit `pyproject.toml` and add a new entry to `[project.optional-dependencies]`:

```toml
cache = ["redis>=5.0.0,<8.0.0"]
```

Update the `all` extra to include it:

```toml
all = ["obskit[prometheus,otlp,...,cache]"]
```

**5. Update `mkdocs.yml`**

Add an entry under the appropriate section.

**6. Write a `py.typed` marker**

```bash
touch src/obskit/cache/py.typed
```

---

## Pull Request Process

1. **Fork** the repository on GitHub.
2. **Create a branch** named `feat/short-description` or `fix/short-description`.
3. **Implement** the change with tests.
4. **Run** `pre-commit run --all-files` and `pytest tests/unit/` locally.
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
| `mutation.yml` | Weekly | mutmut mutation testing on obskit |

### Local CI equivalent

```bash
# Matches what CI runs
pre-commit run --all-files
pytest tests/unit/ --tb=short -q
python benchmarks/macro_runner.py --requests 1000 --workers 4
```
