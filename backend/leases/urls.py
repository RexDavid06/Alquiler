"""Lease & Renewal API route registration (Phase 4)."""

from rest_framework.routers import DefaultRouter

from .views import LeaseViewSet

router = DefaultRouter()
router.register('', LeaseViewSet, basename='lease')

urlpatterns = router.urls