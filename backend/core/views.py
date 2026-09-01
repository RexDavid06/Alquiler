"""Authentication and account views."""

from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .exceptions import DomainError
from .models import AccountStatus, AuditLog, NotificationPreference, User
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    UpdateProfileSerializer,
    UserSerializer,
)


def _issue_token(user):
    token, _ = Token.objects.get_or_create(user=user)
    return token.key


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    # Self-registration is landlord-only. Activate and assign a subscription.
    user.activate()
    # Landing a landlord without a subscription is never allowed.
    from subscriptions.services import ensure_landlord_subscription
    ensure_landlord_subscription(user)
    NotificationPreference.objects.get_or_create(user=user)
    AuditLog.objects.create(
        actor=user, action='ACCOUNT_CREATED',
        object_type='User', object_id=user.id,
        detail={'role': user.role},
    )
    return Response(
        {'user': UserSerializer(user).data, 'token': _issue_token(user)},
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data['user']
    return Response(
        {'user': UserSerializer(user).data, 'token': _issue_token(user)},
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    # Delete the token so it can no longer be used.
    try:
        request.auth.delete()
    except Exception:
        pass
    return Response({'detail': 'Logged out.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(UserSerializer(request.user).data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    serializer = UpdateProfileSerializer(
        request.user, data=request.data, partial=True,
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(UserSerializer(request.user).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = ChangePasswordSerializer(
        data=request.data, context={'request': request},
    )
    serializer.is_valid(raise_exception=True)
    request.user.set_password(serializer.validated_data['new_password'])
    request.user.save(update_fields=['password', 'updated_at'])
    # Invalidate other sessions by deleting existing tokens.
    Token.objects.filter(user=request.user).delete()
    return Response({'detail': 'Password changed.'})


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_request(request):
    serializer = PasswordResetRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data['email'].lower()
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Do not reveal whether an account exists.
        return Response({'detail': 'If that email exists, a reset link was sent.'})
    if user.status == AccountStatus.SUSPENDED:
        return Response({'detail': 'If that email exists, a reset link was sent.'})
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    # Email delivery is routed through core.services.send_email, the seam where
    # the notification service (Phase 6) will be attached. For MVP it sends
    # through Django's configured mail backend.
    from django.conf import settings
    from core.services import send_email
    reset_url = f"{settings.SITE_URL}/auth/reset-password?uid={uid}&token={token}"
    send_email(
        subject='Reset your Alquiler password',
        message=f'Use this link to reset your password: {reset_url}',
        recipient=user.email,
    )
    return Response({'detail': 'If that email exists, a reset link was sent.'})


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    serializer = PasswordResetConfirmSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        uid = force_str(urlsafe_base64_decode(data['uid']))
        user = User.objects.get(pk=uid, email=data['email'].lower())
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        raise DomainError('Invalid reset link.')
    if not default_token_generator.check_token(user, data['token']):
        raise DomainError('Invalid or expired reset link.')
    user.set_password(data['new_password'])
    user.save(update_fields=['password', 'updated_at'])
    # Invalidate existing sessions.
    Token.objects.filter(user=user).delete()
    return Response({'detail': 'Password has been reset.'})
