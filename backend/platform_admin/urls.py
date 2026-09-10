"""Platform admin API routes."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminPlanViewSet,
    AdminPropertyViewSet,
    AdminSubscriptionViewSet,
    AdminUserViewSet,
    AdminIssuesView,
    AuditLogViewSet,
)

app_name = 'platform_admin'

router = DefaultRouter()
router.register('users', AdminUserViewSet, basename='admin-user')
router.register('properties', AdminPropertyViewSet, basename='admin-property')
router.register('plans', AdminPlanViewSet, basename='admin-plan')
router.register('subscriptions', AdminSubscriptionViewSet, basename='admin-subscription')
router.register('audit-logs', AuditLogViewSet, basename='admin-audit-log')

urlpatterns = [
    path('', include(router.urls)),
    path('plans/<int:pk>/subscribers/', AdminPlanViewSet.as_view({'get': 'subscribers'}), name='admin-plan-subscribers'),
    path('issues/', AdminIssuesView.as_view(), name='admin-issues'),
]
