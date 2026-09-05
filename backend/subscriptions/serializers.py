"""Serializers for the Subscription API."""

from rest_framework import serializers

from .models import BillingCycle, Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    """Read/write representation of a subscription plan.

    All fields are writable for admin. Read-only for regular users
    (enforced at the view/permission level).
    """

    class Meta:
        model = Plan
        fields = [
            'id', 'tier', 'name', 'description',
            'max_active_tenants', 'max_properties',
            'price_ngn', 'is_active', 'display_order',
        ]


class SubscriptionSerializer(serializers.ModelSerializer):
    """Read representation of a landlord's subscription."""

    plan = PlanSerializer(read_only=True)
    is_trial_expired = serializers.BooleanField(read_only=True)
    is_active_subscription = serializers.BooleanField(read_only=True)
    active_tenants_count = serializers.IntegerField(read_only=True)
    property_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            'id', 'plan', 'status', 'billing_cycle',
            'started_at', 'current_period_start', 'current_period_end',
            'trial_end', 'cancelled_at', 'cancel_reason',
            'is_trial_expired', 'is_active_subscription',
            'active_tenants_count', 'property_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'plan', 'status', 'started_at',
            'current_period_start', 'current_period_end',
            'trial_end', 'cancelled_at', 'cancel_reason',
            'created_at', 'updated_at',
        ]


class SubscriptionCreateSerializer(serializers.Serializer):
    """Validate a subscription upgrade/downgrade request."""

    plan_id = serializers.IntegerField()
    billing_cycle = serializers.ChoiceField(
        choices=BillingCycle.choices,
        default=BillingCycle.MONTHLY,
    )

    def validate_plan_id(self, value):
        try:
            plan = Plan.objects.get(id=value, is_active=True)
        except Plan.DoesNotExist:
            raise serializers.ValidationError(
                'Plan not found or inactive.',
                code='plan_not_found',
            )
        self._plan = plan
        return value

    def validate(self, attrs):
        attrs['plan'] = self._plan
        return attrs


class SubscriptionCancelSerializer(serializers.Serializer):
    """Validate a subscription cancellation request."""

    reason = serializers.CharField(required=False, allow_blank=True, default='')


class UsageSerializer(serializers.Serializer):
    """Read representation of subscription usage metrics."""

    plan_name = serializers.CharField(source='plan.name', read_only=True)
    max_active_tenants = serializers.IntegerField(source='plan.max_active_tenants', read_only=True)
    active_tenants = serializers.IntegerField(read_only=True)
    max_properties = serializers.IntegerField(source='plan.max_properties', read_only=True)
    properties = serializers.IntegerField(read_only=True)
