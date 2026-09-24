import os
from pathlib import Path
from urllib.parse import urlparse, unquote
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
# Minimal .env loader: environment always takes precedence. No evaluation/interpolation.
if (BASE_DIR / '.env').exists():
    for line in (BASE_DIR / '.env').read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
DEBUG = os.getenv('DEBUG', '0') == '1'
DEMO_MODE = os.getenv('DEMO_MODE', '0') == '1'
if DEMO_MODE and not DEBUG:
    raise ImproperlyConfigured('Ambiente demonstrativo não é permitido em produção.')
SECRET_KEY = os.getenv('SECRET_KEY', '')
if len(SECRET_KEY) < 40:
    raise ImproperlyConfigured('Configure SECRET_KEY aleatória com pelo menos 40 caracteres.')
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
PUBLIC_URL = os.getenv('PUBLIC_URL', 'http://127.0.0.1:8765').rstrip('/')
CSRF_TRUSTED_ORIGINS = [x for x in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if x]
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.staticfiles', 'agenda']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware', 'agenda.middleware.SecurityHeaders']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request']}}]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
if DATABASE_URL:
    parsed=urlparse(DATABASE_URL)
    if parsed.scheme not in ('postgres','postgresql') or not parsed.hostname or not parsed.path.strip('/'):
        raise ImproperlyConfigured('DATABASE_URL deve ser uma URL PostgreSQL válida.')
    DATABASES = {'default': {'ENGINE':'django.db.backends.postgresql','NAME':unquote(parsed.path.lstrip('/')),'USER':unquote(parsed.username or ''),'PASSWORD':unquote(parsed.password or ''),'HOST':parsed.hostname,'PORT':str(parsed.port or 5432),'CONN_MAX_AGE':600,'OPTIONS':({'sslmode':'require'} if not DEBUG else {})}}
else:
    DATABASES = {'default': {'ENGINE':'django.db.backends.sqlite3', 'NAME':os.getenv('DATABASE_PATH', str(BASE_DIR/'data'/'agenda.sqlite3')), 'OPTIONS':{'timeout':30, 'transaction_mode':'IMMEDIATE'}}}
(BASE_DIR/'data').mkdir(exist_ok=True)
AUTH_USER_MODEL = 'agenda.User'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME':'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME':'django.contrib.auth.password_validation.MinimumLengthValidator','OPTIONS':{'min_length':12}},
    {'NAME':'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME':'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR/'static']
STATIC_ROOT = BASE_DIR/'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
MAIL_MODE = os.getenv('MAIL_MODE','smtp')
if MAIL_MODE == 'file' and not DEBUG:
    raise ImproperlyConfigured('MAIL_MODE=file é permitido apenas em desenvolvimento.')
EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend' if MAIL_MODE == 'file' else 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_FILE_PATH = BASE_DIR / 'data' / 'emails'
EMAIL_HOST = os.getenv('EMAIL_HOST','')
EMAIL_PORT = int(os.getenv('EMAIL_PORT','587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER','')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD','')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS','1') == '1'
EMAIL_TIMEOUT = 15
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL','')
RESEND_API_KEY = os.getenv('RESEND_API_KEY', '')
if MAIL_MODE == 'resend':
    EMAIL_HOST = 'smtp.resend.com'
    EMAIL_PORT = 465
    EMAIL_HOST_USER = 'resend'
    EMAIL_HOST_PASSWORD = RESEND_API_KEY
    EMAIL_USE_TLS = False
    EMAIL_USE_SSL = True
CSRF_FAILURE_VIEW = 'agenda.views.csrf_failure'
