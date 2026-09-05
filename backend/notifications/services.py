"""Notification domain services.

Provides deterministic idempotency-key generation, notification persistence,
email delivery, and the scheduled-notification generators for lease expiry
and rent due/overdue reminders.

Idempotency keys are always generated here — never supplied by clients.
Running the scheduler multiple times on the same day is safe and will not
create duplicate notifications.
"""

from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.models import NotificationPreference

from .models import (
    Notification,
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)


# ---------------------------------------------------------------------------
# Idempotency key builder
# ---------------------------------------------------------------------------

def build_idempotency_key(*, recipient_id, notification_type, channel,
                          scheduled_date=None, lease_id=None,
                          ref_type=None, ref_id=None):
    """Build a deterministic idempotency key.

    The key combines the recipient, notification type, channel, and the
    calendar day the notification is scheduled for, plus an optional related
    resource.  Two identical jobs (e.g. the scheduler running twice on the
    same day) therefore produce the same key and the DB unique constraint
    prevents a duplicate.
    """
    day = scheduled_date or timezone.localdate()
    # If a datetime is passed, extract just the date for the key.
    if hasattr(day, 'date'):
        day = day.date()
    parts = [recipient_id, notification_type, channel, day.isoformat()]
    if lease_id is not None:
        parts.append(f'lease:{lease_id}')
    if ref_type and ref_id is not None:
        parts.append(f'{ref_type}:{ref_id}')
    return '|'.join(str(p) for p in parts)


# ---------------------------------------------------------------------------
# Core persistence
# ---------------------------------------------------------------------------

@transaction.atomic
def create_notification(*, recipient, notification_type, channel, title, message,
                        lease=None, payment=None, rent_period=None,
                        invitation=None, scheduled_for=None, key_parts=None):
    """Persist a notification with a deterministic idempotency key.

    If a notification with the same idempotency key already exists, the call
    is a no-op (returns the existing row).  This makes scheduled reminder
    generation idempotent and safe against duplicate job execution.

    The returned notification has a ``_created`` attribute (bool) indicating
    whether this call created a new row or returned an existing one.
    """
    key = build_idempotency_key(
        recipient_id=recipient.id,
        notification_type=notification_type,
        channel=channel,
        scheduled_date=scheduled_for,
        lease_id=lease.id if lease else None,
        ref_type=_ref_type(payment, invitation, rent_period),
        ref_id=_ref_id(payment, invitation, rent_period),
        **(key_parts or {}),
    )
    existing = Notification.objects.filter(idempotency_key=key).first()
    if existing:
        existing._created = False
        return existing

    notification = Notification(
        recipient=recipient,
        notification_type=notification_type,
        channel=channel,
        status=NotificationStatus.PENDING,
        lease=lease,
        payment=payment,
        rent_period=rent_period,
        invitation=invitation,
        title=title,
        message=message,
        scheduled_for=scheduled_for,
        idempotency_key=key,
    )
    try:
        notification.save()
    except IntegrityError:
        # Lost a race with another identical job run — reuse the existing row.
        existing = Notification.objects.get(idempotency_key=key)
        existing._created = False
        return existing
    notification._created = True
    return notification


def _ref_type(payment, invitation, rent_period):
    if payment:
        return 'payment'
    if invitation:
        return 'invitation'
    if rent_period:
        return 'rent_period'
    return None


def _ref_id(payment, invitation, rent_period):
    if payment:
        return payment.id
    if invitation:
        return invitation.id
    if rent_period:
        return rent_period.id
    return None


# ---------------------------------------------------------------------------
# Email delivery
# ---------------------------------------------------------------------------

def send_notification_email(notification):
    """Send an email for a notification via the existing email seam.

    Returns True on success, False on failure.  Email failure never raises
    an exception — it is logged in the notification's error_message field.
    """
    from core.services import send_email

    try:
        send_email(
            subject=notification.title,
            message=notification.message,
            recipient=notification.recipient.email,
        )
        notification.status = NotificationStatus.SENT
        notification.sent_at = timezone.now()
        notification.save(update_fields=['status', 'sent_at', 'updated_at'])
        return True
    except Exception as exc:
        notification.status = NotificationStatus.FAILED
        notification.error_message = str(exc)
        notification.save(update_fields=['status', 'error_message', 'updated_at'])
        return False


