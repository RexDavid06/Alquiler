"""Management command to generate and send rent due/overdue notifications.

Safe to execute repeatedly — deterministic idempotency keys prevent
duplicate notifications.  Designed to be triggered by a cron job or
process scheduler.

Usage:
    python manage.py send_rent_notifications
    python manage.py send_rent_notifications --today 2026-09-04
    python manage.py send_rent_notifications --send-emails
"""

from django.core.management.base import BaseCommand

from notifications.services import generate_rent_notifications, send_notification_email
from notifications.models import Notification, NotificationChannel, NotificationStatus


class Command(BaseCommand):
    help = 'Generate rent due/overdue notifications for eligible rent periods.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--today',
            type=str,
            default=None,
            help='Override the current date (YYYY-MM-DD) for testing.',
        )
        parser.add_argument(
            '--send-emails',
            action='store_true',
            default=False,
            help='Also dispatch EMAIL-channel notifications that are PENDING.',
        )

    def handle(self, *args, **options):
        today_override = None
        if options['today']:
            from datetime import date
            today_override = date.fromisoformat(options['today'])

        result = generate_rent_notifications(today=today_override)
        self.stdout.write(
            self.style.SUCCESS(
                f"Rent notifications: created={result['created']}, "
                f"skipped={result['skipped']}"
            )
        )

        if options['send_emails']:
            pending = Notification.objects.filter(
                channel=NotificationChannel.EMAIL,
                status=NotificationStatus.PENDING,
            )
            sent = 0
            failed = 0
            for notification in pending:
                if send_notification_email(notification):
                    sent += 1
                else:
                    failed += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"Email dispatch: sent={sent}, failed={failed}"
                )
            )
