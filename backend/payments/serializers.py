"""Serializers for the Rent & Payment Management API (Phase 5).

Payment creation/update validates ownership (lease/tenant/period belong to
the authenticated landlord).  Clients never supply landlord, calculated
financial fields (paid_amount, remaining_amount, status) are derived on the
server and never writable.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from leases.models import Lease
from payments.models import Payment, PaymentMethod, PaymentStatus, RentSchedule
from payments.services import paid_amount, period_status, remaining_amount

User = get_user_model()


# ---------------------------------------------------------------------------
# Rent Schedule (read-only)
# ---------------------------------------------------------------------------

class RentScheduleSerializer(serializers.ModelSerializer):
    """Read-only representation of a rent period with derived financial fields."""

    status = serializers.SerializerMethodField()
    paid_amount = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()
    lease_id = serializers.PrimaryKeyRelatedField(source='lease', read_only=True)

    class Meta:
        model = RentSchedule
        fields = [
            'id', 'lease_id', 'period_start', 'period_end', 'due_date',
            'amount', 'currency', 'notes',
            'status', 'paid_amount', 'remaining_amount',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_status(self, obj):
        return period_status(obj)

    def get_paid_amount(self, obj):
        return str(paid_amount(obj))

    def get_remaining_amount(self, obj):
        return str(remaining_amount(obj))


# ---------------------------------------------------------------------------
# Payment (read)
# ---------------------------------------------------------------------------

class PaymentSerializer(serializers.ModelSerializer):
    """Full read representation of a payment record."""

    class Meta:
        model = Payment
        fields = [
            'id', 'landlord', 'tenant', 'lease', 'rent_period',
            'amount', 'currency', 'payment_date', 'payment_method',
            'reference', 'notes', 'status',
            'gateway', 'gateway_reference', 'verified',
            'recorded_by', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'landlord', 'tenant', 'lease',
            'gateway', 'gateway_reference', 'verified',
            'recorded_by', 'created_at', 'updated_at',
        ]


# ---------------------------------------------------------------------------
# Payment (create)
# ---------------------------------------------------------------------------

class PaymentCreateSerializer(serializers.Serializer):
    """Validates a new payment: ensures lease/tenant/period belong to the
    authenticated landlord.  Delegates to ``record_payment()``."""

    tenant = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),  # scoped in __init__
    )
    lease = serializers.PrimaryKeyRelatedField(
        queryset=Lease.objects.all(),  # scoped in __init__
    )
    rent_period = serializers.PrimaryKeyRelatedField(
        queryset=RentSchedule.objects.all(), required=False, allow_null=True,
    )
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)
    currency = serializers.RegexField(r'^[A-Z]{3}$', default='NGN')
    payment_date = serializers.DateField()
    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices, default=PaymentMethod.BANK_TRANSFER,
    )
    reference = serializers.CharField(max_length=200, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(
        choices=PaymentStatus.choices, default=PaymentStatus.PAID,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Scope querysets to the authenticated landlord.
        user = self.context['request'].user
        self.fields['tenant'].queryset = User.objects.filter(role='TENANT')
        self.fields['lease'].queryset = Lease.objects.filter(landlord=user)

    def validate_lease(self, lease):
        """Ensure the lease belongs to the authenticated landlord."""
        user = self.context['request'].user
        if lease.landlord_id != user.id:
            raise serializers.ValidationError(
                'You do not own this lease.',
                code='lease_not_owned',
            )
        return lease

    def validate_rent_period(self, period):
        """If provided, ensure the rent period belongs to a lease owned by the landlord."""
        if period is None:
            return period
        user = self.context['request'].user
        if not Lease.objects.filter(id=period.lease_id, landlord=user).exists():
            raise serializers.ValidationError(
                'This rent period does not belong to any of your leases.',
                code='period_not_owned',
            )
        return period

    def validate(self, attrs):
        """Cross-field: rent_period must belong to the selected lease."""
        lease = attrs.get('lease')
        period = attrs.get('rent_period')
        if period is not None and lease is not None:
            if period.lease_id != lease.id:
                raise serializers.ValidationError(
                    {'rent_period': 'This rent period does not belong to the selected lease.'},
                    code='period_lease_mismatch',
                )
        # Ensure the tenant has a lease with this landlord (via the selected lease).
        tenant = attrs.get('tenant')
        if tenant is not None and lease is not None:
            if lease.tenant_id != tenant.id:
                raise serializers.ValidationError(
                    {'tenant': 'This tenant does not belong to the selected lease.'},
                    code='tenant_lease_mismatch',
                )
        return attrs


# ---------------------------------------------------------------------------
# Payment (update)
# ---------------------------------------------------------------------------

class PaymentUpdateSerializer(serializers.Serializer):
    """Partial update of a payment.  Only mutable fields are allowed."""

    amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=0, required=False,
    )
    currency = serializers.RegexField(r'^[A-Z]{3}$', required=False)
    payment_date = serializers.DateField(required=False)
    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices, required=False,
    )
    reference = serializers.CharField(max_length=200, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=PaymentStatus.choices, required=False)
    rent_period = serializers.PrimaryKeyRelatedField(
        queryset=RentSchedule.objects.all(), required=False, allow_null=True,
    )

    def validate_rent_period(self, period):
        """Ensure the target rent period belongs to one of the landlord's leases."""
        if period is None:
            return period
        user = self.context['request'].user
        if not Lease.objects.filter(id=period.lease_id, landlord=user).exists():
            raise serializers.ValidationError(
                'This rent period does not belong to any of your leases.',
                code='period_not_owned',
            )
        return period

    def validate_status(self, value):
        """Prevent clients from directly setting status to PAID via update.
        Status changes should go through the cancel action instead."""
        return value

    def validate(self, attrs):
        """Cross-field: if both rent_period and (implicitly) the payment's
        existing lease are known, verify consistency."""
        period = attrs.get('rent_period')
        if period is not None:
            # The parent view will have the payment object; verify the period
            # belongs to the same lease as the payment.
            payment = self.context.get('payment')
            if payment is not None and period.lease_id != payment.lease_id:
                raise serializers.ValidationError(
                    {'rent_period': 'Cannot move payment to a different lease.'},
                    code='period_lease_mismatch',
                )
        return attrs
