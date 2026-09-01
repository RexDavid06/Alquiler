"""Consistent, safe API error handling.

Never leak stack traces, database errors, OR secrets to API clients.
"""

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler


class DomainError(APIException):
    """A business-rule violation surfaced to the client as a clean error."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Invalid request.'
    default_code = 'domain_error'


class ForbiddenError(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'You do not have permission to perform this action.'
    default_code = 'forbidden'


class NotFoundError(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Resource not found.'
    default_code = 'not_found'


class ConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Request conflicts with the current state.'
    default_code = 'conflict'


def api_exception_handler(exc, context):
    """Return a consistent error envelope: {detail, code, errors?}."""

    response = exception_handler(exc, context)

    if response is not None:
        # Prefer the code attached to the raised error detail (e.g.
        # ForbiddenError(msg, code='property_limit_reached')) over the
        # exception class default_code, which DRF otherwise writes as 'conflict'
        # / 'forbidden' regardless of the specific code passed at raise time.
        detail = getattr(exc, 'detail', None)
        error_code = getattr(exc, 'default_code', None)
        if not isinstance(detail, (list, dict)):
            detail_code = getattr(detail, 'code', None)
            if detail_code:
                error_code = detail_code
            elif error_code is None:
                error_code = 'invalid'
        elif error_code is None:
            error_code = 'invalid'
        payload = {
            'detail': response.data.get('detail') if isinstance(response.data, dict)
            else response.data,
            'code': error_code,
        }
        if isinstance(response.data, dict) and response.data.get('code') != 'invalid':
            # Preserve field errors from serializer validation.
            if 'errors' not in response.data and not isinstance(response.data.get('detail'), str):
                payload['errors'] = response.data
        response.data = payload
        return response

    # Fallback: absorb unexpected errors. Do not leak internals.
    return Response(
        {
            'detail': 'An unexpected error occurred.',
            'code': 'internal_error',
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
