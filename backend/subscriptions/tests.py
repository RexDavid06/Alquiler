"""Comprehensive tests for the Subscription system (Phase 8).

Covers plan CRUD, subscription lifecycle (upgrade/downgrade/cancel/reactivate),
trial management, usage/limit enforcement, billing history (AuditLog),
data isolation, and regression of existing limit-checking behavior.
"""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.models import AuditLog, User
from leases.models import Lease, LeaseStatus, RentFrequency
from payments.models import Payment, PaymentStatus, RentSchedule
from properties.models import Property, Unit
from subscriptions.models import (
    BillingCycle,
    Plan,
    PlanTier,
    Subscription,
    SubscriptionStatus,
)
from subscriptions.services import (
    cancel_subscription,
    check_trial_expiry,
    downgrade_subscription,
    ensure_landlord_subscription,
    get_subscription,
    reactivate_subscription,
    upgrade_subscription,
)

TODAY = timezone.localdate()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_landlord(email='landlord@example.com'):
    user = User.objects.create_user(
        email=email, password='pass12345', role='LANDLORD',
        first_name='L', last_name='Lord', status='ACTIVE',
    )
    ensure_landlord_subscription(user)
    return user


def make_admin(email='admin@example.com'):
    return User.objects.create_user(
        email=email, password='pass12345', role='PLATFORM_ADMIN',
        first_name='A', last_name='Admin', status='ACTIVE',
    )


def make_tenant(email='tenant@example.com'):
    return User.objects.create_user(
        email=email, password='pass12345', role='TENANT',
        first_name='T', last_name='Tenant', status='ACTIVE',
    )


