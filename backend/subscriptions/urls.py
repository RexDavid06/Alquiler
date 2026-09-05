"""Subscription API routes."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PlanViewSet, SubscriptionViewSet

app_name = 'subscriptions'

router = DefaultRouter()
router.register('plans', PlanViewSet, basename='plan')

urlpatterns = [
    path('', include(router.urls)),
    path('subscription/', SubscriptionViewSet.as_view({
        'get': 'retrieve',
        'post': 'create',
    }), name='subscription'),
    path('subscription/cancel/', SubscriptionViewSet.as_view({
        'post': 'cancel',
    }), name='subscription-cancel'),
    path('subscription/reactivate/', SubscriptionViewSet.as_view({
        'post': 'reactivate',
    }), name='subscription-reactivate'),
    path('subscription/usage/', SubscriptionViewSet.as_view({
        'get': 'usage',
    }), name='subscription-usage'),
    path('subscription/history/', SubscriptionViewSet.as_view({
        'get': 'history',
    }), name='subscription-history'),
]
