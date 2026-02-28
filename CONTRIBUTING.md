# Contributing to obskit

Thank you for your interest in contributing to obskit! This document provides guidelines and instructions for contributing.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/talaatmagdyx/obskit.git
cd obskit

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install development dependencies
pip install -e "packages/obskit-core" \
            -e "packages/obskit-logging" \
            -e "packages/obskit-metrics" \
            -e "packages/obskit-tracing" \
            -e "packages/obskit-health" \
            -e "packages/obskit-resilience" \
            -e "packages/obskit-slo" \
            -e "packages/obskit"

# Run tests
pytest packages/ tests/ -v

# Run linting
ruff check packages/ tests/
```

## Development Workflow

1. **Fork** the repository
2. **Create a branch** for your feature/fix
3. **Make changes** following our code style
4. **Write tests** for new functionality
5. **Run checks** locally
6. **Submit a PR**

## Code Style

- **Linting**: ruff
- **Type checking**: mypy --strict
- **Docstrings**: Google style
- **Test coverage**: 100%

## Running Checks

```bash
# All checks
./scripts/ci-local.sh

# Individual checks
./scripts/lint.sh
mypy packages/
./scripts/test.sh
```

## Commit Messages

Use conventional commits:

```
feat: add new feature
fix: fix a bug
docs: update documentation
test: add tests
refactor: code refactoring
```

## Pull Request Requirements

- [ ] All tests pass
- [ ] Coverage ≥ 100%
- [ ] Type checking passes
- [ ] Linting passes
- [ ] Documentation updated

## Getting Help

- **Questions**: GitHub Discussions
- **Bugs**: GitHub Issues
- **Security**: talaatmagdy75@gmail.com

## Full Guide

See the [Contributing Guide](https://talaatmagdyx.github.io/obskit/contributing/) for full details.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

