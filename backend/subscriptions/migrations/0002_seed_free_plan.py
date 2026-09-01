"""Seed the default FREE subscription plan.

The FREE plan is the fallback assigned to every newly registered landlord
(see subscriptions.services.ensure_landlord_subscription). Seeding it here
guarantees the plan exists before any landlord registers, so the invariant
"every landlord has a subscription" cannot be violated.
"""

from django.db import migrations


def seed_free_plan(apps, schema_editor):
    Plan = apps.get_model('subscriptions', 'Plan')
    Plan.objects.update_or_create(
        tier='FREE',
        defaults={
            'name': 'Free',
            'description': (
                'Up to 3 active tenants, property management, lease '
                'management, rent tracking, email and in-app notifications.'
            ),
            'max_active_tenants': 3,
            'max_properties': 1,
            'price_ngn': 0,
            'is_active': True,
            'display_order': 0,
        },
    )


def unseed_free_plan(apps, schema_editor):
    Plan = apps.get_model('subscriptions', 'Plan')
    Plan.objects.filter(tier='FREE').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_free_plan, unseed_free_plan),
    ]
