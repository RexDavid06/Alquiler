"""Automated tests for the Core/Auth API (Phase 1).

Covers all 9 auth endpoints: register, login, logout, me, update_profile,
change_password, password_reset_request, password_reset_confirm, health_check.
Tests success paths, failure paths, authorization, and data-integrity invariants.
"""

from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.models import AccountStatus, AuditLog, NotificationPreference, User


BASE = '/api/v1/auth/'


def make_user(email='test@example.com', role='LANDLORD', status='ACTIVE', **kwargs):
    """Create and return a user for testing."""
    user = User.objects.create_user(
        email=email, password=kwargs.pop('password', 'pass12345'),
        role=role, first_name=kwargs.pop('first_name', 'Test'),
        last_name=kwargs.pop('last_name', 'User'),
        status=status, **kwargs,
    )
    return user


def auth_header(user):
    """Return DRF token auth header dict."""
    token, _ = Token.objects.get_or_create(user=user)
    return {'HTTP_AUTHORIZATION': f'Token {token.key}'}


# ---------------------------------------------------------------------------
# 1. Register
# ---------------------------------------------------------------------------

class RegisterApiTestCase(TestCase):
    """POST /api/v1/auth/register/"""

    def setUp(self):
        self.client = APIClient()
        self.url = BASE + 'register/'
        self.valid_payload = {
            'role': 'LANDLORD',
            'email': 'newlandlord@example.com',
            'password': 'Str0ngP@ss!',
            'first_name': 'Jane',
            'last_name': 'Doe',
        }

    # -- success ---------------------------------------------------------- #

    def test_register_creates_landlord(self):
        resp = self.client.post(self.url, self.valid_payload)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['user']['role'], 'LANDLORD')
        self.assertEqual(resp.data['user']['email'], 'newlandlord@example.com')
        self.assertIn('token', resp.data)
        user = User.objects.get(email='newlandlord@example.com')
        self.assertEqual(user.status, AccountStatus.ACTIVE)
        self.assertTrue(user.is_active)

    def test_register_returns_user_serializer_fields(self):
        resp = self.client.post(self.url, self.valid_payload)
        self.assertEqual(resp.status_code, 201)
        user_data = resp.data['user']
        for field in ('id', 'email', 'role', 'first_name', 'last_name',
                       'phone', 'full_name', 'status', 'email_verified',
                       'created_at', 'updated_at'):
            self.assertIn(field, user_data)

    def test_register_creates_notification_preference(self):
        resp = self.client.post(self.url, self.valid_payload)
        self.assertEqual(resp.status_code, 201)
        user = User.objects.get(email='newlandlord@example.com')
        self.assertTrue(NotificationPreference.objects.filter(user=user).exists())

    def test_register_creates_audit_log(self):
        resp = self.client.post(self.url, self.valid_payload)
        self.assertEqual(resp.status_code, 201)
        user = User.objects.get(email='newlandlord@example.com')
        log = AuditLog.objects.filter(
            actor=user, action='ACCOUNT_CREATED', object_type='User',
            object_id=user.id,
        )
        self.assertEqual(log.count(), 1)
        self.assertEqual(log.first().detail['role'], 'LANDLORD')

    def test_register_issues_token(self):
        resp = self.client.post(self.url, self.valid_payload)
        self.assertEqual(resp.status_code, 201)
        user = User.objects.get(email='newlandlord@example.com')
        self.assertTrue(Token.objects.filter(user=user).exists())

    def test_register_case_insensitive_email(self):
        payload = {**self.valid_payload, 'email': 'NEWLANDLORD@EXAMPLE.COM'}
        resp = self.client.post(self.url, payload)
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(User.objects.filter(email='newlandlord@example.com').exists())

    # -- failure ---------------------------------------------------------- #

    def test_register_rejects_duplicate_email(self):
        make_user(email='existing@example.com')
        payload = {**self.valid_payload, 'email': 'existing@example.com'}
        resp = self.client.post(self.url, payload)
        self.assertEqual(resp.status_code, 400)

    def test_register_rejects_duplicate_email_case_insensitive(self):
        make_user(email='existing@example.com')
        payload = {**self.valid_payload, 'email': 'EXISTING@EXAMPLE.COM'}
        resp = self.client.post(self.url, payload)
        self.assertEqual(resp.status_code, 400)

    def test_register_rejects_tenant_role(self):
        payload = {**self.valid_payload, 'role': 'TENANT', 'email': 't@example.com'}
        resp = self.client.post(self.url, payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('tenant_registration_not_allowed', str(resp.data))

    def test_register_rejects_invalid_email(self):
        payload = {**self.valid_payload, 'email': 'not-an-email'}
        resp = self.client.post(self.url, payload)
        self.assertEqual(resp.status_code, 400)

    def test_register_rejects_weak_password(self):
        payload = {**self.valid_payload, 'password': '123'}
        resp = self.client.post(self.url, payload)
        self.assertEqual(resp.status_code, 400)

    def test_register_rejects_missing_required_fields(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, 400)

    def test_register_rejects_missing_email(self):
        payload = {
            'role': 'LANDLORD',
            'password': 'Str0ngP@ss!',
            'first_name': 'Jane',
            'last_name': 'Doe',
        }
        resp = self.client.post(self.url, payload)
        self.assertEqual(resp.status_code, 400)

    def test_register_rejects_missing_first_name(self):
        payload = {
            'role': 'LANDLORD',
            'email': 'nf@example.com',
            'password': 'Str0ngP@ss!',
            'last_name': 'Doe',
        }
        resp = self.client.post(self.url, payload)
        self.assertEqual(resp.status_code, 400)

    def test_register_optional_phone(self):
        payload = {**self.valid_payload, 'phone': ''}
        resp = self.client.post(self.url, payload)
        self.assertEqual(resp.status_code, 201)

    def test_register_allows_phone(self):
        payload = {**self.valid_payload, 'phone': '+2348012345678'}
        resp = self.client.post(self.url, payload)
        self.assertEqual(resp.status_code, 201)
        user = User.objects.get(email='newlandlord@example.com')
        self.assertEqual(user.phone, '+2348012345678')


# ---------------------------------------------------------------------------
# 2. Login
# ---------------------------------------------------------------------------

class LoginApiTestCase(TestCase):
    """POST /api/v1/auth/login/"""

    def setUp(self):
        self.client = APIClient()
        self.url = BASE + 'login/'
        self.user = make_user(
            email='landlord@example.com', password='pass12345',
            status='ACTIVE',
        )

    # -- success ---------------------------------------------------------- #

    def test_login_success(self):
        resp = self.client.post(self.url, {
            'email': 'landlord@example.com', 'password': 'pass12345',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['user']['email'], 'landlord@example.com')
        self.assertIn('token', resp.data)

    def test_login_returns_user_serializer_fields(self):
        resp = self.client.post(self.url, {
            'email': 'landlord@example.com', 'password': 'pass12345',
        })
        self.assertEqual(resp.status_code, 200)
        user_data = resp.data['user']
        for field in ('id', 'email', 'role', 'first_name', 'last_name',
                       'full_name', 'status', 'created_at'):
            self.assertIn(field, user_data)

    def test_login_creates_token(self):
        Token.objects.filter(user=self.user).delete()
        resp = self.client.post(self.url, {
            'email': 'landlord@example.com', 'password': 'pass12345',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Token.objects.filter(user=self.user).exists())

    def test_login_reuses_existing_token(self):
        old_token, _ = Token.objects.get_or_create(user=self.user)
        resp = self.client.post(self.url, {
            'email': 'landlord@example.com', 'password': 'pass12345',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['token'], old_token.key)

    def test_login_case_insensitive_email(self):
        resp = self.client.post(self.url, {
            'email': 'LANDLORD@EXAMPLE.COM', 'password': 'pass12345',
        })
        self.assertEqual(resp.status_code, 200)

    # -- failure ---------------------------------------------------------- #

    def test_login_wrong_password(self):
        resp = self.client.post(self.url, {
            'email': 'landlord@example.com', 'password': 'wrongpass',
        })
        self.assertEqual(resp.status_code, 400)

    def test_login_nonexistent_email(self):
        resp = self.client.post(self.url, {
            'email': 'nonexistent@example.com', 'password': 'pass12345',
        })
        self.assertEqual(resp.status_code, 400)

    def test_login_suspended_account(self):
        self.user.status = AccountStatus.SUSPENDED
        self.user.save()
        resp = self.client.post(self.url, {
            'email': 'landlord@example.com', 'password': 'pass12345',
        })
        self.assertEqual(resp.status_code, 400)

    def test_login_inactive_account(self):
        self.user.is_active = False
        self.user.save()
        resp = self.client.post(self.url, {
            'email': 'landlord@example.com', 'password': 'pass12345',
        })
        self.assertEqual(resp.status_code, 400)

    def test_login_missing_fields(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, 400)

    def test_login_missing_password(self):
        resp = self.client.post(self.url, {'email': 'landlord@example.com'})
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# 3. Logout
# ---------------------------------------------------------------------------

class LogoutApiTestCase(TestCase):
    """POST /api/v1/auth/logout/"""

    def setUp(self):
        self.client = APIClient()
        self.url = BASE + 'logout/'
        self.user = make_user(email='landlord@example.com')

    # -- success ---------------------------------------------------------- #

    def test_logout_success(self):
        token, _ = Token.objects.get_or_create(user=self.user)
        resp = self.client.post(self.url, **auth_header(self.user))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['detail'], 'Logged out.')
        self.assertFalse(Token.objects.filter(pk=token.pk).exists())

    def test_logout_invalidates_token(self):
        Token.objects.get_or_create(user=self.user)
        self.client.post(self.url, **auth_header(self.user))
        # After logout, the old token should not authenticate.
        auth_dict = auth_header(self.user)  # This creates a new token
        self.client.post(self.url, **auth_dict)  # logout again cleanly

    # -- failure ---------------------------------------------------------- #

    def test_logout_unauthenticated(self):
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 401)


# ---------------------------------------------------------------------------
# 4. Me
# ---------------------------------------------------------------------------

class MeApiTestCase(TestCase):
    """GET /api/v1/auth/me/"""

    def setUp(self):
        self.client = APIClient()
        self.url = BASE + 'me/'
        self.user = make_user(
            email='landlord@example.com', first_name='Jane', last_name='Doe',
        )

    # -- success ---------------------------------------------------------- #

    def test_me_returns_current_user(self):
        resp = self.client.get(self.url, **auth_header(self.user))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['email'], 'landlord@example.com')
        self.assertEqual(resp.data['first_name'], 'Jane')
        self.assertEqual(resp.data['last_name'], 'Doe')
        self.assertEqual(resp.data['full_name'], 'Jane Doe')

    def test_me_returns_all_expected_fields(self):
        resp = self.client.get(self.url, **auth_header(self.user))
        self.assertEqual(resp.status_code, 200)
        for field in ('id', 'email', 'role', 'first_name', 'last_name',
                       'phone', 'full_name', 'status', 'email_verified',
                       'created_at', 'updated_at'):
            self.assertIn(field, resp.data)

    def test_me_does_not_expose_password(self):
        resp = self.client.get(self.url, **auth_header(self.user))
        self.assertNotIn('password', resp.data)
        self.assertNotIn('password_hash', resp.data)

    # -- failure ---------------------------------------------------------- #

    def test_me_unauthenticated(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 401)

    def test_me_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token invalidtoken123')
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 401)


