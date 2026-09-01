from django.contrib import admin

from .models import AuditLog, NotificationPreference, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'role', 'status', 'full_name', 'is_active', 'created_at')
    list_filter = ('role', 'status', 'is_active', 'email_verified')
    search_fields = ('email', 'first_name', 'last_name', 'phone')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'actor', 'object_type', 'object_id', 'created_at')
    list_filter = ('action', 'object_type')
    search_fields = ('actor__email',)


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'email_enabled', 'in_app_enabled')
    search_fields = ('user__email',)
