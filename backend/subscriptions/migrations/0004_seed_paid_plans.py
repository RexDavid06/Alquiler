"""Seed the PROFESSIONAL and BUSINESS subscription plans.

These plans are offered to landlords who need more than the FREE plan limits.
Plan prices and limits are configurable via the admin after seeding.
"""

from django.db import migrations


def seed_paid_plans(apps, schema_editor):
    Plan = apps.get_model('subscriptions', 'Plan')
    Plan.objects.update_or_create(
        tier='PROFESSIONAL',
        defaults={
            'name': 'Professional',
            'description': (
                'Up to 10 active tenants, 5 properties, priority support, '
                'advanced reporting.'
            ),
            'max_active_tenants': 10,
            'max_properties': 5,
            'price_ngn': 15000.00,
            'is_active': True,
            'display_order': 1,
        },
    )
    Plan.objects.update_or_create(
        tier='BUSINESS',
        defaults={
            'name': 'Business',
            'description': (
                'Unlimited active tenants, 20 properties, dedicated support, '
                'full reporting, API access.'
            ),
            'max_active_tenants': 50,
            'max_properties': 20,
            'price_ngn': 45000.00,
            'is_active': True,
            'display_order': 2,
        },
    )


def unseed_paid_plans(apps, schema_editor):
    Plan = apps.get_model('subscriptions', 'Plan')
    Plan.objects.filter(tier__in=['PROFESSIONAL', 'BUSINESS']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('subscriptions', '0003_subscription_billing_cycle_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_paid_plans, unseed_paid_plans),
    ]
