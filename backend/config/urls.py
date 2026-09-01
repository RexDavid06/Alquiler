"""Root URL configuration for the Alquiler backend.

The API is versioned under /api/v1/ and is designed to be consumed by the
web application and future mobile clients.
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter

from properties.views import PropertyViewSet, UnitViewSet

API_PREFIX = 'api/v1/'

router = DefaultRouter()
router.register('properties', PropertyViewSet, basename='property')

urlpatterns = [
    path('admin/', admin.site.urls),
    path(API_PREFIX + 'auth/', include('core.urls')),
    path(API_PREFIX + 'tenants/', include('tenants.urls')),
    path(API_PREFIX + 'leases/', include('leases.urls')),
    path(API_PREFIX, include(router.urls)),
    # Nested units: /api/v1/properties/{property_pk}/units/
    path(
        API_PREFIX + 'properties/<int:property_pk>/units/',
        UnitViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='unit-list',
    ),
    path(
        API_PREFIX + 'properties/<int:property_pk>/units/<int:unit_pk>/',
        UnitViewSet.as_view({
            'get': 'retrieve', 'put': 'update',
            'patch': 'partial_update', 'delete': 'destroy',
        }),
        name='unit-detail',
    ),

    # OpenAPI / Swagger documentation (Phase 10 hardens this).
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'),
         name='swagger-ui'),
]
