"""Custom user manager. Users authenticate by email."""

from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, role, first_name, last_name,
                     **extra_fields):
        if not email:
            raise ValueError('An email address is required.')
        email = self.normalize_email(email)
        user = self.model(
            email=email, role=role, first_name=first_name, last_name=last_name,
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password, role, first_name, last_name,
                    **extra_fields):
        extra_fields.setdefault('is_staff', False)
        return self._create_user(
            email, password, role, first_name, last_name, **extra_fields,
        )

    def create_superuser(self, email, password, first_name='Admin',
                         last_name='Admin', **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'PLATFORM_ADMIN')
        extra_fields.setdefault('status', 'ACTIVE')
        return self._create_user(
            email, password, 'PLATFORM_ADMIN', first_name, last_name,
            **extra_fields,
        )

    def landlords(self):
        return self.filter(role='LANDLORD')

    def tenants(self):
        return self.filter(role='TENANT')

    def platform_admins(self):
        return self.filter(role='PLATFORM_ADMIN')
