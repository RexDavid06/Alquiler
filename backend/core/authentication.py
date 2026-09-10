"""Custom token authentication with configurable expiry.

Extends DRF's built-in TokenAuthentication to reject tokens older than
AUTH_TOKEN_EXPIRY_DAYS. No migration required — uses the existing
``rest_framework.authtoken.Token.created`` field.
"""

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class ExpiringTokenAuthentication(TokenAuthentication):
    """TokenAuthentication that rejects expired tokens.

    Token lifetime is controlled by the ``AUTH_TOKEN_EXPIRY_DAYS`` setting
    (default: 7). Expired tokens are deleted on detection so they cannot
    be reused.
    """

    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)

        expiry_days = getattr(settings, 'AUTH_TOKEN_EXPIRY_DAYS', 7)
        if token.created < timezone.now() - timezone.timedelta(days=expiry_days):
            token.delete()
            raise AuthenticationFailed(
                'Token has expired. Please log in again.',
                code='token_expired',
            )

        return user, token
