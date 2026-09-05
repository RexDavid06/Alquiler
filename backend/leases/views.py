"""Lease & Renewal Management API views (Phase 4).

Lease lifecycle (create, edit-while-future, renew, terminate, history) is
entirely delegated to the service layer; views only scope the queryset to the
caller's tenancy relationship and define HTTP behaviour:
* Landlords list/read their leases, create them, and manage renewals.
* Tenants have read-only access to their own leases.
* Status is derived on the backend (annotated in SQL, filtered when asked).
"""

from datetime import timedelta

from django.db.models import Case, CharField, Value, When
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from leases import services

from .models import Lease, LeaseStatus
from .serializers import (
    LeaseDetailSerializer,
    LeaseHistorySerializer,
    LeaseRenewSerializer,
    LeaseSerializer,
)


class LeaseAccessPermission(BasePermission):
    """Read access for the lease's landlord or tenant; writes for landlords."""

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False
        if view.action in ('list', 'retrieve', 'history'):
            return user.is_landlord or user.is_tenant or user.is_platform_admin
        if view.action in ('create', 'update', 'partial_update', 'renew', 'terminate'):
            return user.is_landlord
        return True


def _effective_status_expression():
    """SQL mirror of Lease.effective_status() for filtering current status."""
    today = timezone.localdate()
    expiring_limit = today + timedelta(days=30)
    return Case(
        When(status=LeaseStatus.TERMINATED, then=Value(LeaseStatus.TERMINATED)),
        When(start_date__gt=today, then=Value(LeaseStatus.FUTURE)),
        When(expiry_date__lt=today, then=Value(LeaseStatus.EXPIRED)),
        When(expiry_date__lte=expiring_limit, then=Value(LeaseStatus.EXPIRING)),
        default=Value(LeaseStatus.ACTIVE),
        output_field=CharField(),
    )


class LeaseViewSet(viewsets.ModelViewSet):
    """Lease lifecycle for landlords (write) and tenants (read-only)."""

    serializer_class = LeaseSerializer
    permission_classes = [LeaseAccessPermission]
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = [
        'tenant__first_name', 'tenant__last_name', 'tenant__email',
        'property__name', 'unit__name',
    ]
    ordering_fields = ['start_date', 'expiry_date', 'rent_amount', 'created_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return LeaseDetailSerializer
        return LeaseSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Lease.objects.none()
        user = getattr(self.request, 'user', None)
        if user is not None and getattr(user, 'is_landlord', False):
            qs = Lease.objects.filter(landlord=user)
        elif user is not None and getattr(user, 'is_tenant', False):
            qs = Lease.objects.filter(tenant=user)
        elif user is not None and getattr(user, 'is_platform_admin', False):
            qs = Lease.objects.all()
        else:
            qs = Lease.objects.none()

        qs = qs.select_related('landlord', 'tenant', 'property', 'unit')
        # Derive lifecycle status in SQL so filtering and output both use the
        # computed value rather than the (possibly stale) stored status.
        qs = qs.annotate(effective_status_value=_effective_status_expression())

        lease_status = self.request.query_params.get('status')
        if lease_status:
            qs = qs.filter(effective_status_value=lease_status.upper())
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        lease = serializer.save()
        return Response(
            self.get_serializer(lease).data, status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='renew')
    def renew(self, request, pk=None):
        lease = self.get_object()
        serializer = LeaseRenewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_lease = services.renew_lease(lease, **serializer.validated_data)
        return Response(
            LeaseDetailSerializer(new_lease, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='terminate')
    def terminate(self, request, pk=None):
        lease = self.get_object()
        updated = services.terminate_lease(lease)
        return Response(
            LeaseDetailSerializer(updated, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        lease = self.get_object()
        chain = services.lease_history(lease)
        serializer = LeaseHistorySerializer(chain, many=True)
        return Response(serializer.data)