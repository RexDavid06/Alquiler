"""Device/session services for multi-device token auth (Phase 11A).

Access tokens are the short-lived ``core.Token`` (checked by
``ExpiringTokenAuthentication``).  Each device owns a ``DeviceSession`` row
that pairs one access token with a rotating, hashed refresh credential.

Security properties:
- Refresh credentials are stored only as SHA-256 hashes (never plaintext).
- Refresh credentials rotate on every use; presenting a rotated-out
  credential revokes the whole session (reuse detection).
- Logging in from a second device never touches the first device's session.
- Sessions are individually revocable; logout revokes only the current one.
"""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed

from core.models import AccountStatus, DeviceSession, Token


def _hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _new_refresh_token():
    return secrets.token_hex(32)


def _refresh_ttl():
    return timedelta(days=getattr(settings, 'AUTH_REFRESH_TOKEN_TTL_DAYS', 90))


def _expires_in_seconds():
    return getattr(settings, 'AUTH_TOKEN_EXPIRY_DAYS', 7) * 86400


def _extract_ip(request):
    if request is None:
        return None
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()[:45] or None
    return request.META.get('REMOTE_ADDR') or None


def _extract_user_agent(request, max_length=255):
    if request is None:
        return ''
    return request.META.get('HTTP_USER_AGENT', '')[:max_length]


def create_device_session(*, user, device_id=None, device_name=None, request=None):
    """Create (or refresh) the device session for ``user``.

    Does NOT delete other devices' tokens.  Re-login from the same
    ``device_id`` replaces only that device's session/access token.

    Returns ``(session, access_token_key, refresh_token, device_id)``.
    """
    device_id = (device_id or secrets.token_hex(16)).strip()[:64] or secrets.token_hex(16)
    if device_name is None:
        device_name = _extract_user_agent(request, 100) or 'Unknown device'
    device_name = device_name.strip()[:100] or 'Unknown device'

    session = DeviceSession.objects.filter(
        user=user, device_id=device_id,
    ).first()
    if session is None:
        session = DeviceSession.objects.create(
            user=user,
            device_id=device_id,
            refresh_token_hash=_hash(_new_refresh_token()),
            refresh_expires_at=timezone.now(),
        )

    # Same-device re-login: drop the stale access token only (other
    # devices are untouched).
    if session.access_token_id:
        session.access_token.delete()

    access = Token.objects.create(user=user)
    refresh = _new_refresh_token()
    now = timezone.now()
    session.access_token = access
    session.device_name = device_name
    session.refresh_token_hash = _hash(refresh)
    session.previous_refresh_token_hash = ''
    session.refresh_expires_at = now + _refresh_ttl()
    session.revoked_at = None
    session.last_used_at = now
    session.ip_address = _extract_ip(request)
    session.user_agent = _extract_user_agent(request)
    session.save()

    _trim_excess_sessions(user, keep=session)
    return session, access.key, refresh, device_id


def _trim_excess_sessions(user, *, keep):
    """Enforce AUTH_DEVICE_LIMIT by revoking the oldest inactive sessions."""
    limit = getattr(settings, 'AUTH_DEVICE_LIMIT', 20)
    if not limit:
        return
    active = list(
        DeviceSession.objects.filter(user=user, revoked_at__isnull=True)
        .order_by('-last_used_at', '-created_at')
    )
    excess = [s for s in active if s.pk != keep.pk][limit - 1:]
    for session in excess:
        if session.access_token_id:
            session.access_token.delete()
            session.access_token = None
        session.revoked_at = timezone.now()
        session.save(update_fields=['revoked_at'])


def refresh_access_token(*, device_id, refresh_token, request=None):
    """Rotate the device session's credentials.

    Returns ``(new_access_token_key, new_refresh_token)``.

    Raises ``AuthenticationFailed`` (401) for invalid, expired, revoked, or
    replayed credentials.  Replay of a rotated-out credential revokes the
    entire session.
    """
    if not refresh_token:
        raise AuthenticationFailed(
            'Refresh token is required.', code='invalid_refresh_token',
        )
    hashed = _hash(refresh_token)
    now = timezone.now()

    session = (
        DeviceSession.objects.select_related('user')
        .filter(
            user__is_active=True,
            user__status=AccountStatus.ACTIVE,
            device_id=device_id,
            revoked_at__isnull=True,
            refresh_expires_at__gt=now,
        )
        .filter(refresh_token_hash=hashed)
        .first()
    )
    if session is not None:
        return _rotate_session(session, request)

    # Reuse detection: a rotated-out credential is a replay/breach signal.
    reused = (
        DeviceSession.objects.select_related('user')
        .filter(
            device_id=device_id,
            revoked_at__isnull=True,
            previous_refresh_token_hash=hashed,
        )
        .first()
    )
    if reused is not None:
        reused.revoked_at = now
        reused.save(update_fields=['revoked_at'])
        if reused.access_token_id:
            reused.access_token.delete()
        raise AuthenticationFailed('Session revoked.', code='session_revoked')

    raise AuthenticationFailed(
        'Invalid or expired refresh token.', code='invalid_refresh_token',
    )


@transaction.atomic
def _rotate_session(session, request):
    """Replace the access token and rotate the refresh credential."""
    if session.access_token_id:
        session.access_token.delete()

    access = Token.objects.create(user=session.user)
    new_refresh = _new_refresh_token()
    now = timezone.now()
    session.previous_refresh_token_hash = session.refresh_token_hash
    session.refresh_token_hash = _hash(new_refresh)
    session.access_token = access
    session.refresh_expires_at = now + _refresh_ttl()
    session.last_used_at = now
    session.ip_address = _extract_ip(request)
    session.user_agent = _extract_user_agent(request)
    session.save()
    return access.key, new_refresh


def revoke_session_for_token(token):
    """Revoke the device session that owns ``token`` (no-op for legacy tokens)."""
    session = DeviceSession.objects.filter(access_token=token).first()
    if session is not None:
        session.revoked_at = timezone.now()
        session.save(update_fields=['revoked_at'])


def revoke_all_sessions(user):
    """Revoke every active device session for ``user`` (all devices).

    Access tokens are deleted separately by callers so the FK is cleared.
    """
    DeviceSession.objects.filter(user=user, revoked_at__isnull=True).update(
        revoked_at=timezone.now(),
    )