"""
Django settings for the SkyStay hotel booking platform.

Environment driven configuration lives in `.env` (see `.env.example`).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from backend/.env when present.
load_dotenv(BASE_DIR / '.env')


def env(key, default=None):
    return os.environ.get(key, default)


def env_bool(key, default=False):
    value = os.environ.get(key)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(key, default=''):
    raw = os.environ.get(key, default) or ''
    return [item.strip() for item in raw.split(',') if item.strip()]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

SECRET_KEY = env('DJANGO_SECRET_KEY', 'django-insecure-!t&64d$6+0&*z6ii@+$wycpe$4oxk+djn#yg%tos*h$skf23$m')

DEBUG = env_bool('DJANGO_DEBUG', True)

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]')

# The admin's location picker loads OpenStreetMap tiles and Nominatim geocoding
# cross-origin. Django's default SECURE_REFERRER_POLICY ('same-origin') strips
# the Referer header on those requests, which the OSM tile usage policy forbids
# and which makes their tile server answer 403 "Access blocked".
# 'strict-origin-when-cross-origin' is the browser default: it sends the origin
# (scheme + host), satisfying the policy without leaking full paths externally.
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Used for the default "from" name and the admin branding below.
SITE_NAME = env('SITE_NAME', 'SkyStay')


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',

    # Local apps
    'accounts',
    'content',
    'hotels',
    'offers',
    'bookings',
    'reviews',
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
        'DIRS': [BASE_DIR / 'templates'],
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
ASGI_APPLICATION = 'config.asgi.application'


# ---------------------------------------------------------------------------
# Database (MySQL)
# ---------------------------------------------------------------------------

import sys

if 'test' in sys.argv:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'OPTIONS': {
                'timeout': 30,
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': env('DB_NAME', 'skystay_db'),
            'USER': env('DB_USER', 'root'),
            'PASSWORD': env('DB_PASSWORD', ''),
            'HOST': env('DB_HOST', '127.0.0.1'),
            'PORT': env('DB_PORT', '3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTHENTICATION_BACKENDS = ['accounts.backends.EmailOrUsernameBackend']


# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------

LANGUAGE_CODE = 'en-us'
TIME_ZONE = env('DJANGO_TIME_ZONE', 'UTC')
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# `or` (not just a default) so an empty value in .env falls back to the project default
# instead of resolving to the current working directory.
MEDIA_URL = env('MEDIA_URL') or '/media/'
MEDIA_ROOT = Path(env('MEDIA_ROOT') or (BASE_DIR / 'media'))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Upload guard rails for admin uploaded content.
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

# `MAILERS` is not a Django setting — the backend has to be declared through
# EMAIL_BACKEND, otherwise Django falls back to SMTP and booking notifications fail silently.
#
# Credentials come from .env. A Gmail account needs an *app password*
# (Google Account → Security → 2-Step Verification → App passwords), not the
# account password; Gmail strips the spaces Google displays it with.
EMAIL_HOST = env('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(env('EMAIL_PORT', '587'))
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = (env('EMAIL_HOST_PASSWORD', '') or '').replace(' ', '')
EMAIL_TIMEOUT = int(env('EMAIL_TIMEOUT', '15'))

# Without credentials the console backend keeps development zero-config; as soon as
# EMAIL_HOST_USER is set, real mail goes out over SMTP.
EMAIL_BACKEND = env(
    'EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend'
    if EMAIL_HOST_USER
    else 'django.core.mail.backends.console.EmailBackend',
)
DEFAULT_FROM_EMAIL = env(
    'DEFAULT_FROM_EMAIL',
    f'{SITE_NAME} <{EMAIL_HOST_USER}>' if EMAIL_HOST_USER else f'{SITE_NAME} <no-reply@skystay.com>',
)
# Internal address that receives the "new booking" notice. Defaults to the sending
# mailbox so the site owner is always notified, even before Site settings is filled in.
BOOKING_NOTIFICATION_EMAIL = env('BOOKING_NOTIFICATION_EMAIL', EMAIL_HOST_USER)
# Mailbox that receives public contact form submissions. Defaults to the booking
# inbox so the site owner only has to configure one address.
CONTACT_NOTIFICATION_EMAIL = env('CONTACT_NOTIFICATION_EMAIL', '') or BOOKING_NOTIFICATION_EMAIL


# ---------------------------------------------------------------------------
# Razorpay Payment Gateway
# ---------------------------------------------------------------------------
RAZORPAY_KEY_ID = env('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = env('RAZORPAY_KEY_SECRET', '')



# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.StandardPagination',
    'PAGE_SIZE': 9,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%SZ',
}


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = env_list(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173',
) or [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = env_bool('CORS_ALLOW_ALL_ORIGINS', False)

CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173')

# Where the React front end is served. Used by the admin "VIEW SITE" link and
# the Django landing page at "/".
FRONTEND_URL = env('FRONTEND_URL', 'http://localhost:5173').rstrip('/')

# Admin branding (overridden at runtime by SiteSettings through context processor)
ADMIN_SITE_HEADER = 'SkyStay Administration'
ADMIN_SITE_TITLE = 'SkyStay CMS'
ADMIN_INDEX_TITLE = 'Content & Booking Management'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': 'INFO'},
}
