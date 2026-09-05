"""Subscription / SaaS plan domain models.

SaaS billing is entirely separate from tenant rent payments.
The architecture supports future Paystack subscription billing.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class PlanTier(models.TextChoices):
    FREE = 'FREE', 'Free'
    PROFESSIONAL = 'PROFESSIONAL', 'Professional'
    BUSINESS = 'BUSINESS', 'Business'


class PlanStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    INACTIVE = 'INACTIVE', 'Inactive'


class SubscriptionStatus(models.TextChoices):
    TRIAL = 'TRIAL', 'Trial'
    ACTIVE = 'ACTIVE', 'Active'
    PAST_DUE = 'PAST_DUE', 'Past due'
    CANCELLED = 'CANCELLED', 'Cancelled'
    EXPIRED = 'EXPIRED', 'Expired'


class BillingCycle(models.TextChoices):
    MONTHLY = 'MONTHLY', 'Monthly'
    QUARTERLY = 'QUARTERLY', 'Quarterly'
    ANNUALLY = 'ANNUALLY', 'Annually'


# Valid status transitions: from status -> set of allowed target statuses.
# INVALID transitions should raise a DomainError in services.
VALID_STATUS_TRANSITIONS = {
    SubscriptionStatus.TRIAL: {
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.CANCELLED,
        SubscriptionStatus.EXPIRED,
    },
    SubscriptionStatus.ACTIVE: {
        SubscriptionStatus.PAST_DUE,
        SubscriptionStatus.CANCELLED,
    },
    SubscriptionStatus.PAST_DUE: {
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.CANCELLED,
        SubscriptionStatus.EXPIRED,
    },
    SubscriptionStatus.CANCELLED: {
        SubscriptionStatus.ACTIVE,  # reactivation
    },
    SubscriptionStatus.EXPIRED: {
        SubscriptionStatus.ACTIVE,  # reactivation
    },
}


class Plan(models.Model):
    """A subscription plan offered to landlords. Configurable via DB/admin."""

    tier = models.CharField(
        max_length=20, choices=PlanTier.choices, unique=True,
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    max_active_tenants = models.PositiveIntegerField(default=3)
    max_properties = models.PositiveIntegerField(default=1)
    price_ngn = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Price per billing period in NGN.',
    )
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'price_ngn']

    def __str__(self):
        return self.name


class Subscription(models.Model):
    """A landlord's active subscription to a plan."""

    landlord = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='subscription', limit_choices_to={'role': 'LANDLORD'},
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    status = models.CharField(
        max_length=20, choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.TRIAL,
    )
    billing_cycle = models.CharField(
        max_length=20, choices=BillingCycle.choices,
        default=BillingCycle.MONTHLY,
    )
    started_at = models.DateTimeField(default=timezone.now)
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.landlord.email} → {self.plan.name} [{self.status}]'

    @property
    def is_trial_expired(self):
        """True if this subscription is on a paid plan and the trial has ended."""
        if self.status != SubscriptionStatus.TRIAL:
            return False
        if self.plan.tier == PlanTier.FREE:
            return False
        if self.trial_end is None:
            return False
        return timezone.now() >= self.trial_end

    @property
    def is_cancelled(self):
        return self.status == SubscriptionStatus.CANCELLED

    @property
    def is_active_subscription(self):
        """True if the subscription allows resource creation."""
        return self.status in (
            SubscriptionStatus.TRIAL,
            SubscriptionStatus.ACTIVE,
        )

    @property
    def active_tenants_count(self):
        """Count active leases for this landlord's tenant."""
        from leases.models import Lease, LeaseStatus
        return Lease.objects.filter(
            landlord=self.landlord,
            status__in=[LeaseStatus.ACTIVE, LeaseStatus.EXPIRING],
        ).values('tenant').distinct().count()

    @property
    def can_add_tenant(self):
        return self.active_tenants_count < self.plan.max_active_tenants

    @property
    def property_count(self):
        return self.landlord.properties.count()

    @property
    def can_add_property(self):
        return self.property_count < self.plan.max_properties
