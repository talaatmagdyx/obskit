.PHONY: test test-fast test-coverage test-watch help lint typecheck docs

# Default target
help:
	@echo "Available targets:"
	@echo "  make test          - Run integration tests with coverage"
	@echo "  make test-fast     - Run integration tests without coverage"
	@echo "  make test-coverage - Run all package tests with full coverage report"
	@echo "  make test-packages - Run all per-package unit tests"
	@echo "  make lint          - Run ruff linter"
	@echo "  make typecheck     - Run mypy type checker"
	@echo "  make docs          - Build MkDocs documentation"

# Integration tests with coverage
test:
	python -m pytest tests/ \
		--cov-config=.coveragerc \
		--cov-report=term-missing \
		-n auto --dist=worksteal \
		-W ignore::pytest_benchmark.logger.PytestBenchmarkWarning

# Fast integration tests without coverage
test-fast:
	python -m pytest tests/ -q -n $(or $(WORKERS),auto) --dist=worksteal --no-cov \
		--tb=short \
		-W ignore::pytest_benchmark.logger.PytestBenchmarkWarning \
		-W ignore::pluggy.PluggyTeardownRaisedWarning

# Run all per-package unit tests
test-packages:
	@for pkg in packages/obskit-core packages/obskit-logging packages/obskit-metrics \
		packages/obskit-tracing packages/obskit-health packages/obskit-resilience \
		packages/obskit-slo packages/obskit-decorators packages/obskit-db \
		packages/obskit-queue packages/obskit-dashboards \
		packages/obskit-middleware-fastapi packages/obskit-middleware-flask \
		packages/obskit-middleware-django packages/obskit-middleware-grpc \
		packages/obskit; do \
		echo "=== $$pkg ==="; \
		python -m pytest $$pkg/tests/ -q --tb=short || exit 1; \
	done

# Full coverage report across all packages
test-coverage:
	python -m pytest packages/ \
		--cov-config=.coveragerc \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-report=xml:coverage.xml \
		--cov-fail-under=100 \
		-n auto --dist=worksteal

# Show only failed tests
test-failures:
	python -m pytest tests/ -n auto --dist=worksteal --no-cov --tb=line \
		-W ignore::pytest_benchmark.logger.PytestBenchmarkWarning \
		--maxfail=10 -q || true

# Run specific test file
test-file:
	python -m pytest $(FILE) -v

# Run specific test
test-single:
	python -m pytest $(TEST) -v

# Linting
lint:
	ruff check packages/ tests/ benchmarks/
	ruff format --check packages/ tests/

# Type checking
typecheck:
	mypy packages/

# Build documentation
docs:
	mkdocs build --strict

# Serve documentation locally
docs-serve:
	mkdocs serve
