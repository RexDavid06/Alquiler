"""Comprehensive tests for the Rent & Payment Management API (Phase 5).

Covers rent status derivation, partial payments, overpayment, payment
status, lifecycle (create/retrieve/update/cancel), authorization,
data isolation, rent schedule filtering, rent frequencies, lease
boundaries, and payment-update edge cases.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.models import User
from leases.models import Lease, LeaseStatus, RentFrequency
from payments.models import Payment, PaymentStatus, RentSchedule
from payments.services import (
    generate_schedule,
    paid_amount,
    period_status,
    remaining_amount,
)
from properties.models import Property, PropertyType, Unit
from subscriptions.services import ensure_landlord_subscription

TODAY = timezone.localdate()
IN_ONE_MONTH = TODAY + timedelta(days=30)
IN_THREE_MONTHS = TODAY + timedelta(days=90)


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


def auth(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {'HTTP_AUTHORIZATION': f'Token {token.key}'}


def make_property(landlord, name='Sunshine Apartments'):
    return Property.objects.create(
        landlord=landlord, name=name,
        property_type=PropertyType.APARTMENT,
        address='12 Marine Road', city='Lagos', state='Lagos',
        country='Nigeria', currency='NGN', description='Block of flats',
    )


def make_unit(prop, name='Flat A'):
    return Unit.objects.create(property=prop, name=name)


def make_lease(landlord, tenant, prop, unit, **overrides):
    defaults = {
        'start_date': TODAY,
        'expiry_date': IN_THREE_MONTHS,
        'rent_amount': 500000,
        'currency': 'NGN',
        'rent_frequency': RentFrequency.MONTHLY,
        'rent_due_day': 1,
        'notes': '',
    }
    defaults.update(overrides)
    lease = Lease.objects.create(
        landlord=landlord, tenant=tenant,
        property=prop, unit=unit,
        **defaults,
    )
    lease.refresh_status()
    generate_schedule(lease)
    return lease


def make_payment(landlord, tenant, lease, rent_period=None, **overrides):
    defaults = {
        'landlord': landlord,
        'tenant': tenant,
        'lease': lease,
        'rent_period': rent_period,
        'amount': Decimal('500000'),
        'currency': 'NGN',
        'payment_date': TODAY,
        'payment_method': 'BANK_TRANSFER',
        'reference': '',
        'notes': '',
        'status': PaymentStatus.PAID,
        'recorded_by': landlord,
    }
    defaults.update(overrides)
    return Payment.objects.create(**defaults)


# ---------------------------------------------------------------------------
# Rent Status Derivation Tests
# ---------------------------------------------------------------------------

class RentStatusDerivationTests(TestCase):
    """Unit tests for period_status() financial status derivation."""

    def setUp(self):
        self.landlord = make_landlord('status@example.com')
        self.tenant = make_tenant('status-tenant@example.com')
        self.prop = make_property(self.landlord, 'Status Block')
        self.unit = make_unit(self.prop, 'S1')
        self.lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            start_date=TODAY, expiry_date=IN_THREE_MONTHS,
            rent_frequency=RentFrequency.MONTHLY, rent_due_day=1,
        )
        self.period = self.lease.rent_schedule.first()

    def test_no_payments_upcoming(self):
        """Due date > today → UPCOMING."""
        # Period with future due date
        future_period = RentSchedule.objects.create(
            lease=self.lease, period_start=TODAY + timedelta(days=31),
            period_end=TODAY + timedelta(days=60),
            due_date=TODAY + timedelta(days=31),
            amount=500000, currency='NGN',
        )
        self.assertEqual(period_status(future_period), 'UPCOMING')

    def test_no_payments_due_today(self):
        """Due date == today → DUE."""
        # Create a period due today
        today_period = RentSchedule.objects.create(
            lease=self.lease, period_start=TODAY,
            period_end=TODAY + timedelta(days=30),
            due_date=TODAY,
            amount=500000, currency='NGN',
        )
        self.assertEqual(period_status(today_period), 'DUE')

    def test_no_payments_overdue(self):
        """Due date < today → OVERDUE."""
        # Use the first auto-generated period which has due_date in the past
        # (rent_due_day=1 → first period due_date = 1st of current month,
        # which is before TODAY on the 2nd).
        overdue_period = self.lease.rent_schedule.first()
        self.assertLess(overdue_period.due_date, TODAY,
                        'Precondition: first period due_date must be in the past')
        self.assertEqual(period_status(overdue_period), 'OVERDUE')

    def test_partial_payment(self):
        """0 < paid < amount → PARTIALLY_PAID."""
        make_payment(
            self.landlord, self.tenant, self.lease, self.period,
            amount=Decimal('300000'),
        )
        self.assertEqual(period_status(self.period), 'PARTIALLY_PAID')

    def test_full_payment(self):
        """paid >= amount → PAID."""
        make_payment(
            self.landlord, self.tenant, self.lease, self.period,
            amount=Decimal('500000'),
        )
        self.assertEqual(period_status(self.period), 'PAID')

    def test_overpayment(self):
        """paid > amount → PAID (excess visible but status is PAID)."""
        make_payment(
            self.landlord, self.tenant, self.lease, self.period,
            amount=Decimal('600000'),
        )
        self.assertEqual(period_status(self.period), 'PAID')
        self.assertEqual(paid_amount(self.period), Decimal('600000'))
        self.assertEqual(remaining_amount(self.period), Decimal('0'))

    def test_multiple_partial_payments(self):
        """Multiple partial payments aggregate correctly."""
        make_payment(
            self.landlord, self.tenant, self.lease, self.period,
            amount=Decimal('300000'),
        )
        self.assertEqual(period_status(self.period), 'PARTIALLY_PAID')
        self.assertEqual(paid_amount(self.period), Decimal('300000'))
        self.assertEqual(remaining_amount(self.period), Decimal('200000'))

        make_payment(
            self.landlord, self.tenant, self.lease, self.period,
            amount=Decimal('200000'),
        )
        self.assertEqual(period_status(self.period), 'PAID')
        self.assertEqual(paid_amount(self.period), Decimal('500000'))
        self.assertEqual(remaining_amount(self.period), Decimal('0'))


# ---------------------------------------------------------------------------
# Payment Status Tests
# ---------------------------------------------------------------------------

class PaymentStatusTests(TestCase):
    """Test that only PAID payments count toward rent period balance."""

    def setUp(self):
        self.landlord = make_landlord('status2@example.com')
        self.tenant = make_tenant('status2-tenant@example.com')
        self.prop = make_property(self.landlord, 'Status Block 2')
        self.unit = make_unit(self.prop, 'S2')
        self.lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            start_date=TODAY, expiry_date=IN_THREE_MONTHS,
        )
        self.period = self.lease.rent_schedule.first()

    def test_paid_counts(self):
        make_payment(
            self.landlord, self.tenant, self.lease, self.period,
            amount=Decimal('500000'), status=PaymentStatus.PAID,
        )
        self.assertEqual(paid_amount(self.period), Decimal('500000'))
        self.assertEqual(period_status(self.period), 'PAID')

    def test_pending_does_not_count(self):
        make_payment(
            self.landlord, self.tenant, self.lease, self.period,
            amount=Decimal('500000'), status=PaymentStatus.PENDING,
        )
        self.assertEqual(paid_amount(self.period), Decimal('0'))
        self.assertNotEqual(period_status(self.period), 'PAID')

    def test_failed_does_not_count(self):
        make_payment(
            self.landlord, self.tenant, self.lease, self.period,
            amount=Decimal('500000'), status=PaymentStatus.FAILED,
        )
        self.assertEqual(paid_amount(self.period), Decimal('0'))

    def test_cancelled_does_not_count(self):
        payment = make_payment(
            self.landlord, self.tenant, self.lease, self.period,
            amount=Decimal('500000'), status=PaymentStatus.PAID,
        )
        self.assertEqual(paid_amount(self.period), Decimal('500000'))
        payment.status = PaymentStatus.CANCELLED
        payment.save(update_fields=['status'])
        self.assertEqual(paid_amount(self.period), Decimal('0'))


# ---------------------------------------------------------------------------
# Overpayment Tests
# ---------------------------------------------------------------------------

class OverpaymentTests(TestCase):
    """Test overpayment behavior: excess is visible but no auto-credit."""

    def setUp(self):
        self.landlord = make_landlord('overpay@example.com')
        self.tenant = make_tenant('overpay-tenant@example.com')
        self.prop = make_property(self.landlord, 'Overpay Block')
        self.unit = make_unit(self.prop, 'OP1')
        self.lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            start_date=TODAY, expiry_date=IN_THREE_MONTHS,
            rent_amount=500000,
        )
        self.period = self.lease.rent_schedule.first()

    def test_overpayment_shows_paid_status(self):
        make_payment(
            self.landlord, self.tenant, self.lease, self.period,
            amount=Decimal('600000'),
        )
        self.assertEqual(period_status(self.period), 'PAID')

    def test_overpayment_excess_visible(self):
        payment = make_payment(
            self.landlord, self.tenant, self.lease, self.period,
            amount=Decimal('600000'),
        )
        self.assertEqual(paid_amount(self.period), Decimal('600000'))
        self.assertEqual(remaining_amount(self.period), Decimal('0'))
        # The payment amount itself is 600k, not reduced to 500k
        self.assertEqual(payment.amount, Decimal('600000'))

    def test_no_automatic_credit_transfer(self):
        """Excess from one period does not automatically apply to another."""
        period1 = self.lease.rent_schedule.first()
        # Create a second period
        period2 = RentSchedule.objects.create(
            lease=self.lease, period_start=TODAY + timedelta(days=31),
            period_end=TODAY + timedelta(days=60),
            due_date=TODAY + timedelta(days=31),
            amount=500000, currency='NGN',
        )
        # Overpay period1
        make_payment(
            self.landlord, self.tenant, self.lease, period1,
            amount=Decimal('600000'),
        )
        # period2 should remain unpaid
        self.assertEqual(paid_amount(period2), Decimal('0'))
        self.assertEqual(period_status(period2), 'UPCOMING')


# ---------------------------------------------------------------------------
# Payment Lifecycle Tests
# ---------------------------------------------------------------------------

class PaymentLifecycleTests(TestCase):
    """Test create/retrieve/update/cancel via API."""

    def setUp(self):
        self.client = APIClient()
        self.landlord = make_landlord('lifecycle@example.com')
        self.tenant = make_tenant('lifecycle-tenant@example.com')
        self.prop = make_property(self.landlord)
        self.unit = make_unit(self.prop)
        self.lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            start_date=TODAY, expiry_date=IN_THREE_MONTHS,
        )
        self.period = self.lease.rent_schedule.first()
        self.url = '/api/v1/payments/'

    def _create_payload(self, **overrides):
        payload = {
            'tenant': self.tenant.id,
            'lease': self.lease.id,
            'rent_period': self.period.id,
            'amount': '500000.00',
            'currency': 'NGN',
            'payment_date': str(TODAY),
            'payment_method': 'BANK_TRANSFER',
            'reference': 'TXN-001',
            'notes': 'Monthly rent',
            'status': 'PAID',
        }
        payload.update(overrides)
        return payload

    def test_create_payment(self):
        resp = self.client.post(
            self.url, self._create_payload(), **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['amount'], '500000.00')
        self.assertEqual(resp.data['status'], 'PAID')
        self.assertEqual(resp.data['landlord'], self.landlord.id)

    def test_retrieve_payment(self):
        resp = self.client.post(
            self.url, self._create_payload(), **auth(self.landlord),
        )
        payment_id = resp.data['id']
        resp = self.client.get(
            f'{self.url}{payment_id}/', **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['id'], payment_id)

    def test_list_payments(self):
        self.client.post(
            self.url, self._create_payload(), **auth(self.landlord),
        )
        resp = self.client.get(self.url, **auth(self.landlord))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_update_payment(self):
        resp = self.client.post(
            self.url, self._create_payload(), **auth(self.landlord),
        )
        payment_id = resp.data['id']
        resp = self.client.patch(
            f'{self.url}{payment_id}/',
            {'amount': '600000.00', 'notes': 'Updated'},
            **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['amount'], '600000.00')
        self.assertEqual(resp.data['notes'], 'Updated')

    def test_cancel_payment(self):
        resp = self.client.post(
            self.url, self._create_payload(), **auth(self.landlord),
        )
        payment_id = resp.data['id']
        resp = self.client.post(
            f'{self.url}{payment_id}/cancel/', **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'CANCELLED')

    def test_cancelled_payment_excluded_from_balance(self):
        resp = self.client.post(
            self.url, self._create_payload(), **auth(self.landlord),
        )
        payment_id = resp.data['id']
        self.assertEqual(paid_amount(self.period), Decimal('500000'))

        self.client.post(
            f'{self.url}{payment_id}/cancel/', **auth(self.landlord),
        )
        self.assertEqual(paid_amount(self.period), Decimal('0'))

    def test_invalid_payment_rejected(self):
        resp = self.client.post(
            self.url, self._create_payload(amount='-100'), **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, 400)

    def test_invalid_rent_period_rejected(self):
        resp = self.client.post(
            self.url, self._create_payload(rent_period=99999), **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, 400)

    def test_payment_moved_to_different_period(self):
        """Moving a payment recalculates both old and new periods."""
        period2 = RentSchedule.objects.create(
            lease=self.lease, period_start=TODAY + timedelta(days=31),
            period_end=TODAY + timedelta(days=60),
            due_date=TODAY + timedelta(days=31),
            amount=500000, currency='NGN',
        )
        resp = self.client.post(
            self.url, self._create_payload(), **auth(self.landlord),
        )
        payment_id = resp.data['id']
        self.assertEqual(paid_amount(self.period), Decimal('500000'))
        self.assertEqual(paid_amount(period2), Decimal('0'))

        resp = self.client.patch(
            f'{self.url}{payment_id}/',
            {'rent_period': period2.id},
            **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(paid_amount(self.period), Decimal('0'))
        self.assertEqual(paid_amount(period2), Decimal('500000'))


# ---------------------------------------------------------------------------
# Authorization Tests
# ---------------------------------------------------------------------------

class PaymentAuthorizationTests(TestCase):
    """Test that authorization rules are enforced."""

    def setUp(self):
        self.client = APIClient()
        self.landlord_a = make_landlord('auth_a@example.com')
        self.landlord_b = make_landlord('auth_b@example.com')
        self.tenant_a = make_tenant('auth_ta@example.com')
        self.tenant_b = make_tenant('auth_tb@example.com')
        self.prop_a = make_property(self.landlord_a, 'A Block')
        self.unit_a = make_unit(self.prop_a, 'A1')
        self.lease_a = make_lease(
            self.landlord_a, self.tenant_a, self.prop_a, self.unit_a,
        )
        self.period_a = self.lease_a.rent_schedule.first()
        self.prop_b = make_property(self.landlord_b, 'B Block')
        self.unit_b = make_unit(self.prop_b, 'B1')
        self.lease_b = make_lease(
            self.landlord_b, self.tenant_b, self.prop_b, self.unit_b,
        )
        self.period_b = self.lease_b.rent_schedule.first()
        self.payment_a = make_payment(
            self.landlord_a, self.tenant_a, self.lease_a, self.period_a,
        )
        self.url = '/api/v1/payments/'

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 401)

    def test_landlord_can_access_own_records(self):
        resp = self.client.get(
            f'{self.url}{self.payment_a.id}/', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)

    def test_landlord_cannot_access_other_landlord_records(self):
        resp = self.client.get(
            f'{self.url}{self.payment_a.id}/', **auth(self.landlord_b),
        )
        self.assertEqual(resp.status_code, 404)

    def test_tenant_can_read_own_records(self):
        resp = self.client.get(
            f'{self.url}{self.payment_a.id}/', **auth(self.tenant_a),
        )
        self.assertEqual(resp.status_code, 200)

    def test_tenant_cannot_read_other_tenant_records(self):
        resp = self.client.get(
            f'{self.url}{self.payment_a.id}/', **auth(self.tenant_b),
        )
        self.assertEqual(resp.status_code, 404)

    def test_tenant_cannot_create_payment(self):
        resp = self.client.post(
            self.url,
            {
                'tenant': self.tenant_a.id,
                'lease': self.lease_a.id,
                'amount': '500000.00',
                'currency': 'NGN',
                'payment_date': str(TODAY),
            },
            **auth(self.tenant_a),
        )
        self.assertEqual(resp.status_code, 403)

    def test_tenant_cannot_update_payment(self):
        resp = self.client.patch(
            f'{self.url}{self.payment_a.id}/',
            {'amount': '1.00'},
            **auth(self.tenant_a),
        )
        self.assertEqual(resp.status_code, 403)

    def test_tenant_cannot_cancel_payment(self):
        resp = self.client.post(
            f'{self.url}{self.payment_a.id}/cancel/',
            **auth(self.tenant_a),
        )
        self.assertEqual(resp.status_code, 403)

    def test_landlord_cannot_create_payment_with_wrong_lease(self):
        """Payment creation with another landlord's lease should fail."""
        resp = self.client.post(
            self.url,
            {
                'tenant': self.tenant_b.id,
                'lease': self.lease_b.id,
                'amount': '500000.00',
                'currency': 'NGN',
                'payment_date': str(TODAY),
            },
            **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# Rent Schedule Authorization Tests
# ---------------------------------------------------------------------------

class RentScheduleAuthorizationTests(TestCase):
    """Test rent schedule access rules."""

    def setUp(self):
        self.client = APIClient()
        self.landlord_a = make_landlord('rs_auth_a@example.com')
        self.landlord_b = make_landlord('rs_auth_b@example.com')
        self.tenant_a = make_tenant('rs_ta@example.com')
        self.tenant_b = make_tenant('rs_tb@example.com')
        self.prop_a = make_property(self.landlord_a, 'RS A Block')
        self.unit_a = make_unit(self.prop_a, 'RS A1')
        self.lease_a = make_lease(
            self.landlord_a, self.tenant_a, self.prop_a, self.unit_a,
        )
        self.period_a = self.lease_a.rent_schedule.first()
        self.prop_b = make_property(self.landlord_b, 'RS B Block')
        self.unit_b = make_unit(self.prop_b, 'RS B1')
        self.lease_b = make_lease(
            self.landlord_b, self.tenant_b, self.prop_b, self.unit_b,
        )
        self.period_b = self.lease_b.rent_schedule.first()
        self.url = '/api/v1/rent-schedules/'

    def test_unauthenticated_returns_401(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 401)

    def test_landlord_lists_only_own_schedules(self):
        resp = self.client.get(self.url, **auth(self.landlord_a))
        self.assertEqual(resp.status_code, 200)
        ids = {item['id'] for item in resp.data['results']}
        self.assertIn(self.period_a.id, ids)
        self.assertNotIn(self.period_b.id, ids)

    def test_tenant_lists_only_own_schedules(self):
        resp = self.client.get(self.url, **auth(self.tenant_a))
        self.assertEqual(resp.status_code, 200)
        ids = {item['id'] for item in resp.data['results']}
        self.assertIn(self.period_a.id, ids)
        self.assertNotIn(self.period_b.id, ids)

    def test_landlord_retrieves_own_schedule(self):
        resp = self.client.get(
            f'{self.url}{self.period_a.id}/', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('status', resp.data)
        self.assertIn('paid_amount', resp.data)
        self.assertIn('remaining_amount', resp.data)

    def test_landlord_cannot_retrieve_other_landlord_schedule(self):
        resp = self.client.get(
            f'{self.url}{self.period_a.id}/', **auth(self.landlord_b),
        )
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Rent Schedule Filter Tests
# ---------------------------------------------------------------------------

class RentScheduleFilterTests(TestCase):
    """Test filtering and pagination for rent schedules."""

    def setUp(self):
        self.client = APIClient()
        self.landlord = make_landlord('filter@example.com')
        self.tenant = make_tenant('filter-tenant@example.com')
        self.prop = make_property(self.landlord, 'Filter Block')
        self.unit = make_unit(self.prop, 'F1')
        self.lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            start_date=TODAY, expiry_date=IN_THREE_MONTHS,
        )
        self.periods = list(self.lease.rent_schedule.all())
        self.url = '/api/v1/rent-schedules/'

    def test_status_filter_paid(self):
        """Filter by status=PAID."""
        make_payment(
            self.landlord, self.tenant, self.lease, self.periods[0],
            amount=Decimal('500000'),
        )
        resp = self.client.get(
            f'{self.url}?status=PAID', **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, 200)
        ids = {item['id'] for item in resp.data['results']}
        self.assertEqual(ids, {self.periods[0].id})

    def test_status_filter_upcoming(self):
        """Filter by status=UPCOMING."""
        resp = self.client.get(
            f'{self.url}?status=UPCOMING', **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, 200)
        # All periods should be upcoming (no payments, future due dates)
        self.assertTrue(resp.data['count'] > 0)

    def test_lease_filter(self):
        """Filter by lease ID."""
        resp = self.client.get(
            f'{self.url}?lease={self.lease.id}', **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, 200)
        for item in resp.data['results']:
            self.assertEqual(item['lease_id'], self.lease.id)

    def test_tenant_filter(self):
        """Filter by tenant ID."""
        resp = self.client.get(
            f'{self.url}?tenant={self.tenant.id}', **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['count'] > 0)

    def test_pagination(self):
        """Verify pagination works."""
        resp = self.client.get(self.url, **auth(self.landlord))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('count', resp.data)
        self.assertIn('results', resp.data)


# ---------------------------------------------------------------------------
# Rent Frequency Tests
# ---------------------------------------------------------------------------

class RentFrequencyTests(TestCase):
    """Test schedule generation for different rent frequencies."""

    def setUp(self):
        self.landlord = make_landlord('freq@example.com')
        self.tenant = make_tenant('freq-tenant@example.com')
        self.prop = make_property(self.landlord, 'Freq Block')
        self.unit = make_unit(self.prop, 'F1')

    def test_monthly_frequency(self):
        lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            start_date=TODAY, expiry_date=TODAY + timedelta(days=90),
            rent_frequency=RentFrequency.MONTHLY,
        )
        periods = list(lease.rent_schedule.all())
        self.assertEqual(len(periods), 3)  # 3 months in ~90 days

    def test_quarterly_frequency(self):
        lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            start_date=TODAY, expiry_date=TODAY + timedelta(days=365),
            rent_frequency=RentFrequency.QUARTERLY,
        )
        periods = list(lease.rent_schedule.all())
        self.assertEqual(len(periods), 4)  # 4 quarters in a year

    def test_bi_annually_frequency(self):
        lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            start_date=TODAY, expiry_date=TODAY + timedelta(days=365),
            rent_frequency=RentFrequency.BI_ANNUALLY,
        )
        periods = list(lease.rent_schedule.all())
        self.assertEqual(len(periods), 2)  # 2 half-years in a year

    def test_annually_frequency(self):
        lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            start_date=TODAY, expiry_date=TODAY + timedelta(days=400),
            rent_frequency=RentFrequency.ANNUALLY,
        )
        periods = list(lease.rent_schedule.all())
        self.assertEqual(len(periods), 1)  # 1 year period


