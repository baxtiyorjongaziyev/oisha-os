# --- Build Stage ---
FROM python:3.12-slim-bookworm AS builder

# Set build-time environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies into a separate directory
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Final Production Stage ---
FROM python:3.12-slim-bookworm

# Standard environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

# Create a non-root user for security
RUN groupadd -r oisha && useradd -r -g oisha oisha \
    && chown -R oisha:oisha /app

# Copy application code
COPY --chown=oisha:oisha . .

# Use the non-root user
USER oisha

# Healthcheck to ensure the bot is alive (optional, depends on implementation)
# HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
#   CMD pgrep -f "python userbot.py" || exit 1

CMD ["python", "userbot.py"]
