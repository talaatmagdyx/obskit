.PHONY: test test-fast test-coverage test-watch help lint typecheck docs

# Default target
help:
	@echo "Available targets:"
	@echo "  make test          - Run unit tests with coverage"
	@echo "  make test-fast     - Run unit tests without coverage"
	@echo "  make test-coverage - Run all tests with full coverage report"
	@echo "  make lint          - Run ruff linter"
	@echo "  make typecheck     - Run mypy type checker"
	@echo "  make docs          - Build MkDocs documentation"

# Unit tests with coverage
test:
	uv run pytest tests/unit/ \
		--cov=src/obskit \
		--cov-report=term-missing \
		-n auto --dist=worksteal \
		-W ignore::pytest_benchmark.logger.PytestBenchmarkWarning

# Fast unit tests without coverage
test-fast:
	uv run pytest tests/unit/ -q -n $(or $(WORKERS),auto) --dist=worksteal --no-cov \
		--tb=short \
		-W ignore::pytest_benchmark.logger.PytestBenchmarkWarning \
		-W ignore::pluggy.PluggyTeardownRaisedWarning

# Full coverage report
test-coverage:
	uv run pytest tests/unit/ \
		--cov=src/obskit \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-report=xml:coverage.xml \
		--cov-fail-under=100 \
		-n auto --dist=worksteal

# Show only failed tests
test-failures:
	uv run pytest tests/unit/ -n auto --dist=worksteal --no-cov --tb=line \
		-W ignore::pytest_benchmark.logger.PytestBenchmarkWarning \
		--maxfail=10 -q || true

# Run specific test file
test-file:
	uv run pytest $(FILE) -v

# Run specific test
test-single:
	uv run pytest $(TEST) -v

# Linting
lint:
	uv run ruff check src/ tests/ benchmarks/
	uv run ruff format --check src/ tests/

# Type checking
typecheck:
	uv run mypy src/

# Build documentation
docs:
	mkdocs build --strict

# Serve documentation locally
docs-serve:
	mkdocs serve