# ---------------------------------------------------------------------------
# Lease Boundary Tests
# ---------------------------------------------------------------------------

class LeaseBoundaryTests(TestCase):
    """Test that rent periods respect lease boundaries."""

    def setUp(self):
        self.landlord = make_landlord('boundary@example.com')
        self.tenant = make_tenant('boundary-tenant@example.com')
        self.prop = make_property(self.landlord, 'Boundary Block')
        self.unit = make_unit(self.prop, 'B1')

    def test_periods_do_not_extend_beyond_lease(self):
        """Rent periods should not extend beyond the lease expiry date."""
        lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            start_date=TODAY, expiry_date=TODAY + timedelta(days=45),
            rent_frequency=RentFrequency.MONTHLY,
        )
        periods = list(lease.rent_schedule.all())
        for period in periods:
            self.assertLessEqual(period.period_end, lease.expiry_date)

    def test_due_date_clamped_to_month(self):
        """Due day is clamped to the last valid day of the month."""
        lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            start_date=date(2026, 1, 28), expiry_date=date(2026, 4, 30),
            rent_frequency=RentFrequency.MONTHLY, rent_due_day=31,
        )
        periods = list(lease.rent_schedule.all())
        # February 2026 has 28 days, so due_date should be Feb 28
        feb_period = [p for p in periods if p.due_date.month == 2][0]
        self.assertEqual(feb_period.due_date.day, 28)


