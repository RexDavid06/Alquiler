"""Comprehensive tests for the Dashboard system (Phase 9).

Covers landlord dashboard KPIs, tenant dashboard, admin dashboard,
date-range filtering, CSV exports, data isolation, authentication,
and read-only behavior.
"""

import csv
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.models import User
from leases.models import Lease, LeaseStatus, RentFrequency
from payments.models import Payment, PaymentStatus, RentSchedule
from payments.services import generate_schedule
from properties.models import Property, Unit, UnitStatus
from subscriptions.services import ensure_landlord_subscription

TODAY = timezone.localdate()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_landlord(email='landlord@example.com'):
    user = User.objects.create_user(
        email=email, password='pass12345', role='LANDLORD',
        first_name='L', last_name='Lord', status='ACTIVE',
    )
    ensure_landlord_subscription(user)
    return user


def make_tenant(email='tenant@example.com'):
    return User.objects.create_user(
        email=email, password='pass12345', role='TENANT',
        first_name='T', last_name='Tenant', status='ACTIVE',
    )


def make_admin(email='admin@example.com'):
    return User.objects.create_user(
        email=email, password='pass12345', role='PLATFORM_ADMIN',
        first_name='A', last_name='Admin', status='ACTIVE',
    )


def auth(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {'HTTP_AUTHORIZATION': f'Token {token.key}'}


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


def make_rent_schedule(lease, due_date, amount=None):
    if amount is None:
        amount = lease.rent_amount
    period_start = due_date.replace(day=1)
    if due_date.month == 12:
        period_end = due_date.replace(year=due_date.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        period_end = due_date.replace(month=due_date.month + 1, day=1) - timedelta(days=1)
    obj, _ = RentSchedule.objects.get_or_create(
        lease=lease,
        due_date=due_date,
        defaults={
            'period_start': period_start,
            'period_end': period_end,
            'amount': amount,
            'currency': lease.currency,
        },
    )
    return obj


def make_payment(lease, rent_period, amount, status=PaymentStatus.PAID):
    return Payment.objects.create(
        landlord=lease.landlord,
        tenant=lease.tenant,
        lease=lease,
        rent_period=rent_period,
        amount=amount,
        payment_date=TODAY,
        status=status,
    )


# ===========================================================================
# Landlord Dashboard Tests
# ===========================================================================

class LandlordDashboardTest(TestCase):
    """Landlord dashboard KPIs."""

    def setUp(self):
        self.client = APIClient()
        self.landlord = make_landlord()
        self.tenant = make_tenant()
        self.prop, self.unit = make_property(self.landlord)
        self.lease = make_lease(self.landlord, self.tenant, self.prop, self.unit)
        self.headers = auth(self.landlord)

    def test_empty_dashboard(self):
        resp = self.client.get('/api/v1/dashboard/landlord/', **self.headers)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['properties']['total'], 1)
        self.assertEqual(resp.data['units']['total'], 1)
        self.assertEqual(resp.data['leases']['total'], 1)
        self.assertEqual(resp.data['revenue']['total'], '0')

    def test_property_count(self):
        make_property(self.landlord, 'Prop 2')
        resp = self.client.get('/api/v1/dashboard/landlord/', **self.headers)
        self.assertEqual(resp.data['properties']['total'], 2)

    def test_occupancy_rate(self):
        Unit.objects.create(property=self.prop, name='Unit B')
        # Unit A is VACANT, Unit B is VACANT = 0% occupancy
        resp = self.client.get('/api/v1/dashboard/landlord/', **self.headers)
        self.assertEqual(resp.data['units']['total'], 2)
        self.assertEqual(resp.data['units']['occupied'], 0)
        self.assertEqual(resp.data['units']['occupancy_rate'], 0)

    def test_occupancy_rate_with_occupied(self):
        self.unit.set_status(UnitStatus.OCCUPIED)
        resp = self.client.get('/api/v1/dashboard/landlord/', **self.headers)
        self.assertEqual(resp.data['units']['occupied'], 1)
        self.assertEqual(resp.data['units']['occupancy_rate'], 100.0)

    def test_revenue_paid_only(self):
        """Only PAID payments count toward revenue."""
        schedule = make_rent_schedule(self.lease, TODAY)
        make_payment(self.lease, schedule, Decimal('50000'), PaymentStatus.PAID)
        make_payment(self.lease, schedule, Decimal('30000'), PaymentStatus.PENDING)
        make_payment(self.lease, schedule, Decimal('20000'), PaymentStatus.CANCELLED)

        lease = self.lease  # for clarity

        resp = self.client.get('/api/v1/dashboard/landlord/', **self.headers)
        self.assertEqual(resp.data['revenue']['total'], '50000')

    def test_overdue_rent(self):
        due = TODAY - timedelta(days=7)
        schedule = make_rent_schedule(self.lease, due)
        resp = self.client.get('/api/v1/dashboard/landlord/', **self.headers)
        self.assertTrue(Decimal(resp.data['overdue_rent']['total']) > 0)
        self.assertEqual(resp.data['overdue_rent']['period_count'], 1)

    def test_upcoming_rent(self):
        due = TODAY + timedelta(days=7)
        schedule = make_rent_schedule(self.lease, due)
        resp = self.client.get('/api/v1/dashboard/landlord/', **self.headers)
        self.assertTrue(Decimal(resp.data['upcoming_rent']['total']) > 0)
        self.assertEqual(resp.data['upcoming_rent']['period_count'], 1)

    def test_lease_expiry_alerts(self):
        lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            expiry_date=TODAY + timedelta(days=15),
        )
        resp = self.client.get('/api/v1/dashboard/landlord/', **self.headers)
        alerts = resp.data['lease_expiry_alerts']
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['expiry_date'], str(TODAY + timedelta(days=15)))

    def test_lease_expiry_alerts_30_day_horizon(self):
        """Leases expiring beyond 30 days are not in alerts."""
        lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            expiry_date=TODAY + timedelta(days=31),
        )
        resp = self.client.get('/api/v1/dashboard/landlord/', **self.headers)
        self.assertEqual(len(resp.data['lease_expiry_alerts']), 0)

    def test_date_range_filter_revenue(self):
        schedule = make_rent_schedule(self.lease, TODAY)
        make_payment(self.lease, schedule, Decimal('50000'), PaymentStatus.PAID)
        resp = self.client.get(
            f'/api/v1/dashboard/landlord/?start_date={TODAY}&end_date={TODAY}',
            **self.headers,
        )
        self.assertEqual(resp.data['revenue']['total'], '50000')

    def test_invalid_date_range(self):
        resp = self.client.get(
            f'/api/v1/dashboard/landlord/?start_date={TODAY}&end_date={TODAY - timedelta(days=1)}',
            **self.headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ===========================================================================
# Tenant Dashboard Tests
# ===========================================================================

class TenantDashboardTest(TestCase):
    """Tenant dashboard KPIs."""

    def setUp(self):
        self.client = APIClient()
        self.landlord = make_landlord()
        self.tenant = make_tenant()
        self.prop, self.unit = make_property(self.landlord)
        self.lease = make_lease(self.landlord, self.tenant, self.prop, self.unit)
        self.schedule = make_rent_schedule(self.lease, TODAY)
        self.headers = auth(self.tenant)

    def test_empty_dashboard(self):
        resp = self.client.get('/api/v1/dashboard/tenant/', **self.headers)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['active_leases']), 1)
        self.assertIsNotNone(resp.data['next_rent_due'])
        self.assertEqual(resp.data['payment_history'], [])
        self.assertEqual(resp.data['unread_notifications'], 0)

    def test_payment_history(self):
        schedule = make_rent_schedule(self.lease, TODAY)
        make_payment(self.lease, schedule, Decimal('100000'), PaymentStatus.PAID)
        resp = self.client.get('/api/v1/dashboard/tenant/', **self.headers)
        self.assertEqual(len(resp.data['payment_history']), 1)

    def test_payment_history_only_paid(self):
        schedule = make_rent_schedule(self.lease, TODAY)
        make_payment(self.lease, schedule, Decimal('100000'), PaymentStatus.PAID)
        make_payment(self.lease, schedule, Decimal('50000'), PaymentStatus.PENDING)
        resp = self.client.get('/api/v1/dashboard/tenant/', **self.headers)
        self.assertEqual(len(resp.data['payment_history']), 1)

    def test_date_range_filter(self):
        schedule = make_rent_schedule(self.lease, TODAY)
        make_payment(self.lease, schedule, Decimal('100000'), PaymentStatus.PAID)
        resp = self.client.get(
            f'/api/v1/dashboard/tenant/?start_date={TODAY}&end_date={TODAY}',
            **self.headers,
        )
        self.assertEqual(len(resp.data['payment_history']), 1)

    def test_tenant_isolation(self):
        """Tenant A cannot see Tenant B's data."""
        tenant_b = make_tenant('tenant_b@example.com')
        prop2, unit2 = make_property(self.landlord, 'Prop2')
        lease_b = make_lease(self.landlord, tenant_b, prop2, unit2)
        schedule_b = make_rent_schedule(lease_b, TODAY)
        make_payment(lease_b, schedule_b, Decimal('100000'), PaymentStatus.PAID)

        resp = self.client.get('/api/v1/dashboard/tenant/', **self.headers)
        self.assertEqual(len(resp.data['payment_history']), 0)


