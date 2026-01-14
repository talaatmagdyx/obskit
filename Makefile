.PHONY: test test-fast test-coverage test-watch help

# Default target
help:
	@echo "Available targets:"
	@echo "  make test          - Run all tests with coverage (slower, for CI)"
	@echo "  make test-fast     - Run tests without coverage (faster, for development)"
	@echo "  make test-coverage - Run tests with full coverage report"
	@echo "  make test-watch    - Run tests in watch mode (requires pytest-watch)"

# Full test suite with coverage (for CI)
test:
	python -m pytest tests/ --cov=src/obskit --cov-report=term-missing --cov-report=html -n auto --dist=worksteal -W ignore::pytest_benchmark.logger.PytestBenchmarkWarning

# Fast tests without coverage (for development)
# Use WORKERS=N to limit parallel workers (e.g., make test-fast WORKERS=4)
test-fast:
	python -m pytest tests/ -q -n $(or $(WORKERS),auto) --dist=worksteal --no-cov --tb=short -W ignore::pytest_benchmark.logger.PytestBenchmarkWarning -W ignore::pluggy.PluggyTeardownRaisedWarning

# Fast tests with progress (less quiet, shows which tests are running)
test-fast-progress:
	python -m pytest tests/ -n $(or $(WORKERS),auto) --dist=worksteal --no-cov --tb=short -W ignore::pytest_benchmark.logger.PytestBenchmarkWarning -W ignore::pluggy.PluggyTeardownRaisedWarning

# Show only failed tests with details (runs tests and shows summary)
test-failures:
	python -m pytest tests/ -n $(or $(WORKERS),auto) --dist=worksteal --no-cov --tb=line -W ignore::pytest_benchmark.logger.PytestBenchmarkWarning -W ignore::pluggy.PluggyTeardownRaisedWarning --maxfail=10 -q || true
	@echo ""
	@echo "💡 Run 'pytest tests/ -v --tb=short' to see detailed failure messages"

# Coverage report only
test-coverage:
	python -m pytest tests/ --cov=src/obskit --cov-report=term-missing --cov-report=html --cov-report=json:coverage.json

# Watch mode (requires: pip install pytest-watch)
test-watch:
	ptw tests/ -- -q --no-cov

# Run specific test file
test-file:
	python -m pytest $(FILE) -v

# Run specific test
test-single:
	python -m pytest $(TEST) -v

