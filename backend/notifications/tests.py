"""Comprehensive tests for the Notification system (Phase 7).

Covers notification creation, idempotency, lease expiry reminders, rent
due/overdue reminders, payment-state interactions, lease-state interactions,
notification preferences, authorization/isolation, management commands, and
the Notification API endpoints.
"""

from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.models import NotificationPreference, User
from leases.models import Lease, LeaseStatus, RentFrequency
from notifications.models import (
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)
from notifications.services import (
    build_idempotency_key,
    create_notification,
    generate_lease_notifications,
    generate_rent_notifications,
    send_notification_email,
)
from payments.models import Payment, PaymentStatus, RentSchedule
from payments.services import generate_schedule, period_status
from properties.models import Property, Unit
from subscriptions.services import ensure_landlord_subscription

TODAY = timezone.localdate()
_notif_counter = 0


def _unique_key():
    global _notif_counter
    _notif_counter += 1
    return f'test-key-{_notif_counter}'


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
    lease = Lease.objects.create(
        landlord=landlord, tenant=tenant,
        property=prop, unit=unit, **defaults,
    )
    return lease


def make_rent_schedule(lease, due_date, amount=None):
    if amount is None:
        amount = lease.rent_amount
    period_start = due_date.replace(day=1)
    if due_date.month == 12:
        period_end = due_date.replace(year=due_date.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        period_end = due_date.replace(month=due_date.month + 1, day=1) - timedelta(days=1)
    return RentSchedule.objects.create(
        lease=lease,
        period_start=period_start,
        period_end=period_end,
        due_date=due_date,
        amount=amount,
        currency=lease.currency,
    )


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


def make_notification(recipient, ntype=NotificationType.GENERAL, **kwargs):
    """Create a notification via the service layer (idempotent key generated)."""
    defaults = {
        'channel': NotificationChannel.IN_APP,
        'title': f'notif-{_unique_key()}',
        'message': 'Test message',
    }
    defaults.update(kwargs)
    return create_notification(
        recipient=recipient,
        notification_type=ntype,
        **defaults,
    )


# ===========================================================================
# Notification Model Tests
# ===========================================================================

class NotificationModelTest(TestCase):
    """Notification creation, relationships, idempotency, SET_NULL behavior."""

    def setUp(self):
        self.landlord = make_landlord()
        self.tenant = make_tenant()
        self.prop, self.unit = make_property(self.landlord)
        self.lease = make_lease(self.landlord, self.tenant, self.prop, self.unit)

    def test_create_notification_basic(self):
        n = make_notification(self.landlord)
        self.assertEqual(n.recipient, self.landlord)
        self.assertEqual(n.status, NotificationStatus.PENDING)
        self.assertFalse(n.is_read)
        self.assertIsNotNone(n.idempotency_key)

    def test_notification_lease_relationship(self):
        n = make_notification(
            self.landlord,
            ntype=NotificationType.LEASE_EXPIRY_30D,
            lease=self.lease,
        )
        self.assertEqual(n.lease, self.lease)
        self.assertIn(n, self.lease.notifications.all())

    def test_notification_rent_period_relationship(self):
        due = TODAY + timedelta(days=7)
        schedule = make_rent_schedule(self.lease, due)
        n = make_notification(
            self.landlord,
            ntype=NotificationType.RENT_UPCOMING_7D,
            lease=self.lease,
            rent_period=schedule,
        )
        self.assertEqual(n.rent_period, schedule)

    def test_idempotency_prevents_duplicate(self):
        n1 = create_notification(
            recipient=self.landlord,
            notification_type=NotificationType.GENERAL,
            channel=NotificationChannel.IN_APP,
            title='Idempotent Test',
            message='Hello',
            scheduled_for=timezone.now(),
        )
        n2 = create_notification(
            recipient=self.landlord,
            notification_type=NotificationType.GENERAL,
            channel=NotificationChannel.IN_APP,
            title='Idempotent Test',
            message='Hello',
            scheduled_for=timezone.now(),
        )
        self.assertEqual(n1.pk, n2.pk)

    def test_lease_set_null_preserves_notification(self):
        n = make_notification(
            self.landlord,
            ntype=NotificationType.LEASE_EXPIRY_30D,
            lease=self.lease,
        )
        self.lease.delete()
        n.refresh_from_db()
        self.assertIsNone(n.lease_id)

    def test_rent_period_set_null_preserves_notification(self):
        due = TODAY + timedelta(days=7)
        schedule = make_rent_schedule(self.lease, due)
        n = make_notification(
            self.landlord,
            ntype=NotificationType.RENT_UPCOMING_7D,
            lease=self.lease,
            rent_period=schedule,
        )
        schedule.delete()
        n.refresh_from_db()
        self.assertIsNone(n.rent_period_id)
        self.assertIsNotNone(n.lease_id)

    def test_recipient_cascade_delete(self):
        n = make_notification(self.landlord)
        landlord_id = self.landlord.pk
        # Delete related objects first to avoid ProtectedError
        Notification.objects.filter(recipient=self.landlord).delete()
        Payment.objects.filter(landlord=self.landlord).delete()
        Lease.objects.filter(landlord=self.landlord).delete()
        Property.objects.filter(landlord=self.landlord).delete()
        User.objects.filter(pk=landlord_id).delete()
        self.assertFalse(Notification.objects.filter(pk=n.pk).exists())


# ===========================================================================
# Authorization / Isolation Tests
# ===========================================================================

class NotificationAuthorizationTest(TestCase):
    """Tenant/landlord isolation, cross-user access denial."""

    def setUp(self):
        self.client = APIClient()
        self.landlord_a = make_landlord('a@example.com')
        self.landlord_b = make_landlord('b@example.com')
        self.tenant_a = make_tenant('tenant_a@example.com')
        self.tenant_b = make_tenant('tenant_b@example.com')
        self.prop_a, self.unit_a = make_property(self.landlord_a)
        self.prop_b, self.unit_b = make_property(self.landlord_b)
        self.lease_a = make_lease(self.landlord_a, self.tenant_a, self.prop_a, self.unit_a)
        self.lease_b = make_lease(self.landlord_b, self.tenant_b, self.prop_b, self.unit_b)
        # Create notifications for each user with unique keys
        self.n_landlord_a = make_notification(
            self.landlord_a, title='Landlord A notification',
        )
        self.n_landlord_b = make_notification(
            self.landlord_b, title='Landlord B notification',
        )
        self.n_tenant_a = make_notification(
            self.tenant_a, title='Tenant A notification',
        )

    def test_unauthenticated_cannot_list(self):
        resp = self.client.get('/api/v1/notifications/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_landlord_sees_only_own_notifications(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.get_or_create(user=self.landlord_a)[0].key}')
        resp = self.client.get('/api/v1/notifications/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [n['id'] for n in resp.data['results']]
        self.assertEqual(ids, [self.n_landlord_a.pk])

    def test_tenant_sees_only_own_notifications(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.get_or_create(user=self.tenant_a)[0].key}')
        resp = self.client.get('/api/v1/notifications/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [n['id'] for n in resp.data['results']]
        self.assertEqual(ids, [self.n_tenant_a.pk])

    def test_cannot_retrieve_another_users_notification(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.get_or_create(user=self.landlord_a)[0].key}')
        resp = self.client.get(f'/api/v1/notifications/{self.n_landlord_b.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_mark_another_users_notification(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.get_or_create(user=self.landlord_a)[0].key}')
        resp = self.client.patch(
            f'/api/v1/notifications/{self.n_landlord_b.pk}/read/',
            {'is_read': True}, format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_readonly_viewset_cannot_create(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {Token.objects.get_or_create(user=self.landlord_a)[0].key}')
        resp = self.client.post('/api/v1/notifications/', {
            'recipient': self.tenant_b.pk,
            'notification_type': 'GENERAL',
            'title': 'X', 'message': 'Y',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


# ===========================================================================
# Lease Expiry Reminder Tests
# ===========================================================================

class LeaseExpiryReminderTest(TestCase):
    """All 7 lease expiry reminder rules + duplicate prevention."""

    def setUp(self):
        self.landlord = make_landlord()
        self.tenant = make_tenant()
        self.prop, self.unit = make_property(self.landlord)

    def _run_for_offset(self, days_offset):
        """Create a lease expiring in `days_offset` days from today and run."""
        expiry = TODAY + timedelta(days=days_offset)
        lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            start_date=expiry - timedelta(days=365),
            expiry_date=expiry,
        )
        result = generate_lease_notifications(today=TODAY)
        return lease, result

    def test_30day_before(self):
        lease, result = self._run_for_offset(30)
        notifs = Notification.objects.filter(
            lease=lease, notification_type=NotificationType.LEASE_EXPIRY_30D,
        )
        self.assertTrue(notifs.exists())
        # Landlord + tenant x in_app + email = 4
        self.assertEqual(result['created'], 4)

    def test_7day_before(self):
        lease, result = self._run_for_offset(7)
        notifs = Notification.objects.filter(
            lease=lease, notification_type=NotificationType.LEASE_EXPIRY_7D,
        )
        self.assertTrue(notifs.exists())
        self.assertEqual(result['created'], 4)

    def test_expiry_day(self):
        lease, result = self._run_for_offset(0)
        notifs = Notification.objects.filter(
            lease=lease, notification_type=NotificationType.LEASE_EXPIRY_DAY,
        )
        self.assertTrue(notifs.exists())
        self.assertEqual(result['created'], 4)

    def test_7day_after(self):
        lease, result = self._run_for_offset(-7)
        notifs = Notification.objects.filter(
            lease=lease, notification_type=NotificationType.LEASE_EXPIRY_7D_AFTER,
        )
        self.assertTrue(notifs.exists())
        self.assertEqual(result['created'], 4)

    def test_14day_after(self):
        lease, result = self._run_for_offset(-14)
        notifs = Notification.objects.filter(
            lease=lease, notification_type=NotificationType.LEASE_EXPIRY_14D_AFTER,
        )
        self.assertTrue(notifs.exists())
        self.assertEqual(result['created'], 4)

    def test_21day_after(self):
        lease, result = self._run_for_offset(-21)
        notifs = Notification.objects.filter(
            lease=lease, notification_type=NotificationType.LEASE_EXPIRY_21D_AFTER,
        )
        self.assertTrue(notifs.exists())
        self.assertEqual(result['created'], 4)

    def test_28day_after(self):
        lease, result = self._run_for_offset(-28)
        notifs = Notification.objects.filter(
            lease=lease, notification_type=NotificationType.LEASE_EXPIRY_28D_AFTER,
        )
        self.assertTrue(notifs.exists())
        self.assertEqual(result['created'], 4)

    def test_duplicate_prevention(self):
        expiry = TODAY + timedelta(days=30)
        lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            start_date=expiry - timedelta(days=365),
            expiry_date=expiry,
        )
        result1 = generate_lease_notifications(today=TODAY)
        self.assertEqual(result1['created'], 4)
        # Second run on same day — should create 0
        result2 = generate_lease_notifications(today=TODAY)
        self.assertEqual(result2['created'], 0)

    def test_terminated_lease_excluded(self):
        expiry = TODAY + timedelta(days=30)
        lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            start_date=expiry - timedelta(days=365),
            expiry_date=expiry,
            status=LeaseStatus.TERMINATED,
        )
        result = generate_lease_notifications(today=TODAY)
        self.assertEqual(result['created'], 0)
        self.assertFalse(Notification.objects.filter(lease=lease).exists())

    def test_suppressed_after_expiry_for_superseded(self):
        """Superseded lease should not get after-expiry notifications."""
        expiry = TODAY - timedelta(days=7)
        old_lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            start_date=expiry - timedelta(days=365),
            expiry_date=expiry,
        )
        prop2, unit2 = make_property(self.landlord, name='Prop2')
        new_lease = make_lease(
            self.landlord, self.tenant, prop2, unit2,
            start_date=expiry,
            expiry_date=expiry + timedelta(days=365),
            previous_lease=old_lease,
        )
        result = generate_lease_notifications(today=TODAY)
        # Old lease should not get after-expiry notifications
        after_expiry_notifs = Notification.objects.filter(
            lease=old_lease,
            notification_type__in=[
                NotificationType.LEASE_EXPIRY_7D_AFTER,
                NotificationType.LEASE_EXPIRY_14D_AFTER,
                NotificationType.LEASE_EXPIRY_21D_AFTER,
                NotificationType.LEASE_EXPIRY_28D_AFTER,
            ],
        )
        self.assertFalse(after_expiry_notifs.exists())

    def test_future_lease_gets_30day_notification(self):
        """FUTURE lease with expiry in 30 days should get notification."""
        expiry = TODAY + timedelta(days=30)
        lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            start_date=TODAY + timedelta(days=10),
            expiry_date=expiry,
            status=LeaseStatus.FUTURE,
        )
        result = generate_lease_notifications(today=TODAY)
        notifs = Notification.objects.filter(
            lease=lease, notification_type=NotificationType.LEASE_EXPIRY_30D,
        )
        self.assertTrue(notifs.exists())

    def test_expiring_lease_no_matching_rule(self):
        """EXPIRING lease (15 days left) — no rule matches."""
        expiry = TODAY + timedelta(days=15)
        lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            start_date=expiry - timedelta(days=365),
            expiry_date=expiry,
        )
        result = generate_lease_notifications(today=TODAY)
        self.assertEqual(result['created'], 0)


# ===========================================================================
# Rent Reminder Tests
# ===========================================================================

class RentReminderTest(TestCase):
    """All 6 rent reminder rules + duplicate prevention + terminated lease."""

    def setUp(self):
        self.landlord = make_landlord()
        self.tenant = make_tenant()
        self.prop, self.unit = make_property(self.landlord)
        self.lease = make_lease(self.landlord, self.tenant, self.prop, self.unit)

    def _run_for_offset(self, days_offset):
        due = TODAY + timedelta(days=days_offset)
        schedule = make_rent_schedule(self.lease, due)
        result = generate_rent_notifications(today=TODAY)
        return schedule, result

    def test_7day_before(self):
        schedule, result = self._run_for_offset(7)
        notifs = Notification.objects.filter(rent_period=schedule)
        # Each recipient x channel = multiple notifications
        self.assertTrue(notifs.exists())

    def test_3day_before(self):
        schedule, result = self._run_for_offset(3)
        notifs = Notification.objects.filter(
            rent_period=schedule,
            notification_type=NotificationType.RENT_UPCOMING_3D,
        )
        self.assertTrue(notifs.exists())

    def test_due_day(self):
        schedule, result = self._run_for_offset(0)
        notifs = Notification.objects.filter(
            rent_period=schedule,
            notification_type=NotificationType.RENT_DUE_DAY,
        )
        self.assertTrue(notifs.exists())

    def test_3day_overdue(self):
        schedule, result = self._run_for_offset(-3)
        notifs = Notification.objects.filter(
            rent_period=schedule,
            notification_type=NotificationType.RENT_OVERDUE_3D,
        )
        self.assertTrue(notifs.exists())

    def test_7day_overdue(self):
        schedule, result = self._run_for_offset(-7)
        notifs = Notification.objects.filter(
            rent_period=schedule,
            notification_type=NotificationType.RENT_OVERDUE_7D,
        )
        self.assertTrue(notifs.exists())

    def test_14day_overdue(self):
        schedule, result = self._run_for_offset(-14)
        notifs = Notification.objects.filter(
            rent_period=schedule,
            notification_type=NotificationType.RENT_OVERDUE_14D,
        )
        self.assertTrue(notifs.exists())

    def test_duplicate_prevention(self):
        due = TODAY + timedelta(days=7)
        schedule = make_rent_schedule(self.lease, due)
        result1 = generate_rent_notifications(today=TODAY)
        self.assertTrue(result1['created'] > 0)
        result2 = generate_rent_notifications(today=TODAY)
        self.assertEqual(result2['created'], 0)

    def test_terminated_lease_excluded(self):
        terminated_lease = make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            status=LeaseStatus.TERMINATED,
            terminated_at=timezone.now(),
        )
        due = TODAY + timedelta(days=7)
        schedule = make_rent_schedule(terminated_lease, due)
        result = generate_rent_notifications(today=TODAY)
        self.assertEqual(result['created'], 0)

    def test_fully_paid_period_no_notification(self):
        due = TODAY + timedelta(days=0)
        schedule = make_rent_schedule(self.lease, due)
        make_payment(self.lease, schedule, schedule.amount, PaymentStatus.PAID)
        result = generate_rent_notifications(today=TODAY)
        notifs = Notification.objects.filter(rent_period=schedule)
        self.assertEqual(notifs.count(), 0)

    def test_partially_paid_gets_overdue_notification(self):
        due = TODAY - timedelta(days=3)
        schedule = make_rent_schedule(self.lease, due, amount=Decimal('100000.00'))
        make_payment(self.lease, schedule, Decimal('50000.00'), PaymentStatus.PAID)
        result = generate_rent_notifications(today=TODAY)
        notifs = Notification.objects.filter(
            rent_period=schedule,
            notification_type=NotificationType.RENT_OVERDUE_3D,
        )
        self.assertTrue(notifs.exists())

    def test_pending_payment_does_not_count(self):
        due = TODAY + timedelta(days=0)
        schedule = make_rent_schedule(self.lease, due)
        make_payment(self.lease, schedule, schedule.amount, PaymentStatus.PENDING)
        result = generate_rent_notifications(today=TODAY)
        notifs = Notification.objects.filter(
            rent_period=schedule,
            notification_type=NotificationType.RENT_DUE_DAY,
        )
        self.assertTrue(notifs.exists())

    def test_failed_payment_does_not_count(self):
        due = TODAY + timedelta(days=0)
        schedule = make_rent_schedule(self.lease, due)
        make_payment(self.lease, schedule, schedule.amount, PaymentStatus.FAILED)
        result = generate_rent_notifications(today=TODAY)
        notifs = Notification.objects.filter(
            rent_period=schedule,
            notification_type=NotificationType.RENT_DUE_DAY,
        )
        self.assertTrue(notifs.exists())

    def test_cancelled_payment_does_not_count(self):
        due = TODAY + timedelta(days=0)
        schedule = make_rent_schedule(self.lease, due)
        make_payment(self.lease, schedule, schedule.amount, PaymentStatus.CANCELLED)
        result = generate_rent_notifications(today=TODAY)
        notifs = Notification.objects.filter(
            rent_period=schedule,
            notification_type=NotificationType.RENT_DUE_DAY,
        )
        self.assertTrue(notifs.exists())


