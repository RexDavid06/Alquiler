"""Rent & Payment Management API views (Phase 5).

Data isolation is enforced at the queryset level:
* Landlords see only payments/schedules belonging to their leases.
* Tenants see only payments/schedules tied to their own leases.
* Write operations (create/update/cancel) are landlord-only.
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from payments.models import Payment, RentSchedule
from payments.services import (
    cancel_payment,
    overdue_periods,
    paid_amount,
    period_status,
    record_payment,
    remaining_amount,
    update_payment,
)

from .serializers import (
    PaymentCreateSerializer,
    PaymentSerializer,
    PaymentUpdateSerializer,
    RentScheduleSerializer,
)


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

class PaymentAccessPermission(BasePermission):
    """Read for the payment's landlord or tenant; writes for landlords only."""

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        if view.action in ('list', 'retrieve'):
            return user.is_landlord or user.is_tenant or user.is_platform_admin
        # create, update, partial_update, cancel
        return user.is_landlord


class RentScheduleAccessPermission(BasePermission):
    """Read-only for landlords and tenants."""

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        return user.is_landlord or user.is_tenant or user.is_platform_admin


# ---------------------------------------------------------------------------
# Payment ViewSet
# ---------------------------------------------------------------------------

class PaymentViewSet(viewsets.ModelViewSet):
    """Landlord-managed payment records with tenant read access.

    * Landlords: full CRUD (create, list, retrieve, partial_update, cancel).
    * Tenants: read-only (list, retrieve).
    """

    permission_classes = [PaymentAccessPermission]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['tenant__email', 'tenant__first_name', 'tenant__last_name', 'reference']
    ordering_fields = ['payment_date', 'amount', 'created_at', 'status']
    ordering = ['-payment_date', '-created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return PaymentCreateSerializer
        if self.action in ('update', 'partial_update'):
            return PaymentUpdateSerializer
        return PaymentSerializer

    def get_queryset(self):
        user = getattr(self.request, 'user', None)
        if user is None or not user.is_authenticated:
            return Payment.objects.none()

        if user.is_landlord or user.is_platform_admin:
            qs = Payment.objects.filter(landlord=user)
        elif user.is_tenant:
            qs = Payment.objects.filter(tenant=user)
        else:
            return Payment.objects.none()

        qs = qs.select_related('landlord', 'tenant', 'lease', 'rent_period')

        # Filter by payment status
        payment_status = self.request.query_params.get('status')
        if payment_status:
            qs = qs.filter(status=payment_status.upper())

        # Filter by lease
        lease_id = self.request.query_params.get('lease')
        if lease_id:
            qs = qs.filter(lease_id=lease_id)

        # Filter by tenant (landlord only)
        tenant_id = self.request.query_params.get('tenant')
        if tenant_id and user.is_landlord:
            qs = qs.filter(tenant_id=tenant_id)

        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        payment = record_payment(
            landlord=request.user,
            tenant=data['tenant'],
            lease=data['lease'],
            rent_period=data.get('rent_period'),
            amount=data['amount'],
            currency=data.get('currency', 'NGN'),
            payment_date=data['payment_date'],
            payment_method=data.get('payment_method'),
            reference=data.get('reference', ''),
            notes=data.get('notes', ''),
            status=data.get('status', 'PAID'),
            recorded_by=request.user,
        )

        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        payment = self.get_object()
        serializer = self.get_serializer(
            data=request.data, partial=True,
            context={'request': request, 'payment': payment},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        updated = update_payment(
            payment,
            amount=data.get('amount'),
            currency=data.get('currency'),
            payment_date=data.get('payment_date'),
            payment_method=data.get('payment_method'),
            reference=data.get('reference'),
            notes=data.get('notes'),
            status=data.get('status'),
            rent_period=data.get('rent_period'),
        )

        return Response(PaymentSerializer(updated).data)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """Cancel a payment — sets status to CANCELLED."""
        payment = self.get_object()
        cancelled = cancel_payment(payment)
        return Response(PaymentSerializer(cancelled).data)


# ---------------------------------------------------------------------------
# Rent Schedule ViewSet
# ---------------------------------------------------------------------------

class RentScheduleViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to rent periods for landlords and tenants.

    Supports filtering by status, lease, and tenant.
    """

    permission_classes = [RentScheduleAccessPermission]
    serializer_class = RentScheduleSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['lease__tenant__email', 'lease__tenant__first_name', 'lease__tenant__last_name']
    ordering_fields = ['due_date', 'amount', 'created_at']
    ordering = ['due_date']

    def get_queryset(self):
        user = getattr(self.request, 'user', None)
        if user is None or not user.is_authenticated:
            return RentSchedule.objects.none()

        if user.is_landlord or user.is_platform_admin:
            from leases.models import Lease
            qs = RentSchedule.objects.filter(
                lease__landlord=user,
            )
        elif user.is_tenant:
            qs = RentSchedule.objects.filter(
                lease__tenant=user,
            )
        else:
            return RentSchedule.objects.none()

        qs = qs.select_related('lease', 'lease__tenant')

        # Filter by status (requires Python-side derivation since status
        # is computed, not stored).
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = [
                p for p in qs if period_status(p) == status_filter.upper()
            ]

        # Filter by lease
        lease_id = self.request.query_params.get('lease')
        if lease_id:
            qs = [p for p in qs if p.lease_id == int(lease_id)] if hasattr(qs, '__iter__') else qs.filter(lease_id=lease_id)

        # Filter by tenant (landlord only)
        tenant_id = self.request.query_params.get('tenant')
        if tenant_id and user.is_landlord:
            qs = [p for p in qs if p.lease.tenant_id == int(tenant_id)] if hasattr(qs, '__iter__') else qs.filter(lease__tenant_id=tenant_id)

        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)
