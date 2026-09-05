"""Dashboard API routes."""

from django.urls import path

from .views import (
    AdminDashboardView,
    AdminExportView,
    LandlordDashboardView,
    LandlordExportView,
    TenantDashboardView,
)

app_name = 'dashboard'

urlpatterns = [
    path('landlord/', LandlordDashboardView.as_view(), name='landlord-dashboard'),
    path('landlord/export/', LandlordExportView.as_view(), name='landlord-export'),
    path('tenant/', TenantDashboardView.as_view(), name='tenant-dashboard'),
    path('admin/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('admin/export/', AdminExportView.as_view(), name='admin-export'),
]
