from django.contrib import admin

from .models import Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'tier', 'price_ngn', 'max_properties', 'max_active_tenants', 'is_active', 'display_order')
    list_filter = ('tier', 'is_active')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('landlord', 'plan', 'status', 'started_at', 'current_period_end')
    list_filter = ('status', 'plan')
    search_fields = ('landlord__email',)
