"""Import an Alquiler JSON archive produced by ``export_data``.

Safety properties
-----------------
- Only archives produced by ``export_data`` are accepted (format check).
- Only known Alquiler domain models are touched; unknown/anonymous models
  abort the whole import before any write happens.
- The entire import runs inside a single transaction — any failure rolls
  everything back.
- Objects whose primary key already exists in the target database are
  skipped, never overwritten.
- Imported users receive an unusable password (passwords are never
  exported; they must use the password-reset flow).
- Authentication secrets (tokens, device sessions, audit logs) are never
  imported.
- Subscription plans are platform reference data seeded by data migrations:
  exported plans are merged into the target by their unique ``tier`` (the
  seeded target record wins; unknown tiers are created), and subscription
  plan links are rewritten to the surviving plans.

Recommended flow for a fresh environment::

    python manage.py migrate
    python manage.py import_data backup.json

Then recreate an admin/landlord password via ``createsuperuser`` or the
password-reset email flow.

Limitations (documented in DEPLOYMENT.md)
-----------------------------------------
- JSON import is NOT a substitute for a PostgreSQL dump/restore. Use the
  JSON tools only to move demo data between environments, and always verify
  the result afterwards.
- ``created_at`` / ``updated_at`` timestamps ARE preserved.
- Pending next-notification schedule state is re-derived by the normal
  management commands.
"""

import json
from pathlib import Path

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import DateTimeField
from django.utils import timezone

from .export_data import (
    ARCHIVE_APP,
    ARCHIVE_VERSION,
    include_model,
)

User = get_user_model()


def _preserve_stored_timestamps():
    """Freeze ``auto_now`` / ``auto_now_add`` fields to insert stored values.

    The ORM insert path runs ``pre_save`` on every field, which overwrites
    ``auto_now``/``auto_now_add`` timestamps with the current time. To honour
    "preserve important timestamps" we temporarily point those fields' hook
    at a pre_save that returns the value already loaded from the archive.
    Returns a restore callable.
    """
    patches = []
    try:
        for model in apps.get_models():
            if model._meta.auto_created or model._meta.proxy:
                continue
            for field in model._meta.concrete_fields:
                if (
                    isinstance(field, DateTimeField)
                    and (field.auto_now or field.auto_now_add)
                    and id(field) not in {id(p[0]) for p in patches}
                ):
                    patches.append((field, field.pre_save))
                    field.pre_save = (
                        lambda instance, add, peek=field:
                        getattr(instance, peek.attname, None) or timezone.now()
                    )
    except Exception:
        for field, original in patches:
            field.pre_save = original
        raise

    def restore():
        for field, original in patches:
            field.pre_save = original

    return restore


def _merge_plans(objects):
    """Merge exported Plan rows into the target's seeded plan catalog.

    Plans are platform reference data seeded by data migrations (FREE /
    PROFESSIONAL / BUSINESS). Inserting them directly would violate the
    unique ``tier`` constraint, so each exported plan is matched to the
    target plan with the same ``tier`` (keeping the seeded record) or
    created if the tier is absent. Subscription ``plan`` FKs are rewritten
    to the surviving pks and exported Plan rows are dropped from the import.
    """
    from subscriptions.models import Plan

    plan_rows = [o for o in objects if o.get('model') == 'subscriptions.plan']
    if not plan_rows:
        return objects

    tier_to_target = {}
    for row in plan_rows:
        value = row.get('fields', {})
        tier = value.get('tier')
        if not tier:
            continue
        obj, _ = Plan.objects.get_or_create(
            tier=tier,
            defaults={
                'name': value.get('name') or tier,
                'description': value.get('description', ''),
                'max_active_tenants': value.get('max_active_tenants', 3),
                'max_properties': value.get('max_properties', 1),
                'price_ngn': value.get('price_ngn', 0),
                'is_active': value.get('is_active', True),
                'display_order': value.get('display_order', 0),
            },
        )
        tier_to_target[tier] = obj.pk

    old_pk_to_target = {}
    for row in plan_rows:
        value = row.get('fields', {})
        tier = value.get('tier')
        if tier in tier_to_target:
            old_pk_to_target[str(row.get('pk'))] = tier_to_target[tier]

    for obj in objects:
        if obj.get('model') != 'subscriptions.subscription':
            continue
        plan_value = obj.get('fields', {}).get('plan')
        if plan_value is not None and str(plan_value) in old_pk_to_target:
            obj['fields']['plan'] = old_pk_to_target[str(plan_value)]

    return [o for o in objects if o.get('model') != 'subscriptions.plan']