# ---------------------------------------------------------------------------
# Payment Update Edge Cases
# ---------------------------------------------------------------------------

class PaymentUpdateEdgeCases(TestCase):
    """Test moving payments between periods and other update edge cases."""

    def setUp(self):
        self.client = APIClient()
        self.landlord = make_landlord('update@example.com')
        self.tenant = make_tenant('update-tenant@example.com')
        self.prop = make_property(self.landlord, 'Update Block')
        self.unit = make_unit(self.prop, 'U1')
        self.lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            start_date=TODAY, expiry_date=IN_THREE_MONTHS,
        )
        self.periods = list(self.lease.rent_schedule.all())
        self.url = '/api/v1/payments/'

    def test_move_payment_between_periods(self):
        """Moving a payment recalculates both periods correctly."""
        payment = make_payment(
            self.landlord, self.tenant, self.lease, self.periods[0],
            amount=Decimal('500000'),
        )
        self.assertEqual(paid_amount(self.periods[0]), Decimal('500000'))

        resp = self.client.patch(
            f'{self.url}{payment.id}/',
            {'rent_period': self.periods[1].id},
            **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(paid_amount(self.periods[0]), Decimal('0'))
        self.assertEqual(paid_amount(self.periods[1]), Decimal('500000'))

    def test_update_payment_amount(self):
        """Updating amount recalculates period balance."""
        payment = make_payment(
            self.landlord, self.tenant, self.lease, self.periods[0],
            amount=Decimal('300000'),
        )
        self.assertEqual(period_status(self.periods[0]), 'PARTIALLY_PAID')

        resp = self.client.patch(
            f'{self.url}{payment.id}/',
            {'amount': '500000.00'},
            **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(period_status(self.periods[0]), 'PAID')

    def test_update_payment_status_to_cancelled(self):
        """Updating status to CANCELLED removes amount from balance."""
        payment = make_payment(
            self.landlord, self.tenant, self.lease, self.periods[0],
            amount=Decimal('500000'), status=PaymentStatus.PAID,
        )
        self.assertEqual(paid_amount(self.periods[0]), Decimal('500000'))

        resp = self.client.patch(
            f'{self.url}{payment.id}/',
            {'status': 'CANCELLED'},
            **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(paid_amount(self.periods[0]), Decimal('0'))


# ---------------------------------------------------------------------------
# OpenAPI Schema Tests
# ---------------------------------------------------------------------------

class OpenAPISchemaTests(TestCase):
    """Verify that the OpenAPI schema generates without errors."""

    def test_schema_generation(self):
        from drf_spectacular.generators import SchemaGenerator
        generator = SchemaGenerator()
        # public=True matches the production contract: SpectacularAPIView
        # serves with serve_public=True (drf-spectacular default), which
        # means the schema documents all endpoints regardless of auth.
        schema = generator.get_schema(public=True)
        self.assertIn('paths', schema)
        paths = schema['paths']
        # Check that all major endpoint groups are present
        self.assertTrue(any('/payments' in p for p in paths))
        self.assertTrue(any('/rent-schedules' in p for p in paths))
        self.assertTrue(any('/leases' in p for p in paths))
        self.assertTrue(any('/properties' in p for p in paths))
        self.assertTrue(any('/tenants' in p for p in paths))
