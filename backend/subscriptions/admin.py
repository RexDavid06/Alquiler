from django.contrib import admin

from .models import Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'tier', 'price_ngn', 'max_properties',
        'max_active_tenants', 'is_active', 'display_order',
    )
    list_filter = ('tier', 'is_active')
    list_editable = ('is_active', 'display_order')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'landlord', 'plan', 'status', 'billing_cycle',
        'started_at', 'current_period_end', 'cancelled_at',
    )
    list_filter = ('status', 'plan', 'billing_cycle')
    search_fields = ('landlord__email',)
    readonly_fields = ('started_at', 'created_at', 'updated_at')
