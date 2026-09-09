"""
Django settings for the Alquiler rental management SaaS.

Configuration is driven by environment variables (via django-environ).
Local development defaults to SQLite for zero-config iteration; production
uses PostgreSQL by setting DB_ENGINE=postgres and the DB_* variables.
Secrets must never be committed. See backend/.env.example.
"""

from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent

env = environ.Env(
    # casting defaults
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1', 'testserver']),
    DB_ENGINE=(str, 'sqlite'),
    REDIS_URL=(str, ''),
)

# Read environment variables from the .env file if it exists.
environ.Env.read_env(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env(
    'DJANGO_SECRET_KEY',
    default='django-insecure-local-dev-se!kwvkw^6ht&!zxbvr(&-%ts+fsxil@+1839oy5t#71w^puo(',
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

# Fail fast: refuse to start with a known insecure SECRET_KEY in production.
if not DEBUG and SECRET_KEY.startswith('django-insecure-'):
    raise ImproperlyConfigured(
        'SECRET_KEY must be set to a secure value in production. '
        'The default insecure key is not allowed when DEBUG=False.'
    )

ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'drf_spectacular',
    # Local apps
    'core',
    'properties',
    'tenants',
    'leases',
    'payments',
    'notifications',
    'subscriptions',
    'dashboard',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
# https://docs.djangoproject.com/en/6.1/ref/settings/#databases
# Local dev defaults to SQLite. Set DB_ENGINE=postgres with the DB_* vars
# for a production PostgreSQL connection.
if env('DB_ENGINE') == 'postgres':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': env('DB_NAME'),
            'USER': env('DB_USER'),
            'PASSWORD': env('DB_PASSWORD'),
            'HOST': env('DB_HOST', default='127.0.0.1'),
            'PORT': env('DB_PORT', default='5432'),
            'CONN_MAX_AGE': 60,
            'OPTIONS': {
                # Reject insecure connections in production by default.
                'sslmode': env('DB_SSLMODE', default='require'),
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Custom user model
AUTH_USER_MODEL = 'core.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# DRF configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'core.authentication.ExpiringTokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.StandardPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'core.exceptions.api_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': [
        'core.throttling.ConditionalScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'login': '10/minute',
        'register': '5/hour',
        'password_reset': '5/hour',
    },
}

# Disable throttling in development/test so the test suite is not rate-limited.
if DEBUG:
    REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = []
    REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Alquiler API',
    'DESCRIPTION': (
        'REST API for the Alquiler rental management SaaS. '
        'Serves landlord, tenant, and platform-admin clients.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SERVE_PERMISSIONS': ['rest_framework.permissions.IsAuthenticated'],
    # Resolve enum naming collisions for fields named "status" across models.
    'ENUM_NAME_OVERRIDES': {
        'AccountStatusEnum': 'core.models.AccountStatus',
        'SubscriptionStatusEnum': 'subscriptions.models.SubscriptionStatus',
        'LeaseStatusEnum': 'leases.models.LeaseStatus',
        'PropertyStatusEnum': 'properties.models.PropertyStatus',
        'UnitStatusEnum': 'properties.models.UnitStatus',
        'PaymentStatusEnum': 'payments.models.PaymentStatus',
        'PaymentMethodEnum': 'payments.models.PaymentMethod',
        'RentFrequencyEnum': 'leases.models.RentFrequency',
        'RentPeriodStatusEnum': 'payments.models.RentPeriodStatus',
        'NotificationStatusEnum': 'notifications.models.NotificationStatus',
        'NotificationTypeEnum': 'notifications.models.NotificationType',
        'PlanTierEnum': 'subscriptions.models.PlanTier',
    },
}

# CORS: allowed frontend origins.
CORS_ALLOWED_ORIGINS = env(
    'CORS_ALLOWED_ORIGINS',
    default=[
        'http://localhost:5173',
        'http://127.0.0.1:5173',
    ],
)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Internationalization
LANGUAGE_CODE = 'en-us'

# Nigeria launch market.
TIME_ZONE = 'Africa/Lagos'

USE_I18N = True

USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email (MVP: console backend by default; production uses SMTP via env).
EMAIL_BACKEND = env(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST = env('EMAIL_HOST', default='smtp.example.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='Alquiler <no-reply@alquiler.example>')

# Invitation token lifetime (hours).
INVITATION_TOKEN_TTL_HOURS = env.int('INVITATION_TOKEN_TTL_HOURS', default=72)

# Notification schedule configuration.
RENT_REMINDER_SCHEDULE = {
    'upcoming_days': [7, 3, 0],
    'overdue_days': [3, 7, 14],
}
LEASE_EXPIRY_REMINDER_SCHEDULE = {
    'before_days': [30, 7, 0],
    'after_days': [7, 14, 21, 28],
}

# Redis / caching
REDIS_URL = env('REDIS_URL')

if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
            'KEY_PREFIX': 'alquiler',
            'TIMEOUT': 300,  # 5 minutes default
        }
    }

# Default currency for the launch market.
DEFAULT_CURRENCY = env('DEFAULT_CURRENCY', default='NGN')

# Base URL for building invitation links in emails.
SITE_URL = env('SITE_URL', default='http://localhost:5173')

# Subscription trial duration (days). Override via env for different markets.
TRIAL_DURATION_DAYS = env.int('TRIAL_DURATION_DAYS', default=14)

# Phase 10A — Token expiry (days). Auth tokens older than this are rejected.
AUTH_TOKEN_EXPIRY_DAYS = env.int('AUTH_TOKEN_EXPIRY_DAYS', default=7)

# Phase 10A — Production security headers (only when DEBUG=False).
if not DEBUG:
    SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=True)
    SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
        'SECURE_HSTS_INCLUDE_SUBDOMAINS', default=True,
    )
    SECURE_HSTS_PRELOAD = env.bool('SECURE_HSTS_PRELOAD', default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Logging configuration
LOG_LEVEL = env('LOG_LEVEL', default='DEBUG' if DEBUG else 'INFO')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': LOG_LEVEL,
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'production': {
            'level': LOG_LEVEL,
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'] if DEBUG else ['production'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console'] if DEBUG else ['production'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'] if DEBUG else ['production'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'] if DEBUG else ['production'],
            'level': 'WARNING',
            'propagate': False,
        },
        'alquiler': {
            'handlers': ['console'] if DEBUG else ['production'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
    },
}