# ===========================================================================
# Preference Tests
# ===========================================================================

class NotificationPreferenceTest(TestCase):
    """Email/in-app preference toggling."""

    def setUp(self):
        self.landlord = make_landlord()
        self.tenant = make_tenant()
        self.prop, self.unit = make_property(self.landlord)
        self.lease = make_lease(self.landlord, self.tenant, self.prop, self.unit)

    def test_email_disabled_no_email_notification(self):
        NotificationPreference.objects.create(
            user=self.landlord, email_enabled=False, in_app_enabled=True,
        )
        due = TODAY + timedelta(days=7)
        schedule = make_rent_schedule(self.lease, due)
        generate_rent_notifications(today=TODAY)
        email_notifs = Notification.objects.filter(
            recipient=self.landlord, channel=NotificationChannel.EMAIL,
        )
        self.assertEqual(email_notifs.count(), 0)

    def test_in_app_disabled_no_in_app_notification(self):
        NotificationPreference.objects.create(
            user=self.landlord, email_enabled=True, in_app_enabled=False,
        )
        due = TODAY + timedelta(days=7)
        schedule = make_rent_schedule(self.lease, due)
        generate_rent_notifications(today=TODAY)
        in_app_notifs = Notification.objects.filter(
            recipient=self.landlord, channel=NotificationChannel.IN_APP,
        )
        self.assertEqual(in_app_notifs.count(), 0)

    def test_both_disabled_no_notifications(self):
        NotificationPreference.objects.create(
            user=self.landlord, email_enabled=False, in_app_enabled=False,
        )
        due = TODAY + timedelta(days=7)
        schedule = make_rent_schedule(self.lease, due)
        generate_rent_notifications(today=TODAY)
        notifs = Notification.objects.filter(recipient=self.landlord)
        self.assertEqual(notifs.count(), 0)

    def test_tenant_preferences_independently_controlled(self):
        NotificationPreference.objects.create(
            user=self.tenant, email_enabled=False, in_app_enabled=True,
        )
        due = TODAY + timedelta(days=7)
        schedule = make_rent_schedule(self.lease, due)
        generate_rent_notifications(today=TODAY)
        # Landlord should get both channels (no preference set = defaults)
        landlord_in_app = Notification.objects.filter(
            recipient=self.landlord, channel=NotificationChannel.IN_APP,
        ).count()
        landlord_email = Notification.objects.filter(
            recipient=self.landlord, channel=NotificationChannel.EMAIL,
        ).count()
        self.assertGreaterEqual(landlord_in_app, 1)
        self.assertGreaterEqual(landlord_email, 1)
        # Tenant should get only in_app
        tenant_email = Notification.objects.filter(
            recipient=self.tenant, channel=NotificationChannel.EMAIL,
        ).count()
        self.assertEqual(tenant_email, 0)

    def test_no_preference_record_defaults_to_enabled(self):
        """When no NotificationPreference exists, both channels default on."""
        due = TODAY + timedelta(days=7)
        schedule = make_rent_schedule(self.lease, due)
        generate_rent_notifications(today=TODAY)
        in_app = Notification.objects.filter(
            recipient=self.landlord, channel=NotificationChannel.IN_APP,
        ).count()
        email = Notification.objects.filter(
            recipient=self.landlord, channel=NotificationChannel.EMAIL,
        ).count()
        self.assertGreaterEqual(in_app, 1)
        self.assertGreaterEqual(email, 1)


