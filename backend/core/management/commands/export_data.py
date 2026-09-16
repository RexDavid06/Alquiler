"""Export Alquiler application data to a portable JSON archive.

This tool is a convenience for moving DEMO data between environments.
It is deliberately NOT the authoritative backup mechanism.

AUTHORITATIVE MIGRATION MECHANISM
---------------------------------
PostgreSQL dump/restore (see DEPLOYMENT.md -> "Database backup and restore").
JSON is a best-effort application-level copy and can never replace a real
database dump.

What is exported
----------------
All Alquiler application models (core, properties, tenants, leases,
payments, notifications, subscriptions) with relationships preserved by
primary key.

What is deliberately NOT exported
---------------------------------
- ``core.Token`` / ``core.DeviceSession`` — authentication secrets.
- ``core.AuditLog`` — operational records, not domain data.
- User ``password`` values — imported users get an unusable password and
  must reset it through the password-reset flow.
- API keys / SMTP credentials — those live in environment variables, never
  in the database.

Usage::

    python manage.py export_data --output backup.json
"""

import json
from pathlib import Path

from django.apps import apps
from django.core import serializers
from django.core.management.base import BaseCommand
from django.utils import timezone

# Authentication-bound models are never exported.
EXCLUDED_MODELS = {
    ('core', 'Token'),
    ('core', 'DeviceSession'),
    ('core', 'AuditLog'),
}

# Fields stripped from user objects on export.
SENSITIVE_USER_FIELDS = {'password'}

ARCHIVE_APP = 'alquiler-data'
ARCHIVE_VERSION = 1


def model_key(model):
    return (model._meta.app_label, model.__name__)


def include_model(model):
    """Only migrateable Alquiler domain models (no proxy/autofield tables)."""
    if model._meta.auto_created or model._meta.proxy:
        return False
    if model_key(model) in EXCLUDED_MODELS:
        return False
    app_label = model._meta.app_label
    return app_label in {
        'core', 'properties', 'tenants', 'leases', 'payments',
        'notifications', 'subscriptions',
    }


class Command(BaseCommand):
    help = 'Export Alquiler application data to a JSON archive.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output', '-o', type=str, default='backup.json',
            help='Output JSON file path (default: backup.json).',
        )

    def handle(self, *args, **options):
        output = Path(options['output'])
        output.parent.mkdir(parents=True, exist_ok=True)

        models = sorted(
            (m for m in apps.get_models() if include_model(m)),
            key=lambda m: (m._meta.app_label, m.__name__),
        )

        objects = []
        for model in models:
            raw = serializers.serialize(
                'json', model._default_manager.all(), indent=2,
            )
            items = json.loads(raw)
            if model_key(model) == ('core', 'User'):
                items = self._strip_user_passwords(items)
            objects.extend(items)

        archive = {
            'app': ARCHIVE_APP,
            'version': ARCHIVE_VERSION,
            'exported_at': timezone.now().isoformat(),
            'objects': objects,
        }
        output.write_text(json.dumps(archive, indent=2), encoding='utf-8')

        counts = {}
        for obj in objects:
            counts[obj['model']] = counts.get(obj['model'], 0) + 1
        self.stdout.write(self.style.SUCCESS(
            f'Exported {len(objects)} objects to {output}',
        ))
        for model_name, count in sorted(counts.items()):
            self.stdout.write(f'  {model_name}: {count}')

    def _strip_user_passwords(self, items):
        for obj in items:
            obj['fields'] = {
                key: value for key, value in obj['fields'].items()
                if key not in SENSITIVE_USER_FIELDS
            }
        return items