# ---------------------------------------------------------------------------
# Preference helpers
# ---------------------------------------------------------------------------

def _email_enabled(user):
    """Return True if the user has email notifications enabled."""
    try:
        pref = NotificationPreference.objects.get(user=user)
        return pref.email_enabled
    except NotificationPreference.DoesNotExist:
        return True  # default when no preference record exists


def _in_app_enabled(user):
    """Return True if the user has in-app notifications enabled."""
    try:
        pref = NotificationPreference.objects.get(user=user)
        return pref.in_app_enabled
    except NotificationPreference.DoesNotExist:
        return True


# ---------------------------------------------------------------------------
# Lease expiry notification generation
# ---------------------------------------------------------------------------

# Map: (days_relative_to_expiry, notification_type, title_template, message_template)
# Positive = before expiry, 0 = on expiry day, negative = after expiry.
LEASE_REMINDER_RULES = [
    (30, NotificationType.LEASE_EXPIRY_30D,
     'Lease expiring in 30 days',
     'The lease for {property_name} ({unit_name}) expires on {expiry_date}. '
     'Please review and take necessary action.'),
    (7, NotificationType.LEASE_EXPIRY_7D,
     'Lease expiring in 7 days',
     'The lease for {property_name} ({unit_name}) expires on {expiry_date}. '
     'Please review and take necessary action.'),
    (0, NotificationType.LEASE_EXPIRY_DAY,
     'Lease expires today',
     'The lease for {property_name} ({unit_name}) expires today ({expiry_date}). '
     'Please take necessary action.'),
    (-7, NotificationType.LEASE_EXPIRY_7D_AFTER,
     'Lease expired 7 days ago',
     'The lease for {property_name} ({unit_name}) expired on {expiry_date}. '
     'Please renew or terminate the lease.'),
    (-14, NotificationType.LEASE_EXPIRY_14D_AFTER,
     'Lease expired 14 days ago',
     'The lease for {property_name} ({unit_name}) expired on {expiry_date}. '
     'Please renew or terminate the lease.'),
    (-21, NotificationType.LEASE_EXPIRY_21D_AFTER,
     'Lease expired 21 days ago',
     'The lease for {property_name} ({unit_name}) expired on {expiry_date}. '
     'Please renew or terminate the lease.'),
    (-28, NotificationType.LEASE_EXPIRY_28D_AFTER,
     'Lease expired 28 days ago',
     'The lease for {property_name} ({unit_name}) expired on {expiry_date}. '
     'Please renew or terminate the lease.'),
]


