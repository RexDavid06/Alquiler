from django.contrib import admin

from .models import Lease


@admin.register(Lease)
class LeaseAdmin(admin.ModelAdmin):
    list_display = (
        'tenant', 'property', 'unit', 'status', 'start_date', 'expiry_date',
        'rent_amount', 'created_at',
    )
    list_filter = ('status', 'rent_frequency')
    search_fields = ('tenant__email', 'landlord__email', 'unit__name')
