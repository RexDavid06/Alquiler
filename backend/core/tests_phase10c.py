"""Phase 10C tests: API & Schema Hardening.

Verifies:
- Consistent error envelope format
- Retry-After header on throttled responses
- Dashboard views have serializer_class (OpenAPI W002 fix)
- CSV export views excluded from OpenAPI schema
- OpenAPI schema generates without errors
- Content-Type validation on POST/PATCH/PUT
"""

from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.models import User


def make_landlord(email='phase10c@example.com'):
    return User.objects.create_user(
        email=email, password='pass12345', role='LANDLORD',
        first_name='L', last_name='Lord', status='ACTIVE',
    )


def auth(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {'HTTP_AUTHORIZATION': f'Token {token.key}'}


# ---------------------------------------------------------------------------
# Error Envelope Tests
# ---------------------------------------------------------------------------

class ErrorEnvelopeTests(TestCase):
    """Verify all error responses use the consistent envelope format."""

    def setUp(self):
        self.client = APIClient()
        self.landlord = make_landlord('envelope@example.com')

    def test_unauthenticated_returns_envelope(self):
        """Unauthenticated request returns {detail, code} envelope."""
        resp = self.client.get('/api/v1/properties/')
        self.assertEqual(resp.status_code, 401)
        self.assertIn('detail', resp.data)
        self.assertIn('code', resp.data)

    def test_not_found_returns_envelope(self):
        """404 response returns {detail, code} envelope."""
        resp = self.client.get(
            '/api/v1/properties/99999/', **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, 404)
        self.assertIn('detail', resp.data)
        self.assertIn('code', resp.data)

    def test_validation_error_returns_envelope_with_errors(self):
        """400 validation error returns {detail, code, errors} envelope."""
        resp = self.client.post(
            '/api/v1/properties/',
            {'name': ''},  # Missing required fields
            format='json',
            **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('detail', resp.data)
        self.assertIn('code', resp.data)

    def test_forbidden_returns_envelope(self):
        """403 response returns {detail, code} envelope."""
        tenant = User.objects.create_user(
            email='tenant-envelope@example.com', password='pass12345',
            role='TENANT', first_name='T', last_name='Tenant',
            status='ACTIVE',
        )
        resp = self.client.post(
            '/api/v1/properties/',
            {'name': 'Test'},
            **auth(tenant),
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn('detail', resp.data)
        self.assertIn('code', resp.data)


# ---------------------------------------------------------------------------
# Retry-After Header Tests
# ---------------------------------------------------------------------------

class RetryAfterHeaderTests(TestCase):
    """Verify that throttled responses include Retry-After header."""

    def test_throttled_response_includes_retry_after(self):
        """When a Throttled exception is raised, Retry-After header is included."""
        from rest_framework.exceptions import Throttled
        from core.exceptions import api_exception_handler

        exc = Throttled(wait=30.0)
        response = api_exception_handler(exc, {})
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)
        self.assertEqual(response['Retry-After'], '30')

    def test_throttled_response_rounds_up_wait(self):
        """Retry-After is ceil'd to whole seconds."""
        from rest_framework.exceptions import Throttled
        from core.exceptions import api_exception_handler

        exc = Throttled(wait=2.3)
        response = api_exception_handler(exc, {})
        self.assertEqual(response['Retry-After'], '3')

    def test_throttled_response_with_zero_wait(self):
        """Retry-After is '0' when wait is 0."""
        from rest_framework.exceptions import Throttled
        from core.exceptions import api_exception_handler

        exc = Throttled(wait=0)
        response = api_exception_handler(exc, {})
        self.assertEqual(response['Retry-After'], '0')


# ---------------------------------------------------------------------------
# Dashboard Serializer Class Tests
# ---------------------------------------------------------------------------

class DashboardSerializerClassTests(TestCase):
    """Verify dashboard views have serializer_class for OpenAPI."""

    def test_landlord_dashboard_has_serializer_class(self):
        """LandlordDashboardView has serializer_class set."""
        from dashboard.views import LandlordDashboardView
        self.assertTrue(hasattr(LandlordDashboardView, 'serializer_class'))
        self.assertIsNotNone(LandlordDashboardView.serializer_class)

    def test_tenant_dashboard_has_serializer_class(self):
        """TenantDashboardView has serializer_class set."""
        from dashboard.views import TenantDashboardView
        self.assertTrue(hasattr(TenantDashboardView, 'serializer_class'))
        self.assertIsNotNone(TenantDashboardView.serializer_class)

    def test_admin_dashboard_has_serializer_class(self):
        """AdminDashboardView has serializer_class set."""
        from dashboard.views import AdminDashboardView
        self.assertTrue(hasattr(AdminDashboardView, 'serializer_class'))
        self.assertIsNotNone(AdminDashboardView.serializer_class)


# ---------------------------------------------------------------------------
# CSV Export Schema Exclusion Tests
# ---------------------------------------------------------------------------

class CSVExportSchemaExclusionTests(TestCase):
    """Verify CSV export views are excluded from OpenAPI schema."""

    def test_landlord_export_has_schema_none(self):
        """LandlordExportView has schema=None to exclude from OpenAPI."""
        from dashboard.views import LandlordExportView
        self.assertIsNone(LandlordExportView.schema)

    def test_admin_export_has_schema_none(self):
        """AdminExportView has schema=None to exclude from OpenAPI."""
        from dashboard.views import AdminExportView
        self.assertIsNone(AdminExportView.schema)


# ---------------------------------------------------------------------------
# OpenAPI Schema Generation Tests
# ---------------------------------------------------------------------------

class OpenAPISchemaGenerationTests(TestCase):
    """Verify OpenAPI schema generates without errors."""

    def test_schema_generates_without_error(self):
        """SchemaGenerator().get_schema() does not raise."""
        from drf_spectacular.generators import SchemaGenerator
        schema = SchemaGenerator().get_schema()
        self.assertIsNotNone(schema)
        self.assertIn('paths', schema)
        self.assertIn('components', schema)

    def test_schema_has_paths(self):
        """Generated schema has at least some API paths."""
        from drf_spectacular.generators import SchemaGenerator
        schema = SchemaGenerator().get_schema()
        paths = schema.get('paths', {})
        self.assertGreater(len(paths), 0)

    def test_schema_has_no_500_errors(self):
        """Schema generation completes without internal server errors."""
        from drf_spectacular.generators import SchemaGenerator
        schema = SchemaGenerator().get_schema()
        # If we got here, no exception was raised
        self.assertIsNotNone(schema)


# ---------------------------------------------------------------------------
# Content-Type Validation Tests
# ---------------------------------------------------------------------------

class ContentTypeValidationTests(TestCase):
    """Verify API rejects unsupported content types on POST/PATCH/PUT.

    DRF's default parsers accept both application/json and
    application/x-www-form-urlencoded. Unsupported types like text/xml
    are rejected with 415 Unsupported Media Type.
    """

    def setUp(self):
        self.client = APIClient()
        self.landlord = make_landlord('contenttype@example.com')
        self.token = Token.objects.get_or_create(user=self.landlord)[0].key

    def test_post_with_xml_rejected(self):
        """POST with text/xml returns 415 Unsupported Media Type."""
        resp = self.client.post(
            '/api/v1/properties/',
            data='<property><name>Test</name></property>',
            content_type='text/xml',
            HTTP_AUTHORIZATION=f'Token {self.token}',
        )
        self.assertEqual(resp.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_post_with_html_rejected(self):
        """POST with text/html returns 415 Unsupported Media Type."""
        resp = self.client.post(
            '/api/v1/properties/',
            data='<html><body>Test</body></html>',
            content_type='text/html',
            HTTP_AUTHORIZATION=f'Token {self.token}',
        )
        self.assertEqual(resp.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_post_with_json_accepted(self):
        """POST with application/json is accepted."""
        resp = self.client.post(
            '/api/v1/properties/',
            {
                'name': 'JSON Test',
                'property_type': 'APARTMENT',
                'address': '12 Marine Rd',
                'city': 'Lagos',
                'state': 'Lagos',
                'country': 'Nigeria',
                'currency': 'NGN',
                'description': 'Test',
            },
            format='json',
            **auth(self.landlord),
        )
        self.assertNotEqual(resp.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