# ===========================================================================
# Email Delivery Tests
# ===========================================================================

class EmailDeliveryTest(TestCase):
    """send_notification_email behavior."""

    def setUp(self):
        self.landlord = make_landlord()

    def test_successful_email_marks_sent(self):
        n = make_notification(
            self.landlord,
            channel=NotificationChannel.EMAIL,
        )
        with patch('core.services.send_email', return_value=1):
            result = send_notification_email(n)
        self.assertTrue(result)
        n.refresh_from_db()
        self.assertEqual(n.status, NotificationStatus.SENT)
        self.assertIsNotNone(n.sent_at)

    def test_failed_email_marks_failed(self):
        n = make_notification(
            self.landlord,
            channel=NotificationChannel.EMAIL,
        )
        with patch('core.services.send_email', side_effect=Exception('SMTP error')):
            result = send_notification_email(n)
        self.assertFalse(result)
        n.refresh_from_db()
        self.assertEqual(n.status, NotificationStatus.FAILED)
        self.assertIn('SMTP error', n.error_message)


# ===========================================================================
# Management Command Tests
# ===========================================================================

class SendRentNotificationsCommandTest(TestCase):
    """Management command: send_rent_notifications."""

    def setUp(self):
        self.landlord = make_landlord()
        self.tenant = make_tenant()
        self.prop, self.unit = make_property(self.landlord)
        self.lease = make_lease(self.landlord, self.tenant, self.prop, self.unit)

    def test_command_executes(self):
        out = StringIO()
        call_command('send_rent_notifications', stdout=out)
        output = out.getvalue()
        self.assertIn('Rent notifications:', output)
        self.assertIn('created=', output)

    def test_command_with_today_override(self):
        due = TODAY + timedelta(days=7)
        make_rent_schedule(self.lease, due)
        out = StringIO()
        call_command('send_rent_notifications', '--today', str(TODAY), stdout=out)
        output = out.getvalue()
        self.assertIn('Rent notifications:', output)

    def test_repeated_execution_idempotent(self):
        due = TODAY + timedelta(days=7)
        make_rent_schedule(self.lease, due)
        out1 = StringIO()
        call_command('send_rent_notifications', '--today', str(TODAY), stdout=out1)
        out2 = StringIO()
        call_command('send_rent_notifications', '--today', str(TODAY), stdout=out2)
        self.assertIn('created=0', out2.getvalue())

    def test_send_emails_flag(self):
        due = TODAY + timedelta(days=7)
        make_rent_schedule(self.lease, due)
        out = StringIO()
        with patch(
            'notifications.management.commands.send_rent_notifications.send_notification_email',
            return_value=True,
        ):
            call_command(
                'send_rent_notifications', '--today', str(TODAY),
                '--send-emails', stdout=out,
            )
        output = out.getvalue()
        self.assertIn('Email dispatch:', output)


