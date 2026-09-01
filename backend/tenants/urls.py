"""Tenant and invitation API routes."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'tenants'

router = DefaultRouter()
router.register('invitations', views.InvitationViewSet, basename='tenant-invitation')
router.register('', views.TenantViewSet, basename='tenant')

urlpatterns = [
    path('me/', views.TenantMeView.as_view(), name='tenant-me'),
    path('invitations/accept/', views.AcceptInvitationView.as_view(),
         name='invitation-accept'),
    path('', include(router.urls)),
]