# =============================================================================
# obskit Development Dockerfile
# Multi-stage build for development and testing
# =============================================================================

# -----------------------------------------------------------------------------
# Base stage: Python with common dependencies
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# -----------------------------------------------------------------------------
# Development stage: Full development environment
# -----------------------------------------------------------------------------
FROM base AS development

# Install all dependencies including dev and docs
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e ".[all,dev,docs]"

# Switch to non-root user
USER appuser

# Default command
CMD ["bash"]

# -----------------------------------------------------------------------------
# Test stage: For running tests
# -----------------------------------------------------------------------------
FROM base AS test

# Copy source and tests
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY tests/ ./tests/

# Install dependencies
RUN pip install --no-cache-dir -e ".[all,dev]"

# Switch to non-root user
USER appuser

# Run tests by default
CMD ["pytest", "tests/", "-v", "--cov=src/obskit", "--cov-report=term-missing"]

# -----------------------------------------------------------------------------
# Docs stage: For building documentation
# -----------------------------------------------------------------------------
FROM base AS docs

# Copy source and docs
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY docs/ ./docs/

# Install dependencies
RUN pip install --no-cache-dir -e ".[docs]"

# Expose port for live-reload server
EXPOSE 8000

# Switch to non-root user
USER appuser

# Build docs by default
CMD ["sphinx-build", "-b", "html", "docs/source", "docs/_build/html"]

# -----------------------------------------------------------------------------
# Production stage: Minimal image with just the package
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS production

WORKDIR /app

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Copy only what's needed
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

# Install package
RUN pip install --no-cache-dir ".[all]"

# Clean up
RUN pip cache purge

# Switch to non-root user
USER appuser

# No default command - this is a library
CMD ["python", "-c", "import obskit; print(f'obskit {obskit.__version__}')"]

