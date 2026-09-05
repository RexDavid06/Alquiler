"""Dashboard API views.

Read-only analytics endpoints for landlord, tenant, and platform admin.
All data is aggregated from existing domain models — no mutation.
"""

import csv

from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsLandlord, IsPlatformAdmin, IsTenant

from .services import (
    _validate_range,
    admin_export_data,
    admin_metrics,
    landlord_export_data,
    landlord_metrics,
    tenant_metrics,
)
from .serializers import (
    AdminDashboardSerializer,
    LandlordDashboardSerializer,
    TenantDashboardSerializer,
)


class LandlordDashboardView(APIView):
    """Landlord dashboard KPIs."""

    permission_classes = [IsLandlord]

    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        try:
            start, end = _validate_range(start_date, end_date)
        except ValueError as e:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(str(e))

        data = landlord_metrics(
            request.user,
            start_date=start,
            end_date=end,
        )
        return Response(data)


class TenantDashboardView(APIView):
    """Tenant dashboard KPIs."""

    permission_classes = [IsTenant]

    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        try:
            start, end = _validate_range(start_date, end_date)
        except ValueError as e:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(str(e))

        data = tenant_metrics(
            request.user,
            start_date=start,
            end_date=end,
        )
        return Response(data)


class AdminDashboardView(APIView):
    """Platform admin dashboard KPIs."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        try:
            start, end = _validate_range(start_date, end_date)
        except ValueError as e:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(str(e))

        data = admin_metrics(start_date=start, end_date=end)
        return Response(data)


class LandlordExportView(APIView):
    """CSV export for landlord dashboard data."""

    permission_classes = [IsLandlord]

    def get(self, request):
        data = landlord_export_data(request.user)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = (
            f'attachment; filename="landlord_dashboard_{request.user.id}.csv"'
        )
        writer = csv.writer(response)

        # Properties section
        writer.writerow(['=== PROPERTIES ==='])
        writer.writerow(['Name', 'Type', 'Address', 'City', 'Status'])
        for row in data['properties']:
            writer.writerow(row)
        writer.writerow([])

        # Units section
        writer.writerow(['=== UNITS ==='])
        writer.writerow(['Property', 'Unit', 'Status'])
        for row in data['units']:
            writer.writerow(row)
        writer.writerow([])

        # Leases section
        writer.writerow(['=== LEASES ==='])
        writer.writerow([
            'Tenant', 'Property', 'Unit', 'Start', 'Expiry',
            'Rent Amount', 'Frequency', 'Status',
        ])
        for row in data['leases']:
            writer.writerow(row)
        writer.writerow([])

        # Revenue summary
        writer.writerow(['=== REVENUE SUMMARY ==='])
        writer.writerow(['Total Paid Revenue (NGN)', str(data['revenue'])])
        writer.writerow([])

        # Overdue summary
        writer.writerow(['=== OVERDUE RENT ==='])
        writer.writerow(['Total Overdue (NGN)', str(data['overdue_total'])])
        writer.writerow(['Overdue Periods', data['overdue_count']])
        writer.writerow([])

        # Upcoming summary
        writer.writerow(['=== UPCOMING RENT ==='])
        writer.writerow(['Total Upcoming (NGN)', str(data['upcoming_total'])])
        writer.writerow(['Upcoming Periods', data['upcoming_count']])
        writer.writerow([])

        # Lease expiry alerts
        writer.writerow(['=== LEASE EXPIRY ALERTS (30 days) ==='])
        writer.writerow(['Tenant', 'Property', 'Unit', 'Expiry Date', 'Rent Amount'])
        for row in data['expiry_alerts']:
            writer.writerow(row)

        return response


class AdminExportView(APIView):
    """CSV export for admin dashboard data."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        start, end = _validate_range(start_date, end_date)

        data = admin_metrics(start_date=start, end_date=end)
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = (
            'attachment; filename="admin_dashboard.csv"'
        )
        writer = csv.writer(response)

        writer.writerow(['=== USERS ==='])
        writer.writerow(['Total', data['users']['total']])
        writer.writerow(['Landlords', data['users']['landlords']])
        writer.writerow(['Tenants', data['users']['tenants']])
        writer.writerow(['Admins', data['users']['admins']])
        writer.writerow([])

        writer.writerow(['=== SUBSCRIPTIONS ==='])
        writer.writerow(['Total', data['subscriptions']['total']])
        writer.writerow(['Active', data['subscriptions']['active']])
        writer.writerow(['Trial', data['subscriptions']['trial']])
        writer.writerow(['Cancelled', data['subscriptions']['cancelled']])
        writer.writerow([])

        writer.writerow(['=== PLATFORM ==='])
        writer.writerow(['Total Properties', data['properties']['total']])
        writer.writerow(['Total Units', data['units']['total']])
        writer.writerow(['Total Leases', data['leases']['total']])
        writer.writerow([])

        writer.writerow(['=== REVENUE ==='])
        writer.writerow(['Total Revenue (NGN)', data['revenue']['total']])
        writer.writerow(['Payment Count', data['revenue']['payment_count']])
        writer.writerow([])

        writer.writerow(['=== SYSTEM HEALTH ==='])
        for key, value in data['system_health'].items():
            writer.writerow([key, value])

        return response
