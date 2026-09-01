"""Core cross-cutting services.

Provides a thin email-dispatch wrapper so that Phase 6 can route mail
through the notification service without restructuring callers.
"""

from django.conf import settings
from django.core.mail import send_mail as django_send_mail
from django.utils import timezone


def send_email(*, subject, message, recipient, html_message=None):
    """Send a transactional email.

    Currently dispatches through Django's configured mail backend. This is
    the seam where the notification service (EMAIL channel, persisted
    Notification records, PENDING->SENT/FAILED tracking) will attach in
    Phase 6. Callers should not bypass this function with send_mail directly.
    """
    return django_send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        html_message=html_message,
        fail_silently=False,
    )