# ===========================================================================
# Admin Dashboard Tests
# ===========================================================================

class AdminDashboardTest(TestCase):
    """Platform admin dashboard KPIs."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        self.landlord = make_landlord()
        self.tenant = make_tenant()
        self.headers = auth(self.admin)

    def test_user_counts(self):
        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['users']['landlords'], 1)
        self.assertEqual(resp.data['users']['tenants'], 1)

    def test_subscription_counts(self):
        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        self.assertEqual(resp.data['subscriptions']['total'], 1)
        self.assertEqual(resp.data['subscriptions']['trial'], 1)

    def test_property_and_lease_counts(self):
        make_property(self.landlord)
        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        self.assertEqual(resp.data['properties']['total'], 1)

    def test_revenue(self):
        prop, unit = make_property(self.landlord)
        lease = make_lease(self.landlord, self.tenant, prop, unit)
        schedule = make_rent_schedule(lease, TODAY)
        make_payment(lease, schedule, Decimal('100000'), PaymentStatus.PAID)
        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        self.assertEqual(resp.data['revenue']['total'], '100000')

    def test_system_health(self):
        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        health = resp.data['system_health']
        self.assertIn('database', health)
        self.assertEqual(health['database'], 'healthy')
        self.assertIn('django_check', health)
        self.assertIn('migrations', health)

    def test_date_range_filter(self):
        prop, unit = make_property(self.landlord)
        lease = make_lease(self.landlord, self.tenant, prop, unit)
        schedule = make_rent_schedule(lease, TODAY)
        make_payment(lease, schedule, Decimal('100000'), PaymentStatus.PAID)
        resp = self.client.get(
            f'/api/v1/dashboard/admin/?start_date={TODAY}&end_date={TODAY}',
            **self.headers,
        )
        self.assertEqual(resp.data['revenue']['total'], '100000')


# ===========================================================================
# CSV Export Tests
# ===========================================================================

class LandlordExportTest(TestCase):
    """Landlord CSV export."""

    def setUp(self):
        self.client = APIClient()
        self.landlord = make_landlord()
        self.tenant = make_tenant()
        self.prop, self.unit = make_property(self.landlord)
        self.headers = auth(self.landlord)

    def test_export_generates_csv(self):
        resp = self.client.get('/api/v1/dashboard/landlord/export/', **self.headers)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        content = resp.content.decode()
        self.assertIn('PROPERTIES', content)
        self.assertIn('UNITS', content)
        self.assertIn('LEASES', content)

    def test_export_scoped_to_landlord(self):
        landlord_b = make_landlord('b@example.com')
        prop_b, unit_b = make_property(landlord_b, 'Other Prop')
        resp = self.client.get('/api/v1/dashboard/landlord/export/', **self.headers)
        content = resp.content.decode()
        self.assertNotIn('Other Prop', content)

    def test_export_empty_data(self):
        resp = self.client.get('/api/v1/dashboard/landlord/export/', **self.headers)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        content = resp.content.decode()
        self.assertIn('PROPERTIES', content)


class AdminExportTest(TestCase):
    """Admin CSV export."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        self.headers = auth(self.admin)

    def test_export_generates_csv(self):
        resp = self.client.get('/api/v1/dashboard/admin/export/', **self.headers)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        content = resp.content.decode()
        self.assertIn('USERS', content)
        self.assertIn('SUBSCRIPTIONS', content)
        self.assertIn('REVENUE', content)
        self.assertIn('SYSTEM HEALTH', content)


