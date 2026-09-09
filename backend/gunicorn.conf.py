"""Gunicorn configuration for Alquiler production deployment.

Workers, timeout, and logging are configurable via environment variables.
Usage: gunicorn config.wsgi:application -c gunicorn.conf.py
"""

import os

# Server socket
bind = os.environ.get('GUNICORN_BIND', '0.0.0.0:8000')

# Worker processes — default to 2 * CPU_CORES + 1, or override via env var.
workers = int(os.environ.get('GUNICORN_WORKERS', '3'))
worker_class = os.environ.get('GUNICORN_WORKER_CLASS', 'sync')
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '120'))
graceful_timeout = int(os.environ.get('GUNICORN_GRACEFUL_TIMEOUT', '30'))
keepalive = int(os.environ.get('GUNICORN_KEEPALIVE', '5'))

# Logging
accesslog = os.environ.get('GUNICORN_ACCESS_LOG', '-')
errorlog = os.environ.get('GUNICORN_ERROR_LOG', '-')
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')

# Security
limit_request_line = int(os.environ.get('GUNICORN_LIMIT_REQUEST_LINE', '8190'))
limit_request_fields = int(os.environ.get('GUNICORN_LIMIT_REQUEST_FIELDS', '100'))
limit_request_field_size = int(os.environ.get('GUNICORN_LIMIT_REQUEST_FIELD_SIZE', '8190'))

# Preloading — loads the application before forking workers, saving memory.
preload_app = os.environ.get('GUNICORN_PRELOAD', 'false').lower() == 'true'