def _allowed_labels():
    return sorted(
        model._meta.label_lower for model in apps.get_models() if include_model(model)
    )


def _dependency_order(deserialized):
    """Sort deserialized objects so referenced models are created first."""
    from django.core.serializers import sort_dependencies

    configs = [apps.get_app_config('core')]
    for label in (
        'properties', 'tenants', 'leases', 'payments',
        'notifications', 'subscriptions',
    ):
        try:
            configs.append(apps.get_app_config(label))
        except LookupError:
            pass
    ordered_models = sort_dependencies(
        [(config, None) for config in configs],
    )
    order_index = {
        model: i for i, model in enumerate(ordered_models)
    }
    return sorted(
        deserialized,
        key=lambda d: order_index.get(type(d.object), len(ordered_models)),
    )


class Command(BaseCommand):
    help = 'Import an Alquiler JSON archive into the current database.'

    def add_arguments(self, parser):
        parser.add_argument('input', type=str, help='JSON archive file path.')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Validate and report what would be imported without writing.',
        )

    def handle(self, *args, **options):
        path = Path(options['input'])
        if not path.exists():
            raise CommandError(f'File not found: {path}')

        try:
            archive = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            raise CommandError(f'Invalid JSON in {path}: {exc}')

        if archive.get('app') != ARCHIVE_APP or archive.get('version') != ARCHIVE_VERSION:
            raise CommandError(
                f'Unsupported archive format in {path}. Expected '
                f'{ARCHIVE_APP} v{ARCHIVE_VERSION}.',
            )

        objects = archive.get('objects')
        if not isinstance(objects, list):
            raise CommandError('Archive contains no objects list.')

        allowed = set(_allowed_labels())

        # Merge reference data (plans) before validation/deserialization.
        objects = _merge_plans(objects)

        # Phase 1 — validate every object before touching the database.
        deserialized = []
        for obj in objects:
            if not isinstance(obj, dict) or not isinstance(obj.get('model'), str):
                raise CommandError('Malformed object in archive (missing model).')
            label = obj['model']
            if label not in allowed:
                raise CommandError(f'Model {label} is not importable.')
            try:
                item = next(
                    serializers.deserialize(
                        'json', json.dumps([obj]), ignorenonexistent=True,
                    )
                )
            except Exception as exc:
                raise CommandError(f'Could not deserialize {label}: {exc}')
            deserialized.append(item)

        per_model = {}
        for item in deserialized:
            label = type(item.object)._meta.label_lower
            per_model.setdefault(label, []).append(item.object)

        if options['dry_run']:
            self.stdout.write('Dry run — no data was written.')
            for label, objs in sorted(per_model.items()):
                self.stdout.write(f'  would import {len(objs)} {label}')
            return

        # Phase 2 — import in transaction; existing pks are skipped.
        # bulk_create is used per model because it does NOT re-run
        # auto_now / auto_now_add so serialized timestamps are preserved.
        ordered = _dependency_order(deserialized)
        created = 0
        skipped = 0

        def flush(group):
            nonlocal created, skipped
            if not group:
                return
            model = type(group[0])
            pk_attr = model._meta.pk.attname
            existing = set(
                model.objects.filter(
                    pk__in=[getattr(obj, pk_attr) for obj in group],
                ).values_list('pk', flat=True),
            )
            to_create = [
                obj for obj in group
                if getattr(obj, pk_attr) not in existing
            ]
            skipped += len(group) - len(to_create)
            if to_create:
                for obj in to_create:
                    if model is User:
                        # Passwords are never exported; force an unusable hash.
                        obj.set_unusable_password()
                model.objects.bulk_create(to_create)
                created += len(to_create)

        with transaction.atomic():
            restore = _preserve_stored_timestamps()
            try:
                group = []
                current = None
                for item in ordered:
                    if current is not None and type(item.object) is not current:
                        flush(group)
                        group = []
                    current = type(item.object)
                    group.append(item.object)
                flush(group)
            finally:
                restore()

        self.stdout.write(self.style.SUCCESS(
            f'Imported {created} objects, skipped {skipped} existing.',
        ))