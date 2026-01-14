# Test Troubleshooting Guide

## Tests Seem Stuck or Slow

### Symptoms
- Tests appear to hang or progress very slowly
- "bringing up nodes..." message appears but tests don't complete
- Progress dots (`.`) appear but tests take a very long time

### Solutions

#### 1. Reduce Parallel Workers
Too many workers can cause resource contention. Try limiting workers:

```bash
# Limit to 4 workers
make test-fast WORKERS=4

# Or with script
WORKERS=4 ./scripts/test-fast.sh

# Or directly
pytest tests/ -n 4 --no-cov
```

#### 2. Use Verbose Mode to See Progress
See which tests are actually running:

```bash
# Verbose mode shows test names
./scripts/test-fast-verbose.sh

# Or
make test-fast-progress
```

#### 3. Run Tests Sequentially
If parallel execution is causing issues:

```bash
pytest tests/ --no-cov -v
```

#### 4. Check for Hanging Tests
Run with timeout to identify slow tests:

```bash
pytest tests/ --no-cov --durations=10 -v
```

This will show the 10 slowest tests at the end.

#### 5. Run Specific Test Files
If you know which file is slow:

```bash
pytest tests/test_specific_file.py -v
```

## Common Issues

### Issue: "bringing up nodes..." takes forever
**Cause**: Too many workers or system resource limits

**Solution**:
```bash
# Reduce workers
pytest tests/ -n 2 --no-cov
```

### Issue: Tests fail randomly in parallel
**Cause**: Test isolation issues or shared state

**Solution**:
1. Run sequentially to confirm: `pytest tests/ --no-cov`
2. Check for shared fixtures or global state
3. Use `--forked` if available (requires pytest-forked)

### Issue: Coverage collection is very slow
**Cause**: Coverage adds significant overhead

**Solution**:
- Use fast mode for development: `make test-fast`
- Only run coverage in CI or before commits: `make test-coverage`

### Issue: Benchmark warnings clutter output
**Status**: ✅ Fixed - warnings are now suppressed automatically

### Issue: "PluggyTeardownRaisedWarning: OSError: cannot send (already closed?)"
**Cause**: Known issue with pytest-xdist when workers close during teardown

**Status**: ✅ Fixed - warnings are now suppressed automatically

**Note**: This warning is harmless and doesn't affect test results. It occurs when pytest-xdist workers are closed during teardown, which is expected behavior.

## Performance Tips

1. **Use fast mode for development**: `make test-fast` (no coverage)
2. **Run coverage only when needed**: `make test-coverage`
3. **Limit workers if system is slow**: `WORKERS=2 make test-fast`
4. **Use verbose mode to debug**: `./scripts/test-fast-verbose.sh`

## Quick Reference

| Command | Speed | Coverage | Use Case |
|---------|-------|----------|----------|
| `make test-fast` | ⚡ Fastest | ❌ No | Development |
| `make test-fast WORKERS=4` | ⚡ Fast | ❌ No | Development (limited workers) |
| `make test-fast-progress` | ⚡ Fast | ❌ No | Debugging hangs |
| `make test` | 🐢 Slower | ✅ Yes | CI/Pre-commit |
| `pytest tests/ --no-cov` | ⚡ Fast | ❌ No | Sequential (no parallel) |

