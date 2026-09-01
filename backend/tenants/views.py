"""Tenant profile, invitation, and self-profile API views.

Data isolation is enforced at the queryset level:
* Landlord invitation views scope to `landlord=request.user` (404 otherwise).
* Landlord tenant views scope to tenants that have a Lease with the
  authenticated landlord (404 for guessing other landlords' tenants).
* Tenants can only read their own profile via /me/.
"""

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from core.permissions import IsLandlord, IsTenant
from core.serializers import UserSerializer
from core.views import _issue_token
from leases.models import Lease

from .models import TenantInvitation
from .serializers import (
    InvitationAcceptSerializer,
    InvitationSerializer,
    LandlordTenantDetailSerializer,
    LandlordTenantListSerializer,
    TenantSelfSerializer,
)
from .services import accept_invitation, resend_invitation, revoke_invitation

User = get_user_model()

ACTIVE_LEASE_STATUSES = ['ACTIVE', 'EXPIRING']


class InvitationViewSet(viewsets.ModelViewSet):
    """Landlord CRUD (create/list/retrieve) + resend/revoke for invitations."""

    serializer_class = InvitationSerializer
    permission_classes = [IsLandlord]
    http_method_names = ['get', 'post']
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['email', 'first_name', 'last_name']
    ordering_fields = ['created_at', 'expires_at']
    ordering = ['-created_at']

    def get_queryset(self):
        landlord = getattr(self.request, 'user', None)
        if landlord is None or not getattr(landlord, 'is_authenticated', False):
            return TenantInvitation.objects.none()
        qs = TenantInvitation.objects.filter(landlord=landlord).select_related(
            'property', 'unit',
        )
        invite_status = self.request.query_params.get('status')
        if invite_status:
            qs = qs.filter(status=invite_status.upper())
        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['landlord'] = self.request.user
        return context

    @action(detail=True, methods=['post'])
    def resend(self, request, pk=None):
        invitation = self.get_object()
        new_invitation = resend_invitation(invitation)
        serializer = self.get_serializer(new_invitation)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        invitation = self.get_object()
        updated = revoke_invitation(invitation)
        serializer = self.get_serializer(updated)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TenantViewSet(viewsets.ReadOnlyModelViewSet):
    """Landlord read access to tenants linked to their leases."""

    permission_classes = [IsLandlord]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['email', 'first_name', 'last_name']
    ordering_fields = ['first_name', 'last_name', 'email', 'created_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return LandlordTenantDetailSerializer
        return LandlordTenantListSerializer

    def get_queryset(self):
        landlord = getattr(self.request, 'user', None)
        if landlord is None or not getattr(landlord, 'is_authenticated', False):
            return User.objects.none()

        tenant_ids = Lease.objects.filter(landlord=landlord).values('tenant_id')
        qs = User.objects.filter(
            id__in=tenant_ids, role='TENANT',
        ).annotate(
            total_leases=Count(
                'tenant_leases',
                filter=Q(tenant_leases__landlord=landlord),
            ),
            active_leases=Count(
                'tenant_leases',
                filter=Q(
                    tenant_leases__landlord=landlord,
                    tenant_leases__status__in=ACTIVE_LEASE_STATUSES,
                ),
            ),
        )
        user_status = self.request.query_params.get('status')
        if user_status:
            qs = qs.filter(status=user_status.upper())
        return qs


class TenantMeView(GenericAPIView):
    """A tenant's own profile and lease information."""

    serializer_class = TenantSelfSerializer
    permission_classes = [IsTenant]

    def get(self, request):
        return Response(self.get_serializer(request.user).data)


class AcceptInvitationView(GenericAPIView):
    """Consume a landlord invitation and onboard/activate the tenant."""

    serializer_class = InvitationAcceptSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, invitation = accept_invitation(
            serializer.validated_data['token'],
            first_name=serializer.validated_data.get('first_name', ''),
            last_name=serializer.validated_data.get('last_name', ''),
            phone=serializer.validated_data.get('phone', ''),
            password=serializer.validated_data['password'],
        )
        return Response(
            {
                'user': UserSerializer(user).data,
                'token': _issue_token(user),
                'invitation': {
                    'landlord': invitation.landlord.full_name,
                    'property': invitation.property.name,
                    'unit': invitation.unit.name,
                },
            },
            status=status.HTTP_201_CREATED,
        )