# Testing Performance Guide

## Quick Start

### Fast Testing (Development)
For quick feedback during development, use the fast configuration:

```bash
# Option 1: Use fast config
pytest -c pytest-fast.ini

# Option 2: Use Makefile
make test-fast

# Option 3: Manual fast command
pytest tests/ -q -n auto --no-cov
```

### Full Coverage Testing (CI/Pre-commit)
For complete coverage reports:

```bash
# Option 1: Use default config
pytest

# Option 2: Use Makefile
make test

# Option 3: Manual command
pytest tests/ --cov=src/obskit --cov-report=term-missing
```

## Performance Optimizations

### 1. Parallel Execution
Tests run in parallel using all CPU cores (`-n auto`). This is already configured.

### 2. Coverage Optimization
- Coverage collection is optimized via `.coveragerc`
- Excludes test files, `__pycache__`, and other non-source files
- Uses parallel coverage collection

### 3. Reduced Verbosity
- `-q` flag for quiet mode (less output = faster)
- `--tb=line` for shorter tracebacks

### 4. Fast Mode Options

**Skip slow tests:**
```bash
pytest -m "not slow"
```

**Run only unit tests:**
```bash
pytest -m unit
```

**Run specific test file:**
```bash
pytest tests/test_specific.py
```

**Run specific test:**
```bash
pytest tests/test_file.py::TestClass::test_method
```

## Performance Tips

1. **Use fast mode during development** - Skip coverage for faster feedback
2. **Run specific tests** - Don't run the entire suite when working on one feature
3. **Use test markers** - Mark slow tests and skip them during development
4. **Parallel execution** - Already enabled, but you can limit cores: `-n 4`
5. **Cache coverage** - Coverage data is cached between runs

## Coverage Reports

After running tests with coverage:

```bash
# View HTML report
open htmlcov/index.html

# View JSON report
cat coverage.json
```

## Troubleshooting

### Tests are still slow?
1. Check for slow tests: `pytest --durations=10`
2. Skip integration tests: `pytest -m "not integration"`
3. Use fewer workers: `pytest -n 2` (instead of auto)

### Coverage collection is slow?
1. Use fast mode: `pytest -c pytest-fast.ini`
2. Limit coverage scope: `--cov=src/obskit/specific/module`
3. Disable branch coverage in `.coveragerc`: `branch = False`

