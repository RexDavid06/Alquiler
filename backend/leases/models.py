"""Lease (tenancy) domain models.

A lease ties one landlord, tenant, property and unit together with rent
terms. Lease status is partly derived from dates (ACTIVE / EXPIRING /
EXPIRED) and partly explicit (TERMINATED). Renewal creates a new lease and
links it to the previous one; historical leases are never overwritten.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import date


class LeaseStatus(models.TextChoices):
    FUTURE = 'FUTURE', 'Future'
    ACTIVE = 'ACTIVE', 'Active'
    EXPIRING = 'EXPIRING', 'Expiring'
    EXPIRED = 'EXPIRED', 'Expired'
    TERMINATED = 'TERMINATED', 'Terminated'


class RentFrequency(models.TextChoices):
    MONTHLY = 'MONTHLY', 'Monthly'
    QUARTERLY = 'QUARTERLY', 'Quarterly'
    BI_ANNUALLY = 'BI_ANNUALLY', 'Bi-annually'
    ANNUALLY = 'ANNUALLY', 'Annually'


class Lease(models.Model):
    landlord = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='landlord_leases', limit_choices_to={'role': 'LANDLORD'},
    )
    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='tenant_leases', limit_choices_to={'role': 'TENANT'},
    )
    property = models.ForeignKey(
        'properties.Property', on_delete=models.PROTECT, related_name='leases',
    )
    unit = models.ForeignKey(
        'properties.Unit', on_delete=models.PROTECT, related_name='leases',
    )
    start_date = models.DateField()
    expiry_date = models.DateField()
    rent_amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default='NGN')
    rent_frequency = models.CharField(
        max_length=20, choices=RentFrequency.choices, default=RentFrequency.MONTHLY,
    )
    rent_due_day = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(
        max_length=20, choices=LeaseStatus.choices, default=LeaseStatus.ACTIVE,
    )
    previous_lease = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='renewals',
    )
    notes = models.TextField(blank=True)
    terminated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['landlord', 'status']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['unit', 'start_date', 'expiry_date']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(expiry_date__gte=models.F('start_date')),
                name='lease_expiry_after_start',
            ),
            models.CheckConstraint(
                condition=models.Q(currency__regex=r'^[A-Z]{3}$'),
                name='lease_currency_iso3',
            ),
            models.CheckConstraint(
                condition=models.Q(rent_due_day__gte=1) & models.Q(rent_due_day__lte=28),
                name='lease_rent_due_day_range',
            ),
            models.CheckConstraint(
                condition=models.Q(rent_amount__gte=0),
                name='lease_rent_amount_non_negative',
            ),
        ]

    def __str__(self):
        return f'{self.tenant.email} @ {self.unit} ({self.start_date}–{self.expiry_date})'

    def effective_status(self):
        """Return the derived lifecycle status.

        A lease is FUTURE while its start date has not been reached. Once it
        begins it is ACTIVE, moves to EXPIRING within 30 days of the end, and
        becomes EXPIRED the day after expiry. TERMINATED is explicit and never
        overridden by dates. Derived from dates so callers never trust a
        client-supplied status.
        """
        if self.status == LeaseStatus.TERMINATED:
            return LeaseStatus.TERMINATED
        today = timezone.localdate()
        if self.start_date > today:
            return LeaseStatus.FUTURE
        days_left = (self.expiry_date - today).days
        if days_left < 0:
            return LeaseStatus.EXPIRED
        if days_left <= 30:
            return LeaseStatus.EXPIRING
        return LeaseStatus.ACTIVE

    def refresh_status(self):
        """Persist the derived status where it differs from the stored one."""
        derived = self.effective_status()
        if derived != self.status:
            self.status = derived
            self.save(update_fields=['status', 'updated_at'])
        return self.status

    def days_remaining(self):
        if self.status == LeaseStatus.TERMINATED:
            return 0
        return (self.expiry_date - timezone.localdate()).days