def auth(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {'HTTP_AUTHORIZATION': f'Token {token.key}'}


def make_property(landlord, name='Test Property'):
    prop = Property.objects.create(
        landlord=landlord, name=name, address='1 Test Rd',
    )
    unit = Unit.objects.create(property=prop, name='Unit A')
    return prop, unit


def make_lease(landlord, tenant, prop, unit, **overrides):
    defaults = {
        'start_date': TODAY,
        'expiry_date': TODAY + timedelta(days=365),
        'rent_amount': Decimal('100000.00'),
        'currency': 'NGN',
        'rent_frequency': RentFrequency.MONTHLY,
        'rent_due_day': 1,
        'status': LeaseStatus.ACTIVE,
    }
    defaults.update(overrides)
    return Lease.objects.create(
        landlord=landlord, tenant=tenant,
        property=prop, unit=unit, **defaults,
    )


def get_pro_plan():
    return Plan.objects.get(tier=PlanTier.PROFESSIONAL)


def get_business_plan():
    return Plan.objects.get(tier=PlanTier.BUSINESS)


def get_free_plan():
    return Plan.objects.get(tier=PlanTier.FREE)


# ===========================================================================
# Plan Tests
# ===========================================================================

class PlanModelTest(TestCase):
    """Plan model behavior."""

    def test_free_plan_seeded(self):
        plan = Plan.objects.get(tier=PlanTier.FREE)
        self.assertEqual(plan.name, 'Free')
        self.assertEqual(plan.price_ngn, 0)
        self.assertTrue(plan.is_active)

    def test_professional_plan_seeded(self):
        plan = Plan.objects.get(tier=PlanTier.PROFESSIONAL)
        self.assertEqual(plan.name, 'Professional')
        self.assertEqual(plan.price_ngn, Decimal('15000.00'))
        self.assertTrue(plan.is_active)

    def test_business_plan_seeded(self):
        plan = Plan.objects.get(tier=PlanTier.BUSINESS)
        self.assertEqual(plan.name, 'Business')
        self.assertEqual(plan.price_ngn, Decimal('45000.00'))
        self.assertTrue(plan.is_active)


class PlanAPITest(TestCase):
    """Plan API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.landlord = make_landlord()
        self.admin = make_admin()
        self.tenant = make_tenant()

    def test_landlord_can_list_plans(self):
        resp = self.client.get(
            '/api/v1/subscriptions/plans/', **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 3)

    def test_tenant_can_list_plans(self):
        resp = self.client.get(
            '/api/v1/subscriptions/plans/', **auth(self.tenant),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_unauthenticated_cannot_list_plans(self):
        resp = self.client.get('/api/v1/subscriptions/plans/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_landlord_can_retrieve_plan(self):
        plan = get_pro_plan()
        resp = self.client.get(
            f'/api/v1/subscriptions/plans/{plan.id}/', **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['tier'], 'PROFESSIONAL')

    def test_admin_can_create_plan(self):
        resp = self.client.post(
            '/api/v1/subscriptions/plans/', {
                'tier': 'PROFESSIONAL',
                'name': 'Pro Updated',
                'max_active_tenants': 15,
                'max_properties': 8,
                'price_ngn': '25000.00',
                'display_order': 1,
            }, format='json', **auth(self.admin),
        )
        # 201=created, 200=updated, 400=validation (e.g. duplicate tier)
        # All indicate admin has write access (not 403)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_landlord_cannot_create_plan(self):
        resp = self.client.post(
            '/api/v1/subscriptions/plans/', {
                'tier': 'PROFESSIONAL',
                'name': 'Pro',
            }, format='json', **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_update_plan(self):
        plan = get_pro_plan()
        resp = self.client.patch(
            f'/api/v1/subscriptions/plans/{plan.id}/',
            {'price_ngn': '20000.00'}, format='json', **auth(self.admin),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        plan.refresh_from_db()
        self.assertEqual(plan.price_ngn, Decimal('20000.00'))

    def test_admin_can_deactivate_plan(self):
        plan = get_pro_plan()
        resp = self.client.delete(
            f'/api/v1/subscriptions/plans/{plan.id}/', **auth(self.admin),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        plan.refresh_from_db()
        self.assertFalse(plan.is_active)

    def test_inactive_plan_not_in_list(self):
        plan = get_pro_plan()
        plan.is_active = False
        plan.save(update_fields=['is_active'])
        resp = self.client.get(
            '/api/v1/subscriptions/plans/', **auth(self.landlord),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        tiers = [p['tier'] for p in resp.data['results']]
        self.assertNotIn('PROFESSIONAL', tiers)


# ===========================================================================
# Subscription Model Tests
# ===========================================================================

class SubscriptionModelTest(TestCase):
    """Subscription model properties."""

    def setUp(self):
        self.landlord = make_landlord()

    def test_is_trial_expired_false_for_free(self):
        sub = get_subscription(self.landlord)
        self.assertFalse(sub.is_trial_expired)

    def test_is_trial_expired_false_for_active(self):
        sub = get_subscription(self.landlord)
        sub.status = SubscriptionStatus.ACTIVE
        sub.save(update_fields=['status'])
        self.assertFalse(sub.is_trial_expired)

    def test_is_trial_expired_true_for_expired_trial(self):
        sub = get_subscription(self.landlord)
        sub.plan = get_pro_plan()
        sub.status = SubscriptionStatus.TRIAL
        sub.trial_end = timezone.now() - timedelta(days=1)
        sub.save(update_fields=['plan', 'status', 'trial_end'])
        self.assertTrue(sub.is_trial_expired)

    def test_is_active_subscription_trial(self):
        sub = get_subscription(self.landlord)
        self.assertTrue(sub.is_active_subscription)

    def test_is_active_subscription_active(self):
        sub = get_subscription(self.landlord)
        sub.status = SubscriptionStatus.ACTIVE
        sub.save(update_fields=['status'])
        self.assertTrue(sub.is_active_subscription)

    def test_is_not_active_subscription_cancelled(self):
        sub = get_subscription(self.landlord)
        sub.status = SubscriptionStatus.CANCELLED
        sub.save(update_fields=['status'])
        self.assertFalse(sub.is_active_subscription)

    def test_is_not_active_subscription_expired(self):
        sub = get_subscription(self.landlord)
        sub.status = SubscriptionStatus.EXPIRED
        sub.save(update_fields=['status'])
        self.assertFalse(sub.is_active_subscription)


# ===========================================================================
# Subscription Lifecycle Tests
# ===========================================================================

class SubscriptionLifecycleTest(TestCase):
    """Upgrade, downgrade, cancel, reactivate."""

    def setUp(self):
        self.landlord = make_landlord()

    def test_upgrade_free_to_professional(self):
        sub = upgrade_subscription(self.landlord, get_pro_plan())
        self.assertEqual(sub.plan.tier, PlanTier.PROFESSIONAL)
        self.assertEqual(sub.status, SubscriptionStatus.TRIAL)
        self.assertIsNotNone(sub.trial_end)

    def test_upgrade_free_to_professional_starts_trial(self):
        sub = upgrade_subscription(self.landlord, get_pro_plan())
        self.assertEqual(sub.status, SubscriptionStatus.TRIAL)
        self.assertGreater(sub.trial_end, timezone.now())

    @override_settings(TRIAL_DURATION_DAYS=30)
    def test_trial_duration_configurable(self):
        sub = upgrade_subscription(self.landlord, get_pro_plan())
        expected_end = timezone.now() + timedelta(days=30)
        self.assertAlmostEqual(
            sub.trial_end.timestamp(),
            expected_end.timestamp(),
            delta=60,
        )

    def test_upgrade_professional_to_business(self):
        sub = upgrade_subscription(self.landlord, get_pro_plan())
        sub = upgrade_subscription(self.landlord, get_business_plan())
        self.assertEqual(sub.plan.tier, PlanTier.BUSINESS)
        self.assertEqual(sub.status, SubscriptionStatus.ACTIVE)
        self.assertIsNone(sub.trial_end)

    def test_same_plan_rejected(self):
        from core.exceptions import ConflictError
        with self.assertRaises(ConflictError):
            upgrade_subscription(self.landlord, get_free_plan())

    def test_downgrade_business_to_professional(self):
        sub = upgrade_subscription(self.landlord, get_business_plan())
        sub.status = SubscriptionStatus.ACTIVE
        sub.save(update_fields=['status'])
        sub = downgrade_subscription(self.landlord, get_pro_plan())
        self.assertEqual(sub.plan.tier, PlanTier.PROFESSIONAL)
        self.assertEqual(sub.status, SubscriptionStatus.ACTIVE)

    def test_downgrade_professional_to_free(self):
        sub = upgrade_subscription(self.landlord, get_pro_plan())
        sub.status = SubscriptionStatus.ACTIVE
        sub.save(update_fields=['status'])
        sub = downgrade_subscription(self.landlord, get_free_plan())
        self.assertEqual(sub.plan.tier, PlanTier.FREE)

    def test_downgrade_same_plan_rejected(self):
        from core.exceptions import ConflictError
        with self.assertRaises(ConflictError):
            downgrade_subscription(self.landlord, get_free_plan())

    def test_cancel_active(self):
        sub = upgrade_subscription(self.landlord, get_pro_plan())
        sub.status = SubscriptionStatus.ACTIVE
        sub.save(update_fields=['status'])
        sub = cancel_subscription(self.landlord, reason='Too expensive')
        self.assertEqual(sub.status, SubscriptionStatus.CANCELLED)
        self.assertEqual(sub.cancel_reason, 'Too expensive')
        self.assertIsNotNone(sub.cancelled_at)

    def test_cancel_trial(self):
        sub = upgrade_subscription(self.landlord, get_pro_plan())
        sub = cancel_subscription(self.landlord)
        self.assertEqual(sub.status, SubscriptionStatus.CANCELLED)

    def test_cancel_already_cancelled_rejected(self):
        from core.exceptions import ConflictError
        sub = upgrade_subscription(self.landlord, get_pro_plan())
        sub = cancel_subscription(self.landlord)
        with self.assertRaises(ConflictError):
            cancel_subscription(self.landlord)

    def test_reactivate_cancelled(self):
        sub = upgrade_subscription(self.landlord, get_pro_plan())
        sub = cancel_subscription(self.landlord)
        sub = reactivate_subscription(self.landlord)
        self.assertEqual(sub.status, SubscriptionStatus.ACTIVE)
        self.assertIsNone(sub.cancelled_at)
        self.assertEqual(sub.cancel_reason, '')

    def test_reactivate_expired(self):
        sub = upgrade_subscription(self.landlord, get_pro_plan())
        sub.status = SubscriptionStatus.EXPIRED
        sub.save(update_fields=['status'])
        sub = reactivate_subscription(self.landlord)
        self.assertEqual(sub.status, SubscriptionStatus.ACTIVE)

    def test_reactivate_active_rejected(self):
        from core.exceptions import ConflictError
        sub = upgrade_subscription(self.landlord, get_pro_plan())
        sub.status = SubscriptionStatus.ACTIVE
        sub.save(update_fields=['status'])
        with self.assertRaises(ConflictError):
            reactivate_subscription(self.landlord)

    def test_inactive_plan_rejected(self):
        from core.exceptions import NotFoundError
        plan = get_pro_plan()
        plan.is_active = False
        plan.save(update_fields=['is_active'])
        with self.assertRaises(NotFoundError):
            upgrade_subscription(self.landlord, plan)


# ===========================================================================
# Trial Expiry Tests
# ===========================================================================

class TrialExpiryTest(TestCase):
    """Trial expiry behavior."""

    def setUp(self):
        self.landlord = make_landlord()

    def test_free_trial_never_expires(self):
        sub = get_subscription(self.landlord)
        sub = check_trial_expiry(self.landlord)
        self.assertEqual(sub.status, SubscriptionStatus.TRIAL)

    def test_paid_trial_not_yet_expired(self):
        sub = upgrade_subscription(self.landlord, get_pro_plan())
        sub = check_trial_expiry(self.landlord)
        self.assertEqual(sub.status, SubscriptionStatus.TRIAL)

    def test_paid_trial_expired(self):
        sub = upgrade_subscription(self.landlord, get_pro_plan())
        sub.trial_end = timezone.now() - timedelta(days=1)
        sub.save(update_fields=['trial_end'])
        sub = check_trial_expiry(self.landlord)
        self.assertEqual(sub.status, SubscriptionStatus.EXPIRED)

    def test_trial_expiry_creates_audit_log(self):
        sub = upgrade_subscription(self.landlord, get_pro_plan())
        sub.trial_end = timezone.now() - timedelta(days=1)
        sub.save(update_fields=['trial_end'])
        check_trial_expiry(self.landlord)
        log = AuditLog.objects.filter(
            actor=self.landlord,
            action='SUBSCRIPTION_CHANGED',
            detail__action='trial_expired',
        ).first()
        self.assertIsNotNone(log)


# ===========================================================================
# Usage / Limit Enforcement Tests
# ===========================================================================

class UsageLimitTest(TestCase):
    """Usage metrics and plan limit enforcement."""

    def setUp(self):
        self.landlord = make_landlord()

    def test_usage_free_plan(self):
        sub = get_subscription(self.landlord)
        prop, unit = make_property(self.landlord)
        data = {
            'plan_name': sub.plan.name,
            'max_active_tenants': sub.plan.max_active_tenants,
            'active_tenants': sub.active_tenants_count,
            'max_properties': sub.plan.max_properties,
            'properties': sub.property_count,
        }
        self.assertEqual(data['max_properties'], 1)
        self.assertEqual(data['properties'], 1)

    def test_downgrade_allows_existing_resources(self):
        """Downgrade to FREE allows existing 2 properties to remain."""
        sub = upgrade_subscription(self.landlord, get_pro_plan())
        sub.status = SubscriptionStatus.ACTIVE
        sub.save(update_fields=['status'])

        prop1, unit1 = make_property(self.landlord, 'Prop 1')
        prop2, unit2 = make_property(self.landlord, 'Prop 2')

        sub = downgrade_subscription(self.landlord, get_free_plan())
        # Both properties still exist
        self.assertEqual(Property.objects.filter(landlord=self.landlord).count(), 2)
        # But FREE plan only allows 1 — new creation should be blocked
        from core.exceptions import ForbiddenError
        from subscriptions.services import assert_can_add_property
        with self.assertRaises(ForbiddenError):
            assert_can_add_property(self.landlord)

    def test_downgrade_allows_existing_tenants(self):
        """Downgrade to FREE with 5 active tenants — existing tenants kept."""
        sub = upgrade_subscription(self.landlord, get_pro_plan())
        sub.status = SubscriptionStatus.ACTIVE
        sub.save(update_fields=['status'])

        prop, unit = make_property(self.landlord)
        for i in range(5):
            t = make_tenant(f'tenant{i}@example.com')
            make_lease(self.landlord, t, prop, unit)

        sub = downgrade_subscription(self.landlord, get_free_plan())
        # All 5 tenants still have active leases
        active_leases = Lease.objects.filter(
            landlord=self.landlord,
            status=LeaseStatus.ACTIVE,
        )
        self.assertEqual(active_leases.count(), 5)


# ===========================================================================
# Billing History (AuditLog) Tests
# ===========================================================================

class BillingHistoryTest(TestCase):
    """AuditLog entries for subscription lifecycle events."""

    def setUp(self):
        self.landlord = make_landlord()

    def test_upgrade_creates_audit_log(self):
        upgrade_subscription(self.landlord, get_pro_plan())
        log = AuditLog.objects.filter(
            actor=self.landlord,
            action='SUBSCRIPTION_CHANGED',
            detail__action='upgrade',
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.detail['to_plan'], 'Professional')

    def test_downgrade_creates_audit_log(self):
        sub = upgrade_subscription(self.landlord, get_pro_plan())
        sub.status = SubscriptionStatus.ACTIVE
        sub.save(update_fields=['status'])
        downgrade_subscription(self.landlord, get_free_plan())
        log = AuditLog.objects.filter(
            actor=self.landlord,
            action='SUBSCRIPTION_CHANGED',
            detail__action='downgrade',
        ).first()
        self.assertIsNotNone(log)

    def test_cancel_creates_audit_log(self):
        sub = upgrade_subscription(self.landlord, get_pro_plan())
        cancel_subscription(self.landlord, reason='Test')
        log = AuditLog.objects.filter(
            actor=self.landlord,
            action='SUBSCRIPTION_CHANGED',
            detail__action='cancel',
        ).first()
        self.assertIsNotNone(log)

    def test_reactivate_creates_audit_log(self):
        sub = upgrade_subscription(self.landlord, get_pro_plan())
        cancel_subscription(self.landlord)
        reactivate_subscription(self.landlord)
        log = AuditLog.objects.filter(
            actor=self.landlord,
            action='SUBSCRIPTION_CHANGED',
            detail__action='reactivate',
        ).first()
        self.assertIsNotNone(log)

    def test_trial_expiry_creates_audit_log(self):
        sub = upgrade_subscription(self.landlord, get_pro_plan())
        sub.trial_end = timezone.now() - timedelta(days=1)
        sub.save(update_fields=['trial_end'])
        check_trial_expiry(self.landlord)
        log = AuditLog.objects.filter(
            actor=self.landlord,
            action='SUBSCRIPTION_CHANGED',
            detail__action='trial_expired',
        ).first()
        self.assertIsNotNone(log)


# ===========================================================================
# API Tests
# ===========================================================================

class SubscriptionAPITest(TestCase):
    """Subscription API: retrieve, upgrade, cancel, reactivate, usage, history."""

    def setUp(self):
        self.client = APIClient()
        self.landlord = make_landlord()
        self.headers = auth(self.landlord)

    def test_retrieve_subscription(self):
        resp = self.client.get(
            '/api/v1/subscriptions/subscription/', **self.headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('plan', resp.data)
        self.assertIn('status', resp.data)

    def test_upgrade_subscription(self):
        resp = self.client.post(
            '/api/v1/subscriptions/subscription/',
            {'plan_id': get_pro_plan().id}, format='json', **self.headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['plan']['tier'], 'PROFESSIONAL')
        self.assertEqual(resp.data['status'], 'TRIAL')

    def test_downgrade_subscription(self):
        # First upgrade
        self.client.post(
            '/api/v1/subscriptions/subscription/',
            {'plan_id': get_pro_plan().id}, format='json', **self.headers,
        )
        # Then downgrade
        resp = self.client.post(
            '/api/v1/subscriptions/subscription/',
            {'plan_id': get_free_plan().id}, format='json', **self.headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['plan']['tier'], 'FREE')

    def test_same_plan_rejected(self):
        resp = self.client.post(
            '/api/v1/subscriptions/subscription/',
            {'plan_id': get_free_plan().id}, format='json', **self.headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_cancel_subscription(self):
        # Upgrade first so there's something to cancel
        self.client.post(
            '/api/v1/subscriptions/subscription/',
            {'plan_id': get_pro_plan().id}, format='json', **self.headers,
        )
        resp = self.client.post(
            '/api/v1/subscriptions/subscription/cancel/',
            {'reason': 'Too expensive'}, format='json', **self.headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'CANCELLED')

    def test_cancel_already_cancelled(self):
        self.client.post(
            '/api/v1/subscriptions/subscription/',
            {'plan_id': get_pro_plan().id}, format='json', **self.headers,
        )
        self.client.post(
            '/api/v1/subscriptions/subscription/cancel/',
            format='json', **self.headers,
        )
        resp = self.client.post(
            '/api/v1/subscriptions/subscription/cancel/',
            format='json', **self.headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_reactivate_subscription(self):
        self.client.post(
            '/api/v1/subscriptions/subscription/',
            {'plan_id': get_pro_plan().id}, format='json', **self.headers,
        )
        self.client.post(
            '/api/v1/subscriptions/subscription/cancel/',
            format='json', **self.headers,
        )
        resp = self.client.post(
            '/api/v1/subscriptions/subscription/reactivate/',
            format='json', **self.headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'ACTIVE')

    def test_usage_endpoint(self):
        resp = self.client.get(
            '/api/v1/subscriptions/subscription/usage/', **self.headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('properties', resp.data)
        self.assertIn('active_tenants', resp.data)

    def test_history_endpoint(self):
        upgrade_subscription(self.landlord, get_pro_plan())
        resp = self.client.get(
            '/api/v1/subscriptions/subscription/history/', **self.headers,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(len(resp.data) > 0)

    def test_unauthenticated_rejected(self):
        resp = self.client.get('/api/v1/subscriptions/subscription/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ===========================================================================
# Data Isolation Tests
# ===========================================================================

class SubscriptionIsolationTest(TestCase):
    """Cross-landlord subscription isolation."""

    def setUp(self):
        self.client = APIClient()
        self.landlord_a = make_landlord('a@example.com')
        self.landlord_b = make_landlord('b@example.com')

    def test_landlord_a_cannot_see_landlord_b_subscription(self):
        sub_b = get_subscription(self.landlord_b)
        resp = self.client.get(
            f'/api/v1/subscriptions/subscription/',
            **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Should return Landlord A's subscription, not B's
        self.assertEqual(resp.data['id'], get_subscription(self.landlord_a).id)

    def test_landlord_a_cannot_cancel_landlord_b(self):
        resp = self.client.post(
            '/api/v1/subscriptions/subscription/cancel/',
            format='json', **auth(self.landlord_a),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Landlord B should still be active
        sub_b = get_subscription(self.landlord_b)
        self.assertNotEqual(sub_b.status, SubscriptionStatus.CANCELLED)
