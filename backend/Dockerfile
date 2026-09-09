# ============================================================
# Alquiler Backend — Production Dockerfile
# Multi-stage build for minimal image size.
# ============================================================

# --- Stage 1: Build dependencies ---
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Stage 2: Runtime ---
FROM python:3.11-slim AS runtime

# Install only runtime system dependencies (no compilers).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-built Python packages from the builder stage.
COPY --from=builder /install /usr/local

# Create a non-root user for the application.
RUN groupadd -r alquiler && useradd -r -g alquiler -d /app -s /sbin/nologin alquiler

WORKDIR /app

# Copy application code.
COPY . .

# Collect static files at build time (requires Django settings).
RUN DJANGO_SECRET_KEY=build-placeholder \
    DEBUG=False \
    DB_ENGINE=sqlite \
    python manage.py collectstatic --noinput 2>/dev/null || true

# Ensure the staticfiles directory exists even if collectstatic was skipped.
RUN mkdir -p staticfiles

# Switch to non-root user.
USER alquiler

EXPOSE 8000

# Default to gunicorn with config file. The CMD can be overridden by docker-compose.
CMD ["gunicorn", "config.wsgi:application", "-c", "gunicorn.conf.py"]
