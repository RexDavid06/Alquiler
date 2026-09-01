"""Tenant profile and invitation domain models.

Tenants join only through a landlord invitation. Invitations are secure,
unpredictable, time-limited and single-use.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import default_invitation_expiry, generate_token_chars


class TenantProfile(models.Model):
    """The tenant-specific profile, linked to a User with role TENANT.

    The source of truth for landlord/tenant relationships is the Lease
    domain (a tenant may have leases with different landlords over time).
    This profile only holds tenant-scoped extras, not landlord ownership.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='tenant_profile',
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.full_name} ({self.user.email})'


class InvitationStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    ACCEPTED = 'ACCEPTED', 'Accepted'
    REVOKED = 'REVOKED', 'Revoked'
    EXPIRED = 'EXPIRED', 'Expired'
    USED = 'USED', 'Used'


class TenantInvitation(models.Model):
    """A single-use, time-limited invitation from a landlord to a prospective
    tenant for a specific unit."""

    landlord = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='tenant_invitations', limit_choices_to={'role': 'LANDLORD'},
    )
    email = models.EmailField(db_index=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    property = models.ForeignKey(
        'properties.Property', on_delete=models.CASCADE, related_name='invitations',
    )
    unit = models.ForeignKey(
        'properties.Unit', on_delete=models.CASCADE, related_name='invitations',
    )
    token = models.CharField(
        max_length=64, unique=True, default=generate_token_chars, editable=False,
    )
    status = models.CharField(
        max_length=20, choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
    )
    expires_at = models.DateTimeField(default=default_invitation_expiry)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='accepted_invitations',
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['landlord', 'status']),
        ]

    def __str__(self):
        return f'Invitation to {self.email} for {self.unit}'

    def is_expired(self):
        return timezone.now() > self.expires_at

    def is_usable(self):
        return (
            self.status == InvitationStatus.PENDING
            and not self.is_expired()
        )
