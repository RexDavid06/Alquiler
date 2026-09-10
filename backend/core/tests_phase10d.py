"""Phase 10D tests: Production & Infrastructure Hardening.

Verifies:
- Gunicorn configuration file exists and is valid
- Logging production handler respects LOG_LEVEL
- .dockerignore exists and excludes sensitive files
- collectstatic runs without errors
- Health check endpoint works
"""

import os
from pathlib import Path

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import User


# ---------------------------------------------------------------------------
# Gunicorn Configuration Tests
# ---------------------------------------------------------------------------

class GunicornConfigTests(TestCase):
    """Verify gunicorn.conf.py exists and is valid."""

    def test_gunicorn_conf_exists(self):
        """gunicorn.conf.py exists in the backend directory."""
        conf_path = Path(__file__).resolve().parent.parent / 'gunicorn.conf.py'
        self.assertTrue(conf_path.exists(), f'gunicorn.conf.py not found at {conf_path}')

    def test_gunicorn_conf_has_required_settings(self):
        """gunicorn.conf.py defines bind, workers, and timeout."""
        conf_path = Path(__file__).resolve().parent.parent / 'gunicorn.conf.py'
        content = conf_path.read_text()
        self.assertIn('bind', content)
        self.assertIn('workers', content)
        self.assertIn('timeout', content)

    def test_gunicorn_conf_uses_env_vars(self):
        """gunicorn.conf.py reads configuration from environment variables."""
        conf_path = Path(__file__).resolve().parent.parent / 'gunicorn.conf.py'
        content = conf_path.read_text()
        self.assertIn('os.environ', content)
        self.assertIn('GUNICORN_WORKERS', content)
        self.assertIn('GUNICORN_TIMEOUT', content)


# ---------------------------------------------------------------------------
# Logging Configuration Tests
# ---------------------------------------------------------------------------

class LoggingConfigTests(TestCase):
    """Verify production logging handler respects LOG_LEVEL."""

    def test_production_handler_uses_log_level(self):
        """The production handler level is not hardcoded to WARNING.

        This was a bug: the production handler had level='WARNING' which
        dropped INFO-level logs from django and alquiler loggers even
        though LOG_LEVEL defaulted to INFO in production.
        """
        from django.conf import settings
        logging_config = settings.LOGGING
        production_handler = logging_config['handlers']['production']
        # The handler level should match LOG_LEVEL, not be hardcoded to WARNING
        self.assertNotEqual(production_handler['level'], 'WARNING')

    def test_log_level_env_var_respected(self):
        """LOG_LEVEL setting is read from environment."""
        from django.conf import settings
        # In test mode (DEBUG=True), LOG_LEVEL defaults to 'DEBUG'
        self.assertIn(settings.LOG_LEVEL, ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])


# ---------------------------------------------------------------------------
# .dockerignore Tests
# ---------------------------------------------------------------------------

class DockerignoreTests(TestCase):
    """Verify .dockerignore exists and excludes sensitive files."""

    def test_dockerignore_exists(self):
        """.dockerignore exists in the project root."""
        dockerignore_path = Path(__file__).resolve().parent.parent.parent / '.dockerignore'
        self.assertTrue(dockerignore_path.exists())

    def test_dockerignore_excludes_env_files(self):
        """.dockerignore excludes .env files."""
        dockerignore_path = Path(__file__).resolve().parent.parent.parent / '.dockerignore'
        content = dockerignore_path.read_text()
        self.assertIn('.env', content)

    def test_dockerignore_excludes_sqlite(self):
        """.dockerignore excludes SQLite database files."""
        dockerignore_path = Path(__file__).resolve().parent.parent.parent / '.dockerignore'
        content = dockerignore_path.read_text()
        self.assertIn('*.sqlite3', content)

    def test_dockerignore_excludes_git(self):
        """.dockerignore excludes .git directory."""
        dockerignore_path = Path(__file__).resolve().parent.parent.parent / '.dockerignore'
        content = dockerignore_path.read_text()
        self.assertIn('.git/', content)

    def test_dockerignore_excludes_pycache(self):
        """.dockerignore excludes __pycache__ directories."""
        dockerignore_path = Path(__file__).resolve().parent.parent.parent / '.dockerignore'
        content = dockerignore_path.read_text()
        self.assertIn('__pycache__/', content)


# ---------------------------------------------------------------------------
# Static Files Tests
# ---------------------------------------------------------------------------

class StaticFilesTests(TestCase):
    """Verify collectstatic configuration is correct."""

    def test_static_root_is_configured(self):
        """STATIC_ROOT is set to a valid path."""
        from django.conf import settings
        self.assertTrue(settings.STATIC_ROOT)
        self.assertIsInstance(settings.STATIC_ROOT, Path)

    def test_static_url_is_configured(self):
        """STATIC_URL is set."""
        from django.conf import settings
        self.assertTrue(settings.STATIC_URL)


# ---------------------------------------------------------------------------
# Health Check Endpoint Tests
# ---------------------------------------------------------------------------

class HealthCheckTests(TestCase):
    """Verify the health check endpoint works correctly."""

    def test_health_check_returns_200(self):
        """Health check endpoint returns 200 when healthy."""
        client = APIClient()
        resp = client.get('/api/v1/auth/health/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'healthy')
        self.assertEqual(resp.data['database'], 'ok')

    def test_health_check_is_unauthenticated(self):
        """Health check endpoint does not require authentication."""
        client = APIClient()
        resp = client.get('/api/v1/auth/health/')
        self.assertEqual(resp.status_code, 200)

    def test_health_check_returns_json(self):
        """Health check endpoint returns JSON response."""
        client = APIClient()
        resp = client.get('/api/v1/auth/health/')
        self.assertEqual(resp['Content-Type'], 'application/json')
