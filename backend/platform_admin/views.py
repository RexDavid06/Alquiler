"""Platform administration API views.

Provides platform-wide visibility and management for users, properties,
subscriptions, and operational issues. All endpoints enforce PLATFORM_ADMIN
authorization at the backend level.

Write operations are limited to user suspend/reactivate and plan management —
all other mutations go through existing domain services.
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
    AdminAuditLogSerializer,
    AdminPlanSerializer,
    AdminPropertyDetailSerializer,
    AdminPropertySerializer,
    AdminSubscriptionSerializer,
    AdminUserDetailSerializer,
    AdminUserSerializer,
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

    @action(detail=True, methods=['post'], url_path='suspend')
    def suspend(self, request, pk=None):
        """Suspend a user account. Prevents login and active sessions."""
        user = self.get_object()

        if user.is_platform_admin:
            raise ConflictError('Cannot suspend a platform admin account.')

        if user.status == AccountStatus.SUSPENDED:
            raise ConflictError(f'User {user.email} is already suspended.')

        user.status = AccountStatus.SUSPENDED
        user.is_active = False
        user.save(update_fields=['status', 'is_active', 'updated_at'])

        AuditLog.objects.create(
            actor=request.user,
            action='USER_SUSPENDED',
            object_type='user',
            object_id=user.id,
            detail={'email': user.email, 'role': user.role},
        )

        serializer = self.get_serializer(user)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='reactivate')
    def reactivate(self, request, pk=None):
        """Reactivate a suspended or deactivated user account."""
        user = self.get_object()

        if user.status == AccountStatus.ACTIVE:
            raise ConflictError(f'User {user.email} is already active.')

        user.status = AccountStatus.ACTIVE
        user.is_active = True
        user.save(update_fields=['status', 'is_active', 'updated_at'])

        AuditLog.objects.create(
            actor=request.user,
            action='USER_REACTIVATED',
            object_type='user',
            object_id=user.id,
            detail={'email': user.email, 'role': user.role},
        )

        serializer = self.get_serializer(user)
        return Response(serializer.data)


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


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

class AdminAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Platform-wide audit log listing for administrators.

    Read-only access to all audit log entries with search, filtering,
    and pagination. Supports filtering by action, actor, and object type.
    """

    serializer_class = AdminAuditLogSerializer
    permission_classes = [IsPlatformAdminPermission]
    pagination_class = StandardPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['actor__email', 'actor__first_name', 'actor__last_name', 'action', 'object_type']
    ordering_fields = ['action', 'object_type', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return AuditLog.objects.none()
        qs = AuditLog.objects.select_related('actor')

        action_filter = self.request.query_params.get('action')
        if action_filter:
            qs = qs.filter(action=action_filter.upper())

        actor_id = self.request.query_params.get('actor')
        if actor_id:
            qs = qs.filter(actor_id=actor_id)

        object_type = self.request.query_params.get('object_type')
        if object_type:
            qs = qs.filter(object_type=object_type.lower())

        return qs


# ---------------------------------------------------------------------------
# Recent Activity Feed
# ---------------------------------------------------------------------------

class AdminActivityFeedView(APIView):
    """Platform-wide recent activity feed for administrators.

    Aggregates recent events from multiple sources into a unified timeline:
    - Audit log entries
    - Recent payments
    - Recent lease changes
    - Recent user registrations
    - Recent subscription changes

    Returns the most recent activities sorted by timestamp (newest first).
    """

    permission_classes = [IsPlatformAdminPermission]

    def get(self, request):
        limit = min(int(request.query_params.get('limit', 50)), 100)
        activities = []

        # Audit log entries (most recent)
        audit_logs = AuditLog.objects.select_related('actor').order_by('-created_at')[:limit]
        for log in audit_logs:
            activities.append({
                'id': f'audit-{log.id}',
                'type': 'audit_log',
                'action': log.action,
                'description': self._format_audit_action(log),
                'actor_email': log.actor.email if log.actor else None,
                'actor_name': log.actor.full_name if log.actor else None,
                'entity_type': log.object_type,
                'entity_id': log.object_id,
                'timestamp': log.created_at.isoformat(),
            })

        # Recent payments (last 24 hours)
        recent_payments = Payment.objects.select_related(
            'tenant', 'landlord', 'lease'
        ).order_by('-created_at')[:20]
        for p in recent_payments:
            activities.append({
                'id': f'payment-{p.id}',
                'type': 'payment',
                'action': 'PAYMENT_RECORDED',
                'description': f'{p.currency} {p.amount} payment from {p.tenant.full_name} — {p.status}',
                'actor_email': p.landlord.email,
                'actor_name': p.landlord.full_name,
                'entity_type': 'payment',
                'entity_id': p.id,
                'timestamp': p.created_at.isoformat(),
            })

        # Recent lease changes (last 24 hours)
        recent_leases = Lease.objects.select_related(
            'tenant', 'landlord', 'property'
        ).order_by('-created_at')[:20]
        for l in recent_leases:
            activities.append({
                'id': f'lease-{l.id}',
                'type': 'lease',
                'action': 'LEASE_CREATED',
                'description': f'Lease #{l.id} for {l.tenant.full_name} at {l.property.name}',
                'actor_email': l.landlord.email,
                'actor_name': l.landlord.full_name,
                'entity_type': 'lease',
                'entity_id': l.id,
                'timestamp': l.created_at.isoformat(),
            })

        # Recent user registrations (last 24 hours)
        recent_users = User.objects.order_by('-created_at')[:20]
        for u in recent_users:
            activities.append({
                'id': f'user-{u.id}',
                'type': 'user',
                'action': 'USER_REGISTERED',
                'description': f'{u.full_name} ({u.role}) registered',
                'actor_email': u.email,
                'actor_name': u.full_name,
                'entity_type': 'user',
                'entity_id': u.id,
                'timestamp': u.created_at.isoformat(),
            })

        # Recent subscription changes (last 24 hours)
        recent_subs = Subscription.objects.select_related(
            'landlord', 'plan'
        ).order_by('-created_at')[:20]
        for s in recent_subs:
            activities.append({
                'id': f'subscription-{s.id}',
                'type': 'subscription',
                'action': 'SUBSCRIPTION_CHANGED',
                'description': f'{s.landlord.full_name} — {s.plan.name} ({s.status})',
                'actor_email': s.landlord.email,
                'actor_name': s.landlord.full_name,
                'entity_type': 'subscription',
                'entity_id': s.id,
                'timestamp': s.created_at.isoformat(),
            })

        # Sort by timestamp descending and limit
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        activities = activities[:limit]

        return Response({
            'count': len(activities),
            'activities': activities,
        })

    def _format_audit_action(self, log):
        """Format audit log action into human-readable description."""
        action = log.action
        obj_type = log.object_type
        detail = log.detail or {}

        if action == 'USER_SUSPENDED':
            return f'User {detail.get("email", "")} suspended'
        elif action == 'USER_REACTIVATED':
            return f'User {detail.get("email", "")} reactivated'
        elif action == 'INVITATION_CREATED':
            return f'Invitation sent to {detail.get("email", "")}'
        elif action == 'INVITATION_ACCEPTED':
            return f'Invitation accepted by {detail.get("email", "")}'
        elif action == 'LEASE_CREATED':
            return f'New lease #{log.object_id} created'
        elif action == 'LEASE_RENEWED':
            return f'Lease #{log.object_id} renewed'
        elif action == 'LEASE_TERMINATED':
            return f'Lease #{log.object_id} terminated'
        elif action == 'PAYMENT_CREATED':
            return f'Payment #{log.object_id} recorded'
        elif action == 'PAYMENT_UPDATED':
            return f'Payment #{log.object_id} updated'
        elif action == 'SUBSCRIPTION_CHANGED':
            return f'Subscription changed to {detail.get("plan", "")}'
        elif action == 'PROPERTY_CREATED':
            return f'Property "{detail.get("name", "")}" created'
        elif action == 'UNIT_CREATED':
            return f'Unit "{detail.get("name", "")}" created'
        elif action == 'ACCOUNT_CREATED':
            return f'Account created for {detail.get("email", "")}'
        return f'{action} on {obj_type}#{log.object_id}'
