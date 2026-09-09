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
from subscriptions.models import SubscriptionStatus
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
        self.assertEqual(resp.data['collected_rent']['total'], '0')

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
        self.assertEqual(resp.data['collected_rent']['total'], '50000')

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
        self.assertEqual(resp.data['collected_rent']['total'], '50000')

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
        self.assertEqual(resp.data['collected_rent']['total'], '100000')

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
        self.assertEqual(resp.data['collected_rent']['total'], '100000')


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
        self.assertIn('COLLECTED RENT', content)
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
        self.assertEqual(resp.data['collected_rent']['total'], '0')

    def test_landlord_b_sees_only_own_data(self):
        schedule_a = make_rent_schedule(self.lease_a, TODAY)
        make_payment(self.lease_a, schedule_a, Decimal('100000'), PaymentStatus.PAID)
        resp = self.client.get('/api/v1/dashboard/landlord/', **auth(self.landlord_b))
        self.assertEqual(resp.data['properties']['total'], 1)
        self.assertEqual(resp.data['collected_rent']['total'], '0')


# ===========================================================================
# Phase 10B — Enhanced Admin Analytics Tests
# ===========================================================================

class AdminUserStatusTest(TestCase):
    """User status breakdown in admin dashboard."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        self.headers = auth(self.admin)

    def test_user_status_counts(self):
        """Active and suspended landlords/tenants are counted."""
        l1 = make_landlord('l1@example.com')
        l2 = make_landlord('l2@example.com')
        l2.status = 'SUSPENDED'
        l2.save(update_fields=['status'])
        t1 = make_tenant('t1@example.com')
        t2 = make_tenant('t2@example.com')
        t2.status = 'SUSPENDED'
        t2.save(update_fields=['status'])

        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        users = resp.data['users']
        self.assertEqual(users['landlords'], 2)
        self.assertEqual(users['active_landlords'], 1)
        self.assertEqual(users['suspended_landlords'], 1)
        self.assertEqual(users['tenants'], 2)
        self.assertEqual(users['active_tenants'], 1)
        self.assertEqual(users['suspended_tenants'], 1)

    def test_empty_user_counts(self):
        """Zero users yields zero counts."""
        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        users = resp.data['users']
        self.assertEqual(users['total'], 1)  # just the admin
        self.assertEqual(users['landlords'], 0)
        self.assertEqual(users['tenants'], 0)
        self.assertEqual(users['active_landlords'], 0)
        self.assertEqual(users['suspended_landlords'], 0)
        self.assertEqual(users['active_tenants'], 0)
        self.assertEqual(users['suspended_tenants'], 0)


class AdminUnitOccupancyTest(TestCase):
    """Unit occupancy breakdown in admin dashboard."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        self.landlord = make_landlord()
        self.headers = auth(self.admin)

    def test_occupancy_breakdown(self):
        """Occupied, vacant, and occupancy rate."""
        prop, unit = make_property(self.landlord)
        unit2 = Unit.objects.create(property=prop, name='Unit B')
        unit.set_status(UnitStatus.OCCUPIED)

        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        units = resp.data['units']
        self.assertEqual(units['total'], 2)
        self.assertEqual(units['occupied'], 1)
        self.assertEqual(units['vacant'], 1)
        self.assertEqual(units['occupancy_rate'], 50.0)

    def test_zero_units(self):
        """No units yields 0% occupancy."""
        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        units = resp.data['units']
        self.assertEqual(units['total'], 0)
        self.assertEqual(units['occupied'], 0)
        self.assertEqual(units['vacant'], 0)
        self.assertEqual(units['occupancy_rate'], 0)

    def test_all_occupied(self):
        """All occupied yields 100% occupancy."""
        prop, unit = make_property(self.landlord)
        unit.set_status(UnitStatus.OCCUPIED)
        unit2 = Unit.objects.create(property=prop, name='Unit B')
        unit2.set_status(UnitStatus.OCCUPIED)

        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        self.assertEqual(resp.data['units']['occupancy_rate'], 100.0)


