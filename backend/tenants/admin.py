from django.contrib import admin

from .models import TenantInvitation, TenantProfile


@admin.register(TenantProfile)
class TenantProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')


@admin.register(TenantInvitation)
class TenantInvitationAdmin(admin.ModelAdmin):
    list_display = ('email', 'landlord', 'unit', 'status', 'expires_at', 'created_at')
    list_filter = ('status',)
    search_fields = ('email', 'landlord__email', 'token')
    readonly_fields = ('token',)
