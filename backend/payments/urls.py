"""Rent & Payment Management API routes (Phase 5)."""

from rest_framework.routers import DefaultRouter

from .views import PaymentViewSet, RentScheduleViewSet

app_name = 'payments'

router = DefaultRouter()
router.register('payments', PaymentViewSet, basename='payment')
router.register('rent-schedules', RentScheduleViewSet, basename='rent-schedule')

urlpatterns = router.urls