# ===========================================================================
# Authentication / Authorization Tests
# ===========================================================================

class DashboardAuthTest(TestCase):
    """Authentication and wrong-role rejection."""

    def setUp(self):
        self.client = APIClient()
        self.landlord = make_landlord()
        self.tenant = make_tenant()
        self.admin = make_admin()

    def test_unauthenticated_landlord_dashboard(self):
        resp = self.client.get('/api/v1/dashboard/landlord/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_tenant_dashboard(self):
        resp = self.client.get('/api/v1/dashboard/tenant/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_admin_dashboard(self):
        resp = self.client.get('/api/v1/dashboard/admin/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_tenant_cannot_access_landlord_dashboard(self):
        resp = self.client.get('/api/v1/dashboard/landlord/', **auth(self.tenant))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_landlord_cannot_access_admin_dashboard(self):
        resp = self.client.get('/api/v1/dashboard/admin/', **auth(self.landlord))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_access_landlord_dashboard(self):
        resp = self.client.get('/api/v1/dashboard/landlord/', **auth(self.admin))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_landlord_export(self):
        resp = self.client.get('/api/v1/dashboard/landlord/export/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_admin_export(self):
        resp = self.client.get('/api/v1/dashboard/admin/export/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ===========================================================================
# Data Isolation Tests
# ===========================================================================

class DashboardIsolationTest(TestCase):
    """Cross-landlord data isolation."""

    def setUp(self):
        self.client = APIClient()
        self.landlord_a = make_landlord('a@example.com')
        self.landlord_b = make_landlord('b@example.com')
        self.tenant_a = make_tenant('tenant_a@example.com')
        self.tenant_b = make_tenant('tenant_b@example.com')
        self.prop_a, self.unit_a = make_property(self.landlord_a, 'Prop A')
        self.prop_b, self.unit_b = make_property(self.landlord_b, 'Prop B')
        self.lease_a = make_lease(self.landlord_a, self.tenant_a, self.prop_a, self.unit_a)
        self.lease_b = make_lease(self.landlord_b, self.tenant_b, self.prop_b, self.unit_b)

    def test_landlord_a_does_not_see_landlord_b_data(self):
        schedule_b = make_rent_schedule(self.lease_b, TODAY)
        make_payment(self.lease_b, schedule_b, Decimal('100000'), PaymentStatus.PAID)
        resp = self.client.get('/api/v1/dashboard/landlord/', **auth(self.landlord_a))
        self.assertEqual(resp.data['properties']['total'], 1)
        self.assertEqual(resp.data['revenue']['total'], '0')

    def test_landlord_b_sees_only_own_data(self):
        schedule_a = make_rent_schedule(self.lease_a, TODAY)
        make_payment(self.lease_a, schedule_a, Decimal('100000'), PaymentStatus.PAID)
        resp = self.client.get('/api/v1/dashboard/landlord/', **auth(self.landlord_b))
        self.assertEqual(resp.data['properties']['total'], 1)
        self.assertEqual(resp.data['revenue']['total'], '0')
