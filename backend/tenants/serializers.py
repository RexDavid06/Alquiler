"""Serializers for tenant profiles, invitations, and tenant visibility."""

from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from core.exceptions import NotFoundError
from leases.models import Lease
from properties.models import Property, PropertyStatus, Unit

from .models import TenantInvitation
from .services import create_invitation

User = get_user_model()


class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField()
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)


class InvitationSerializer(serializers.ModelSerializer):
    """Landlord-facing invitation. Never exposes the token."""

    property_name = serializers.CharField(source='property.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)

    class Meta:
        model = TenantInvitation
        fields = [
            'id', 'email', 'first_name', 'last_name', 'phone',
            'property', 'property_name', 'unit', 'unit_name',
            'status', 'expires_at', 'created_at',
        ]
        read_only_fields = ['id', 'status', 'expires_at', 'created_at']

    def validate_email(self, value):
        return value.strip().lower()

    def validate(self, attrs):
        landlord = self.context['landlord']
        property = attrs.get('property')
        unit = attrs.get('unit')

        if property is None or unit is None:
            raise serializers.ValidationError(
                'Both property and unit are required.', code='property_unit_required',
            )
        # The property must belong to the authenticated landlord.
        if not Property.objects.filter(id=property.id, landlord=landlord).exists():
            raise NotFoundError('Property not found.', code='property_not_found')
        if property.status == PropertyStatus.ARCHIVED:
            raise serializers.ValidationError(
                'Cannot invite tenants to an archived property.', code='property_archived',
            )
        if unit.property_id != property.id:
            raise serializers.ValidationError(
                'Unit does not belong to the selected property.',
                code='unit_property_mismatch',
            )
        return attrs

    def create(self, validated_data):
        return create_invitation(landlord=self.context['landlord'], **validated_data)


class TenantLeaseSummarySerializer(serializers.ModelSerializer):
    property_name = serializers.CharField(source='property.name', read_only=True)
    unit_name = serializers.CharField(source='unit.name', read_only=True)
    landlord_name = serializers.CharField(source='landlord.full_name', read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Lease
        fields = [
            'id', 'landlord_name', 'property_name', 'unit_name', 'status',
            'start_date', 'expiry_date', 'rent_amount', 'currency',
            'rent_frequency', 'created_at',
        ]


class LandlordTenantListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    total_leases = serializers.IntegerField(read_only=True)
    active_leases = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'full_name', 'first_name', 'last_name', 'phone',
            'status', 'email_verified', 'created_at',
            'total_leases', 'active_leases',
        ]


class LandlordTenantDetailSerializer(LandlordTenantListSerializer):
    leases = serializers.SerializerMethodField()

    class Meta(LandlordTenantListSerializer.Meta):
        fields = LandlordTenantListSerializer.Meta.fields + ['leases']

    @extend_schema_field(TenantLeaseSummarySerializer(many=True))
    def get_leases(self, obj):
        request = self.context.get('request')
        if request is None or not getattr(getattr(request, 'user', None), 'is_authenticated', False):
            return []
        landlord = getattr(request, 'user')
        qs = obj.tenant_leases.filter(landlord=landlord)
        return TenantLeaseSummarySerializer(qs, many=True).data


class TenantSelfSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    leases = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'full_name', 'first_name', 'last_name', 'phone',
            'status', 'email_verified', 'created_at', 'leases',
        ]

    @extend_schema_field(TenantLeaseSummarySerializer(many=True))
    def get_leases(self, obj):
        qs = obj.tenant_leases.all()
        return TenantLeaseSummarySerializer(qs, many=True).data