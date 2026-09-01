"""Notification domain services (foundation).

Provides the deterministic idempotency-key builder and a persistence/delivery
primitive that the scheduled reminders (Phase 6) will use. Idempotency keys
are always generated here - never supplied by clients.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Notification, NotificationChannel, NotificationStatus


def build_idempotency_key(*, recipient_id, notification_type, scheduled_date=None,
                          lease_id=None, ref_type=None, ref_id=None):
    """Build a deterministic idempotency key.

    The key combines the recipient, notification type, and the calendar day
    the notification is scheduled for, plus an optional related resource. Two
    identical jobs (e.g. the scheduler running twice on the same day) therefore
    produce the same key and the DB unique constraint prevents a duplicate.
    """
    day = scheduled_date or timezone.localdate()
    parts = [recipient_id, notification_type, day.isoformat()]
    if lease_id is not None:
        parts.append(f'lease:{lease_id}')
    if ref_type and ref_id is not None:
        parts.append(f'{ref_type}:{ref_id}')
    return '|'.join(str(p) for p in parts)


@transaction.atomic
def create_notification(*, recipient, notification_type, channel, title, message,
                        lease=None, payment=None, invitation=None,
                        scheduled_for=None, key_parts=None):
    """Persist a notification with a deterministic idempotency key.

    If a notification with the same idempotency key already exists, the call
    is a no-op (returns the existing row). This makes scheduled reminder
    generation idempotent and safe against duplicate job execution.
    """
    key = build_idempotency_key(
        recipient_id=recipient.id,
        notification_type=notification_type,
        scheduled_date=scheduled_for,
        lease_id=lease.id if lease else None,
        ref_type=payment and 'payment' or (invitation and 'invitation'),
        ref_id=(payment and payment.id) or (invitation and invitation.id),
        **(key_parts or {}),
    )
    existing = Notification.objects.filter(idempotency_key=key).first()
    if existing:
        return existing

    notification = Notification(
        recipient=recipient,
        notification_type=notification_type,
        channel=channel,
        status=NotificationStatus.PENDING,
        lease=lease,
        payment=payment,
        invitation=invitation,
        title=title,
        message=message,
        scheduled_for=scheduled_for,
        idempotency_key=key,
    )
    try:
        notification.save()
    except IntegrityError:
        # Lost a race with another identical job run - reuse the existing row.
        return Notification.objects.get(idempotency_key=key)
    return notification
