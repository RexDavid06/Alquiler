"""Subscription domain services.

Ensures every landlord has a subscription and provides limit-checking
primitives that the Phase 2/3 service and view layers will use. Plan prices
and limits are read from the database (never hardcoded in the frontend).
"""

from django.db import transaction

from core.exceptions import ForbiddenError

from .models import Plan, PlanTier, Subscription, SubscriptionStatus


def get_default_free_plan():
    """Return the FREE plan, raising if it has not been seeded."""
    plan = Plan.objects.filter(tier=PlanTier.FREE, is_active=True).first()
    if plan is None:
        raise ForbiddenError(
            'The FREE plan has not been configured. Please contact support.',
            code='plan_unavailable',
        )
    return plan


@transaction.atomic
def ensure_landlord_subscription(landlord):
    """Guarantee a landlord always has a subscription.

    If one already exists it is returned unchanged; otherwise the landlord is
    subscribed to the FREE plan. Called on landlord registration and safe to
    call defensively before operations requiring a subscription.
    """
    sub = Subscription.objects.filter(landlord=landlord).first()
    if sub is not None:
        return sub
    plan = get_default_free_plan()
    return Subscription.objects.create(landlord=landlord, plan=plan)


def get_subscription(landlord):
    sub = Subscription.objects.filter(landlord=landlord).first()
    if sub is not None:
        return sub
    # Defensive: a landlord without a subscription is an invariant violation.
    return ensure_landlord_subscription(landlord)


def assert_can_add_property(landlord):
    """Raise if the landlord's plan limit for properties is reached."""
    sub = get_subscription(landlord)
    if sub.property_count >= sub.plan.max_properties:
        raise ForbiddenError(
            f'Plan limit reached: the {sub.plan.name} plan allows up to '
            f'{sub.plan.max_properties} {_plural('property', sub.plan.max_properties)}. '
            'Upgrade your plan to continue.',
            code='property_limit_reached',
        )


def assert_can_add_tenant(landlord):
    """Raise if the landlord's plan limit for active tenants is reached."""
    sub = get_subscription(landlord)
    if not sub.can_add_tenant:
        raise ForbiddenError(
            f'Plan limit reached: the {sub.plan.name} plan allows up to '
            f'{sub.plan.max_active_tenants} active tenants. '
            'Upgrade your plan to continue.',
            code='tenant_limit_reached',
        )


def assert_can_add_lease_tenant(landlord, tenant):
    """Raise if creating a lease for `tenant` exceeds the active-tenant cap.

    A tenant already holding a live lease is not re-counted, so a landlord can
    hold multiple leases for the same tenant without consuming extra quota.
    FUTURE leases do not count - the cap applies to active/expiring tenancies.
    """
    from leases.models import Lease, LeaseStatus

    sub = get_subscription(landlord)
    active_ids = set(
        Lease.objects.filter(
            landlord=landlord,
            status__in=[LeaseStatus.ACTIVE, LeaseStatus.EXPIRING],
        ).values_list('tenant_id', flat=True)
    )
    if tenant.id not in active_ids and len(active_ids) >= sub.plan.max_active_tenants:
        raise ForbiddenError(
            f'Plan limit reached: the {sub.plan.name} plan allows up to '
            f'{sub.plan.max_active_tenants} active tenants. '
            'Upgrade your plan to continue.',
            code='tenant_limit_reached',
        )


def _plural(word, count):
    return word if count == 1 else word + 's'


def serialize_usage(subscription):
    """Return usage metrics for a landlord's subscription (dashboard/UI)."""
    return {
        'max_active_tenants': subscription.plan.max_active_tenants,
        'active_tenants': subscription.active_tenants_count,
        'max_properties': subscription.plan.max_properties,
        'properties': subscription.property_count,
    }
