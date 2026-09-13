"""
Core application: shared domain primitives.

Defines the custom User model (roles), base model mixins, enums, and
cross-cutting helpers used by all domain apps.
"""

from datetime import timedelta
import secrets

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


class Token(models.Model):
    """A bearer access token, one per device (Phase 11A).

    Replaces DRF's ``rest_framework.authtoken.Token``, whose unique
    ``user`` constraint capped the system at ONE token per user and made
    independent, per-device sessions impossible.  ``key``, ``created``,
    and ``user`` keep DRF's shape so ``ExpiringTokenAuthentication`` and
    existing ``Token <key>`` clients are unaffected.
    """

    key = models.CharField(max_length=40, primary_key=True, verbose_name='Key')
    created = models.DateTimeField(auto_now_add=True, verbose_name='Created')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='auth_token', verbose_name='User',
    )

    class Meta:
        verbose_name = 'Token'
        verbose_name_plural = 'Tokens'
        ordering = ['-created']

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        return super().save(*args, **kwargs)

    @classmethod
    def generate_key(cls):
        return secrets.token_hex(20)

    def __str__(self):
        return self.key


class DeviceSession(models.Model):
    """One authenticated device for a user (Phase 11A multi-device auth).

    Pairs a short-lived access token (``core.Token``) with a rotating,
    hashed refresh credential.  A user may hold many sessions (one per
    device) at once; each session is revoked independently.  Logging in
    from a second device never invalidates the first.

    The refresh credential is stored only as a SHA-256 hash and rotates on
    every use, so a rotated-out credential cannot be replayed (reuse after
    rotation revokes the whole session).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='device_sessions',
    )
    access_token = models.OneToOneField(
        'core.Token', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='device_session',
        help_text='Short-lived access token for this device. Deleted on expiry/logout.',
    )
    device_id = models.CharField(max_length=64)
    device_name = models.CharField(max_length=100, default='')
    refresh_token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    previous_refresh_token_hash = models.CharField(max_length=64, blank=True, default='')
    refresh_expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, default='')

    class Meta:
        ordering = ['-last_used_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'device_id'], name='uniq_user_device_session',
            ),
        ]

    def __str__(self):
        return f'{self.user.email} — {self.device_name or self.device_id}'


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
