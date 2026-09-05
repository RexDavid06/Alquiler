"""Subscription API views.

Landlords can view plans, manage their subscription, and see usage.
Platform admins can manage plan definitions.
"""

from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework.permissions import IsAuthenticated

from core.exceptions import ConflictError, NotFoundError
from core.models import AuditLog
from core.permissions import IsLandlord, IsPlatformAdmin

from .models import Plan, Subscription, SubscriptionStatus
from .serializers import (
    PlanSerializer,
    SubscriptionCancelSerializer,
    SubscriptionCreateSerializer,
    SubscriptionSerializer,
    UsageSerializer,
)
from .services import (
    cancel_subscription,
    check_trial_expiry,
    downgrade_subscription,
    get_available_plans,
    get_subscription,
    reactivate_subscription,
    upgrade_subscription,
)


class PlanViewSet(viewsets.ModelViewSet):
    """Subscription plans.

    * Any authenticated user can list/retrieve active plans.
    * Only platform admins can create, update, or deactivate plans.
    """

    serializer_class = PlanSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsPlatformAdmin()]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Plan.objects.none()
        if self.request.user.is_authenticated and self.request.user.is_platform_admin:
            return Plan.objects.all().order_by('display_order', 'price_ngn')
        return get_available_plans()

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance.is_active:
            raise ConflictError(
                'Plan is already inactive.',
                code='plan_already_inactive',
            )
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])
        return Response(
            PlanSerializer(instance).data,
            status=status.HTTP_200_OK,
        )


class SubscriptionViewSet(viewsets.GenericViewSet):
    """Landlord's subscription management.

    * GET /subscription/ — retrieve current subscription
    * POST /subscription/ — upgrade/downgrade
    * POST /subscription/cancel/ — cancel subscription
    * POST /subscription/reactivate/ — reactivate cancelled/expired
    * GET /subscription/usage/ — usage metrics
    * GET /subscription/history/ — plan change history
    """

    serializer_class = SubscriptionSerializer
    permission_classes = [IsLandlord]

    def get_object(self):
        return get_subscription(self.request.user)

    @action(detail=False, methods=['get'])
    def retrieve(self, request):
        sub = self.get_object()
        # Check trial expiry before returning
        sub = check_trial_expiry(request.user)
        return Response(SubscriptionSerializer(sub).data)

    @action(detail=False, methods=['post'])
    def create(self, request):
        serializer = SubscriptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = serializer.validated_data['plan']
        billing_cycle = serializer.validated_data.get('billing_cycle')

        sub = get_subscription(request.user)

        # Determine if this is an upgrade or downgrade
        from .models import PlanTier
        current_order = dict(
            (t, i) for i, t in enumerate(PlanTier.choices, 0)
        )
        current_idx = current_order.get((sub.plan.tier, sub.plan.get_tier_display()), 0)
        target_idx = current_order.get((plan.tier, plan.get_tier_display()), 0)

        if plan.tier == sub.plan.tier:
            raise ConflictError(
                'You are already on this plan.',
                code='already_on_plan',
            )

        if target_idx > current_idx:
            sub = upgrade_subscription(request.user, plan, billing_cycle)
        else:
            sub = downgrade_subscription(request.user, plan, billing_cycle)

        return Response(SubscriptionSerializer(sub).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='cancel')
    def cancel(self, request):
        serializer = SubscriptionCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get('reason', '')
        sub = cancel_subscription(request.user, reason)
        return Response(SubscriptionSerializer(sub).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='reactivate')
    def reactivate(self, request):
        sub = reactivate_subscription(request.user)
        return Response(SubscriptionSerializer(sub).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='usage')
    def usage(self, request):
        sub = get_subscription(request.user)
        sub = check_trial_expiry(request.user)
        data = {
            'plan_name': sub.plan.name,
            'max_active_tenants': sub.plan.max_active_tenants,
            'active_tenants': sub.active_tenants_count,
            'max_properties': sub.plan.max_properties,
            'properties': sub.property_count,
        }
        return Response(data)

    @action(detail=False, methods=['get'], url_path='history')
    def history(self, request):
        logs = AuditLog.objects.filter(
            actor=request.user,
            object_type='Subscription',
            action='SUBSCRIPTION_CHANGED',
        ).order_by('-created_at')[:50]

        results = []
        for log in logs:
            results.append({
                'id': log.id,
                'action': log.detail.get('action', ''),
                'detail': log.detail,
                'created_at': log.created_at,
            })

        return Response(results)