class AdminLeaseStatusTest(TestCase):
    """Lease status breakdown in admin dashboard."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        self.landlord = make_landlord()
        self.tenant = make_tenant()
        self.headers = auth(self.admin)

    def test_lease_status_counts(self):
        """Active, expired, terminated leases counted."""
        prop, unit = make_property(self.landlord)
        make_lease(self.landlord, self.tenant, prop, unit, status=LeaseStatus.ACTIVE)
        tenant2 = make_tenant('t2@example.com')
        unit2 = Unit.objects.create(property=prop, name='Unit B')
        make_lease(
            self.landlord, tenant2, prop, unit2,
            start_date=TODAY - timedelta(days=400),
            expiry_date=TODAY - timedelta(days=1),
            status=LeaseStatus.EXPIRED,
        )
        tenant3 = make_tenant('t3@example.com')
        unit3 = Unit.objects.create(property=prop, name='Unit C')
        make_lease(
            self.landlord, tenant3, prop, unit3,
            status=LeaseStatus.TERMINATED,
            terminated_at=timezone.now(),
        )

        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        leases = resp.data['leases']
        self.assertEqual(leases['total'], 3)
        self.assertEqual(leases['active'], 1)
        self.assertEqual(leases['expired'], 1)
        self.assertEqual(leases['terminated'], 1)

    def test_empty_leases(self):
        """Zero leases."""
        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        leases = resp.data['leases']
        self.assertEqual(leases['total'], 0)
        self.assertEqual(leases['active'], 0)
        self.assertEqual(leases['expired'], 0)
        self.assertEqual(leases['terminated'], 0)


class AdminRevenueTest(TestCase):
    """Revenue with period comparison."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        self.landlord = make_landlord()
        self.tenant = make_tenant()
        self.headers = auth(self.admin)

    def test_total_revenue(self):
        """All-time revenue includes all PAID payments."""
        prop, unit = make_property(self.landlord)
        lease = make_lease(self.landlord, self.tenant, prop, unit)
        schedule = make_rent_schedule(lease, TODAY)
        make_payment(lease, schedule, Decimal('100000'), PaymentStatus.PAID)
        make_payment(lease, schedule, Decimal('50000'), PaymentStatus.PAID)

        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        self.assertEqual(resp.data['collected_rent']['total'], '150000')
        self.assertEqual(resp.data['collected_rent']['payment_count'], 2)

    def test_only_paid_payments_count(self):
        """PENDING/CANCELLED/FAILED payments excluded."""
        prop, unit = make_property(self.landlord)
        lease = make_lease(self.landlord, self.tenant, prop, unit)
        schedule = make_rent_schedule(lease, TODAY)
        make_payment(lease, schedule, Decimal('100000'), PaymentStatus.PAID)
        make_payment(lease, schedule, Decimal('50000'), PaymentStatus.PENDING)
        make_payment(lease, schedule, Decimal('30000'), PaymentStatus.CANCELLED)
        make_payment(lease, schedule, Decimal('20000'), PaymentStatus.FAILED)

        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        self.assertEqual(resp.data['collected_rent']['total'], '100000')
        self.assertEqual(resp.data['collected_rent']['payment_count'], 1)

    def test_period_revenue(self):
        """Date-filtered revenue."""
        prop, unit = make_property(self.landlord)
        lease = make_lease(self.landlord, self.tenant, prop, unit)
        schedule = make_rent_schedule(lease, TODAY)
        make_payment(lease, schedule, Decimal('100000'), PaymentStatus.PAID)

        resp = self.client.get(
            f'/api/v1/dashboard/admin/?start_date={TODAY}&end_date={TODAY}',
            **self.headers,
        )
        self.assertEqual(resp.data['collected_rent']['period_total'], '100000')
        self.assertEqual(resp.data['collected_rent']['period_payments'], 1)


