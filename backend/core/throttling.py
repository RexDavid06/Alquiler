"""Custom throttling for Phase 10A.

ConditionalScopedRateThrottle only rate-limits views that have a
``throttle_scope`` attribute set. Views without it are always allowed.
This lets us put it in DEFAULT_THROTTLE_CLASSES without crashing on
views that don't need scoped throttling.

Phase 10C: Retry-After header is added in the exception handler
(core/exceptions.py) when a Throttled exception is raised.
"""

from rest_framework.throttling import ScopedRateThrottle


class ConditionalScopedRateThrottle(ScopedRateThrottle):
    """ScopedRateThrottle that skips views without ``throttle_scope``."""

    def allow_request(self, request, view):
        scope = getattr(view, 'throttle_scope', None)
        if not scope:
            return True
        return super().allow_request(request, view)
