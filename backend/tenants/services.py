"""Tenant invitation and onboarding domain services.

Tenants are created and activated only through a landlord invitation. The
invitation token is the single granting mechanism: it is validated (status,
expiry, single-use, matching email) before any account is created. The
tenant's relationship to property/unit is derived from the lease domain, not
from client-supplied input.
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from core.exceptions import ConflictError, DomainError, NotFoundError
from core.models import AccountStatus, AuditLog, NotificationPreference, Role
from leases.services import unit_has_active_tenancy
from subscriptions.services import assert_can_add_tenant

from .models import InvitationStatus, TenantInvitation, TenantProfile

User = get_user_model()


def resolve_invitation(token):
    """Return a validated, usable invitation or raise a clean error."""
    try:
        invitation = TenantInvitation.objects.select_related(
            'landlord', 'property', 'unit',
        ).get(token=token)
    except TenantInvitation.DoesNotExist:
        raise NotFoundError('Invitation not found.', code='invitation_not_found')

    if invitation.status == InvitationStatus.REVOKED:
        raise DomainError(
            'This invitation has been revoked.', code='invitation_revoked',
        )
    if invitation.status in (InvitationStatus.ACCEPTED, InvitationStatus.USED):
        raise DomainError(
            'This invitation has already been used.', code='invitation_used',
        )
    if invitation.status == InvitationStatus.EXPIRED or invitation.is_expired():
        # Normalize stored state if we discover it is expired.
        if invitation.status != InvitationStatus.EXPIRED:
            invitation.status = InvitationStatus.EXPIRED
            invitation.save(update_fields=['status', 'updated_at'])
        raise DomainError(
            'This invitation has expired.', code='invitation_expired',
        )
    return invitation


@transaction.atomic
def create_invitation(*, landlord, email, property, unit,
                      first_name='', last_name='', phone=''):
    """Send an invitation for a specific unit, enforcing the business rules.

    * The landlord's subscription tenant limit is enforced server-side
      (assert_can_add_tenant). Invitations themselves are NOT counted as
      active tenants - the limit is measured against active leases.
    * A unit with an active/expiring tenancy cannot legally receive a new
      tenant, so invitations to occupied units are refused.
    * At most one pending scaffolding to (unit, email) may exist at a time;
      landlords resend instead, which replaces the previous token.
    """
    assert_can_add_tenant(landlord)

    if unit_has_active_tenancy(unit):
        raise ConflictError(
            f'Unit "{unit.name}" currently has an active tenancy and cannot '
            'receive a new tenant invitation.',
            code='unit_occupied',
        )

    email = email.strip().lower()
    pending = TenantInvitation.objects.filter(
        landlord=landlord, unit=unit, email__iexact=email,
        status=InvitationStatus.PENDING,
        expires_at__gt=timezone.now(),
    ).exists()
    if pending:
        raise ConflictError(
            'An active invitation already exists for this unit and email. '
            'Resend it to issue a new token.',
            code='invitation_already_pending',
        )

    invitation = TenantInvitation.objects.create(
        landlord=landlord, email=email,
        first_name=first_name, last_name=last_name, phone=phone,
        property=property, unit=unit,
    )
    AuditLog.objects.create(
        actor=landlord, action='INVITATION_CREATED',
        object_type='TenantInvitation', object_id=invitation.id,
        detail={'email': email, 'unit': unit.id},
    )
    return invitation


@transaction.atomic
def resend_invitation(invitation):
    """Replace an invitation with a new token, expiring the previous one.

    A resend never leaves multiple valid active tokens: the old invitation is
    marked EXPIRED and a fresh invitation (new single-use token, new expiry)
    is issued for the same destination. Used or revoked invitations cannot be
    resent.
    """
    if invitation.status in (InvitationStatus.ACCEPTED, InvitationStatus.USED):
        raise DomainError(
            'This invitation has already been used and cannot be resent.',
            code='invitation_used',
        )
    if invitation.status == InvitationStatus.REVOKED:
        raise DomainError(
            'This invitation has been revoked and cannot be resent.',
            code='invitation_revoked',
        )

    invitation.status = InvitationStatus.EXPIRED
    invitation.save(update_fields=['status', 'updated_at'])

    return TenantInvitation.objects.create(
        landlord=invitation.landlord,
        email=invitation.email,
        first_name=invitation.first_name,
        last_name=invitation.last_name,
        phone=invitation.phone,
        property=invitation.property,
        unit=invitation.unit,
    )


@transaction.atomic
def revoke_invitation(invitation):
    """Revoke a PENDING (or time-expired) invitation, if it is still revocable."""
    if invitation.status in (InvitationStatus.ACCEPTED, InvitationStatus.USED):
        raise DomainError(
            'This invitation has already been used and cannot be revoked.',
            code='invitation_used',
        )
    if invitation.status == InvitationStatus.REVOKED:
        raise DomainError(
            'This invitation is already revoked.', code='invitation_revoked',
        )
    invitation.status = InvitationStatus.REVOKED
    invitation.save(update_fields=['status', 'updated_at'])
    return invitation


@transaction.atomic
def accept_invitation(token, *, first_name, last_name, phone, password):
    """Create/activate the tenant for a valid invitation and consume it.

    Returns the (user, invitation) tuple. The invitation is single-use: once
    accepted it leaves the PENDING state and can never be accepted again.
    """
    invitation = resolve_invitation(token)

    existing = User.objects.filter(email__iexact=invitation.email).first()
    if existing is not None and existing.role != Role.TENANT:
        raise DomainError(
            'An account with this email already exists and is not a tenant.',
            code='email_in_use',
        )

    user = existing
    if user is None:
        user = User(
            email=invitation.email.lower(),
            role=Role.TENANT,
            first_name=first_name or invitation.first_name,
            last_name=last_name or invitation.last_name,
            phone=phone or invitation.phone,
        )
        user.set_password(password)
        user.status = AccountStatus.ACTIVE
        user.is_active = True
        user.save()
    else:
        # Existing tenant user: update profile, ensure active.
        user.first_name = first_name or user.first_name
        user.last_name = last_name or user.last_name
        if phone:
            user.phone = phone
        user.status = AccountStatus.ACTIVE
        user.is_active = True
        if password:
            user.set_password(password)
        user.save()

    if not TenantProfile.objects.filter(user=user).exists():
        TenantProfile.objects.create(user=user)
    NotificationPreference.objects.get_or_create(user=user)

    # Consume the invitation (single-use).
    invitation.accepted_by = user
    invitation.accepted_at = timezone.now()
    invitation.status = InvitationStatus.ACCEPTED
    invitation.save(update_fields=['accepted_by', 'accepted_at', 'status', 'updated_at'])

    AuditLog.objects.create(
        actor=user, action='INVITATION_ACCEPTED',
        object_type='TenantInvitation', object_id=invitation.id,
        detail={'invitation_token': token, 'email': invitation.email},
    )
    return user, invitation