class AdminOutstandingRentTest(TestCase):
    """Outstanding and overdue rent calculations."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        self.landlord = make_landlord()
        self.tenant = make_tenant()
        self.headers = auth(self.admin)

    def test_outstanding_rent(self):
        """Unpaid past-due periods are outstanding."""
        prop, unit = make_property(self.landlord)
        lease = make_lease(self.landlord, self.tenant, prop, unit)
        due = TODAY - timedelta(days=7)
        schedule = make_rent_schedule(lease, due)

        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        self.assertEqual(resp.data['outstanding_rent']['period_count'], 1)
        self.assertEqual(resp.data['outstanding_rent']['total'], '100000.00')

    def test_overdue_rent(self):
        """Past-due periods with no payment are overdue."""
        prop, unit = make_property(self.landlord)
        lease = make_lease(self.landlord, self.tenant, prop, unit)
        due = TODAY - timedelta(days=7)
        schedule = make_rent_schedule(lease, due)

        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        self.assertEqual(resp.data['overdue_rent']['period_count'], 1)
        self.assertEqual(resp.data['overdue_rent']['total'], '100000.00')

    def test_partially_paid_is_outstanding_not_overdue(self):
        """Partially paid period is outstanding but not overdue."""
        prop, unit = make_property(self.landlord)
        lease = make_lease(self.landlord, self.tenant, prop, unit)
        due = TODAY - timedelta(days=7)
        schedule = make_rent_schedule(lease, due)
        make_payment(lease, schedule, Decimal('50000'), PaymentStatus.PAID)

        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        self.assertEqual(resp.data['outstanding_rent']['period_count'], 1)
        self.assertEqual(resp.data['outstanding_rent']['total'], '50000.00')
        self.assertEqual(resp.data['overdue_rent']['period_count'], 0)
        self.assertEqual(resp.data['overdue_rent']['total'], '0')

    def test_fully_paid_period_not_outstanding(self):
        """Fully paid past-due period is not outstanding."""
        prop, unit = make_property(self.landlord)
        lease = make_lease(self.landlord, self.tenant, prop, unit)
        due = TODAY - timedelta(days=7)
        schedule = make_rent_schedule(lease, due)
        make_payment(lease, schedule, Decimal('100000'), PaymentStatus.PAID)

        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        self.assertEqual(resp.data['outstanding_rent']['period_count'], 0)
        self.assertEqual(resp.data['outstanding_rent']['total'], '0')
        self.assertEqual(resp.data['overdue_rent']['period_count'], 0)
        self.assertEqual(resp.data['overdue_rent']['total'], '0')


class AdminSubscriptionTest(TestCase):
    """Subscription plan tier breakdown."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        self.headers = auth(self.admin)

    def test_plan_tier_breakdown(self):
        """Free, Professional, Business subscriptions counted."""
        from subscriptions.models import Plan, PlanTier

        l1 = make_landlord('l1@example.com')
        l2 = make_landlord('l2@example.com')
        l3 = make_landlord('l3@example.com')

        # l1 has FREE (default from ensure_landlord_subscription)
        # Change l2 to PROFESSIONAL
        pro_plan, _ = Plan.objects.get_or_create(
            tier=PlanTier.PROFESSIONAL,
            defaults={'name': 'Professional', 'max_active_tenants': 20, 'max_properties': 10, 'price_ngn': 15000},
        )
        l2.subscription.plan = pro_plan
        l2.subscription.status = SubscriptionStatus.ACTIVE
        l2.subscription.save(update_fields=['plan', 'status', 'updated_at'])

        # Change l3 to BUSINESS
        biz_plan, _ = Plan.objects.get_or_create(
            tier=PlanTier.BUSINESS,
            defaults={'name': 'Business', 'max_active_tenants': 100, 'max_properties': 50, 'price_ngn': 50000},
        )
        l3.subscription.plan = biz_plan
        l3.subscription.status = SubscriptionStatus.ACTIVE
        l3.subscription.save(update_fields=['plan', 'status', 'updated_at'])

        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        subs = resp.data['subscriptions']
        self.assertEqual(subs['free'], 1)
        self.assertEqual(subs['professional'], 1)
        self.assertEqual(subs['business'], 1)
        self.assertEqual(subs['total'], 3)

    def test_subscription_status_counts(self):
        """Trial, active, cancelled, past_due, expired."""
        from subscriptions.models import Plan, PlanTier

        l1 = make_landlord('l1@example.com')
        l2 = make_landlord('l2@example.com')
        l3 = make_landlord('l3@example.com')

        # l1 = trial (default)
        # l2 = active
        l2.subscription.status = SubscriptionStatus.ACTIVE
        l2.subscription.save(update_fields=['status', 'updated_at'])
        # l3 = cancelled
        l3.subscription.status = SubscriptionStatus.CANCELLED
        l3.subscription.cancelled_at = timezone.now()
        l3.subscription.save(update_fields=['status', 'cancelled_at', 'updated_at'])

        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        subs = resp.data['subscriptions']
        self.assertEqual(subs['trial'], 1)
        self.assertEqual(subs['active'], 2)  # TRIAL + ACTIVE
        self.assertEqual(subs['cancelled'], 1)
        self.assertEqual(subs['total'], 3)


