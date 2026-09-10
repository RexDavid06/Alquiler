"""Platform administration API views.

Provides read-only platform-wide visibility for users, properties,
subscriptions, and operational issues. All endpoints enforce PLATFORM_ADMIN
authorization at the backend level.

Write operations are NOT exposed here — all mutations go through existing
domain services (leases, payments, subscriptions). This module is strictly
for operational inspection.
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import ConflictError
from core.models import AccountStatus, AuditLog, Role, User
from core.pagination import StandardPagination
from leases.models import Lease, LeaseStatus
from payments.models import Payment, PaymentStatus, RentSchedule
from payments.services import period_status, remaining_amount
from properties.models import Property, PropertyStatus, Unit, UnitStatus
from subscriptions.models import Plan, Subscription, SubscriptionStatus

from .serializers import (
    AdminPlanSerializer,
    AdminPropertyDetailSerializer,
    AdminPropertySerializer,
    AdminSubscriptionSerializer,
    AdminUserDetailSerializer,
    AdminUserSerializer,
    AuditLogSerializer,
)


# ---------------------------------------------------------------------------
# Permission
# ---------------------------------------------------------------------------

class IsPlatformAdminPermission(BasePermission):
    """Only PLATFORM_ADMIN may access these endpoints."""

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        return bool(user and user.is_authenticated and user.is_platform_admin)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class AdminUserViewSet(viewsets.ReadOnlyModelViewSet):
    """Platform-wide user listing for administrators.

    Supports search by email/name, filtering by role and status,
    and server-side pagination.
    """

    serializer_class = AdminUserSerializer
    permission_classes = [IsPlatformAdminPermission]
    pagination_class = StandardPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['email', 'first_name', 'last_name']
    ordering_fields = ['email', 'role', 'status', 'created_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AdminUserDetailSerializer
        return AdminUserSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return User.objects.none()
        qs = User.objects.all()

        role = self.request.query_params.get('role')
        if role:
            qs = qs.filter(role=role.upper())

        acct_status = self.request.query_params.get('status')
        if acct_status:
            qs = qs.filter(status=acct_status.upper())

        return qs


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

class AdminPropertyViewSet(viewsets.ReadOnlyModelViewSet):
    """Platform-wide property listing for administrators.

    Supports search by name/address, filtering by landlord, property type,
    and status. Includes unit counts.
    """

    serializer_class = AdminPropertySerializer
    permission_classes = [IsPlatformAdminPermission]
    pagination_class = StandardPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'address', 'city', 'state', 'landlord__email', 'landlord__first_name', 'landlord__last_name']
    ordering_fields = ['name', 'city', 'property_type', 'status', 'created_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AdminPropertyDetailSerializer
        return AdminPropertySerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Property.objects.none()
        qs = Property.objects.select_related('landlord').prefetch_related('units')

        landlord_id = self.request.query_params.get('landlord')
        if landlord_id:
            qs = qs.filter(landlord_id=landlord_id)

        property_type = self.request.query_params.get('property_type')
        if property_type:
            qs = qs.filter(property_type=property_type.upper())

        prop_status = self.request.query_params.get('status')
        if prop_status:
            qs = qs.filter(status=prop_status.upper())

        # Annotate unit counts (prefixed to avoid conflict with model properties)
        qs = qs.annotate(
            _unit_count=Count('units'),
            _occupied_units=Count('units', filter=Q(units__status=UnitStatus.OCCUPIED)),
            _vacant_units=Count('units', filter=Q(units__status=UnitStatus.VACANT)),
        )

        return qs


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

class AdminSubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """Platform-wide subscription listing for administrators.

    Supports search by landlord email/name, filtering by plan tier and status.
    """

    serializer_class = AdminSubscriptionSerializer
    permission_classes = [IsPlatformAdminPermission]
    pagination_class = StandardPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['landlord__email', 'landlord__first_name', 'landlord__last_name', 'plan__name']
    ordering_fields = ['status', 'billing_cycle', 'started_at', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Subscription.objects.none()
        qs = Subscription.objects.select_related('landlord', 'plan')

        plan_tier = self.request.query_params.get('plan')
        if plan_tier:
            qs = qs.filter(plan__tier=plan_tier.upper())

        sub_status = self.request.query_params.get('status')
        if sub_status:
            qs = qs.filter(status=sub_status.upper())

        landlord_id = self.request.query_params.get('landlord')
        if landlord_id:
            qs = qs.filter(landlord_id=landlord_id)

        return qs


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

class AdminPlanViewSet(viewsets.ModelViewSet):
    """Platform plan management for administrators.

    Full CRUD with subscriber counts, activate/deactivate actions,
    and subscriber listing per plan.
    """

    serializer_class = AdminPlanSerializer
    permission_classes = [IsPlatformAdminPermission]
    pagination_class = StandardPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'tier']
    ordering_fields = ['name', 'tier', 'price_ngn', 'display_order', 'is_active', 'created_at']
    ordering = ['display_order', 'price_ngn']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Plan.objects.none()
        return Plan.objects.annotate(subscriber_count=Count('subscriptions'))

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        plan = self.get_object()
        plan.is_active = True
        plan.save(update_fields=['is_active', 'updated_at'])
        serializer = self.get_serializer(plan)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        plan = self.get_object()
        active_subs = Subscription.objects.filter(
            plan=plan,
            status__in=[SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE],
        ).count()
        if active_subs:
            raise ConflictError(
                f'Cannot deactivate plan "{plan.name}": {active_subs} active subscription(s) exist.'
            )
        plan.is_active = False
        plan.save(update_fields=['is_active', 'updated_at'])
        serializer = self.get_serializer(plan)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def subscribers(self, request, pk=None):
        plan = self.get_object()
        subs = Subscription.objects.filter(plan=plan).select_related('landlord')
        paginator = StandardPagination()
        page = paginator.paginate_queryset(subs, request)
        data = [
            {
                'id': s.id,
                'landlord_email': s.landlord.email,
                'landlord_name': s.landlord.full_name,
                'status': s.status,
                'billing_cycle': s.billing_cycle,
                'started_at': s.started_at,
                'trial_end': s.trial_end,
            }
            for s in page
        ]
        return paginator.get_paginated_response(data)


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Platform-wide audit log listing for administrators."""

    serializer_class = AuditLogSerializer
    permission_classes = [IsPlatformAdminPermission]
    pagination_class = StandardPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['action', 'object_type']
    ordering_fields = ['action', 'object_type', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return AuditLog.objects.none()
        qs = AuditLog.objects.select_related('actor')

        action = self.request.query_params.get('action')
        if action:
            qs = qs.filter(action=action)

        object_type = self.request.query_params.get('object_type')
        if object_type:
            qs = qs.filter(object_type=object_type)

        actor = self.request.query_params.get('actor')
        if actor:
            qs = qs.filter(actor_id=actor)

        return qs


# ---------------------------------------------------------------------------
# Operational Issues
# ---------------------------------------------------------------------------

class AdminIssuesView(APIView):
    """Platform-wide operational issues.

    Aggregates authoritative problems from existing domain data:
    - Failed payments
    - Overdue rent periods
    - Expired leases
    - Suspended users
    - Expired/past-due subscriptions

    Each issue includes enough context for the admin to navigate to the
    relevant management view.
    """

    permission_classes = [IsPlatformAdminPermission]

    def get(self, request):
        issues = []
        today = timezone.localdate()

        # Failed payments
        failed_payments = Payment.objects.filter(
            status=PaymentStatus.FAILED,
        ).select_related('tenant', 'landlord', 'lease')[:50]
        for p in failed_payments:
            issues.append({
                'issue_type': 'failed_payment',
                'severity': 'high',
                'title': f'Failed payment #{p.id}',
                'description': f'Payment of {p.currency} {p.amount} from {p.tenant.full_name} failed.',
                'entity_type': 'payment',
                'entity_id': p.id,
                'created_at': str(p.created_at.date()),
            })

        # Overdue rent periods
        overdue_periods = RentSchedule.objects.filter(
            due_date__lt=today,
        ).annotate(
            _paid=Sum(
                'payments__amount',
                filter=Q(payments__status=PaymentStatus.PAID),
                default=Decimal('0'),
            ),
        ).select_related('lease', 'lease__tenant', 'lease__landlord')[:50]

        for period in overdue_periods:
            if period._paid >= period.amount:
                continue
            remaining = period.amount - period._paid
            issues.append({
                'issue_type': 'overdue_rent',
                'severity': 'high',
                'title': f'Overdue rent: {period.lease.tenant.full_name}',
                'description': (
                    f'{period.currency} {remaining} overdue since {period.due_date}. '
                    f'Lease #{period.lease_id}.'
                ),
                'entity_type': 'rent_schedule',
                'entity_id': period.id,
                'created_at': str(period.due_date),
            })

        # Expired leases
        expired_leases = Lease.objects.filter(
            expiry_date__lt=today,
            status__in=[LeaseStatus.ACTIVE, LeaseStatus.EXPIRING],
        ).select_related('tenant', 'landlord', 'property', 'unit')[:50]
        for l in expired_leases:
            issues.append({
                'issue_type': 'expired_lease',
                'severity': 'medium',
                'title': f'Expired lease #{l.id}',
                'description': (
                    f'Lease for {l.tenant.full_name} at {l.property.name} — {l.unit.name} '
                    f'expired on {l.expiry_date}.'
                ),
                'entity_type': 'lease',
                'entity_id': l.id,
                'created_at': str(l.expiry_date),
            })

        # Suspended users
        suspended_users = User.objects.filter(
            status=AccountStatus.SUSPENDED,
        )[:50]
        for u in suspended_users:
            issues.append({
                'issue_type': 'suspended_user',
                'severity': 'medium',
                'title': f'Suspended account: {u.full_name}',
                'description': f'User {u.email} ({u.role}) is suspended.',
                'entity_type': 'user',
                'entity_id': u.id,
                'created_at': str(u.updated_at.date()),
            })

        # Expired subscriptions
        expired_subs = Subscription.objects.filter(
            status=SubscriptionStatus.EXPIRED,
        ).select_related('landlord', 'plan')[:50]
        for s in expired_subs:
            issues.append({
                'issue_type': 'expired_subscription',
                'severity': 'medium',
                'title': f'Expired subscription: {s.landlord.full_name}',
                'description': (
                    f'{s.plan.name} subscription for {s.landlord.email} has expired.'
                ),
                'entity_type': 'subscription',
                'entity_id': s.id,
                'created_at': str(s.updated_at.date()),
            })

        # Past-due subscriptions
        past_due_subs = Subscription.objects.filter(
            status=SubscriptionStatus.PAST_DUE,
        ).select_related('landlord', 'plan')[:50]
        for s in past_due_subs:
            issues.append({
                'issue_type': 'past_due_subscription',
                'severity': 'medium',
                'title': f'Past-due subscription: {s.landlord.full_name}',
                'description': (
                    f'{s.plan.name} subscription for {s.landlord.email} is past due.'
                ),
                'entity_type': 'subscription',
                'entity_id': s.id,
                'created_at': str(s.updated_at.date()),
            })

        # Sort by severity then date
        severity_order = {'high': 0, 'medium': 1, 'low': 2}
        issues.sort(key=lambda x: (severity_order.get(x['severity'], 99), x['created_at']))

        return Response({
            'count': len(issues),
            'issues': issues,
        })
