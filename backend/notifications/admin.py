from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'notification_type', 'channel', 'status', 'is_read', 'created_at')
    list_filter = ('notification_type', 'channel', 'status')
    search_fields = ('recipient__email',)
    readonly_fields = ('idempotency_key',)