class AdminGrowthTrendsTest(TestCase):
    """Growth trend data in admin dashboard."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        self.landlord = make_landlord()
        self.headers = auth(self.admin)

    def test_growth_trends_structure(self):
        """Growth trends returns monthly data for all entities."""
        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        trends = resp.data['growth_trends']
        self.assertIn('landlords', trends)
        self.assertIn('tenants', trends)
        self.assertIn('properties', trends)
        self.assertIn('units', trends)
        self.assertIn('leases', trends)
        self.assertIn('payments', trends)
        self.assertIn('subscriptions', trends)

    def test_growth_trends_with_data(self):
        """Growth trends reflect actual creation dates."""
        # Create a property and unit
        prop, unit = make_property(self.landlord)

        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        trends = resp.data['growth_trends']
        # There should be at least one month with property creation
        self.assertGreater(len(trends['properties']), 0)
        # The month should match today
        current_month = TODAY.strftime('%Y-%m')
        property_counts = [t['count'] for t in trends['properties'] if t['month'] == current_month]
        self.assertEqual(len(property_counts), 1)
        self.assertEqual(property_counts[0], 1)


class AdminEmptyStateTest(TestCase):
    """Admin dashboard with no data at all."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        self.headers = auth(self.admin)

    def test_empty_dashboard(self):
        """All KPIs return zero/empty when only admin exists."""
        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        users = resp.data['users']
        self.assertEqual(users['landlords'], 0)
        self.assertEqual(users['tenants'], 0)
        self.assertEqual(users['active_landlords'], 0)
        self.assertEqual(users['suspended_landlords'], 0)

        units = resp.data['units']
        self.assertEqual(units['total'], 0)
        self.assertEqual(units['occupancy_rate'], 0)

        leases = resp.data['leases']
        self.assertEqual(leases['total'], 0)
        self.assertEqual(leases['active'], 0)

        revenue = resp.data['collected_rent']
        self.assertEqual(revenue['total'], '0')
        self.assertEqual(revenue['payment_count'], 0)

        outstanding = resp.data['outstanding_rent']
        self.assertEqual(outstanding['total'], '0')
        self.assertEqual(outstanding['period_count'], 0)

        overdue = resp.data['overdue_rent']
        self.assertEqual(overdue['total'], '0')
        self.assertEqual(overdue['period_count'], 0)

    def test_empty_growth_trends(self):
        """Growth trends are empty lists with no data."""
        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        trends = resp.data['growth_trends']
        for key in ('landlords', 'tenants', 'properties', 'units', 'leases', 'payments', 'subscriptions'):
            self.assertIsInstance(trends[key], list)
            self.assertEqual(len(trends[key]), 0)


class AdminEdgeCasesTest(TestCase):
    """Edge cases for admin analytics."""

    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        self.landlord = make_landlord()
        self.tenant = make_tenant()
        self.headers = auth(self.admin)

    def test_cancelled_payments_not_in_revenue(self):
        """Cancelled payments don't count toward revenue."""
        prop, unit = make_property(self.landlord)
        lease = make_lease(self.landlord, self.tenant, prop, unit)
        schedule = make_rent_schedule(lease, TODAY)
        make_payment(lease, schedule, Decimal('100000'), PaymentStatus.CANCELLED)

        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        self.assertEqual(resp.data['collected_rent']['total'], '0')

    def test_future_leases_counted(self):
        """Future leases are counted in lease breakdown."""
        prop, unit = make_property(self.landlord)
        tenant2 = make_tenant('t2@example.com')
        make_lease(
            self.landlord, tenant2, prop, unit,
            start_date=TODAY + timedelta(days=30),
            expiry_date=TODAY + timedelta(days=395),
            status=LeaseStatus.FUTURE,
        )

        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        self.assertEqual(resp.data['leases']['future'], 1)
        self.assertEqual(resp.data['leases']['total'], 1)

    def test_multiple_landlords_isolated_in_admin(self):
        """Admin sees all landlords' data (platform-wide)."""
        l2 = make_landlord('l2@example.com')
        prop2, unit2 = make_property(l2, 'Other Property')

        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        self.assertEqual(resp.data['properties']['total'], 1)
        self.assertEqual(resp.data['users']['landlords'], 2)

    def test_backdated_lease(self):
        """Backdated lease doesn't affect analytics."""
        prop, unit = make_property(self.landlord)
        lease = make_lease(
            self.landlord, self.tenant, prop, unit,
            start_date=TODAY - timedelta(days=60),
            expiry_date=TODAY + timedelta(days=305),
            status=LeaseStatus.ACTIVE,
        )
        schedule = make_rent_schedule(lease, TODAY)
        make_payment(lease, schedule, Decimal('100000'), PaymentStatus.PAID)

        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        self.assertEqual(resp.data['leases']['active'], 1)
        self.assertEqual(resp.data['collected_rent']['total'], '100000')

    def test_zero_period_lease(self):
        """Lease with start == expiry (zero period) doesn't crash."""
        prop, unit = make_property(self.landlord)
        tenant2 = make_tenant('t2@example.com')
        lease = make_lease(
            self.landlord, tenant2, prop, unit,
            start_date=TODAY,
            expiry_date=TODAY,
            status=LeaseStatus.EXPIRED,
        )
        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        self.assertEqual(resp.data['leases']['expired'], 1)

    def test_occupancy_rate_uses_unit_status(self):
        """Occupancy is based on Unit.status, not lease existence."""
        prop, unit = make_property(self.landlord)
        # Unit is VACANT by default
        tenant2 = make_tenant('t2@example.com')
        lease = make_lease(self.landlord, tenant2, prop, unit)
        # Even with a lease, if unit status is VACANT, occupancy is 0
        resp = self.client.get('/api/v1/dashboard/admin/', **self.headers)
        self.assertEqual(resp.data['units']['occupied'], 0)
        self.assertEqual(resp.data['units']['occupancy_rate'], 0)
