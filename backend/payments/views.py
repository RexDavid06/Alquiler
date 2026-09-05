"""Rent & Payment Management API views (Phase 5).

Data isolation is enforced at the queryset level:
* Landlords see only payments/schedules belonging to their leases.
* Tenants see only payments/schedules tied to their own leases.
* Write operations (create/update/cancel) are landlord-only.
"""

from decimal import Decimal

from django.db.models import Case, F, Q, Sum, Value, When
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from payments.models import Payment, PaymentStatus, RentSchedule
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

    serializer_class = PaymentSerializer
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
        if getattr(self, 'swagger_fake_view', False):
            return Payment.objects.none()
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
    Status filtering is DB-level: the paid amount is annotated via a
    conditional aggregation subquery so that the queryset remains
    filterable, orderable, and paginated.
    """

    permission_classes = [RentScheduleAccessPermission]
    serializer_class = RentScheduleSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['lease__tenant__email', 'lease__tenant__first_name', 'lease__tenant__last_name']
    ordering_fields = ['due_date', 'amount', 'created_at']
    ordering = ['due_date']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return RentSchedule.objects.none()
        user = getattr(self.request, 'user', None)
        if user is None or not user.is_authenticated:
            return RentSchedule.objects.none()

        if user.is_landlord or user.is_platform_admin:
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

        # Annotate the aggregate paid amount so status filtering
        # can be expressed as DB-level conditions.
        paid_annotation = Sum(
            'payments__amount',
            filter=Q(payments__status=PaymentStatus.PAID),
            default=Decimal('0'),
        )
        qs = qs.annotate(_paid=paid_annotation)

        # DB-level status filtering using the annotated _paid value.
        status_filter = self.request.query_params.get('status')
        if status_filter:
            today = timezone.localdate()
            sf = status_filter.upper()
            if sf == 'PAID':
                qs = qs.filter(_paid__gte=F('amount'))
            elif sf == 'PARTIALLY_PAID':
                qs = qs.filter(_paid__gt=0, _paid__lt=F('amount'))
            elif sf == 'UPCOMING':
                qs = qs.filter(_paid=0, due_date__gt=today)
            elif sf == 'DUE':
                qs = qs.filter(_paid=0, due_date=today)
            elif sf == 'OVERDUE':
                qs = qs.filter(_paid=0, due_date__lt=today)
            else:
                # Unknown status → empty result, keep queryset type.
                qs = qs.none()

        # Filter by lease
        lease_id = self.request.query_params.get('lease')
        if lease_id:
            qs = qs.filter(lease_id=lease_id)

        # Filter by tenant (landlord only)
        tenant_id = self.request.query_params.get('tenant')
        if tenant_id and user.is_landlord:
            qs = qs.filter(lease__tenant_id=tenant_id)

        return qs