class SendLeaseNotificationsCommandTest(TestCase):
    """Management command: send_lease_notifications."""

    def setUp(self):
        self.landlord = make_landlord()
        self.tenant = make_tenant()
        self.prop, self.unit = make_property(self.landlord)

    def test_command_executes(self):
        out = StringIO()
        call_command('send_lease_notifications', stdout=out)
        output = out.getvalue()
        self.assertIn('Lease notifications:', output)

    def test_command_with_today_override(self):
        expiry = TODAY + timedelta(days=30)
        make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            start_date=expiry - timedelta(days=365),
            expiry_date=expiry,
        )
        out = StringIO()
        call_command('send_lease_notifications', '--today', str(TODAY), stdout=out)
        output = out.getvalue()
        self.assertIn('Lease notifications:', output)

    def test_repeated_execution_idempotent(self):
        expiry = TODAY + timedelta(days=30)
        make_lease(
            self.landlord, self.tenant, self.prop, self.unit,
            start_date=expiry - timedelta(days=365),
            expiry_date=expiry,
        )
        out1 = StringIO()
        call_command('send_lease_notifications', '--today', str(TODAY), stdout=out1)
        out2 = StringIO()
        call_command('send_lease_notifications', '--today', str(TODAY), stdout=out2)
        self.assertIn('created=0', out2.getvalue())


