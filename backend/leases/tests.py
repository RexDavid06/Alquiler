"""Automated tests for the Lease & Renewal Management API (Phase 4).

Covers creation rules (ownership/relationships/conflicts/quota), lifecycle
status derivation (FUTURE leases never occupy), future-lease editing, renewal
and termination transitions, history chains, tenant read-only access, data
isolation, status filtering, and authentication.
"""

from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.models import User
from leases.models import Lease, LeaseStatus, RentFrequency
from payments.services import period_status
from properties.models import Property, PropertyStatus, PropertyType, Unit
from subscriptions.services import ensure_landlord_subscription

TODAY = timezone.localdate()
IN_ONE_MONTH = TODAY + timedelta(days=30)
IN_THREE_MONTHS = TODAY + timedelta(days=90)


def make_landlord(email='landlord@example.com'):
    user = User.objects.create_user(
        email=email, password='pass12345', role='LANDLORD',
        first_name='L', last_name='Lord', status='ACTIVE',
    )
    ensure_landlord_subscription(user)
    return user


def make_tenant(email='tenant@example.com'):
    return User.objects.create_user(
        email=email, password='pass12345', role='TENANT',
        first_name='T', last_name='Tenant', status='ACTIVE',
    )


def auth(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {'HTTP_AUTHORIZATION': f'Token {token.key}'}


def lease_payload(**overrides):
    payload = {
        'tenant': None,  # set by caller
        'property': None,  # set by caller
        'unit': None,  # set by caller
        'start_date': str(TODAY),
        'expiry_date': str(IN_THREE_MONTHS),
        'rent_amount': '150000.00',
        'currency': 'NGN',
        'rent_frequency': 'MONTHLY',
        'rent_due_day': 1,
        'notes': '',
    }
    payload.update(overrides)
    return payload


class LeaseApiBase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.landlord_a = make_landlord('a@example.com')
        self.landlord_b = make_landlord('b@example.com')

    def _property(self, landlord, name='Sunshine Apartments'):
        return Property.objects.create(
            landlord=landlord, name=name,
            property_type=PropertyType.APARTMENT,
            address='12 Marine Road', city='Lagos', state='Lagos',
            country='Nigeria', currency='NGN', description='Block of flats',
        )

    def _unit(self, property, name='Flat A'):
        return Unit.objects.create(property=property, name=name)

    def _lease(self, **overrides):
        defaults = {
            'landlord': self.landlord_a,
            'property': None,
            'unit': None,
            'start_date': TODAY,
            'expiry_date': IN_THREE_MONTHS,
            'rent_amount': 150000,
            'currency': 'NGN',
            'rent_frequency': RentFrequency.MONTHLY,
            'rent_due_day': 1,
            'notes': '',
        }
        defaults.update(overrides)
        tenant = defaults.pop('tenant', None) or make_tenant()
        lease = Lease.objects.create(tenant=tenant, **defaults)
        lease.refresh_status()
        from payments.services import generate_schedule
        generate_schedule(lease)
        return lease


class LeaseCreateApiTests(LeaseApiBase):
    def setUp(self):
        super().setUp()
        self.property = self._property(self.landlord_a)
        self.unit = self._unit(self.property, 'Flat A')
        self.unit_b = self._unit(self.property, 'Flat B')
        self.tenant = make_tenant('t@example.com')
        self.url = '/api/v1/leases/'

    def test_unauthenticated_cannot_create(self):
        resp = self.client.post(
            self.url, lease_payload(
                tenant=self.tenant.id, property=self.property.id, unit=self.unit.id,
            ),
        )
        self.assertEqual(resp.status_code, 401)

    def test_tenant_role_cannot_create(self):
        resp = self.client.post(
            self.url, lease_payload(
                tenant=self.tenant.id, property=self.property.id, unit=self.unit.id,
            ), **auth(self.tenant),
        )
        self.assertEqual(resp.status_code, 403)

    def test_landlord_creates_active_lease(self):
        resp = self.client.post(
            self.url, lease_payload(
                tenant=self.tenant.id, property=self.property.id, unit=self.unit.id,
            ), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['landlord'], self.landlord_a.id)
        self.assertEqual(resp.data['tenant'], self.tenant.id)
        self.assertEqual(resp.data['status'], 'ACTIVE')
        self.assertEqual(resp.data['currency'], 'NGN')
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.status, 'OCCUPIED')

    def test_landlord_creates_future_lease_does_not_occupy(self):
        resp = self.client.post(
            self.url, lease_payload(
                tenant=self.tenant.id, property=self.property.id, unit=self.unit.id,
                start_date=str(IN_ONE_MONTH),
                expiry_date=str(IN_ONE_MONTH + timedelta(days=60)),
            ), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['status'], 'FUTURE')
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.status, 'VACANT')

    def test_client_supplied_status_ignored(self):
        resp = self.client.post(
            self.url, lease_payload(
                tenant=self.tenant.id, property=self.property.id, unit=self.unit.id,
                status='TERMINATED', start_date=str(IN_ONE_MONTH),
            ), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['status'], 'FUTURE')

    def test_expiry_before_start_rejected(self):
        resp = self.client.post(
            self.url, lease_payload(
                tenant=self.tenant.id, property=self.property.id, unit=self.unit.id,
                start_date=str(IN_THREE_MONTHS), expiry_date=str(TODAY),
            ), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('expiry_date', resp.data.get('errors', {}))

    def test_invalid_currency_rejected(self):
        resp = self.client.post(
            self.url, lease_payload(
                tenant=self.tenant.id, property=self.property.id, unit=self.unit.id,
                currency='USD1',
            ), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 400)

    def test_invalid_due_day_rejected(self):
        resp = self.client.post(
            self.url, lease_payload(
                tenant=self.tenant.id, property=self.property.id, unit=self.unit.id,
                rent_due_day=29,
            ), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 400)

    def test_property_not_owned_rejected(self):
        other_property = self._property(self.landlord_b, name='Other Block')
        other_unit = self._unit(other_property, 'Room 1')
        resp = self.client.post(
            self.url, lease_payload(
                tenant=self.tenant.id, property=other_property.id,
                unit=other_unit.id,
            ), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 'invalid')
        self.assertIn('property', resp.data.get('errors', {}))

    def test_unit_property_mismatch_rejected(self):
        second_block = self._property(self.landlord_a, 'Second Block')
        foreign_unit = self._unit(second_block, 'Room Z')
        resp = self.client.post(
            self.url, lease_payload(
                tenant=self.tenant.id, property=self.property.id,
                unit=foreign_unit.id,
            ), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 400)

    def test_non_tenant_account_rejected(self):
        employee = User.objects.create_user(
            email='ops@example.com', password='pass12345', role='STAFF',
            first_name='O', last_name='Ops', status='ACTIVE',
        )
        resp = self.client.post(
            self.url, lease_payload(
                tenant=employee.id, property=self.property.id, unit=self.unit.id,
            ), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 400)

    def test_overlapping_lease_rejected(self):
        self.client.post(
            self.url, lease_payload(
                tenant=self.tenant.id, property=self.property.id, unit=self.unit.id,
            ), **auth(self.landlord_a),
        )
        other = make_tenant('t2@example.com')
        resp = self.client.post(
            self.url, lease_payload(
                tenant=other.id, property=self.property.id, unit=self.unit.id,
                start_date=str(TODAY + timedelta(days=5)),
                expiry_date=str(IN_THREE_MONTHS + timedelta(days=5)),
            ), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data['code'], 'unit_has_conflicting_lease')

    def test_adjacent_non_overlapping_lease_allowed(self):
        first = self.client.post(
            self.url, lease_payload(
                tenant=self.tenant.id, property=self.property.id, unit=self.unit.id,
                start_date=str(TODAY),
                expiry_date=str(TODAY + timedelta(days=29)),
            ), **auth(self.landlord_a),
        )
        self.assertEqual(first.status_code, 201)
        other = make_tenant('t2@example.com')
        second = self.client.post(
            self.url, lease_payload(
                tenant=other.id, property=self.property.id, unit=self.unit.id,
                start_date=str(TODAY + timedelta(days=30)),
                expiry_date=str(TODAY + timedelta(days=60)),
            ), **auth(self.landlord_a),
        )
        self.assertEqual(second.status_code, 201)

    def test_future_lease_blocks_overlapping_new_lease(self):
        self.client.post(
            self.url, lease_payload(
                tenant=self.tenant.id, property=self.property.id, unit=self.unit.id,
                start_date=str(IN_ONE_MONTH),
                expiry_date=str(IN_ONE_MONTH + timedelta(days=60)),
            ), **auth(self.landlord_a),
        )
        other = make_tenant('t2@example.com')
        resp = self.client.post(
            self.url, lease_payload(
                tenant=other.id, property=self.property.id, unit=self.unit.id,
                start_date=str(TODAY),
                expiry_date=str(TODAY + timedelta(days=45)),
            ), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data['code'], 'unit_has_conflicting_lease')

    def test_active_tenant_quota_enforced(self):
        # FREE plan allows 3 active tenants. The same tenant is never counted
        # twice, so a landlord may hold multiple leases for one tenant.
        tenants = [make_tenant(f'q{i}@example.com') for i in range(1, 5)]
        units = [self._unit(self.property, f'Q{i}') for i in range(1, 5)]
        for idx in range(3):
            status = self.client.post(
                self.url, lease_payload(
                    tenant=tenants[idx].id, property=self.property.id,
                    unit=units[idx].id,
                ), **auth(self.landlord_a),
            )
            self.assertEqual(status.status_code, 201)

        resp = self.client.post(
            self.url, lease_payload(
                tenant=tenants[3].id, property=self.property.id, unit=units[3].id,
            ), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data['code'], 'tenant_limit_reached')

        # A repeat lease for an already-active tenant consumes no extra quota.
        extra = self.client.post(
            self.url, lease_payload(
                tenant=tenants[0].id, property=self.property.id,
                unit=self._unit(self.property, 'Extra for t1').id,
            ), **auth(self.landlord_a),
        )
        self.assertEqual(extra.status_code, 201)

    def test_rent_schedule_generated_on_create(self):
        resp = self.client.post(
            self.url, lease_payload(
                tenant=self.tenant.id, property=self.property.id, unit=self.unit.id,
                start_date=str(TODAY), expiry_date=str(TODAY + timedelta(days=60)),
                rent_frequency='MONTHLY', rent_due_day=5,
            ), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 201)
        lease = Lease.objects.get(pk=resp.data['id'])
        periods = list(lease.rent_schedule.all())
        self.assertEqual(len(periods), 2)  # 2 full monthly periods in ~2 months
        self.assertEqual(periods[0].due_date.day, 5)
        self.assertEqual(str(periods[0].amount), '150000.00')


class LeaseListRetrieveTests(LeaseApiBase):
    def setUp(self):
        super().setUp()
        self.property_a = self._property(self.landlord_a)
        self.unit_a = self._unit(self.property_a, 'Flat A')
        self.tenant = make_tenant('t@example.com')

    def test_landlord_lists_only_own_leases(self):
        my_lease = self._lease(
            landlord=self.landlord_a, tenant=self.tenant,
            property=self.property_a, unit=self.unit_a,
        )
        b_property = self._property(self.landlord_b, name='B Blocks')
        self._lease(
            landlord=self.landlord_b, tenant=make_tenant('tb@example.com'),
            property=b_property, unit=self._unit(b_property, 'Room 1'),
            start_date=TODAY, expiry_date=IN_THREE_MONTHS,
        )
        resp = self.client.get('/api/v1/leases/', **auth(self.landlord_a))
        self.assertEqual(resp.status_code, 200)
        ids = {item['id'] for item in resp.data['results']}
        self.assertEqual(ids, {my_lease.id})

    def test_tenant_lists_only_own_leases(self):
        mine = self._lease(
            landlord=self.landlord_a, tenant=self.tenant,
            property=self.property_a, unit=self.unit_a,
        )
        other = self._lease(
            landlord=self.landlord_a, tenant=make_tenant('other@example.com'),
            property=self.property_a, unit=self._unit(self.property_a, 'Flat B'),
            start_date=TODAY, expiry_date=IN_THREE_MONTHS,
        )
        resp = self.client.get('/api/v1/leases/', **auth(self.tenant))
        self.assertEqual(resp.status_code, 200)
        ids = {item['id'] for item in resp.data['results']}
        self.assertEqual(ids, {mine.id})
        self.assertNotIn(other.id, ids)

    def test_tenant_reading_foreign_lease_404s(self):
        lease = self._lease(
            landlord=self.landlord_a, tenant=self.tenant,
            property=self.property_a, unit=self.unit_a,
        )
        stranger = make_tenant('stranger@example.com')
        resp = self.client.get(f'/api/v1/leases/{lease.id}/', **auth(stranger))
        self.assertEqual(resp.status_code, 404)

    def test_landlord_reading_tenant_lease_404s(self):
        lease = self._lease(
            landlord=self.landlord_a, tenant=self.tenant,
            property=self.property_a, unit=self.unit_a,
        )
        resp = self.client.get(f'/api/v1/leases/{lease.id}/', **auth(self.landlord_b))
        self.assertEqual(resp.status_code, 404)

    def test_status_filter_uses_derived_status(self):
        future = self._lease(
            landlord=self.landlord_a, tenant=self.tenant,
            property=self.property_a, unit=self.unit_a,
            start_date=IN_ONE_MONTH,
            expiry_date=IN_ONE_MONTH + timedelta(days=60),
        )
        active = self._lease(
            landlord=self.landlord_a,
            tenant=make_tenant('ta@example.com'),
            property=self.property_a, unit=self._unit(self.property_a, 'Flat B'),
            start_date=TODAY, expiry_date=IN_THREE_MONTHS,
        )
        resp = self.client.get(
            '/api/v1/leases/?status=FUTURE', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual({i['id'] for i in resp.data['results']}, {future.id})
        resp = self.client.get(
            '/api/v1/leases/?status=ACTIVE', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual({i['id'] for i in resp.data['results']}, {active.id})

    def test_bogus_status_filter_returns_empty(self):
        resp = self.client.get(
            '/api/v1/leases/?status=GONE', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)

    def test_tenant_reading_foreign_lease_detail_include_schedule(self):
        lease = self._lease(
            landlord=self.landlord_a, tenant=self.tenant,
            property=self.property_a, unit=self.unit_a,
        )
        resp = self.client.get(f'/api/v1/leases/{lease.id}/', **auth(self.tenant))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('rent_schedule', resp.data)
        self.assertEqual(resp.data['status'], 'ACTIVE')
        self.assertTrue(len(resp.data['rent_schedule']) > 0)
        self.assertIn('status', resp.data['rent_schedule'][0])

    def test_search_by_tenant_name(self):
        self._lease(
            landlord=self.landlord_a, tenant=make_tenant('zulu@example.com'),
            property=self.property_a, unit=self.unit_a,
        )
        resp = self.client.get('/api/v1/leases/?search=zulu', **auth(self.landlord_a))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)


class LeaseUpdateTests(LeaseApiBase):
    def setUp(self):
        super().setUp()
        self.property_a = self._property(self.landlord_a)
        self.unit_a = self._unit(self.property_a, 'Flat A')
        self.tenant = make_tenant('t@example.com')

    def _future_lease(self):
        return self._lease(
            landlord=self.landlord_a, tenant=self.tenant,
            property=self.property_a, unit=self.unit_a,
            start_date=IN_ONE_MONTH,
            expiry_date=IN_ONE_MONTH + timedelta(days=60),
        )

    def test_edit_future_lease_updates_terms_and_schedule(self):
        lease = self._future_lease()
        resp = self.client.patch(
            f'/api/v1/leases/{lease.id}/',
            {
                'start_date': str(IN_ONE_MONTH + timedelta(days=15)),
                'rent_amount': '200000.00',
                'rent_due_day': 10,
            },
            **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        lease.refresh_from_db()
        self.assertEqual(lease.rent_amount, 200000)
        self.assertEqual(lease.rent_due_day, 10)
        self.assertEqual(lease.start_date, IN_ONE_MONTH + timedelta(days=15))
        # Schedule regenerated around the new terms.
        periods = list(lease.rent_schedule.all())
        self.assertTrue(all(p.due_date.day == 10 for p in periods))

    def test_edit_active_lease_rejected(self):
        lease = self._lease(
            landlord=self.landlord_a, tenant=self.tenant,
            property=self.property_a, unit=self.unit_a,
        )
        resp = self.client.patch(
            f'/api/v1/leases/{lease.id}/', {'rent_amount': '1.00'},
            **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 'lease_not_editable')

    def test_relationships_immutable_on_edit(self):
        lease = self._future_lease()
        other_unit = self._unit(self.property_a, 'Flat B')
        resp = self.client.patch(
            f'/api/v1/leases/{lease.id}/', {'unit': other_unit.id},
            **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['code'], 'invalid')
        self.assertIn('unit', resp.data.get('errors', {}))

    def test_edit_into_conflicting_period_rejected(self):
        lease = self._future_lease()
        other = make_tenant('other@example.com')
        self._lease(
            landlord=self.landlord_a, tenant=other,
            property=self.property_a, unit=self.unit_a,
            start_date=IN_THREE_MONTHS,
            expiry_date=IN_THREE_MONTHS + timedelta(days=30),
        )
        resp = self.client.patch(
            f'/api/v1/leases/{lease.id}/',
            {'expiry_date': str(IN_THREE_MONTHS + timedelta(days=10))},
            **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data['code'], 'unit_has_conflicting_lease')

    def test_tenant_cannot_edit_lease(self):
        lease = self._future_lease()
        resp = self.client.patch(
            f'/api/v1/leases/{lease.id}/', {'rent_amount': '1.00'},
            **auth(self.tenant),
        )
        self.assertEqual(resp.status_code, 403)


class LeaseRenewAndTerminateTests(LeaseApiBase):
    def setUp(self):
        super().setUp()
        self.property_a = self._property(self.landlord_a)
        self.unit_a = self._unit(self.property_a, 'Flat A')
        self.tenant = make_tenant('t@example.com')

    def _renew_payload(self, **overrides):
        payload = {
            'start_date': str(TODAY),
            'expiry_date': str(IN_THREE_MONTHS),
            'rent_amount': '180000.00',
            'currency': 'NGN',
            'rent_frequency': 'MONTHLY',
            'rent_due_day': 1,
            'notes': 'Renewal terms',
        }
        payload.update(overrides)
        return payload

    def test_renewal_links_previous_lease_and_chains(self):
        old = self._lease(
            landlord=self.landlord_a, tenant=self.tenant,
            property=self.property_a, unit=self.unit_a,
            start_date=TODAY - timedelta(days=300),
            expiry_date=TODAY - timedelta(days=1),
        )
        resp = self.client.post(
            f'/api/v1/leases/{old.id}/renew/',
            self._renew_payload(start_date=str(TODAY)),
            **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 201)
        new = Lease.objects.get(pk=resp.data['id'])
        self.assertEqual(new.previous_lease_id, old.id)
        self.assertEqual(new.tenant_id, old.tenant_id)
        self.assertEqual(new.unit_id, old.unit_id)
        self.assertEqual(resp.data['status'], 'ACTIVE')

        history = self.client.get(
            f'/api/v1/leases/{new.id}/history/', **auth(self.landlord_a),
        )
        self.assertEqual(history.status_code, 200)
        ids = [item['id'] for item in history.data]
        self.assertEqual(ids, [old.id, new.id])
        self.assertEqual(
            history.data[0]['previous_lease_id'], None,
        )

    def test_renewal_overlapping_live_lease_rejected(self):
        old = self._lease(
            landlord=self.landlord_a, tenant=self.tenant,
            property=self.property_a, unit=self.unit_a,
            start_date=TODAY - timedelta(days=30),
            expiry_date=IN_THREE_MONTHS,
        )
        resp = self.client.post(
            f'/api/v1/leases/{old.id}/renew/',
            self._renew_payload(
                start_date=str(TODAY + timedelta(days=5)),
                expiry_date=str(IN_THREE_MONTHS + timedelta(days=5)),
            ),
            **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data['code'], 'unit_has_conflicting_lease')

    def test_terminate_frees_unit_and_is_allowed_after_expiry(self):
        lease = self._lease(
            landlord=self.landlord_a, tenant=self.tenant,
            property=self.property_a, unit=self.unit_a,
        )
        resp = self.client.post(
            f'/api/v1/leases/{lease.id}/terminate/', {}, **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        lease.refresh_from_db()
        self.assertEqual(lease.status, 'TERMINATED')
        self.assertIsNotNone(lease.terminated_at)
        self.unit_a.refresh_from_db()
        self.assertEqual(self.unit_a.status, 'VACANT')

    def test_terminate_again_rejected(self):
        lease = self._lease(
            landlord=self.landlord_a, tenant=self.tenant,
            property=self.property_a, unit=self.unit_a,
        )
        self.client.post(
            f'/api/v1/leases/{lease.id}/terminate/', {}, **auth(self.landlord_a),
        )
        resp = self.client.post(
            f'/api/v1/leases/{lease.id}/terminate/', {}, **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 400)

    def test_renew_or_terminate_foreign_lease_404s(self):
        lease = self._lease(
            landlord=self.landlord_a, tenant=self.tenant,
            property=self.property_a, unit=self.unit_a,
        )
        resp = self.client.post(
            f'/api/v1/leases/{lease.id}/terminate/', {}, **auth(self.landlord_b),
        )
        self.assertEqual(resp.status_code, 404)

    def test_tenant_cannot_renew_or_terminate(self):
        lease = self._lease(
            landlord=self.landlord_a, tenant=self.tenant,
            property=self.property_a, unit=self.unit_a,
        )
        self.assertEqual(
            self.client.post(
                f'/api/v1/leases/{lease.id}/renew/',
                self._renew_payload(), **auth(self.tenant),
            ).status_code, 403,
        )
        self.assertEqual(
            self.client.post(
                f'/api/v1/leases/{lease.id}/terminate/', {},
                **auth(self.tenant),
            ).status_code, 403,
        )


class LeaseStatusDerivationTests(TestCase):
    """Unit-level status derivation for the new FUTURE lifecycle stage."""

    def setUp(self):
        self.landlord = make_landlord('s@example.com')
        self.tenant = make_tenant('s-tenant@example.com')
        self.property = Property.objects.create(
            landlord=self.landlord, name='Status Block',
            property_type=PropertyType.APARTMENT,
            address='1 Test Road', city='Lagos', state='Lagos',
            country='Nigeria', currency='NGN', description='x',
        )
        self.unit = Unit.objects.create(property=self.property, name='S1')

    def _lease(self, start, expiry, stored='ACTIVE'):
        lease = Lease.objects.create(
            landlord=self.landlord, tenant=self.tenant,
            property=self.property, unit=self.unit,
            start_date=start, expiry_date=expiry, status=stored,
            rent_amount=150000, currency='NGN',
            rent_frequency=RentFrequency.MONTHLY, rent_due_day=1,
        )
        return lease

    def test_future_start_derives_future(self):
        lease = self._lease(IN_ONE_MONTH, IN_THREE_MONTHS)
        self.assertEqual(lease.effective_status(), LeaseStatus.FUTURE)

    def test_start_reached_derives_active(self):
        lease = self._lease(TODAY, TODAY + timedelta(days=90))
        self.assertEqual(lease.effective_status(), LeaseStatus.ACTIVE)

    def test_terminated_never_overridden_by_dates(self):
        lease = self._lease(TODAY - timedelta(days=400), TODAY - timedelta(days=300),
                            stored='TERMINATED')
        self.assertEqual(lease.effective_status(), LeaseStatus.TERMINATED)

    def test_expiry_soon_derives_expiring(self):
        lease = self._lease(TODAY - timedelta(days=30), TODAY + timedelta(days=10))
        self.assertEqual(lease.effective_status(), LeaseStatus.EXPIRING)

    def test_expired_past_date(self):
        lease = self._lease(TODAY - timedelta(days=400), TODAY - timedelta(days=1))
        self.assertEqual(lease.effective_status(), LeaseStatus.EXPIRED)