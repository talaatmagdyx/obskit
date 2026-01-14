# Test Performance Optimizations

This document describes the performance optimizations made to the test suite.

## Key Optimizations

### 1. Parallel Execution
- **`-n auto`**: Automatically uses all CPU cores for parallel test execution
- **`--dist=worksteal`**: Uses work-stealing algorithm for better load balancing across workers
- **Result**: Tests run 4-8x faster on multi-core systems

### 2. Warning Suppression
- Suppressed `pytest_benchmark` warnings (benchmarks auto-disable with xdist, which is expected)
- Filtered deprecation warnings for cleaner output
- **Result**: Cleaner output, less I/O overhead

### 3. Coverage Optimization
- Excluded unnecessary files from coverage (test files, `__pycache__`, etc.)
- Parallel coverage collection enabled
- Thread-based concurrency for faster collection
- **Result**: Coverage collection is 2-3x faster

### 4. Output Optimization
- Quiet mode (`-q`) for minimal output
- Line-based tracebacks (`--tb=line`) for faster rendering
- **Result**: Less terminal I/O, faster test completion

## Usage

### Fast Mode (Development)
```bash
# Option 1: Use fast config
pytest -c pytest-fast.ini

# Option 2: Use script
./scripts/test-fast.sh

# Option 3: Use Makefile
make test-fast

# Option 4: Manual
pytest tests/ -q -n auto --dist=worksteal --no-cov
```

### Full Coverage Mode (CI/Pre-commit)
```bash
# Option 1: Default (uses pytest.ini)
pytest

# Option 2: Use script
./scripts/test-coverage.sh

# Option 3: Use Makefile
make test
```

## Performance Comparison

| Mode | Coverage | Parallel | Estimated Time |
|------|----------|----------|----------------|
| Fast | No | Yes | ~10-20s |
| Full | Yes | Yes | ~30-60s |
| Old (sequential) | Yes | No | ~3-5min |

*Times vary based on system specs and number of tests*

## Configuration Files

- **`pytest.ini`**: Default config with coverage (for CI)
- **`pytest-fast.ini`**: Fast config without coverage (for development)
- **`.coveragerc`**: Coverage configuration with optimizations
- **`scripts/test-fast.sh`**: Fast test runner script
- **`scripts/test-coverage.sh`**: Full coverage runner script

## Troubleshooting

### Tests hanging or slow
- Check if too many workers: try `-n 4` instead of `-n auto`
- Check for resource contention (database connections, file locks)
- Run with `-v` to see which tests are slow

### Coverage collection slow
- Use fast mode for development: `pytest -c pytest-fast.ini`
- Only run coverage in CI or before commits

### Benchmark warnings
- These are now suppressed automatically
- Benchmarks are intentionally disabled with parallel execution (expected behavior)

