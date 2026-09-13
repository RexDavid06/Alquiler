"""Phase 11A — Multi-device session & token refresh tests.

Covers:
- multi-device coexistence and per-device logout
- refresh flow (rotation, expired-access recovery, rejection paths)
- refresh-token reuse detection (replay revokes the session)
- global revocation on password change / password reset
- backward compatibility for legacy tokens created without a session
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase, override_settings
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient

from core.models import AccountStatus, DeviceSession, Token

User = get_user_model()

BASE = '/api/v1/auth/'


def _make_user(email='sess@example.com', role='LANDLORD', password='pass12345',
               **kwargs):
    return User.objects.create_user(
        email=email, password=password, role=role,
        first_name=kwargs.pop('first_name', 'Test'),
        last_name=kwargs.pop('last_name', 'User'),
        status=kwargs.pop('status', 'ACTIVE'),
        is_active=kwargs.pop('is_active', True),
        **kwargs,
    )


def _login(client, email, password, device_id):
    return client.post(BASE + 'login/', {
        'email': email, 'password': password, 'device_id': device_id,
    })


class MultiDeviceTests(TestCase):
    """Two devices can stay logged in simultaneously and log out independently."""

    def setUp(self):
        self.client = APIClient()
        self.user = _make_user(email='multi@example.com')

    def test_login_returns_refresh_credentials(self):
        resp = _login(self.client, 'multi@example.com', 'pass12345', 'dev-a')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(all(k in resp.data for k in (
            'token', 'refresh_token', 'device_id', 'expires_in',
        )))
        self.assertEqual(resp.data['device_id'], 'dev-a')

    def test_two_devices_coexist(self):
        a = _login(self.client, 'multi@example.com', 'pass12345', 'dev-a').data
        b = _login(self.client, 'multi@example.com', 'pass12345', 'dev-b').data
        self.assertNotEqual(a['token'], b['token'])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {a['token']}")
        me_a = self.client.get(BASE + 'me/')
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {b['token']}")
        me_b = self.client.get(BASE + 'me/')
        self.assertEqual(me_a.status_code, 200)
        self.assertEqual(me_b.status_code, 200)
        self.assertEqual(Token.objects.filter(user=self.user).count(), 2)

    def test_logout_revokes_only_the_logging_out_device(self):
        a = _login(self.client, 'multi@example.com', 'pass12345', 'dev-a').data
        b = _login(self.client, 'multi@example.com', 'pass12345', 'dev-b').data

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {a['token']}")
        resp = self.client.post(BASE + 'logout/')
        self.assertEqual(resp.status_code, 200)

        self.assertFalse(Token.objects.filter(key=a['token']).exists())
        self.assertTrue(Token.objects.filter(key=b['token']).exists())
        self.assertFalse(DeviceSession.objects.filter(
            user=self.user, device_id='dev-a', revoked_at__isnull=True,
        ).exists())
        self.assertTrue(DeviceSession.objects.filter(
            user=self.user, device_id='dev-b', revoked_at__isnull=True,
        ).exists())

    def test_factory_device_limit_revokes_oldest(self):
        with override_settings(AUTH_DEVICE_LIMIT=2):
            _login(self.client, 'multi@example.com', 'pass12345', 'dev-a')
            _login(self.client, 'multi@example.com', 'pass12345', 'dev-b')
            third = _login(
                self.client, 'multi@example.com', 'pass12345', 'dev-c',
            ).data
            self.assertTrue(Token.objects.filter(key=third['token']).exists())
            active = DeviceSession.objects.filter(
                user=self.user, revoked_at__isnull=True,
            )
            self.assertEqual(active.count(), 2)
            self.assertFalse(active.filter(device_id='dev-a').exists())


class RefreshTests(TestCase):
    """Refresh rotates credentials and recovers from access-token expiry."""

    def setUp(self):
        self.client = APIClient()
        self.user = _make_user(email='refresh@example.com')
        data = _login(
            self.client, 'refresh@example.com', 'pass12345', 'dev-a',
        ).data
        self.access_a = data['token']
        self.refresh_a = data['refresh_token']
        self.device_id = data['device_id']

    def _refresh(self, device_id=None, refresh_token=None):
        return self.client.post(BASE + 'refresh/', {
            'device_id': device_id or self.device_id,
            'refresh_token': refresh_token if refresh_token is not None else self.refresh_a,
        })

    def test_refresh_rotates_both_credentials(self):
        resp = self._refresh()
        self.assertEqual(resp.status_code, 200)
        new_access = resp.data['token']
        new_refresh = resp.data['refresh_token']
        self.assertNotEqual(new_access, self.access_a)
        self.assertNotEqual(new_refresh, self.refresh_a)
        # Old access token is gone; new one authenticates.
        self.assertFalse(Token.objects.filter(key=self.access_a).exists())
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {new_access}')
        self.assertEqual(self.client.get(BASE + 'me/').status_code, 200)

    def test_refresh_recovers_expired_access_token(self):
        # Expire the access token (simulate 8 days passing) but keep refresh valid.
        Token.objects.filter(key=self.access_a).update(
            created=timezone.now() - timedelta(days=8),
        )
        resp = self._refresh()
        self.assertEqual(resp.status_code, 200)
        # The refreshed access token authenticates.
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {resp.data['token']}")
        self.assertEqual(self.client.get(BASE + 'me/').status_code, 200)

    def test_refresh_wrong_credential_rejected(self):
        resp = self._refresh(refresh_token='not-the-real-token')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_unknown_device_rejected(self):
        resp = self._refresh(device_id='no-such-device')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_missing_fields_rejected(self):
        resp = self.client.post(BASE + 'refresh/', {})
        self.assertEqual(resp.status_code, 400)

    def test_refresh_rejected_after_logout(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.access_a}')
        self.client.post(BASE + 'logout/')
        resp = self._refresh()
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_expired_refresh_credential_rejected(self):
        DeviceSession.objects.filter(user=self.user).update(
            refresh_expires_at=timezone.now() - timedelta(days=1),
        )
        resp = self._refresh()
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_reuse_after_rotation_revokes_session(self):
        first = self._refresh().data
        # Replay the ORIGINAL refresh credential (already rotated out).
        resp = self.client.post(BASE + 'refresh/', {
            'device_id': self.device_id,
            'refresh_token': self.refresh_a,
        })
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        # Entire session revoked, including the newly-issued access token.
        self.assertFalse(Token.objects.filter(key=first['token']).exists())
        self.assertFalse(DeviceSession.objects.filter(
            user=self.user, revoked_at__isnull=True,
        ).exists())


class GlobalRevocationTests(TestCase):
    """Password change / reset revoke every device."""

    def setUp(self):
        self.client = APIClient()
        self.user = _make_user(email='revoke@example.com', password='OldP@ss123')
        self.a = _login(self.client, 'revoke@example.com', 'OldP@ss123', 'dev-a').data
        self.b = _login(self.client, 'revoke@example.com', 'OldP@ss123', 'dev-b').data

    def test_change_password_revokes_all_sessions(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.a['token']}")
        resp = self.client.post(BASE + 'change-password/', {
            'old_password': 'OldP@ss123', 'new_password': 'NewP@ss456',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Token.objects.filter(user=self.user).count(), 0)
        self.assertFalse(DeviceSession.objects.filter(
            user=self.user, revoked_at__isnull=True,
        ).exists())
        # Both devices' refresh credentials are dead.
        for data in (self.a, self.b):
            refresh_resp = self.client.post(BASE + 'refresh/', {
                'device_id': data['device_id'],
                'refresh_token': data['refresh_token'],
            })
            self.assertEqual(refresh_resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_password_reset_revokes_all_sessions(self):
        token = default_token_generator.make_token(self.user)
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        resp = self.client.post(BASE + 'password-reset/confirm/', {
            'email': 'revoke@example.com',
            'uid': uid,
            'token': token,
            'new_password': 'ResetP@ss789',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Token.objects.filter(user=self.user).count(), 0)
        self.assertFalse(DeviceSession.objects.filter(
            user=self.user, revoked_at__isnull=True,
        ).exists())


class LegacyTokenTests(TestCase):
    """Tokens created without a DeviceSession keep working (Phase 10 clients)."""

    def setUp(self):
        self.client = APIClient()
        self.user = _make_user(email='legacy@example.com')

    def test_legacy_token_authenticates_and_logs_out(self):
        token, _ = Token.objects.get_or_create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.assertEqual(self.client.get(BASE + 'me/').status_code, 200)
        resp = self.client.post(BASE + 'logout/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Token.objects.filter(key=token.key).exists())


class SuspendedUserSecurityTests(TestCase):
    """A SUSPENDED user is cut off from refresh and existing access tokens."""

    def setUp(self):
        self.client = APIClient()
        self.user = _make_user(email='suspended@example.com')
        data = _login(
            self.client, 'suspended@example.com', 'pass12345', 'dev-a',
        ).data
        self.access = data['token']
        self.refresh = data['refresh_token']
        self.device_id = data['device_id']

    def _refresh(self):
        return self.client.post(BASE + 'refresh/', {
            'device_id': self.device_id,
            'refresh_token': self.refresh,
        })

    def test_suspended_user_gets_no_new_token_via_refresh(self):
        self.user.status = AccountStatus.SUSPENDED
        self.user.save(update_fields=['status'])
        resp = self._refresh()
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_suspended_user_existing_access_token_rejected(self):
        self.user.status = AccountStatus.SUSPENDED
        self.user.save(update_fields=['status'])
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.access}')
        resp = self.client.get(BASE + 'me/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_active_user_still_authenticates_and_refreshes(self):
        resp = self._refresh()
        self.assertEqual(resp.status_code, 200)
        # Rotation revoked the original access token; the new one is valid.
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {resp.data['token']}")
        self.assertEqual(self.client.get(BASE + 'me/').status_code, 200)

    def test_inactive_user_cannot_refresh(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        resp = self._refresh()
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user_existing_access_token_rejected(self):
        """An existing access token must be rejected once is_active=False."""
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.access}')
        resp = self.client.get(BASE + 'me/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)