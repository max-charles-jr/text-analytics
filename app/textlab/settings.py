"""
Django settings for the textlab project (CLD-410 text analytics assignment).

Configuration is driven by environment variables so the same image can run
locally (for development/testing) and on ECS Fargate without code changes.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
# Supplied via the ECS task definition / container environment, never
# hard-coded in source control.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-only-insecure-key-change-me')

# DEBUG must be explicitly enabled; defaults closed for safety in production.
DEBUG = os.environ.get('DJANGO_DEBUG', 'false').lower() == 'true'

ALLOWED_HOSTS = [h for h in os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',') if h]

INSTALLED_APPS = [
    'django.contrib.staticfiles',
    'novels',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'textlab.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
            ],
        },
    },
]

WSGI_APPLICATION = 'textlab.wsgi.application'

DATABASES = {}

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
NOVELS_BUCKET = os.environ.get('NOVELS_BUCKET', 'tesu-cld410-text-analytics-mcharlescld-mc-ta')
RAW_PREFIX = os.environ.get('RAW_PREFIX', 'raw/')
AUDIO_PREFIX = os.environ.get('AUDIO_PREFIX', 'audio/')

# AWS Polly voice/engine used for text-to-speech conversion.
POLLY_VOICE_ID = os.environ.get('POLLY_VOICE_ID', 'Joanna')
POLLY_ENGINE = os.environ.get('POLLY_ENGINE', 'neural')

MAX_TABLE_ROWS = int(os.environ.get('MAX_TABLE_ROWS', '75'))

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO')},
}
