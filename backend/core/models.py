"""
Core application: shared domain primitives.

Defines the custom User model (roles), base model mixins, enums, and
cross-cutting helpers used by all domain apps.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager


class Role(models.TextChoices):
    PLATFORM_ADMIN = 'PLATFORM_ADMIN', 'Platform Admin'
    LANDLORD = 'LANDLORD', 'Landlord'
    TENANT = 'TENANT', 'Tenant'


class AccountStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    ACTIVE = 'ACTIVE', 'Active'
    SUSPENDED = 'SUSPENDED', 'Suspended'
    DEACTIVATED = 'DEACTIVATED', 'Deactivated'


class Currency(models.TextChoices):
    NGN = 'NGN', 'Nigerian Naira'
    USD = 'USD', 'US Dollar'
    GBP = 'GBP', 'British Pound'
    EUR = 'EUR', 'Euro'


class User(AbstractBaseUser, PermissionsMixin):
    """A single authentication principal for all roles on the platform."""

    email = models.EmailField(unique=True, db_index=True)
    role = models.CharField(max_length=20, choices=Role.choices)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    status = models.CharField(
        max_length=20, choices=AccountStatus.choices, default=AccountStatus.PENDING
    )
    email_verified = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['role', 'first_name', 'last_name']

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def is_landlord(self):
        return self.role == Role.LANDLORD

    @property
    def is_tenant(self):
        return self.role == Role.TENANT

    @property
    def is_platform_admin(self):
        return self.role == Role.PLATFORM_ADMIN

    def activate(self):
        self.status = AccountStatus.ACTIVE
        self.is_active = True
        self.save(update_fields=['status', 'is_active', 'updated_at'])


class TimeStampedModel(models.Model):
    """Abstract base adding created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditLog(models.Model):
    """Immutable record of important platform events."""

    ACTOR_ROLE_CHOICES = Role.choices
    ACTIONS = [
        ('INVITATION_CREATED', 'Invitation created'),
        ('INVITATION_ACCEPTED', 'Invitation accepted'),
        ('LEASE_CREATED', 'Lease created'),
        ('LEASE_RENEWED', 'Lease renewed'),
        ('LEASE_TERMINATED', 'Lease terminated'),
        ('PAYMENT_CREATED', 'Payment created'),
        ('PAYMENT_UPDATED', 'Payment updated'),
        ('SUBSCRIPTION_CHANGED', 'Subscription changed'),
        ('PROPERTY_CREATED', 'Property created'),
        ('UNIT_CREATED', 'Unit created'),
        ('ACCOUNT_CREATED', 'Account created'),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='audit_logs',
    )
    action = models.CharField(max_length=40, choices=ACTIONS)
    object_type = models.CharField(max_length=40)
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['object_type', 'object_id']),
        ]

    def __str__(self):
        return f'{self.action} {self.object_type}#{self.object_id}'


class NotificationPreference(models.Model):
    """Per-user channel preferences for notifications."""

    CHANNELS = [
        ('email', 'Email'),
        ('in_app', 'In-app'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notification_preferences',
    )
    email_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.email} preferences'


# Used by invitation tokens and other single-use, time-limited secrets.
def generate_token_chars(n=32):
    import secrets
    import string
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(n))


def default_invitation_expiry():
    from django.conf import settings as s
    return timezone.now() + timedelta(hours=s.INVITATION_TOKEN_TTL_HOURS)
