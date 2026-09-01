"""Role-based and object-level permissions.

Authorization is always derived from the authenticated backend identity
(the request user's role in the DB) - never from frontend-declared roles.
"""

from rest_framework.permissions import BasePermission


class IsPlatformAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_platform_admin)


class IsLandlord(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_landlord)


class IsTenant(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_tenant)


class IsLandlordOrAdmin(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated
            and (user.is_landlord or user.is_platform_admin)
        )
