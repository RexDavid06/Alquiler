from django.contrib import admin

from .models import Notification, PushDevice


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'notification_type', 'channel', 'status', 'is_read', 'created_at')
    list_filter = ('notification_type', 'channel', 'status')
    search_fields = ('recipient__email',)
    readonly_fields = ('idempotency_key',)


@admin.register(PushDevice)
class PushDeviceAdmin(admin.ModelAdmin):
    list_display = ('user', 'platform', 'device_name', 'is_active', 'last_seen_at', 'updated_at')
    list_filter = ('platform', 'is_active')
    search_fields = ('user__email', 'token')
    readonly_fields = ('token', 'created_at', 'updated_at')
