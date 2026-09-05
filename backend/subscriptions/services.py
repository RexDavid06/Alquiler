"""Subscription domain services.

Ensures every landlord has a subscription and provides limit-checking
primitives that the Phase 2/3 service and view layers will use. Plan prices
and limits are read from the database (never hardcoded in the frontend).
"""

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.exceptions import ConflictError, ForbiddenError, NotFoundError

from .models import (
    Plan,
    PlanTier,
    Subscription,
    SubscriptionStatus,
    VALID_STATUS_TRANSITIONS,
)


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
            f'{sub.plan.max_properties} {_plural("property", sub.plan.max_properties)}. '
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


# ---------------------------------------------------------------------------
# Phase 8: Subscription lifecycle services
# ---------------------------------------------------------------------------

def _validate_status_transition(current_status, target_status):
    """Raise if the status transition is not allowed."""
    allowed = VALID_STATUS_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise ConflictError(
            f'Cannot transition from {current_status} to {target_status}.',
            code='invalid_status_transition',
        )


def _log_subscription_change(landlord, action, detail):
    """Create an AuditLog entry for a subscription lifecycle event."""
    from core.models import AuditLog
    sub = Subscription.objects.filter(landlord=landlord).first()
    AuditLog.objects.create(
        actor=landlord,
        action=action,
        object_type='Subscription',
        object_id=sub.id if sub else None,
        detail=detail,
    )


def get_available_plans():
    """Return active plans ordered by display_order."""
    return Plan.objects.filter(is_active=True).order_by('display_order', 'price_ngn')


@transaction.atomic
def upgrade_subscription(landlord, new_plan, billing_cycle=None):
    """Upgrade (or change) a landlord's subscription plan.

    - FREE -> paid: starts a trial period.
    - paid -> higher paid: immediate change, no new trial.
    - same plan: rejected.
    - cancelled/expired: reactivation via upgrade.
    """
    sub = get_subscription(landlord)

    if new_plan.tier == sub.plan.tier:
        raise ConflictError(
            'You are already on this plan.',
            code='already_on_plan',
        )

    if not new_plan.is_active:
        raise NotFoundError(
            'The selected plan is not available.',
            code='plan_inactive',
        )

    now = timezone.now()
    is_paid_plan = new_plan.tier != PlanTier.FREE
    is_from_free = sub.plan.tier == PlanTier.FREE

    # Determine the new status
    if is_paid_plan and is_from_free:
        # FREE -> paid: start trial
        trial_days = getattr(settings, 'TRIAL_DURATION_DAYS', 14)
        new_status = SubscriptionStatus.TRIAL
        trial_end = now + timezone.timedelta(days=trial_days)
    elif is_paid_plan and not is_from_free:
        # paid -> different paid: active immediately (no new trial)
        new_status = SubscriptionStatus.ACTIVE
        trial_end = None
    else:
        # paid -> FREE: active immediately
        new_status = SubscriptionStatus.ACTIVE
        trial_end = None

    old_plan_name = sub.plan.name
    sub.plan = new_plan
    sub.status = new_status
    sub.trial_end = trial_end
    sub.current_period_start = now
    if billing_cycle:
        sub.billing_cycle = billing_cycle
    sub.cancelled_at = None
    sub.cancel_reason = ''
    sub.save(update_fields=[
        'plan', 'status', 'trial_end', 'current_period_start',
        'billing_cycle', 'cancelled_at', 'cancel_reason', 'updated_at',
    ])

    _log_subscription_change(landlord, 'SUBSCRIPTION_CHANGED', {
        'action': 'upgrade',
        'from_plan': old_plan_name,
        'to_plan': new_plan.name,
        'status': new_status,
    })

    return sub


@transaction.atomic
def downgrade_subscription(landlord, new_plan, billing_cycle=None):
    """Downgrade a landlord's subscription plan.

    Downgrade is allowed even when current usage exceeds the target plan's
    limits. Existing resources are NOT deleted. Plan limits are enforced on
    NEW resource creation after the downgrade.
    """
    sub = get_subscription(landlord)

    if new_plan.tier == sub.plan.tier:
        raise ConflictError(
            'You are already on this plan.',
            code='already_on_plan',
        )

    if not new_plan.is_active:
        raise NotFoundError(
            'The selected plan is not available.',
            code='plan_inactive',
        )

    now = timezone.now()
    old_plan_name = sub.plan.name
    sub.plan = new_plan
    sub.current_period_start = now
    if billing_cycle:
        sub.billing_cycle = billing_cycle
    sub.save(update_fields=[
        'plan', 'current_period_start', 'billing_cycle', 'updated_at',
    ])

    _log_subscription_change(landlord, 'SUBSCRIPTION_CHANGED', {
        'action': 'downgrade',
        'from_plan': old_plan_name,
        'to_plan': new_plan.name,
    })

    return sub


@transaction.atomic
def cancel_subscription(landlord, reason=''):
    """Cancel a landlord's subscription.

    Cancellation transitions to CANCELLED status. Existing resources are
    preserved. The landlord cannot create new resources that require a
    subscription after cancellation.
    """
    sub = get_subscription(landlord)

    _validate_status_transition(sub.status, SubscriptionStatus.CANCELLED)

    now = timezone.now()
    sub.status = SubscriptionStatus.CANCELLED
    sub.cancelled_at = now
    sub.cancel_reason = reason
    sub.save(update_fields=[
        'status', 'cancelled_at', 'cancel_reason', 'updated_at',
    ])

    _log_subscription_change(landlord, 'SUBSCRIPTION_CHANGED', {
        'action': 'cancel',
        'plan': sub.plan.name,
        'reason': reason,
    })

    return sub


@transaction.atomic
def reactivate_subscription(landlord):
    """Reactivate a cancelled or expired subscription (to the same plan).

    Transitions CANCELLED/EXPIRED -> ACTIVE. Existing resources are
    unaffected.
    """
    sub = get_subscription(landlord)

    _validate_status_transition(sub.status, SubscriptionStatus.ACTIVE)

    now = timezone.now()
    sub.status = SubscriptionStatus.ACTIVE
    sub.cancelled_at = None
    sub.cancel_reason = ''
    sub.current_period_start = now
    sub.save(update_fields=[
        'status', 'cancelled_at', 'cancel_reason',
        'current_period_start', 'updated_at',
    ])

    _log_subscription_change(landlord, 'SUBSCRIPTION_CHANGED', {
        'action': 'reactivate',
        'plan': sub.plan.name,
    })

    return sub


@transaction.atomic
def check_trial_expiry(landlord):
    """Check and expire a trial subscription if the trial period has ended.

    Returns the subscription. If the trial has expired, status is transitioned
    to EXPIRED and an audit log is created. FREE plan trials never expire.
    """
    sub = get_subscription(landlord)

    if sub.status != SubscriptionStatus.TRIAL:
        return sub

    if sub.plan.tier == PlanTier.FREE:
        return sub

    if sub.trial_end is None:
        return sub

    if timezone.now() < sub.trial_end:
        return sub

    # Trial has expired
    sub.status = SubscriptionStatus.EXPIRED
    sub.save(update_fields=['status', 'updated_at'])

    _log_subscription_change(landlord, 'SUBSCRIPTION_CHANGED', {
        'action': 'trial_expired',
        'plan': sub.plan.name,
        'trial_end': sub.trial_end.isoformat(),
    })

    return sub
