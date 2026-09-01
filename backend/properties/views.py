"""Property and Unit API views.

Data isolation is enforced at the queryset level: every view scopes the
queryset to the authenticated landlord, so requesting or mutating another
landlord's property/unit yields a 404 (the resource does not exist in the
caller's scope). Client-supplied IDs are never trusted.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from core.exceptions import ConflictError
from core.permissions import IsLandlord
from subscriptions.services import assert_can_add_property

from .models import Property, PropertyStatus, Unit
from .serializers import PropertySerializer, UnitSerializer


class PropertyViewSet(viewsets.ModelViewSet):
    """Landlord CRUD for their own properties."""

    serializer_class = PropertySerializer
    permission_classes = [IsLandlord]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'property_type', 'city', 'state', 'country', 'address']
    ordering_fields = ['name', 'city', 'state', 'property_type', 'created_at', 'updated_at']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = Property.objects.select_related('landlord')
        # Schema generation runs without an authenticated request user.
        user = getattr(self.request, 'user', None)
        if user is not None and user.is_authenticated:
            qs = qs.filter(landlord=user)
        property_type = self.request.query_params.get('property_type')
        if property_type:
            qs = qs.filter(property_type=property_type.upper())
        prop_status = self.request.query_params.get('status')
        if prop_status:
            qs = qs.filter(status=prop_status.upper())
        return qs

    def perform_create(self, serializer):
        # Enforce the subscription property limit before creating.
        assert_can_add_property(self.request.user)
        serializer.save(landlord=self.request.user)

    def destroy(self, request, *args, **kwargs):
        # Data-integrity rule: a property that owns units or is referenced by
        # lease/payment history cannot be hard-deleted (Lease FKs are PROTECT
        # and units would silently cascade away). Archive it instead.
        instance = self.get_object()
        if instance.units.exists():
            instance.status = PropertyStatus.ARCHIVED
            instance.save(update_fields=['status', 'updated_at'])
            serializer = self.get_serializer(instance)
            return Response(serializer.data, status=status.HTTP_200_OK)
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UnitViewSet(viewsets.ModelViewSet):
    """Landlord CRUD for units belonging to their own property."""

    serializer_class = UnitSerializer
    permission_classes = [IsLandlord]
    lookup_url_kwarg = 'unit_pk'
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['name']

    def _get_owned_property(self):
        """Resolve the property from the URL and verify landowner ownership."""
        property_id = self.kwargs.get('property_pk')
        if property_id is None:
            raise NotFound('Property not specified.')
        return get_object_or_404(
            Property.objects.filter(landlord=self.request.user),
            id=property_id,
        )

    def get_queryset(self):
        qs = Unit.objects.select_related('property')
        # Schema generation runs without an authenticated request user.
        user = getattr(self.request, 'user', None)
        if user is None or not user.is_authenticated:
            return qs
        property = self._get_owned_property()
        return qs.filter(property=property)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        user = getattr(self.request, 'user', None)
        if user is not None and user.is_authenticated:
            context['property'] = self._get_owned_property()
        return context

    def perform_create(self, serializer):
        property = self._get_owned_property()
        serializer.save(property=property)

    def destroy(self, request, *args, **kwargs):
        # A unit referenced by any lease (even a historical one) must not be
        # hard-deleted; Lease.unit is PROTECT, so deletion would orphan the
        # tenancy record. Refuse with a clear conflict error.
        instance = self.get_object()
        if instance.leases.exists():
            raise ConflictError(
                'This unit is referenced by tenancy history and cannot be '
                'deleted. Archive the property instead.',
                code='unit_has_leases',
            )
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)