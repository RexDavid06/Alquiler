"""Phase 10C — Platform administration tests.

Covers: admin user listing, property listing, subscription listing,
operational issues, authorization (PLATFORM_ADMIN allowed, others denied),
search/filter/pagination, detail views, and financial immutability.
"""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.models import AccountStatus, Role, User
from leases.models import Lease, LeaseStatus, RentFrequency
from payments.models import Payment, PaymentStatus, RentSchedule
from properties.models import Property, PropertyStatus, Unit, UnitStatus
from subscriptions.models import Plan, PlanTier, Subscription, SubscriptionStatus
from subscriptions.services import ensure_landlord_subscription

TODAY = timezone.localdate()
BASE = '/api/v1/admin/'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(email='user@example.com', role='LANDLORD', **kwargs):
    return User.objects.create_user(
        email=email,
        password=kwargs.pop('password', 'pass12345'),
        role=role,
        first_name=kwargs.pop('first_name', 'Test'),
        last_name=kwargs.pop('last_name', 'User'),
        status=kwargs.pop('status', 'ACTIVE'),
        **kwargs,
    )


def auth(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {'HTTP_AUTHORIZATION': f'Token {token.key}'}


def make_landlord(email='landlord@example.com'):
    user = make_user(email=email, role='LANDLORD')
    ensure_landlord_subscription(user)
    return user


def make_tenant(email='tenant@example.com'):
    return make_user(email=email, role='TENANT')


def make_admin(email='admin@example.com'):
    return make_user(email=email, role='PLATFORM_ADMIN')


def make_property(landlord, name='Test Property'):
    prop = Property.objects.create(
        landlord=landlord, name=name, address='1 Test Rd',
    )
    unit = Unit.objects.create(property=prop, name='Unit A')
    return prop, unit


def make_lease(landlord, tenant, prop, unit, **overrides):
    defaults = {
        'start_date': TODAY,
        'expiry_date': TODAY + timedelta(days=365),
        'rent_amount': Decimal('100000.00'),
        'currency': 'NGN',
        'rent_frequency': RentFrequency.MONTHLY,
        'rent_due_day': 1,
        'status': LeaseStatus.ACTIVE,
    }
    defaults.update(overrides)
    return Lease.objects.create(
        landlord=landlord, tenant=tenant,
        property=prop, unit=unit, **defaults,
    )


def make_payment(landlord, tenant, lease, **overrides):
    defaults = {
        'amount': Decimal('100000.00'),
        'currency': 'NGN',
        'payment_date': TODAY,
        'payment_method': 'BANK_TRANSFER',
        'reference': 'TXN001',
        'status': PaymentStatus.PAID,
    }
    defaults.update(overrides)
    return Payment.objects.create(
        landlord=landlord, tenant=tenant, lease=lease, **defaults,
    )


# =====================================================================
# Admin User Tests
# =====================================================================

class AdminUserListTests(TestCase):
    """Test admin user listing endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        self.landlord = make_landlord()
        self.tenant = make_tenant()

    def test_platform_admin_can_list_users(self):
        res = self.client.get(BASE + 'users/', **auth(self.admin))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('results', res.data)
        self.assertGreaterEqual(res.data['count'], 3)

    def test_landlord_denied(self):
        res = self.client.get(BASE + 'users/', **auth(self.landlord))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_tenant_denied(self):
        res = self.client.get(BASE + 'users/', **auth(self.tenant))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_denied(self):
        res = self.client.get(BASE + 'users/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_search_by_email(self):
        res = self.client.get(BASE + 'users/', {'search': 'landlord'}, **auth(self.admin))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        emails = [u['email'] for u in res.data['results']]
        self.assertIn('landlord@example.com', emails)

    def test_filter_by_role(self):
        res = self.client.get(BASE + 'users/', {'role': 'TENANT'}, **auth(self.admin))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        roles = [u['role'] for u in res.data['results']]
        self.assertTrue(all(r == 'TENANT' for r in roles))

    def test_filter_by_status(self):
        suspended = make_user(email='suspended@example.com', status='SUSPENDED')
        res = self.client.get(BASE + 'users/', {'status': 'SUSPENDED'}, **auth(self.admin))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        statuses = [u['status'] for u in res.data['results']]
        self.assertTrue(all(s == 'SUSPENDED' for s in statuses))

    def test_pagination(self):
        res = self.client.get(BASE + 'users/', {'page': 1, 'page_size': 2}, **auth(self.admin))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(res.data['results']), 2)

    def test_user_detail(self):
        res = self.client.get(BASE + f'users/{self.landlord.id}/', **auth(self.admin))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['id'], self.landlord.id)
        self.assertIn('recent_leases', res.data)
        self.assertIn('recent_payments', res.data)

    def test_user_detail_includes_landlord_properties(self):
        make_property(self.landlord)
        res = self.client.get(BASE + f'users/{self.landlord.id}/', **auth(self.admin))
        self.assertEqual(res.data['property_count'], 1)

    def test_ordering(self):
        res = self.client.get(BASE + 'users/', {'ordering': 'email'}, **auth(self.admin))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        emails = [u['email'] for u in res.data['results']]
        self.assertEqual(emails, sorted(emails))


# =====================================================================
# Admin Property Tests
# =====================================================================

class AdminPropertyListTests(TestCase):
    """Test admin property listing endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        self.landlord = make_landlord()
        self.prop, self.unit = make_property(self.landlord)

    def test_platform_admin_can_list_properties(self):
        res = self.client.get(BASE + 'properties/', **auth(self.admin))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('results', res.data)
        self.assertGreaterEqual(res.data['count'], 1)

    def test_landlord_denied(self):
        res = self.client.get(BASE + 'properties/', **auth(self.landlord))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_denied(self):
        res = self.client.get(BASE + 'properties/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_search_by_name(self):
        res = self.client.get(BASE + 'properties/', {'search': 'Test'}, **auth(self.admin))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        names = [p['name'] for p in res.data['results']]
        self.assertIn('Test Property', names)

    def test_filter_by_type(self):
        res = self.client.get(BASE + 'properties/', {'property_type': 'APARTMENT'}, **auth(self.admin))
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_filter_by_status(self):
        res = self.client.get(BASE + 'properties/', {'status': 'ACTIVE'}, **auth(self.admin))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        statuses = [p['status'] for p in res.data['results']]
        self.assertTrue(all(s == 'ACTIVE' for s in statuses))

    def test_property_detail(self):
        res = self.client.get(BASE + f'properties/{self.prop.id}/', **auth(self.admin))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['id'], self.prop.id)
        self.assertIn('units', res.data)
        self.assertEqual(len(res.data['units']), 1)

    def test_unit_counts_annotated(self):
        res = self.client.get(BASE + 'properties/', **auth(self.admin))
        prop_data = res.data['results'][0]
        self.assertEqual(prop_data['unit_count'], 1)
        self.assertEqual(prop_data['vacant_units'], 1)
        self.assertEqual(prop_data['occupied_units'], 0)


# =====================================================================
# Admin Subscription Tests
# =====================================================================

class AdminSubscriptionListTests(TestCase):
    """Test admin subscription listing endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        self.landlord = make_landlord()

    def test_platform_admin_can_list_subscriptions(self):
        res = self.client.get(BASE + 'subscriptions/', **auth(self.admin))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('results', res.data)
        self.assertGreaterEqual(res.data['count'], 1)

    def test_landlord_denied(self):
        res = self.client.get(BASE + 'subscriptions/', **auth(self.landlord))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_denied(self):
        res = self.client.get(BASE + 'subscriptions/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_filter_by_plan(self):
        res = self.client.get(BASE + 'subscriptions/', {'plan': 'FREE'}, **auth(self.admin))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        tiers = [s['plan_tier'] for s in res.data['results']]
        self.assertTrue(all(t == 'FREE' for t in tiers))

    def test_filter_by_status(self):
        res = self.client.get(BASE + 'subscriptions/', {'status': 'TRIAL'}, **auth(self.admin))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        statuses = [s['status'] for s in res.data['results']]
        self.assertTrue(all(s == 'TRIAL' for s in statuses))

    def test_search_by_landlord_email(self):
        res = self.client.get(BASE + 'subscriptions/', {'search': 'landlord'}, **auth(self.admin))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(res.data['count'], 1)


# =====================================================================
# Admin Issues Tests
# =====================================================================

class AdminIssuesTests(TestCase):
    """Test admin operational issues endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        self.landlord = make_landlord()
        self.tenant = make_tenant()

    def test_platform_admin_can_get_issues(self):
        res = self.client.get(BASE + 'issues/', **auth(self.admin))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('count', res.data)
        self.assertIn('issues', res.data)

    def test_landlord_denied(self):
        res = self.client.get(BASE + 'issues/', **auth(self.landlord))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_denied(self):
        res = self.client.get(BASE + 'issues/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_detects_suspended_users(self):
        make_user(email='suspended@example.com', status='SUSPENDED')
        res = self.client.get(BASE + 'issues/', **auth(self.admin))
        issues = [i for i in res.data['issues'] if i['issue_type'] == 'suspended_user']
        self.assertGreaterEqual(len(issues), 1)

    def test_detects_overdue_rent(self):
        prop, unit = make_property(self.landlord)
        lease = make_lease(self.landlord, self.tenant, prop, unit)
        RentSchedule.objects.create(
            lease=lease,
            period_start=TODAY - timedelta(days=60),
            period_end=TODAY - timedelta(days=30),
            due_date=TODAY - timedelta(days=30),
            amount=lease.rent_amount,
            currency='NGN',
        )
        res = self.client.get(BASE + 'issues/', **auth(self.admin))
        issues = [i for i in res.data['issues'] if i['issue_type'] == 'overdue_rent']
        self.assertGreaterEqual(len(issues), 1)

    def test_detects_expired_leases(self):
        prop, unit = make_property(self.landlord)
        make_lease(
            self.landlord, self.tenant, prop, unit,
            start_date=TODAY - timedelta(days=400),
            expiry_date=TODAY - timedelta(days=30),
            status=LeaseStatus.ACTIVE,
        )
        res = self.client.get(BASE + 'issues/', **auth(self.admin))
        issues = [i for i in res.data['issues'] if i['issue_type'] == 'expired_lease']
        self.assertGreaterEqual(len(issues), 1)

    def test_detects_failed_payments(self):
        prop, unit = make_property(self.landlord)
        lease = make_lease(self.landlord, self.tenant, prop, unit)
        make_payment(self.landlord, self.tenant, lease, status=PaymentStatus.FAILED)
        res = self.client.get(BASE + 'issues/', **auth(self.admin))
        issues = [i for i in res.data['issues'] if i['issue_type'] == 'failed_payment']
        self.assertGreaterEqual(len(issues), 1)

    def test_detects_expired_subscriptions(self):
        self.landlord.subscription.status = SubscriptionStatus.EXPIRED
        self.landlord.subscription.save()
        res = self.client.get(BASE + 'issues/', **auth(self.admin))
        issues = [i for i in res.data['issues'] if i['issue_type'] == 'expired_subscription']
        self.assertGreaterEqual(len(issues), 1)

    def test_detects_past_due_subscriptions(self):
        self.landlord.subscription.status = SubscriptionStatus.PAST_DUE
        self.landlord.subscription.save()
        res = self.client.get(BASE + 'issues/', **auth(self.admin))
        issues = [i for i in res.data['issues'] if i['issue_type'] == 'past_due_subscription']
        self.assertGreaterEqual(len(issues), 1)


# =====================================================================
# Financial Immutability Tests
# =====================================================================

class FinancialImmutabilityTests(TestCase):
    """Verify that admin endpoints cannot modify financial records."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        self.landlord = make_landlord()
        self.tenant = make_tenant()
        self.prop, self.unit = make_property(self.landlord)
        self.lease = make_lease(self.landlord, self.tenant, self.prop, self.unit)
        self.payment = make_payment(self.landlord, self.tenant, self.lease)

    def test_admin_cannot_modify_payment_amount_via_lease_endpoint(self):
        """Admin lease update cannot change payment amounts — financial invariant."""
        res = self.client.patch(
            f'/api/v1/leases/{self.lease.id}/',
            {'rent_amount': '99999'},
            **auth(self.admin),
        )
        # Either 400 (rejected) or 200 but amount unchanged — domain service protects
        if res.status_code == status.HTTP_200_OK:
            self.lease.refresh_from_db()
            self.assertEqual(self.lease.rent_amount, Decimal('100000.00'))

    def test_read_only_admin_endpoints_reject_post(self):
        """Admin user/property/subscription endpoints are read-only — no POST."""
        endpoints = [
            BASE + 'users/',
            BASE + 'properties/',
            BASE + 'subscriptions/',
        ]
        for url in endpoints:
            res = self.client.post(url, {}, **auth(self.admin))
            self.assertIn(
                res.status_code,
                [status.HTTP_405_METHOD_NOT_ALLOWED, status.HTTP_400_BAD_REQUEST],
                f'POST {url} should be rejected',
            )

    def test_read_only_admin_endpoints_reject_delete(self):
        """Admin user/property/subscription endpoints are read-only — no DELETE."""
        endpoints = [
            BASE + 'users/1/',
            BASE + 'properties/1/',
            BASE + 'subscriptions/1/',
        ]
        for url in endpoints:
            res = self.client.delete(url, **auth(self.admin))
            self.assertIn(
                res.status_code,
                [status.HTTP_405_METHOD_NOT_ALLOWED, status.HTTP_404_NOT_FOUND],
                f'DELETE {url} should be rejected',
            )


# =====================================================================
# Authorization Security Tests
# =====================================================================

class AdminAuthorizationTests(TestCase):
    """Comprehensive authorization tests across all admin endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        self.landlord = make_landlord()
        self.tenant = make_tenant()

    def test_all_admin_endpoints_require_authentication(self):
        endpoints = [
            ('GET', BASE + 'users/'),
            ('GET', BASE + 'properties/'),
            ('GET', BASE + 'subscriptions/'),
            ('GET', BASE + 'issues/'),
        ]
        for method, url in endpoints:
            res = self.client.get(url)
            self.assertEqual(
                res.status_code, status.HTTP_401_UNAUTHORIZED,
                f'{method} {url} should require authentication',
            )

    def test_all_admin_endpoints_deny_landlord(self):
        endpoints = [
            BASE + 'users/',
            BASE + 'properties/',
            BASE + 'subscriptions/',
            BASE + 'issues/',
        ]
        for url in endpoints:
            res = self.client.get(url, **auth(self.landlord))
            self.assertEqual(
                res.status_code, status.HTTP_403_FORBIDDEN,
                f'Landlord should be denied access to {url}',
            )

    def test_all_admin_endpoints_deny_tenant(self):
        endpoints = [
            BASE + 'users/',
            BASE + 'properties/',
            BASE + 'subscriptions/',
            BASE + 'issues/',
        ]
        for url in endpoints:
            res = self.client.get(url, **auth(self.tenant))
            self.assertEqual(
                res.status_code, status.HTTP_403_FORBIDDEN,
                f'Tenant should be denied access to {url}',
            )

    def test_all_admin_endpoints_allow_admin(self):
        endpoints = [
            BASE + 'users/',
            BASE + 'properties/',
            BASE + 'subscriptions/',
            BASE + 'issues/',
        ]
        for url in endpoints:
            res = self.client.get(url, **auth(self.admin))
            self.assertEqual(
                res.status_code, status.HTTP_200_OK,
                f'Admin should be allowed access to {url}',
            )