# ===========================================================================
# API Tests
# ===========================================================================

class NotificationAPITest(TestCase):
    """Notification API: list, retrieve, unread filter, mark read,
    unread count, bulk mark-read, preferences."""

    def setUp(self):
        self.client = APIClient()
        self.landlord = make_landlord()
        self.tenant = make_tenant()
        self.prop, self.unit = make_property(self.landlord)
        self.lease = make_lease(self.landlord, self.tenant, self.prop, self.unit)
        self.n1 = make_notification(
            self.landlord, title='Notification 1 unread',
            ntype=NotificationType.GENERAL,
        )
        self.n2 = create_notification(
            recipient=self.landlord,
            notification_type=NotificationType.LEASE_EXPIRY_30D,
            channel=NotificationChannel.IN_APP,
            title='Notification 2 read',
            message='Read notification',
            scheduled_for=timezone.now(),
        )
        self.n2.is_read = True
        self.n2.save(update_fields=['is_read'])
        self.headers = auth(self.landlord)

    def test_list_notifications(self):
        resp = self.client.get('/api/v1/notifications/', **self.headers)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 2)

    def test_retrieve_notification(self):
        resp = self.client.get(
            f'/api/v1/notifications/{self.n1.pk}/', **self.headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['title'], 'Notification 1 unread')

    def test_unread_filter_true(self):
        resp = self.client.get(
            '/api/v1/notifications/?unread=true', **self.headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['id'], self.n1.pk)

    def test_unread_filter_false(self):
        resp = self.client.get(
            '/api/v1/notifications/?unread=false', **self.headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['id'], self.n2.pk)

    def test_mark_read(self):
        resp = self.client.patch(
            f'/api/v1/notifications/{self.n1.pk}/read/',
            {'is_read': True}, format='json', **self.headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.n1.refresh_from_db()
        self.assertTrue(self.n1.is_read)

    def test_unread_count(self):
        resp = self.client.get(
            '/api/v1/notifications/unread-count/', **self.headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['unread_count'], 1)

    def test_bulk_mark_all_read(self):
        resp = self.client.patch(
            '/api/v1/notifications/mark-all-read/',
            {'is_read': True}, format='json', **self.headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['updated'], 1)
        self.n1.refresh_from_db()
        self.assertTrue(self.n1.is_read)

    def test_bulk_mark_read_specific_ids(self):
        resp = self.client.patch(
            '/api/v1/notifications/mark-all-read/',
            {'is_read': True, 'notification_ids': [self.n1.pk]},
            format='json', **self.headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['updated'], 1)
        self.n1.refresh_from_db()
        self.assertTrue(self.n1.is_read)
        self.n2.refresh_from_db()
        self.assertTrue(self.n2.is_read)  # was already read

    def test_preferences_get(self):
        resp = self.client.get(
            '/api/v1/notifications/preferences/', **self.headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('email_enabled', resp.data)
        self.assertIn('in_app_enabled', resp.data)

    def test_preferences_patch(self):
        resp = self.client.patch(
            '/api/v1/notifications/preferences/',
            {'email_enabled': False}, format='json', **self.headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['email_enabled'])
        self.assertTrue(resp.data['in_app_enabled'])

    def test_preferences_creates_default(self):
        NotificationPreference.objects.filter(user=self.landlord).delete()
        resp = self.client.get(
            '/api/v1/notifications/preferences/', **self.headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['email_enabled'])
        self.assertTrue(resp.data['in_app_enabled'])
