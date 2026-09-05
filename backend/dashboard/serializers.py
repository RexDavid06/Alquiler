"""Serializers for the Dashboard API."""

from rest_framework import serializers


class LandlordDashboardSerializer(serializers.Serializer):
    """Read-only landlord dashboard KPIs."""

    properties = serializers.DictField()
    units = serializers.DictField()
    leases = serializers.DictField()
    revenue = serializers.DictField()
    overdue_rent = serializers.DictField()
    upcoming_rent = serializers.DictField()
    lease_expiry_alerts = serializers.ListField()


class TenantDashboardSerializer(serializers.Serializer):
    """Read-only tenant dashboard KPIs."""

    active_leases = serializers.ListField()
    next_rent_due = serializers.DictField(allow_null=True)
    payment_history = serializers.ListField()
    unread_notifications = serializers.IntegerField()


class AdminDashboardSerializer(serializers.Serializer):
    """Read-only platform admin dashboard KPIs."""

    users = serializers.DictField()
    subscriptions = serializers.DictField()
    properties = serializers.DictField()
    units = serializers.DictField()
    leases = serializers.DictField()
    revenue = serializers.DictField()
    system_health = serializers.DictField()
