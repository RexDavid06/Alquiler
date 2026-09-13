"""Custom token authentication with configurable expiry.

Extends DRF's built-in TokenAuthentication to reject tokens older than
AUTH_TOKEN_EXPIRY_DAYS.  Uses the project's own ``core.Token`` model (which
supports many tokens per user, one per device) instead of DRF's legacy
one-token-per-user ``authtoken.Token``.
"""

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from core.models import AccountStatus, Token


class ExpiringTokenAuthentication(TokenAuthentication):
    """TokenAuthentication that rejects expired tokens.

    Token lifetime is controlled by the ``AUTH_TOKEN_EXPIRY_DAYS`` setting
    (default: 7). Expired tokens are deleted on detection so they cannot
    be reused.

    Account status is enforced at the authentication layer so that a user
    whose account is not ACTIVE (for example SUSPENDED) is denied access
    immediately, even if they still hold a valid, unexpired token.
    """

    model = Token

    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)

        if user.status != AccountStatus.ACTIVE:
            raise AuthenticationFailed(
                'This account is not active.',
                code='account_not_active',
            )

        expiry_days = getattr(settings, 'AUTH_TOKEN_EXPIRY_DAYS', 7)
        if token.created < timezone.now() - timezone.timedelta(days=expiry_days):
            token.delete()
            raise AuthenticationFailed(
                'Token has expired. Please log in again.',
                code='token_expired',
            )

        return user, token
