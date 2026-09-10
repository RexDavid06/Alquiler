"""Serializers for platform-wide admin views.

Read-only serializers for inspecting users, properties, subscriptions,
and operational issues across the entire platform. No write operations
are defined here — all mutations go through existing domain services.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from core.models import AuditLog, Role
from leases.models import Lease, LeaseStatus
from payments.models import Payment, PaymentStatus, RentSchedule
from payments.services import paid_amount, period_status, remaining_amount
from properties.models import Property, Unit, UnitStatus, UnitStatus
from subscriptions.models import Plan, Subscription, SubscriptionStatus

User = get_user_model()


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class AdminUserSerializer(serializers.ModelSerializer):
    """Platform-wide user listing for admins."""

    full_name = serializers.CharField(read_only=True)
    property_count = serializers.SerializerMethodField()
    lease_count = serializers.SerializerMethodField()
    subscription_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'role', 'first_name', 'last_name', 'phone',
            'full_name', 'status', 'email_verified', 'created_at', 'updated_at',
            'property_count', 'lease_count', 'subscription_status',
        ]
        read_only_fields = fields

    def get_property_count(self, obj):
        if obj.role == Role.LANDLORD:
            return obj.properties.count()
        return None

    def get_lease_count(self, obj):
        if obj.role == Role.LANDLORD:
            return Lease.objects.filter(landlord=obj).count()
        if obj.role == Role.TENANT:
            return Lease.objects.filter(tenant=obj).count()
        return None

    def get_subscription_status(self, obj):
        if obj.role == Role.LANDLORD:
            try:
                sub = obj.subscription
                return sub.status
            except Subscription.DoesNotExist:
                return None
        return None


class AdminUserDetailSerializer(AdminUserSerializer):
    """Detailed user view with related entities."""

    recent_leases = serializers.SerializerMethodField()
    recent_payments = serializers.SerializerMethodField()

    class Meta(AdminUserSerializer.Meta):
        fields = AdminUserSerializer.Meta.fields + [
            'recent_leases', 'recent_payments',
        ]

    def get_recent_leases(self, obj):
        if obj.role == Role.LANDLORD:
            qs = Lease.objects.filter(landlord=obj).select_related(
                'tenant', 'property', 'unit',
            )[:10]
        elif obj.role == Role.TENANT:
            qs = Lease.objects.filter(tenant=obj).select_related(
                'landlord', 'property', 'unit',
            )[:10]
        else:
            return []
        return [
            {
                'id': l.id,
                'status': l.effective_status(),
                'tenant_name': l.tenant.full_name,
                'property_name': l.property.name,
                'unit_name': l.unit.name,
                'rent_amount': str(l.rent_amount),
                'start_date': str(l.start_date),
                'expiry_date': str(l.expiry_date),
            }
            for l in qs
        ]

    def get_recent_payments(self, obj):
        if obj.role == Role.LANDLORD:
            qs = Payment.objects.filter(
                landlord=obj,
            ).select_related('tenant', 'lease')[:10]
        elif obj.role == Role.TENANT:
            qs = Payment.objects.filter(
                tenant=obj,
            ).select_related('landlord', 'lease')[:10]
        else:
            return []
        return [
            {
                'id': p.id,
                'amount': str(p.amount),
                'currency': p.currency,
                'status': p.status,
                'payment_date': str(p.payment_date),
                'payment_method': p.payment_method,
            }
            for p in qs
        ]


# ---------------------------------------------------------------------------
# Property
# ---------------------------------------------------------------------------

class AdminPropertySerializer(serializers.ModelSerializer):
    """Platform-wide property listing for admins."""

    landlord_name = serializers.CharField(source='landlord.full_name', read_only=True)
    landlord_email = serializers.EmailField(source='landlord.email', read_only=True)
    unit_count = serializers.SerializerMethodField()
    occupied_units = serializers.SerializerMethodField()
    vacant_units = serializers.SerializerMethodField()

    class Meta:
        model = Property
        fields = [
            'id', 'landlord', 'landlord_name', 'landlord_email',
            'name', 'property_type', 'address', 'city', 'state', 'country',
            'currency', 'status', 'unit_count', 'occupied_units', 'vacant_units',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_unit_count(self, obj):
        val = getattr(obj, '_unit_count', None)
        if val is not None:
            return val
        return obj.units.count()

    def get_occupied_units(self, obj):
        val = getattr(obj, '_occupied_units', None)
        if val is not None:
            return val
        return obj.units.filter(status=UnitStatus.OCCUPIED).count()

    def get_vacant_units(self, obj):
        val = getattr(obj, '_vacant_units', None)
        if val is not None:
            return val
        return obj.units.filter(status=UnitStatus.VACANT).count()


class AdminPropertyDetailSerializer(AdminPropertySerializer):
    """Detailed property view with units."""

    units = serializers.SerializerMethodField()

    class Meta(AdminPropertySerializer.Meta):
        fields = AdminPropertySerializer.Meta.fields + ['description', 'units']

    def get_units(self, obj):
        units = obj.units.all()
        return [
            {
                'id': u.id,
                'name': u.name,
                'description': u.description,
                'status': u.status,
                'created_at': u.created_at,
            }
            for u in units
        ]


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------

class AdminSubscriptionSerializer(serializers.ModelSerializer):
    """Platform-wide subscription listing for admins."""

    landlord_email = serializers.EmailField(source='landlord.email', read_only=True)
    landlord_name = serializers.CharField(source='landlord.full_name', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_tier = serializers.CharField(source='plan.tier', read_only=True)

    class Meta:
        model = Subscription
        fields = [
            'id', 'landlord', 'landlord_email', 'landlord_name',
            'plan', 'plan_name', 'plan_tier',
            'status', 'billing_cycle',
            'started_at', 'current_period_start', 'current_period_end',
            'trial_end', 'cancelled_at', 'cancel_reason',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

class AdminPlanSerializer(serializers.ModelSerializer):
    """Platform plan listing for admins with subscriber counts."""

    subscriber_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Plan
        fields = [
            'id', 'tier', 'name', 'description',
            'max_active_tenants', 'max_properties',
            'price_ngn', 'is_active', 'display_order',
            'subscriber_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# ---------------------------------------------------------------------------
# Operational Issues
# ---------------------------------------------------------------------------

class OperationalIssueSerializer(serializers.Serializer):
    """Represents an operational issue found on the platform."""

    ISSUE_TYPES = [
        ('failed_payment', 'Failed Payment'),
        ('overdue_rent', 'Overdue Rent'),
        ('expired_lease', 'Expired Lease'),
        ('suspended_user', 'Suspended User'),
        ('expired_subscription', 'Expired Subscription'),
        ('past_due_subscription', 'Past Due Subscription'),
    ]

    issue_type = serializers.CharField()
    severity = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    entity_type = serializers.CharField()
    entity_id = serializers.IntegerField()
    related_url = serializers.CharField(required=False, allow_blank=True)
    created_at = serializers.CharField()


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

class AdminAuditLogSerializer(serializers.ModelSerializer):
    """Platform-wide audit log listing for admins."""

    actor_email = serializers.EmailField(source='actor.email', read_only=True, default=None)
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            'id', 'actor', 'actor_email', 'actor_name',
            'action', 'object_type', 'object_id', 'detail', 'created_at',
        ]
        read_only_fields = fields

    def get_actor_name(self, obj):
        if obj.actor:
            return obj.actor.full_name
        return None
