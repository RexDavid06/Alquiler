"""Serializers for the Notification API."""

from rest_framework import serializers

from core.models import NotificationPreference

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """Read representation of a notification."""

    recipient_email = serializers.CharField(source='recipient.email', read_only=True)
    notification_type_display = serializers.CharField(
        source='get_notification_type_display', read_only=True,
    )

    class Meta:
        model = Notification
        fields = [
            'id', 'recipient', 'recipient_email',
            'notification_type', 'notification_type_display',
            'channel', 'status',
            'lease', 'rent_period', 'payment', 'invitation',
            'title', 'message',
            'is_read', 'scheduled_for', 'sent_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'recipient', 'recipient_email',
            'notification_type', 'notification_type_display',
            'channel', 'status',
            'lease', 'rent_period', 'payment', 'invitation',
            'title', 'message',
            'scheduled_for', 'sent_at',
            'created_at', 'updated_at',
        ]


class MarkReadSerializer(serializers.Serializer):
    """Serializer for marking a notification as read."""
    is_read = serializers.BooleanField(default=True)


class BulkMarkReadSerializer(serializers.Serializer):
    """Serializer for bulk mark-as-read."""
    is_read = serializers.BooleanField(default=True)
    notification_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=False,
        help_text='Optional list of notification IDs. If omitted, all unread '
                  'notifications for the user are marked.',
    )


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Read/update notification channel preferences."""

    class Meta:
        model = NotificationPreference
        fields = ['email_enabled', 'in_app_enabled', 'updated_at']
        read_only_fields = ['updated_at']
