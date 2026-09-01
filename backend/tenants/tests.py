"""Automated tests for the Tenant Management & Invitations API (Phase 3)."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.models import Role
from leases.services import create_lease
from properties.models import Property, Unit

from .models import InvitationStatus, TenantInvitation

User = get_user_model()


def make_landlord(email):
    user = User.objects.create_user(
        email=email, password='pass12345', role=Role.LANDLORD,
        first_name='L', last_name=email.split('@')[0],
        status='ACTIVE',
    )
    from subscriptions.services import ensure_landlord_subscription
    ensure_landlord_subscription(user)
    return user


def make_tenant(email):
    return User.objects.create_user(
        email=email, password='pass12345', role=Role.TENANT,
        first_name='T', last_name=email.split('@')[0], status='ACTIVE',
    )


def make_property(landlord, unit_names=('Unit A',)):
    prop = Property.objects.create(
        landlord=landlord, name=f'{landlord.email} Towers', address='1 Test Rd',
    )
    units = [Unit.objects.create(property=prop, name=n) for n in unit_names]
    return prop, units


def auth(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {'HTTP_AUTHORIZATION': f'Token {token.key}'}


def invite_payload(prop, unit, email='tenant@example.com'):
    return {'email': email, 'property': prop.id, 'unit': unit.id}


def accept_payload(token, password='password123'):
    return {
        'token': token, 'first_name': 'Ten', 'last_name': 'Ant',
        'phone': '0800', 'password': password,
    }


class InvitationApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.landlord_a = make_landlord('a@example.com')
        self.landlord_b = make_landlord('b@example.com')
        self.prop_a, self.units_a = make_property(self.landlord_a, ('Flat A',))
        self.prop_b, self.units_b = make_property(self.landlord_b, ('Flat B',))
        self.unit_a = self.units_a[0]
        self.unit_b = self.units_b[0]

    def _invite(self, landlord, prop, unit, email='tenant@example.com'):
        resp = self.client.post(
            '/api/v1/tenants/invitations/', invite_payload(prop, unit, email),
            **auth(landlord),
        )
        return resp

    # 1. Create -------------------------------------------------------- #

    def test_landlord_can_create_invitation(self):
        resp = self._invite(self.landlord_a, self.prop_a, self.unit_a)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['email'], 'tenant@example.com')
        self.assertEqual(resp.data['status'], InvitationStatus.PENDING)
        self.assertEqual(resp.data['property_name'], 'a@example.com Towers')
        self.assertEqual(resp.data['unit_name'], 'Flat A')
        self.assertNotIn('token', resp.data)
        self.assertTrue(TenantInvitation.objects.filter(landlord=self.landlord_a).exists())

    def test_invitation_email_normalized(self):
        resp = self._invite(
            self.landlord_a, self.prop_a, self.unit_a,
            email='  MiXeD@ExAmple.COM ',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['email'], 'mixed@example.com')

    # 2. List ---------------------------------------------------------- #

    def test_landlord_can_list_their_invitations(self):
        self._invite(self.landlord_a, self.prop_a, self.unit_a, email='x1@example.com')
        self._invite(self.landlord_a, self.prop_a, self.unit_a, email='x2@example.com')
        self._invite(self.landlord_b, self.prop_b, self.unit_b, email='y@example.com')

        resp = self.client.get(
            '/api/v1/tenants/invitations/', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 2)
        for item in resp.data['results']:
            self.assertNotIn('token', item)
        emails = {item['email'] for item in resp.data['results']}
        self.assertEqual(emails, {'x1@example.com', 'x2@example.com'})

    def test_invitation_list_filter_by_status(self):
        self._invite(self.landlord_a, self.prop_a, self.unit_a, email='x1@example.com')
        invite = TenantInvitation.objects.get(email='x1@example.com')
        invite.status = InvitationStatus.REVOKED
        invite.save()
        resp = self.client.get(
            '/api/v1/tenants/invitations/?status=REVOKED', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)

    def test_landlord_can_retrieve_invitation(self):
        self._invite(self.landlord_a, self.prop_a, self.unit_a, email='x1@example.com')
        invite = TenantInvitation.objects.get(email='x1@example.com')
        resp = self.client.get(
            f'/api/v1/tenants/invitations/{invite.id}/', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['email'], 'x1@example.com')
        self.assertNotIn('token', resp.data)

    # 3 / 4. Isolation -------------------------------------------------- #

    def test_cannot_access_another_landlords_invitation(self):
        self._invite(self.landlord_b, self.prop_b, self.unit_b, email='y@example.com')
        invite = TenantInvitation.objects.get(email='y@example.com')
        resp = self.client.get(
            f'/api/v1/tenants/invitations/{invite.id}/', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 404)

    def test_cannot_invite_to_another_landlords_property(self):
        resp = self._invite(self.landlord_a, self.prop_b, self.unit_b)
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(
            TenantInvitation.objects.filter(landlord=self.landlord_a).exists(),
        )

    def test_unit_property_mismatch_rejected(self):
        resp = self.client.post(
            '/api/v1/tenants/invitations/',
            {'email': 'tenant@example.com', 'property': self.prop_a.id,
             'unit': self.unit_b.id},
            **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('unit_property_mismatch', str(resp.data))

    # 5-8. Lifecycle ---------------------------------------------------- #

    def test_token_is_single_use(self):
        self._invite(self.landlord_a, self.prop_a, self.unit_a)
        invite = TenantInvitation.objects.get()
        r1 = self.client.post(
            '/api/v1/tenants/invitations/accept/', accept_payload(invite.token),
        )
        self.assertEqual(r1.status_code, 201)
        r2 = self.client.post(
            '/api/v1/tenants/invitations/accept/', accept_payload(invite.token),
        )
        self.assertEqual(r2.status_code, 400)
        self.assertEqual(r2.data.get('code'), 'invitation_used')

    def test_expired_invitation_cannot_be_accepted(self):
        self._invite(self.landlord_a, self.prop_a, self.unit_a)
        invite = TenantInvitation.objects.get()
        invite.expires_at = timezone.now() - timedelta(hours=1)
        invite.save()
        resp = self.client.post(
            '/api/v1/tenants/invitations/accept/', accept_payload(invite.token),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data.get('code'), 'invitation_expired')

    def test_revoked_invitation_cannot_be_accepted(self):
        self._invite(self.landlord_a, self.prop_a, self.unit_a)
        invite = TenantInvitation.objects.get()
        resp = self.client.post(
            f'/api/v1/tenants/invitations/{invite.id}/revoke/', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], InvitationStatus.REVOKED)

        accept = self.client.post(
            '/api/v1/tenants/invitations/accept/', accept_payload(invite.token),
        )
        self.assertEqual(accept.status_code, 400)
        self.assertEqual(accept.data.get('code'), 'invitation_revoked')

    def test_resend_replaces_token_and_expires_old(self):
        self._invite(self.landlord_a, self.prop_a, self.unit_a)
        invite = TenantInvitation.objects.get()
        old_token = invite.token

        resp = self.client.post(
            f'/api/v1/tenants/invitations/{invite.id}/resend/', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        new_token = resp.data['token'] if 'token' in resp.data else None
        self.assertIsNone(new_token)  # token never exposed to landlords

        # Old token is now dead (EXPIRED status).
        old_accept = self.client.post(
            '/api/v1/tenants/invitations/accept/', accept_payload(old_token),
        )
        self.assertEqual(old_accept.status_code, 400)
        self.assertEqual(old_accept.data.get('code'), 'invitation_expired')

        # Exactly one PENDING + one EXPIRED row for this destination.
        rows = TenantInvitation.objects.filter(
            unit=self.unit_a, email='tenant@example.com',
        )
        self.assertEqual(rows.filter(status=InvitationStatus.PENDING).count(), 1)
        self.assertEqual(rows.filter(status=InvitationStatus.EXPIRED).count(), 1)

        # The new invitation works.
        new_row = rows.filter(status=InvitationStatus.PENDING).get()
        accept = self.client.post(
            '/api/v1/tenants/invitations/accept/', accept_payload(new_row.token),
        )
        self.assertEqual(accept.status_code, 201)

    def test_resend_rejected_for_revoked_invitation(self):
        self._invite(self.landlord_a, self.prop_a, self.unit_a)
        invite = TenantInvitation.objects.get()
        self.client.post(
            f'/api/v1/tenants/invitations/{invite.id}/revoke/', **auth(self.landlord_a),
        )
        resp = self.client.post(
            f'/api/v1/tenants/invitations/{invite.id}/resend/', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data.get('code'), 'invitation_revoked')

    def test_double_revoke_rejected(self):
        self._invite(self.landlord_a, self.prop_a, self.unit_a)
        invite = TenantInvitation.objects.get()
        self.client.post(
            f'/api/v1/tenants/invitations/{invite.id}/revoke/', **auth(self.landlord_a),
        )
        resp = self.client.post(
            f'/api/v1/tenants/invitations/{invite.id}/revoke/', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data.get('code'), 'invitation_revoked')

    def test_revoke_used_invitation_rejected(self):
        self._invite(self.landlord_a, self.prop_a, self.unit_a)
        invite = TenantInvitation.objects.get()
        self.client.post(
            '/api/v1/tenants/invitations/accept/', accept_payload(invite.token),
        )
        resp = self.client.post(
            f'/api/v1/tenants/invitations/{invite.id}/revoke/', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data.get('code'), 'invitation_used')

    # Edge cases -------------------------------------------------------- #

    def test_invitation_to_occupied_unit_refused(self):
        tenant = make_tenant('tenant-occ@example.com')
        create_lease(
            landlord=self.landlord_a, tenant=tenant,
            property=self.prop_a, unit=self.unit_a,
            start_date=timezone.localdate(),
            expiry_date=timezone.localdate() + timedelta(days=365),
            rent_amount='50000.00', currency='NGN',
            rent_frequency='MONTHLY',
        )
        resp = self._invite(self.landlord_a, self.prop_a, self.unit_a)
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data.get('code'), 'unit_occupied')

    def test_repeated_invitation_same_destination_conflict(self):
        self._invite(self.landlord_a, self.prop_a, self.unit_a, email='x@example.com')
        resp = self._invite(self.landlord_a, self.prop_a, self.unit_a, email='x@example.com')
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data.get('code'), 'invitation_already_pending')

    def test_repeated_invitation_different_email_allowed(self):
        self._invite(self.landlord_a, self.prop_a, self.unit_a, email='x@example.com')
        resp = self._invite(self.landlord_a, self.prop_a, self.unit_a, email='y@example.com')
        self.assertEqual(resp.status_code, 201)

    # 16 / 17. Auth ----------------------------------------------------- #

    def test_unauthenticated_rejected(self):
        for method, path, body in [
            ('get', '/api/v1/tenants/', None),
            ('post', '/api/v1/tenants/invitations/',
             invite_payload(self.prop_a, self.unit_a)),
            ('get', '/api/v1/tenants/me/', None),
        ]:
            resp = getattr(self.client, method)(path, body or {})
            self.assertEqual(resp.status_code, 401, f'{method.upper()} {path}')

    def test_tenant_role_cannot_perform_landlord_operations(self):
        tenant = make_tenant('tenant-role@example.com')
        self._invite(self.landlord_a, self.prop_a, self.unit_a)
        invite = TenantInvitation.objects.get()

        resp_list = self.client.get('/api/v1/tenants/', **auth(tenant))
        self.assertEqual(resp_list.status_code, 403)

        resp_create = self.client.post(
            '/api/v1/tenants/invitations/',
            invite_payload(self.prop_a, self.unit_a), **auth(tenant),
        )
        self.assertEqual(resp_create.status_code, 403)

        resp_resend = self.client.post(
            f'/api/v1/tenants/invitations/{invite.id}/resend/', **auth(tenant),
        )
        self.assertEqual(resp_resend.status_code, 403)


class TenantVisibilityTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.landlord_a = make_landlord('a@example.com')
        self.landlord_b = make_landlord('b@example.com')
        self.prop_a, self.units_a = make_property(self.landlord_a, ('Flat A',))
        self.prop_b, self.units_b = make_property(self.landlord_b, ('Flat B',))
        self.tenant_a = make_tenant('tenant-a@example.com')
        self.tenant_b = make_tenant('tenant-b@example.com')
        self.tenant_no_lease = make_tenant('tenant-none@example.com')

    def _lease(self, landlord, tenant, prop, unit, start, end):
        return create_lease(
            landlord=landlord, tenant=tenant, property=prop, unit=unit,
            start_date=start, expiry_date=end,
            rent_amount='50000.00', currency='NGN',
            rent_frequency='MONTHLY',
        )

    def setUpWithLeases(self):
        today = timezone.localdate()
        self._lease(self.landlord_a, self.tenant_a, self.prop_a, self.units_a[0],
                    today, today + timedelta(days=365))
        self._lease(self.landlord_b, self.tenant_b, self.prop_b, self.units_b[0],
                    today, today + timedelta(days=365))

    # 11. Tenant visibility --------------------------------------------- #

    def test_landlord_sees_only_tenants_via_their_leases(self):
        self.setUpWithLeases()
        resp = self.client.get('/api/v1/tenants/', **auth(self.landlord_a))
        self.assertEqual(resp.status_code, 200)
        emails = {item['email'] for item in resp.data['results']}
        self.assertEqual(emails, {'tenant-a@example.com'})

    def test_landlord_tenant_detail_with_lease_summary(self):
        self.setUpWithLeases()
        resp = self.client.get(
            f'/api/v1/tenants/{self.tenant_a.id}/', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['email'], 'tenant-a@example.com')
        self.assertEqual(resp.data['leases'][0]['property_name'], self.prop_a.name)
        self.assertNotIn('password', resp.data)
        # The summary only covers leases with THIS landlord.
        self.assertEqual(len(resp.data['leases']), 1)

    def test_lease_counts_annotated(self):
        self.setUpWithLeases()
        today = timezone.localdate()
        unit2, = make_property(self.landlord_a, ('Flat C',))[1]
        self._lease(self.landlord_a, self.tenant_a, self.prop_a, unit2,
                    today + timedelta(days=400), today + timedelta(days=800))
        resp = self.client.get(
            f'/api/v1/tenants/{self.tenant_a.id}/', **auth(self.landlord_a),
        )
        self.assertEqual(resp.data['total_leases'], 2)
        # A lease whose start date is in the future is FUTURE, not ACTIVE,
        # so it does not consume an active-tenancy slot (Phase 4 lifecycle).
        self.assertEqual(resp.data['active_leases'], 1)

    # 12. Isolation ----------------------------------------------------- #

    def test_cannot_retrieve_another_landlords_tenant(self):
        self.setUpWithLeases()
        resp = self.client.get(
            f'/api/v1/tenants/{self.tenant_b.id}/', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 404)

    def test_cannot_guess_tenant_id(self):
        ghost = User.objects.create_user(
            email='ghost@example.com', password='pass12345', role=Role.TENANT,
            first_name='G', last_name='Host', status='ACTIVE',
        )
        resp = self.client.get(
            f'/api/v1/tenants/{ghost.id}/', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 404)

    # 13 / 14. Tenant self ---------------------------------------------- #

    def test_tenant_can_access_own_profile(self):
        resp = self.client.get('/api/v1/tenants/me/', **auth(self.tenant_a))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['email'], 'tenant-a@example.com')
        self.assertIn('leases', resp.data)

    def test_tenant_cannot_access_another_tenants_profile(self):
        resp = self.client.get(
            f'/api/v1/tenants/{self.tenant_a.id}/', **auth(self.tenant_b),
        )
        self.assertEqual(resp.status_code, 403)
        me = self.client.get('/api/v1/tenants/me/', **auth(self.tenant_a))
        self.assertEqual(me.data['email'], 'tenant-a@example.com')


class SubscriptionTenantLimitTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.landlord = make_landlord('a@example.com')
        self.prop, self.units = make_property(
            self.landlord, ('U1', 'U2', 'U3', 'U4'),
        )

    def _occupy(self, emails):
        today = timezone.localdate()
        for i, email in enumerate(emails):
            tenant = make_tenant(email)
            create_lease(
                landlord=self.landlord, tenant=tenant,
                property=self.prop, unit=self.units[i],
                start_date=today,
                expiry_date=today + timedelta(days=365),
                rent_amount='50000.00', currency='NGN',
                rent_frequency='MONTHLY',
            )

    def test_subscription_tenant_limit_enforced(self):
        self._occupy(['t1@example.com', 't2@example.com', 't3@example.com'])
        resp = self.client.post(
            '/api/v1/tenants/invitations/',
            invite_payload(self.prop, self.units[3], email='new@example.com'),
            **auth(self.landlord),
        )
        # FREE plan max_active_tenants = 3; all 3 slots are full.
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data.get('code'), 'tenant_limit_reached')

    def test_invitation_does_not_count_as_active_tenant(self):
        self._occupy(['t1@example.com', 't2@example.com'])
        resp = self.client.post(
            '/api/v1/tenants/invitations/',
            invite_payload(self.prop, self.units[2], email='pending@example.com'),
            **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, 201)
        # Invitations do not consume the active-tenant budget.
        self.assertTrue(TenantInvitation.objects.filter(email='pending@example.com').exists())