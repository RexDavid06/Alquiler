"""Automated tests for the Property and Unit API (Phase 2).

Covers CRUD, data isolation between landlords, subscription property limits,
duplicate-unit prevention, occupancy immutability, and authentication.
"""

from datetime import date

from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.models import User
from leases.models import Lease, RentFrequency
from properties.models import Property, PropertyStatus, PropertyType, Unit
from subscriptions.services import ensure_landlord_subscription


def make_landlord(email='landlord@example.com', status='ACTIVE'):
    user = User.objects.create_user(
        email=email, password='pass12345', role='LANDLORD',
        first_name='L', last_name='Lord', status=status,
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


def property_payload(**overrides):
    payload = {
        'name': 'Sunshine Apartments',
        'property_type': 'APARTMENT',
        'address': '12 Marine Road',
        'city': 'Lagos',
        'state': 'Lagos',
        'country': 'Nigeria',
        'currency': 'NGN',
        'description': 'A test apartment block',
    }
    payload.update(overrides)
    return payload


def unit_payload(**overrides):
    payload = {'name': 'Flat A', 'description': 'One-bedroom flat'}
    payload.update(overrides)
    return payload


class PropertyApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.landlord_a = make_landlord('a@example.com')
        self.landlord_b = make_landlord('b@example.com')

    def _create_property(self, landlord, **overrides):
        return Property.objects.create(
            landlord=landlord, **property_payload(**overrides),
        )

    # --- Authentication ------------------------------------------------ #

    def test_unauthenticated_cannot_list(self):
        resp = self.client.get('/api/v1/properties/')
        self.assertEqual(resp.status_code, 401)

    def test_unauthenticated_cannot_create(self):
        resp = self.client.post('/api/v1/properties/', property_payload())
        self.assertEqual(resp.status_code, 401)

    def test_tenant_role_rejected(self):
        tenant = make_tenant()
        resp = self.client.get('/api/v1/properties/', **auth(tenant))
        self.assertEqual(resp.status_code, 403)

    # --- CRUD ----------------------------------------------------------- #

    def test_create_property(self):
        resp = self.client.post(
            '/api/v1/properties/', property_payload(), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['landlord'], self.landlord_a.id)
        self.assertEqual(resp.data['landlord_name'], 'L Lord')
        self.assertEqual(resp.data['status'], 'ACTIVE')
        self.assertEqual(resp.data['unit_count'], 0)
        self.assertEqual(Property.objects.filter(landlord=self.landlord_a).count(), 1)

    def test_create_property_ignores_supplied_landlord(self):
        # A client-supplied landlord id must never be honored.
        resp = self.client.post(
            '/api/v1/properties/', property_payload(landlord=99999),
            **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['landlord'], self.landlord_a.id)

    def test_list_properties_scoped_to_landlord(self):
        a = self._create_property(self.landlord_a, name='A Tower')
        b = self._create_property(self.landlord_a, name='B Tower')
        self._create_property(self.landlord_b, name='B Landlord Tower')

        resp = self.client.get('/api/v1/properties/', **auth(self.landlord_a))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 2)
        names = {item['name'] for item in resp.data['results']}
        self.assertEqual(names, {'A Tower', 'B Tower'})
        self.assertNotIn('B Landlord Tower', names)

    def test_list_returns_paginated_envelope(self):
        self._create_property(self.landlord_a, name='A Tower')
        resp = self.client.get('/api/v1/properties/', **auth(self.landlord_a))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('count', resp.data)
        self.assertIn('results', resp.data)

    def test_retrieve_property(self):
        prop = self._create_property(self.landlord_a, name='A Tower')
        resp = self.client.get(
            f'/api/v1/properties/{prop.id}/', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['name'], 'A Tower')

    def test_update_property(self):
        prop = self._create_property(self.landlord_a, name='A Tower')
        resp = self.client.patch(
            f'/api/v1/properties/{prop.id}/',
            {'name': 'A Tower (renovated)', 'city': 'Abuja'},
            **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        prop.refresh_from_db()
        self.assertEqual(prop.name, 'A Tower (renovated)')
        self.assertEqual(prop.city, 'Abuja')

    def test_delete_empty_property_hard_deletes(self):
        prop = self._create_property(self.landlord_a, name='Empty Plot')
        resp = self.client.delete(
            f'/api/v1/properties/{prop.id}/', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Property.objects.filter(pk=prop.pk).exists())

    def test_delete_property_with_units_archives(self):
        prop = self._create_property(self.landlord_a, name='A Tower')
        Unit.objects.create(property=prop, name='Flat A')
        resp = self.client.delete(
            f'/api/v1/properties/{prop.id}/', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        prop.refresh_from_db()
        self.assertEqual(prop.status, PropertyStatus.ARCHIVED)

    # --- Search / filter / ordering ------------------------------------ #

    def test_search_by_name_and_city(self):
        self._create_property(self.landlord_a, name='Sunshine Homes', city='Lagos')
        self._create_property(self.landlord_a, name='Ikeja Heights', city='Ikeja')
        resp = self.client.get(
            '/api/v1/properties/?search=sunshine', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['name'], 'Sunshine Homes')

    def test_filter_by_property_type(self):
        self._create_property(self.landlord_a, name='Flat', property_type='APARTMENT')
        self._create_property(self.landlord_a, name='Warehouse 1', property_type='WAREHOUSE')
        resp = self.client.get(
            '/api/v1/properties/?property_type=APARTMENT', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['name'], 'Flat')

    def test_filter_by_status(self):
        active = self._create_property(self.landlord_a, name='Active One')
        archived = self._create_property(self.landlord_a, name='Old One')
        archived.status = 'ARCHIVED'
        archived.save()
        resp = self.client.get(
            '/api/v1/properties/?status=ARCHIVED', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['id'], archived.id)

    def test_ordering_by_name(self):
        self._create_property(self.landlord_a, name='Beta')
        self._create_property(self.landlord_a, name='Alpha')
        resp = self.client.get(
            '/api/v1/properties/?ordering=name', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        names = [item['name'] for item in resp.data['results']]
        self.assertEqual(names, ['Alpha', 'Beta'])

    # --- Data isolation ------------------------------------------------ #

    def test_cannot_retrieve_another_landlords_property(self):
        prop_b = self._create_property(self.landlord_b, name='B Tower')
        resp = self.client.get(
            f'/api/v1/properties/{prop_b.id}/', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 404)

    def test_cannot_update_another_landlords_property(self):
        prop_b = self._create_property(self.landlord_b, name='B Tower')
        resp = self.client.patch(
            f'/api/v1/properties/{prop_b.id}/',
            {'name': 'Hijacked'}, **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 404)
        prop_b.refresh_from_db()
        self.assertEqual(prop_b.name, 'B Tower')

    def test_cannot_delete_another_landlords_property(self):
        prop_b = self._create_property(self.landlord_b, name='B Tower')
        resp = self.client.delete(
            f'/api/v1/properties/{prop_b.id}/', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Property.objects.filter(pk=prop_b.pk).exists())

    # --- Subscription limit -------------------------------------------- #

    def test_free_plan_property_limit_enforced(self):
        # The FREE plan allows exactly one property.
        resp1 = self.client.post(
            '/api/v1/properties/', property_payload(name='First'),
            **auth(self.landlord_a),
        )
        self.assertEqual(resp1.status_code, 201)
        resp2 = self.client.post(
            '/api/v1/properties/', property_payload(name='Second'),
            **auth(self.landlord_a),
        )
        self.assertEqual(resp2.status_code, 403)
        self.assertEqual(resp2.data.get('code'), 'property_limit_reached')


class UnitApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.landlord_a = make_landlord('a@example.com')
        self.landlord_b = make_landlord('b@example.com')
        self.property_a = self._create_property(self.landlord_a, 'A Tower')
        self.property_b = self._create_property(self.landlord_b, 'B Tower')

    def _create_property(self, landlord, name):
        return Property.objects.create(
            landlord=landlord, **property_payload(name=name),
        )

    def _unit_url(self, property_id, unit_id=None):
        base = f'/api/v1/properties/{property_id}/units/'
        return f'{base}{unit_id}/' if unit_id is not None else base

    # --- Authentication ------------------------------------------------ #

    def test_unauthenticated_cannot_list_units(self):
        resp = self.client.get(self._unit_url(self.property_a.id))
        self.assertEqual(resp.status_code, 401)

    def test_unauthenticated_cannot_create_unit(self):
        resp = self.client.post(self._unit_url(self.property_a.id), unit_payload())
        self.assertEqual(resp.status_code, 401)

    # --- CRUD ----------------------------------------------------------- #

    def test_create_unit(self):
        resp = self.client.post(
            self._unit_url(self.property_a.id), unit_payload(),
            **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['property'], self.property_a.id)
        self.assertEqual(resp.data['property_name'], 'A Tower')
        self.assertEqual(resp.data['status'], 'VACANT')
        self.assertTrue(Unit.objects.filter(property=self.property_a).exists())

    def test_create_unit_ignores_body_property_id(self):
        # The owning property comes from the URL, never the payload.
        resp = self.client.post(
            self._unit_url(self.property_a.id),
            unit_payload(property=self.property_b.id),
            **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['property'], self.property_a.id)

    def test_list_units(self):
        u1 = Unit.objects.create(property=self.property_a, name='Flat A')
        Unit.objects.create(property=self.property_a, name='Flat B')
        Unit.objects.create(property=self.property_b, name='Flat C')

        resp = self.client.get(
            self._unit_url(self.property_a.id), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 2)
        names = {item['name'] for item in resp.data['results']}
        self.assertEqual(names, {'Flat A', 'Flat B'})

    def test_retrieve_unit(self):
        unit = Unit.objects.create(property=self.property_a, name='Flat A')
        resp = self.client.get(
            self._unit_url(self.property_a.id, unit.id), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['name'], 'Flat A')
        self.assertEqual(resp.data['property_name'], 'A Tower')

    def test_update_unit(self):
        unit = Unit.objects.create(property=self.property_a, name='Flat A')
        resp = self.client.patch(
            self._unit_url(self.property_a.id, unit.id),
            {'name': 'Flat A-1', 'description': 'Renovated'},
            **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        unit.refresh_from_db()
        self.assertEqual(unit.name, 'Flat A-1')
        self.assertEqual(unit.description, 'Renovated')

    def test_delete_unit_without_history(self):
        unit = Unit.objects.create(property=self.property_a, name='Flat A')
        resp = self.client.delete(
            self._unit_url(self.property_a.id, unit.id), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Unit.objects.filter(pk=unit.pk).exists())

    def test_delete_unit_with_lease_refused(self):
        tenant = make_tenant()
        unit = Unit.objects.create(property=self.property_a, name='Flat A')
        Lease.objects.create(
            landlord=self.landlord_a, tenant=tenant,
            property=self.property_a, unit=unit,
            start_date=date(2026, 1, 1), expiry_date=date(2026, 12, 31),
            rent_amount='1000.00', currency='NGN',
            rent_frequency=RentFrequency.MONTHLY, rent_due_day=1,
        )
        resp = self.client.delete(
            self._unit_url(self.property_a.id, unit.id), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data.get('code'), 'unit_has_leases')
        self.assertTrue(Unit.objects.filter(pk=unit.pk).exists())

    def test_occupancy_not_client_controlable(self):
        unit = Unit.objects.create(property=self.property_a, name='Flat A')
        resp = self.client.patch(
            self._unit_url(self.property_a.id, unit.id),
            {'status': 'OCCUPIED'}, **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 200)
        unit.refresh_from_db()
        self.assertEqual(unit.status, 'VACANT')

    # --- Duplicate prevention ------------------------------------------- #

    def test_duplicate_unit_name_rejected(self):
        Unit.objects.create(property=self.property_a, name='Flat A')
        resp = self.client.post(
            self._unit_url(self.property_a.id), unit_payload(name='Flat A'),
            **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('duplicate_unit_name', str(resp.data))

    def test_duplicate_name_allowed_across_different_properties(self):
        Unit.objects.create(property=self.property_a, name='Flat A')
        resp = self.client.post(
            self._unit_url(self.property_b.id), unit_payload(name='Flat A'),
            **auth(self.landlord_b),
        )
        self.assertEqual(resp.status_code, 201)

    def test_duplicate_name_rejected_case_insensitively(self):
        Unit.objects.create(property=self.property_a, name='Flat A')
        resp = self.client.post(
            self._unit_url(self.property_a.id), unit_payload(name='flat a'),
            **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 400)

    # --- Data isolation ------------------------------------------------ #

    def test_cannot_create_unit_under_another_landlords_property(self):
        resp = self.client.post(
            self._unit_url(self.property_b.id), unit_payload(),
            **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(Unit.objects.filter(property=self.property_b).exists())

    def test_cannot_list_another_landlords_units(self):
        Unit.objects.create(property=self.property_b, name='Flat C')
        resp = self.client.get(
            self._unit_url(self.property_b.id), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 404)

    def test_cannot_retrieve_another_landlords_unit(self):
        unit = Unit.objects.create(property=self.property_b, name='Flat C')
        resp = self.client.get(
            self._unit_url(self.property_b.id, unit.id), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 404)

    def test_cannot_update_another_landlords_unit(self):
        unit = Unit.objects.create(property=self.property_b, name='Flat C')
        resp = self.client.patch(
            self._unit_url(self.property_b.id, unit.id),
            {'name': 'Hijacked'}, **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 404)
        unit.refresh_from_db()
        self.assertEqual(unit.name, 'Flat C')

    def test_cannot_delete_another_landlords_unit(self):
        unit = Unit.objects.create(property=self.property_b, name='Flat C')
        resp = self.client.delete(
            self._unit_url(self.property_b.id, unit.id), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Unit.objects.filter(pk=unit.pk).exists())

    def test_cannot_access_unit_of_other_property_same_landlord(self):
        # Even within the same landlord, a unit under property A must not be
        # reachable through property B's URL.
        unit_a = Unit.objects.create(property=self.property_a, name='Flat A')
        resp = self.client.get(
            self._unit_url(self.property_b.id, unit_a.id), **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, 404)


class PropertyOccupancySupervisorTestCase(TestCase):
    """Occupancy counts exposed on the property serializer are authoritative,
    derived from unit status which only the lease lifecycle may change."""

    def setUp(self):
        self.client = APIClient()
        self.landlord = make_landlord('a@example.com')
        self.property = Property.objects.create(
            landlord=self.landlord, **property_payload(),
        )

    def test_occupancy_counts_derived(self):
        Unit.objects.create(property=self.property, name='Flat A')
        occupied = Unit.objects.create(property=self.property, name='Flat B')
        occupied.set_status('OCCUPIED')

        resp = self.client.get(
            f'/api/v1/properties/{self.property.id}/', **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['unit_count'], 2)
        self.assertEqual(resp.data['occupied_units'], 1)
        self.assertEqual(resp.data['vacant_units'], 1)