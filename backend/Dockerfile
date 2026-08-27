# ---- Build Stage ----
FROM python:3.11-slim AS builder

# Install build dependencies only in build stage
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for accurate dependency resolution.
# Non-editable install: an -e install would leave a stale .pth pointing at
# /build in the runtime stage, where that path no longer exists.
COPY pyproject.toml ./
COPY app/ ./app/
RUN pip install --no-cache-dir uv && \
    uv pip install --system --prefix=/install .

# ---- Runtime Stage ----
FROM python:3.11-slim

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code.
# Host trees may carry restrictive modes (e.g. 600); normalize so the
# non-root runtime user can read every source file.
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
RUN chmod -R a+rX /app

# Create data directories with proper ownership
RUN mkdir -p uploads vectorstore && \
    chown -R appuser:appuser uploads vectorstore

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
