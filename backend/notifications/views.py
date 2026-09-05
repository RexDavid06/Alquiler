"""Notification API views.

Data isolation is enforced at the queryset level: every user sees only
their own notifications. Cross-user access returns 404.
"""

from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import NotificationPreference

from .models import Notification
from .serializers import (
    BulkMarkReadSerializer,
    MarkReadSerializer,
    NotificationPreferenceSerializer,
    NotificationSerializer,
)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """Authenticated user's notifications with mark-read support.

    * List / retrieve: own notifications only.
    * GET /notifications/unread-count/: count of unread notifications.
    * PATCH /notifications/mark-all-read/: bulk mark as read.
    * PATCH /notifications/{id}/read/: mark a single notification as read.
    * GET|PATCH /notifications/preferences/: notification channel preferences.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    filter_backends = [OrderingFilter]
    ordering_fields = ['created_at', 'is_read']
    ordering = ['-created_at']

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Notification.objects.none()
        user = self.request.user
        qs = Notification.objects.filter(recipient=user)

        # Unread filter
        unread = self.request.query_params.get('unread')
        if unread is not None:
            if unread.lower() in ('true', '1', 'yes'):
                qs = qs.filter(is_read=False)
            elif unread.lower() in ('false', '0', 'no'):
                qs = qs.filter(is_read=True)

        return qs

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        """Return the count of unread notifications for the authenticated user."""
        count = Notification.objects.filter(
            recipient=request.user, is_read=False,
        ).count()
        return Response({'unread_count': count})

    @action(detail=False, methods=['patch', 'post'], url_path='mark-all-read',
            serializer_class=BulkMarkReadSerializer)
    def mark_all_read(self, request):
        """Mark all (or filtered) notifications as read.

        Accepts optional ``notification_ids`` to limit which notifications
        are marked.  Without it, all unread notifications are marked.
        """
        serializer = BulkMarkReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notification_ids = serializer.validated_data.get('notification_ids')
        is_read = serializer.validated_data.get('is_read', True)

        qs = Notification.objects.filter(
            recipient=request.user, is_read=not is_read,
        )
        if notification_ids:
            qs = qs.filter(id__in=notification_ids)

        updated = qs.update(is_read=is_read)
        return Response({'updated': updated})

    @action(detail=True, methods=['patch', 'post'], url_path='read',
            serializer_class=MarkReadSerializer)
    def mark_read(self, request, pk=None):
        """Mark a notification as read."""
        notification = self.get_object()
        serializer = MarkReadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        is_read = serializer.validated_data.get('is_read', True)
        notification.is_read = is_read
        notification.save(update_fields=['is_read', 'updated_at'])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=['get', 'patch'], url_path='preferences')
    def preferences(self, request):
        """Read or update notification channel preferences.

        GET returns the current preferences (creating defaults if needed).
        PATCH updates email_enabled / in_app_enabled.
        """
        pref, _ = NotificationPreference.objects.get_or_create(
            user=request.user,
        )
        if request.method == 'PATCH':
            serializer = NotificationPreferenceSerializer(
                pref, data=request.data, partial=True,
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        return Response(NotificationPreferenceSerializer(pref).data)
