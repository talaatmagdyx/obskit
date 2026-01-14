# Contributing Guide

Thank you for considering contributing to obskit! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Git
- Docker (optional, for full testing)

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/talaatmagdyx/obskit.git
cd obskit

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e ".[all,dev,docs]"

# Install pre-commit hooks
pre-commit install
```

### Verify Setup

```bash
# Run tests
pytest tests/ -v

# Run linting
ruff check src/ tests/

# Run type checking
mypy src/obskit --strict

# Build documentation
cd docs && make html
```

## Code Style

### Python Style

We use **ruff** for linting and formatting:

```bash
# Check code
ruff check src/ tests/

# Fix auto-fixable issues
ruff check --fix src/ tests/

# Format code
ruff format src/ tests/
```

### Type Hints

All code must have type hints. We enforce `mypy --strict`:

```python
# Good
def process_request(
    endpoint: str,
    method: str,
    headers: dict[str, str] | None = None,
) -> Response:
    ...

# Bad
def process_request(endpoint, method, headers=None):
    ...
```

### Docstrings

Use Google-style docstrings:

```python
def track_request(
    self,
    endpoint: str,
    method: str,
    status: str = "success",
) -> None:
    """Track an HTTP request.
    
    Records rate, error, and duration metrics for the request.
    
    Args:
        endpoint: The request endpoint (e.g., "/api/users").
        method: HTTP method (GET, POST, etc.).
        status: Request outcome ("success" or "error").
    
    Returns:
        None
    
    Raises:
        ValueError: If endpoint is empty.
    
    Example:
        >>> metrics = get_red_metrics(service_name="api")
        >>> with metrics.track_request("/users", "GET"):
        ...     response = get_users()
    """
```

## Testing

### Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src/obskit --cov-report=html

# Specific test file
pytest tests/test_metrics.py -v

# Specific test
pytest tests/test_metrics.py::test_red_metrics -v

# Parallel execution
pytest tests/ -n auto
```

### Writing Tests

```python
import pytest
from obskit import get_red_metrics

class TestREDMetrics:
    """Tests for RED metrics functionality."""
    
    def test_track_request_success(self):
        """Test successful request tracking."""
        metrics = get_red_metrics(service_name="test")
        
        with metrics.track_request(endpoint="/api", method="GET"):
            pass  # Simulated work
        
        # Verify metrics were recorded
        # ...
    
    @pytest.mark.asyncio
    async def test_track_request_async(self):
        """Test async request tracking."""
        metrics = get_red_metrics(service_name="test")
        
        async with metrics.track_request_async(endpoint="/api", method="GET"):
            await asyncio.sleep(0.01)
```

### Test Coverage

We require **100% test coverage**:

```bash
# Check coverage
pytest tests/ --cov=src/obskit --cov-fail-under=100

# View detailed report
pytest tests/ --cov=src/obskit --cov-report=html
open htmlcov/index.html
```

## Pull Request Process

### 1. Create a Branch

```bash
git checkout -b feature/my-feature
# or
git checkout -b fix/bug-description
```

### 2. Make Changes

- Write code following our style guidelines
- Add tests for new functionality
- Update documentation if needed

### 3. Run Checks Locally

```bash
# Run full CI locally
./scripts/ci-local.sh

# Or individual checks
./scripts/lint.sh
./scripts/typecheck.sh
./scripts/test.sh
```

### 4. Commit

Use conventional commit messages:

```
feat: add tenant metrics support
fix: resolve circuit breaker race condition
docs: update installation guide
test: add retry edge case tests
refactor: simplify metrics registry
```

### 5. Push and Create PR

```bash
git push origin feature/my-feature
```

Then create a Pull Request on GitHub.

### PR Requirements

- [ ] All tests pass
- [ ] Code coverage ≥ 100%
- [ ] Type checking passes (mypy --strict)
- [ ] Linting passes (ruff)
- [ ] Documentation updated (if applicable)
- [ ] Changelog updated (if applicable)

## Documentation

### Building Docs

```bash
cd docs
make html
open _build/html/index.html
```

### Live Preview

```bash
cd docs
make livehtml
# Open http://localhost:8000
```

### Writing Docs

- Use Markdown (`.md`) for new pages
- Use reStructuredText (`.rst`) for API docs
- Add examples to all public functions
- Include diagrams where helpful

## Release Process

### Version Bumping

We use semantic versioning:

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

### Creating a Release

1. Update `CHANGELOG.md`
2. Update version in `pyproject.toml`
3. Create a git tag
4. Push to trigger release workflow

```bash
# Update version
# Edit pyproject.toml and CHANGELOG.md

# Commit
git add .
git commit -m "release: v0.2.0"

# Tag
git tag v0.2.0

# Push
git push origin main --tags
```

## Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open a GitHub Issue
- **Security**: Email talaatmagdy75@gmail.com

## Code of Conduct

Be respectful and constructive. We follow the [Contributor Covenant](https://www.contributor-covenant.org/).

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