def generate_lease_notifications(today=None):
    """Generate lease expiry notifications for all eligible leases.

    Returns a summary dict: {created: int, skipped: int}.
    """
    from leases.models import Lease, LeaseStatus

    today = today or timezone.localdate()
    created = 0
    skipped = 0

    # Only leases that are not terminated and not yet renewed (no lease
    # pointing to them as previous_lease) should generate reminders.
    # ACTIVE / EXPIRING / EXPIRED / FUTURE leases are candidates.
    # TERMINATED leases are excluded.
    # Leases that have been renewed (another lease has previous_lease=them)
    # should still generate reminders for the OLD lease until it's terminated,
    # because the old lease is still the active financial obligation.
    # Actually, per spec: "leases that have already been renewed/replaced
    # where the old lease should no longer generate reminders" — but only
    # if the old lease is TERMINATED. Since renewal doesn't auto-terminate,
    # we include non-terminated leases that haven't been superseded.

    # Find leases that have been superseded (another lease points to them
    # as previous_lease AND that new lease is not terminated).
    superseded_ids = set(
        Lease.objects.filter(
            previous_lease__isnull=False,
            status__in=[LeaseStatus.ACTIVE, LeaseStatus.EXPIRING, LeaseStatus.FUTURE],
        ).values_list('previous_lease_id', flat=True)
    )

    # All non-terminated leases
    leases = Lease.objects.select_related(
        'landlord', 'tenant', 'property', 'unit',
    ).exclude(status=LeaseStatus.TERMINATED)

    for lease in leases:
        days_until_expiry = (lease.expiry_date - today).days

        for days_offset, ntype, title_tpl, msg_tpl in LEASE_REMINDER_RULES:
            # days_offset > 0 means BEFORE expiry (days_until_expiry == days_offset)
            # days_offset == 0 means ON expiry day
            # days_offset < 0 means AFTER expiry (days_until_expiry == days_offset)
            if days_until_expiry != days_offset:
                continue

            # Skip expired-day notifications for superseded leases
            if days_offset < 0 and lease.pk in superseded_ids:
                continue

            ctx = {
                'property_name': lease.property.name,
                'unit_name': lease.unit.name,
                'expiry_date': str(lease.expiry_date),
                'tenant_name': lease.tenant.full_name,
                'landlord_name': lease.landlord.full_name,
            }

            # Notify landlord
            if _in_app_enabled(lease.landlord):
                n = create_notification(
                    recipient=lease.landlord,
                    notification_type=ntype,
                    channel=NotificationChannel.IN_APP,
                    title=title_tpl,
                    message=msg_tpl.format(**ctx),
                    lease=lease,
                    scheduled_for=timezone.now(),
                )
                if n._created:
                    created += 1
                else:
                    skipped += 1

            if _email_enabled(lease.landlord):
                n = create_notification(
                    recipient=lease.landlord,
                    notification_type=ntype,
                    channel=NotificationChannel.EMAIL,
                    title=title_tpl,
                    message=msg_tpl.format(**ctx),
                    lease=lease,
                    scheduled_for=timezone.now(),
                )
                if n._created:
                    created += 1
                else:
                    skipped += 1

            # Notify tenant
            if _in_app_enabled(lease.tenant):
                n = create_notification(
                    recipient=lease.tenant,
                    notification_type=ntype,
                    channel=NotificationChannel.IN_APP,
                    title=title_tpl,
                    message=msg_tpl.format(**ctx),
                    lease=lease,
                    scheduled_for=timezone.now(),
                )
                if n._created:
                    created += 1
                else:
                    skipped += 1

            if _email_enabled(lease.tenant):
                n = create_notification(
                    recipient=lease.tenant,
                    notification_type=ntype,
                    channel=NotificationChannel.EMAIL,
                    title=title_tpl,
                    message=msg_tpl.format(**ctx),
                    lease=lease,
                    scheduled_for=timezone.now(),
                )
                if n._created:
                    created += 1
                else:
                    skipped += 1

    return {'created': created, 'skipped': skipped}


# ---------------------------------------------------------------------------
# Rent notification generation
# ---------------------------------------------------------------------------

# (days_offset_from_due, notification_type, title, message)
# Positive = before due, 0 = on due day, negative = overdue.
RENT_REMINDER_RULES = [
    (7, NotificationType.RENT_UPCOMING_7D,
     'Rent due in 7 days',
     'Rent of {currency} {amount} for {property_name} ({unit_name}) '
     'is due on {due_date}.'),
    (3, NotificationType.RENT_UPCOMING_3D,
     'Rent due in 3 days',
     'Rent of {currency} {amount} for {property_name} ({unit_name}) '
     'is due on {due_date}.'),
    (0, NotificationType.RENT_DUE_DAY,
     'Rent due today',
     'Rent of {currency} {amount} for {property_name} ({unit_name}) '
     'is due today ({due_date}).'),
    (-3, NotificationType.RENT_OVERDUE_3D,
     'Rent overdue by 3 days',
     'Rent of {currency} {amount} for {property_name} ({unit_name}) '
     'was due on {due_date} and is now overdue.'),
    (-7, NotificationType.RENT_OVERDUE_7D,
     'Rent overdue by 7 days',
     'Rent of {currency} {amount} for {property_name} ({unit_name}) '
     'was due on {due_date} and is now overdue.'),
    (-14, NotificationType.RENT_OVERDUE_14D,
     'Rent overdue by 14 days',
     'Rent of {currency} {amount} for {property_name} ({unit_name}) '
     'was due on {due_date} and is now overdue.'),
]


