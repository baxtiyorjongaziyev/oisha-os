# --- Build Stage ---
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Final Production Stage ---
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    RUNNING_IN_CLOUD=True

WORKDIR /app

# Create unprivileged application user
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -m -s /bin/sh appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

# Copy application code with non-root ownership
COPY --chown=appuser:appuser . .

# Ensure entrypoint is executable
RUN sed -i 's/\r$//' scripts/entrypoint.sh \
    && chmod +x scripts/entrypoint.sh

# Run as non-root user
USER appuser

# Entrypoint handles app startup
ENTRYPOINT ["/bin/sh", "scripts/entrypoint.sh"]