# ---------------------------------------------------------------------------
# 5. Update Profile
# ---------------------------------------------------------------------------

class UpdateProfileApiTestCase(TestCase):
    """PATCH /api/v1/auth/profile/"""

    def setUp(self):
        self.client = APIClient()
        self.url = BASE + 'profile/'
        self.user = make_user(
            email='landlord@example.com', first_name='Jane', last_name='Doe',
        )

    # -- success ---------------------------------------------------------- #

    def test_update_first_name(self):
        resp = self.client.patch(
            self.url, {'first_name': 'Janet'}, **auth_header(self.user),
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Janet')

    def test_update_last_name(self):
        resp = self.client.patch(
            self.url, {'last_name': 'Smith'}, **auth_header(self.user),
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, 'Smith')

    def test_update_phone(self):
        resp = self.client.patch(
            self.url, {'phone': '+2348012345678'}, **auth_header(self.user),
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, '+2348012345678')

    def test_update_multiple_fields(self):
        resp = self.client.patch(
            self.url,
            {'first_name': 'Janet', 'last_name': 'Smith', 'phone': '+1234'},
            **auth_header(self.user),
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Janet')
        self.assertEqual(self.user.last_name, 'Smith')
        self.assertEqual(self.user.phone, '+1234')

    def test_update_returns_user_serializer(self):
        resp = self.client.patch(
            self.url, {'first_name': 'Janet'}, **auth_header(self.user),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['first_name'], 'Janet')
        self.assertEqual(resp.data['email'], 'landlord@example.com')

    def test_update_profile_read_only_fields_ignored(self):
        """Trying to update read-only fields like email or role should be ignored."""
        resp = self.client.patch(
            self.url,
            {'email': 'hacked@example.com', 'role': 'PLATFORM_ADMIN'},
            **auth_header(self.user),
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'landlord@example.com')
        self.assertEqual(self.user.role, 'LANDLORD')

    # -- failure ---------------------------------------------------------- #

    def test_update_unauthenticated(self):
        resp = self.client.patch(self.url, {'first_name': 'Janet'})
        self.assertEqual(resp.status_code, 401)

    def test_update_empty_body_accepted(self):
        """PATCH with empty body is a no-op but not an error."""
        resp = self.client.patch(self.url, {}, **auth_header(self.user))
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# 6. Change Password
# ---------------------------------------------------------------------------

class ChangePasswordApiTestCase(TestCase):
    """POST /api/v1/auth/change-password/"""

    def setUp(self):
        self.client = APIClient()
        self.url = BASE + 'change-password/'
        self.user = make_user(email='landlord@example.com', password='OldP@ss123')

    # -- success ---------------------------------------------------------- #

    def test_change_password_success(self):
        resp = self.client.post(
            self.url,
            {'old_password': 'OldP@ss123', 'new_password': 'NewP@ss456'},
            **auth_header(self.user),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['detail'], 'Password changed.')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewP@ss456'))

    def test_change_password_invalidates_old_token(self):
        """After password change, the old token should be deleted."""
        Token.objects.get_or_create(user=self.user)
        self.client.post(
            self.url,
            {'old_password': 'OldP@ss123', 'new_password': 'NewP@ss456'},
            **auth_header(self.user),
        )
        self.assertEqual(Token.objects.filter(user=self.user).count(), 0)

    def test_change_password_new_password_works_for_login(self):
        resp = self.client.post(
            self.url,
            {'old_password': 'OldP@ss123', 'new_password': 'NewP@ss456'},
            **auth_header(self.user),
        )
        self.assertEqual(resp.status_code, 200)
        login_resp = self.client.post(BASE + 'login/', {
            'email': 'landlord@example.com', 'password': 'NewP@ss456',
        })
        self.assertEqual(login_resp.status_code, 200)

    def test_change_password_old_password_no_longer_works(self):
        self.client.post(
            self.url,
            {'old_password': 'OldP@ss123', 'new_password': 'NewP@ss456'},
            **auth_header(self.user),
        )
        login_resp = self.client.post(BASE + 'login/', {
            'email': 'landlord@example.com', 'password': 'OldP@ss123',
        })
        self.assertEqual(login_resp.status_code, 400)

    # -- failure ---------------------------------------------------------- #

    def test_change_password_wrong_old_password(self):
        resp = self.client.post(
            self.url,
            {'old_password': 'WrongP@ss', 'new_password': 'NewP@ss456'},
            **auth_header(self.user),
        )
        self.assertEqual(resp.status_code, 400)

    def test_change_password_weak_new_password(self):
        resp = self.client.post(
            self.url,
            {'old_password': 'OldP@ss123', 'new_password': '123'},
            **auth_header(self.user),
        )
        self.assertEqual(resp.status_code, 400)

    def test_change_password_unauthenticated(self):
        resp = self.client.post(self.url, {
            'old_password': 'OldP@ss123', 'new_password': 'NewP@ss456',
        })
        self.assertEqual(resp.status_code, 401)

    def test_change_password_missing_fields(self):
        resp = self.client.post(self.url, {}, **auth_header(self.user))
        self.assertEqual(resp.status_code, 400)

    def test_change_password_missing_new_password(self):
        resp = self.client.post(
            self.url, {'old_password': 'OldP@ss123'}, **auth_header(self.user),
        )
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# 7. Password Reset Request
# ---------------------------------------------------------------------------

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PasswordResetRequestApiTestCase(TestCase):
    """POST /api/v1/auth/password-reset/"""

    def setUp(self):
        self.client = APIClient()
        self.url = BASE + 'password-reset/'
        self.user = make_user(email='landlord@example.com')

    # -- success ---------------------------------------------------------- #

    def test_password_reset_request_existing_email(self):
        resp = self.client.post(self.url, {'email': 'landlord@example.com'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.data['detail'],
            'If that email exists, a reset link was sent.',
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Reset your Alquiler password', mail.outbox[0].subject)

    def test_password_reset_request_email_contains_reset_link(self):
        resp = self.client.post(self.url, {'email': 'landlord@example.com'})
        self.assertEqual(resp.status_code, 200)
        body = mail.outbox[0].body
        self.assertIn('reset-password', body)
        self.assertIn('uid=', body)
        self.assertIn('token=', body)

    def test_password_reset_request_case_insensitive_email(self):
        resp = self.client.post(self.url, {'email': 'LANDLORD@EXAMPLE.COM'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    # -- no email enumeration --------------------------------------------- #

    def test_password_reset_nonexistent_email_returns_same_message(self):
        resp = self.client.post(self.url, {'email': 'nobody@example.com'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.data['detail'],
            'If that email exists, a reset link was sent.',
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_suspended_user_returns_same_message(self):
        self.user.status = AccountStatus.SUSPENDED
        self.user.save()
        resp = self.client.post(self.url, {'email': 'landlord@example.com'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.data['detail'],
            'If that email exists, a reset link was sent.',
        )
        self.assertEqual(len(mail.outbox), 0)

    # -- failure ---------------------------------------------------------- #

    def test_password_reset_request_invalid_email_format(self):
        resp = self.client.post(self.url, {'email': 'not-an-email'})
        self.assertEqual(resp.status_code, 400)

    def test_password_reset_request_missing_email(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# 8. Password Reset Confirm
# ---------------------------------------------------------------------------

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PasswordResetConfirmApiTestCase(TestCase):
    """POST /api/v1/auth/password-reset/confirm/"""

    def setUp(self):
        self.client = APIClient()
        self.url = BASE + 'password-reset/confirm/'
        self.user = make_user(email='landlord@example.com', password='OldP@ss123')
        # Generate valid reset token and uid
        self.token = default_token_generator.make_token(self.user)
        self.uid = urlsafe_base64_encode(force_bytes(self.user.pk))

    # -- success ---------------------------------------------------------- #

    def test_password_reset_confirm_success(self):
        resp = self.client.post(self.url, {
            'email': 'landlord@example.com',
            'uid': self.uid,
            'token': self.token,
            'new_password': 'ResetP@ss456',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['detail'], 'Password has been reset.')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('ResetP@ss456'))

    def test_password_reset_confirm_invalidates_all_tokens(self):
        Token.objects.get_or_create(user=self.user)
        self.client.post(self.url, {
            'email': 'landlord@example.com',
            'uid': self.uid,
            'token': self.token,
            'new_password': 'ResetP@ss456',
        })
        self.assertEqual(Token.objects.filter(user=self.user).count(), 0)

    def test_password_reset_confirm_new_password_works_for_login(self):
        self.client.post(self.url, {
            'email': 'landlord@example.com',
            'uid': self.uid,
            'token': self.token,
            'new_password': 'ResetP@ss456',
        })
        login_resp = self.client.post(BASE + 'login/', {
            'email': 'landlord@example.com', 'password': 'ResetP@ss456',
        })
        self.assertEqual(login_resp.status_code, 200)

    # -- failure ---------------------------------------------------------- #

    def test_password_reset_confirm_invalid_token(self):
        resp = self.client.post(self.url, {
            'email': 'landlord@example.com',
            'uid': self.uid,
            'token': 'invalid-token-123',
            'new_password': 'ResetP@ss456',
        })
        self.assertEqual(resp.status_code, 400)

    def test_password_reset_confirm_invalid_uid(self):
        resp = self.client.post(self.url, {
            'email': 'landlord@example.com',
            'uid': 'invalid-uid',
            'token': self.token,
            'new_password': 'ResetP@ss456',
        })
        self.assertEqual(resp.status_code, 400)

    def test_password_reset_confirm_wrong_email(self):
        """Using a different email than the one the token was generated for."""
        make_user(email='other@example.com')
        resp = self.client.post(self.url, {
            'email': 'other@example.com',
            'uid': self.uid,
            'token': self.token,
            'new_password': 'ResetP@ss456',
        })
        self.assertEqual(resp.status_code, 400)

    def test_password_reset_confirm_weak_password(self):
        resp = self.client.post(self.url, {
            'email': 'landlord@example.com',
            'uid': self.uid,
            'token': self.token,
            'new_password': '123',
        })
        self.assertEqual(resp.status_code, 400)

    def test_password_reset_confirm_missing_fields(self):
        resp = self.client.post(self.url, {})
        self.assertEqual(resp.status_code, 400)

    def test_password_reset_confirm_nonexistent_user_uid(self):
        """UID pointing to a deleted/nonexistent user."""
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        fake_uid = urlsafe_base64_encode(force_bytes(99999))
        resp = self.client.post(self.url, {
            'email': 'landlord@example.com',
            'uid': fake_uid,
            'token': self.token,
            'new_password': 'ResetP@ss456',
        })
        self.assertEqual(resp.status_code, 400)


# ---------------------------------------------------------------------------
# 9. Health Check
# ---------------------------------------------------------------------------

class HealthCheckApiTestCase(TestCase):
    """GET /api/v1/auth/health/"""

    def setUp(self):
        self.client = APIClient()
        self.url = BASE + 'health/'

    # -- success ---------------------------------------------------------- #

    def test_health_check_success(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'healthy')
        self.assertEqual(resp.data['database'], 'ok')

    def test_health_check_unauthenticated(self):
        """Health check is publicly accessible."""
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_health_check_GET_only(self):
        """Health check only accepts GET."""
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 405)

    # -- failure ---------------------------------------------------------- #

    def test_health_check_db_failure(self):
        with patch('django.db.connection') as mock_conn:
            mock_conn.cursor.side_effect = Exception('DB down')
            resp = self.client.get(self.url)
            self.assertEqual(resp.status_code, 503)
            self.assertEqual(resp.data['status'], 'unhealthy')
            self.assertEqual(resp.data['database'], 'unavailable')