def generate_rent_notifications(today=None):
    """Generate rent due/overdue notifications for all eligible rent periods.

    Only periods that are NOT fully paid generate notifications.
    Uses the existing payments.services.period_status() for financial truth.

    Returns a summary dict: {created: int, skipped: int}.
    """
    from leases.models import LeaseStatus
    from payments.models import RentPeriodStatus, RentSchedule
    from payments.services import period_status

    today = today or timezone.localdate()
    created = 0
    skipped = 0

    # Find all rent periods with due dates that are relevant
    # (from 14 days overdue to 7 days before due).
    # Exclude terminated leases — they should not generate rent reminders.
    relevant_periods = RentSchedule.objects.select_related(
        'lease', 'lease__landlord', 'lease__tenant',
        'lease__property', 'lease__unit',
    ).filter(
        due_date__gte=today - timedelta(days=14),
        due_date__lte=today + timedelta(days=7),
    ).exclude(
        lease__status=LeaseStatus.TERMINATED,
    )

    for period in relevant_periods:
        status = period_status(period, today)
        days_until_due = (period.due_date - today).days

        # Only notify for unpaid/partially paid periods
        if status in (RentPeriodStatus.PAID,):
            continue

        for days_offset, ntype, title_tpl, msg_tpl in RENT_REMINDER_RULES:
            if days_until_due != days_offset:
                continue

            # Determine if overdue notification should fire:
            # Overdue notifications only fire when status is OVERDUE or PARTIALLY_PAID
            if days_offset < 0 and status not in (
                RentPeriodStatus.OVERDUE, RentPeriodStatus.PARTIALLY_PAID,
            ):
                continue

            ctx = {
                'property_name': period.lease.property.name,
                'unit_name': period.lease.unit.name,
                'due_date': str(period.due_date),
                'amount': str(period.amount),
                'currency': period.currency,
                'tenant_name': period.lease.tenant.full_name,
                'landlord_name': period.lease.landlord.full_name,
            }

            # Notify landlord
            if _in_app_enabled(period.lease.landlord):
                n = create_notification(
                    recipient=period.lease.landlord,
                    notification_type=ntype,
                    channel=NotificationChannel.IN_APP,
                    title=title_tpl,
                    message=msg_tpl.format(**ctx),
                    lease=period.lease,
                    rent_period=period,
                    scheduled_for=timezone.now(),
                )
                if n._created:
                    created += 1
                else:
                    skipped += 1

            if _email_enabled(period.lease.landlord):
                n = create_notification(
                    recipient=period.lease.landlord,
                    notification_type=ntype,
                    channel=NotificationChannel.EMAIL,
                    title=title_tpl,
                    message=msg_tpl.format(**ctx),
                    lease=period.lease,
                    rent_period=period,
                    scheduled_for=timezone.now(),
                )
                if n._created:
                    created += 1
                else:
                    skipped += 1

            # Notify tenant
            if _in_app_enabled(period.lease.tenant):
                n = create_notification(
                    recipient=period.lease.tenant,
                    notification_type=ntype,
                    channel=NotificationChannel.IN_APP,
                    title=title_tpl,
                    message=msg_tpl.format(**ctx),
                    lease=period.lease,
                    rent_period=period,
                    scheduled_for=timezone.now(),
                )
                if n._created:
                    created += 1
                else:
                    skipped += 1

            if _email_enabled(period.lease.tenant):
                n = create_notification(
                    recipient=period.lease.tenant,
                    notification_type=ntype,
                    channel=NotificationChannel.EMAIL,
                    title=title_tpl,
                    message=msg_tpl.format(**ctx),
                    lease=period.lease,
                    rent_period=period,
                    scheduled_for=timezone.now(),
                )
                if n._created:
                    created += 1
                else:
                    skipped += 1

    return {'created': created, 'skipped': skipped}
