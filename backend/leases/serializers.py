"""Serializers for the Lease & Renewal Management API (Phase 4).

The serializer validates ownership/relationships and delegates the actual
lease lifecycle to the service layer (create_lease / update_lease). Status is
always computed on the backend; client-supplied lifecycle values are ignored.
"""

from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from leases import services
from properties.models import Property
from subscriptions.services import assert_can_add_lease_tenant

from .models import Lease, LeaseStatus, RentFrequency

User = get_user_model()


class RentScheduleItemSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    period_start = serializers.DateField(read_only=True)
    period_end = serializers.DateField(read_only=True)
    due_date = serializers.DateField(read_only=True)
    amount = serializers.CharField(read_only=True)
    currency = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)


class LeaseRenewSerializer(serializers.Serializer):
    """Terms for extending a previous tenancy (mirrors DB checks)."""

    start_date = serializers.DateField()
    expiry_date = serializers.DateField()
    rent_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=0,
    )
    currency = serializers.RegexField(r'^[A-Z]{3}$')
    rent_frequency = serializers.ChoiceField(choices=RentFrequency.choices)
    rent_due_day = serializers.IntegerField(min_value=1, max_value=28)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs['expiry_date'] < attrs['start_date']:
            raise serializers.ValidationError(
                {'expiry_date': 'Expiry cannot be before the start date.'},
                code='lease_dates_invalid',
            )
        return attrs


class LeaseSerializer(serializers.ModelSerializer):
    landlord = serializers.PrimaryKeyRelatedField(read_only=True)
    landlord_name = serializers.CharField(source='landlord.full_name', read_only=True)
    property_name = serializers.CharField(source='property.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    tenant_name = serializers.CharField(source='tenant.full_name', read_only=True)
    tenant_email = serializers.EmailField(source='tenant.email', read_only=True)
    # Mirrors the DB checks so invalid terms are rejected before persist.
    rent_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=0,
    )
    currency = serializers.RegexField(r'^[A-Z]{3}$')
    rent_frequency = serializers.ChoiceField(choices=RentFrequency.choices)
    rent_due_day = serializers.IntegerField(min_value=1, max_value=28)
    # Computed by the backend lifecycle; never settable by clients.
    status = serializers.SerializerMethodField()
    previous_lease = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Lease
        fields = [
            'id', 'landlord', 'landlord_name',
            'tenant', 'tenant_name', 'tenant_email',
            'property', 'property_name', 'unit', 'unit_name',
            'start_date', 'expiry_date',
            'rent_amount', 'currency', 'rent_frequency', 'rent_due_day',
            'status', 'previous_lease', 'notes',
            'terminated_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'landlord', 'property_name', 'unit_name',
            'tenant_name', 'tenant_email', 'previous_lease',
            'terminated_at', 'created_at', 'updated_at',
        ]

    def get_status(self, obj):
        value = getattr(obj, 'effective_status_value', None)
        if value is not None:
            return value
        return obj.effective_status()

    def validate(self, attrs):
        start = attrs.get('start_date')
        expiry = attrs.get('expiry_date')
        if start and expiry and expiry < start:
            raise serializers.ValidationError(
                {'expiry_date': 'Expiry cannot be before the start date.'},
                code='lease_dates_invalid',
            )
        return attrs

    def create(self, validated_data):
        landlord = self.context['request'].user
        tenant = validated_data.pop('tenant')
        property = validated_data.pop('property')
        unit = validated_data.pop('unit')
        self._validate_ownership(landlord, tenant, property, unit)
        assert_can_add_lease_tenant(landlord, tenant)
        return services.create_lease(
            landlord=landlord, tenant=tenant,
            property=property, unit=unit, **validated_data,
        )

    def update(self, instance, validated_data):
        # Only FUTURE leases are editable; the service re-validates dates,
        # unit conflicts, rent rules, and regenerates the rent schedule.
        # Relationships and lifecycle fields are immutable - reject any
        # attempt to change them instead of silently ignoring the payload.
        mutable = {
            'start_date', 'expiry_date', 'rent_amount', 'currency',
            'rent_frequency', 'rent_due_day', 'notes',
        }
        restricted = set(validated_data) - mutable
        if restricted:
            raise serializers.ValidationError(
                {
                    field: 'This field cannot be changed on an existing lease.'
                    for field in sorted(restricted)
                },
                code='field_immutable',
            )
        return services.update_lease(instance, **validated_data)

    def _validate_ownership(self, landlord, tenant, property, unit):
        if not Property.objects.filter(id=property.id, landlord=landlord).exists():
            raise serializers.ValidationError(
                {'property': 'You do not own this property.'},
                code='property_not_owned',
            )
        if unit.property_id != property.id:
            raise serializers.ValidationError(
                {'unit': 'Unit does not belong to the selected property.'},
                code='unit_property_mismatch',
            )
        if not User.objects.filter(id=tenant.id, role='TENANT').exists():
            raise serializers.ValidationError(
                {'tenant': 'Selected user is not a valid TENANT account.'},
                code='tenant_role_invalid',
            )


class LeaseDetailSerializer(LeaseSerializer):
    rent_schedule = serializers.SerializerMethodField()

    class Meta(LeaseSerializer.Meta):
        fields = LeaseSerializer.Meta.fields + ['rent_schedule']

    @extend_schema_field(RentScheduleItemSerializer(many=True))
    def get_rent_schedule(self, obj):
        from payments.services import period_status

        periods = obj.rent_schedule.all()
        return [
            {
                'id': p.id, 'period_start': p.period_start,
                'period_end': p.period_end, 'due_date': p.due_date,
                'amount': str(p.amount), 'currency': p.currency,
                'status': period_status(p),
            }
            for p in periods
        ]


class LeaseHistorySerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.full_name', read_only=True)
    property_name = serializers.CharField(source='property.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    previous_lease_id = serializers.IntegerField(read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = Lease
        fields = [
            'id', 'status', 'start_date', 'expiry_date',
            'tenant_name', 'property_name', 'unit_name',
            'previous_lease_id', 'terminated_at', 'created_at',
        ]

    def get_status(self, obj):
        return obj.effective_status()