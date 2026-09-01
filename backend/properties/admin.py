from django.contrib import admin
from .models import Property, Unit


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('name', 'landlord', 'property_type', 'status', 'city', 'country', 'created_at')
    list_filter = ('property_type', 'status', 'country')
    search_fields = ('name', 'address', 'landlord__email')


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'property', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('name', 'property__name')
