from django.contrib import admin

from .models import Payment, RentSchedule


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'tenant', 'lease', 'amount', 'currency', 'payment_date', 'status',
        'payment_method', 'created_at',
    )
    list_filter = ('status', 'payment_method', 'currency')
    search_fields = ('tenant__email', 'reference', 'notes')


@admin.register(RentSchedule)
class RentScheduleAdmin(admin.ModelAdmin):
    list_display = ('lease', 'period_start', 'period_end', 'due_date', 'amount', 'currency')
    search_fields = ('lease__tenant__email',)
