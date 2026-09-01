"""Serializers for user and authentication concerns."""

from django.contrib.auth import authenticate, password_validation
from django.utils.translation import gettext as _
from rest_framework import serializers

from .models import AccountStatus, User


class UserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(read_only=True)
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'role', 'first_name', 'last_name', 'phone',
            'full_name', 'status', 'email_verified', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    # Public self-registration creates LANDLORD accounts only. Tenants are
    # created through the landlord invitation flow (see tenants app).
    # TENANT is kept as an enumerated choice so we can reject it with a clear
    # explanation (DRF's ChoiceField would otherwise report "invalid choice").
    role = serializers.ChoiceField(choices=['LANDLORD', 'TENANT'])
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)

    def validate_role(self, value):
        if value != 'LANDLORD':
            raise serializers.ValidationError(
                'Standalone registration is only available for landlords. '
                'Tenants must accept a landlord invitation.',
                code='tenant_registration_not_allowed',
            )
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value.lower()

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        role = validated_data.pop('role')
        password = validated_data.pop('password')
        user = User(**validated_data, role=role)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        request = self.context.get('request')
        email = attrs.get('email', '').lower()
        user = authenticate(
            request=request, username=email, password=attrs.get('password'),
        )
        if not user:
            raise serializers.ValidationError(
                'Unable to log in with provided credentials.', code='invalid_credentials',
            )
        if user.status == AccountStatus.SUSPENDED:
            raise serializers.ValidationError(
                'This account is suspended.', code='account_suspended',
            )
        if not user.is_active:
            raise serializers.ValidationError(
                'This account is inactive.', code='account_inactive',
            )
        attrs['user'] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Old password is incorrect.')
        return value

    def validate_new_password(self, value):
        password_validation.validate_password(value)
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        password_validation.validate_password(value)
        return value


class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone']
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
            'phone': {'required': False},
        }
