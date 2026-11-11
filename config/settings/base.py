"""Shared settings for every environment. Secrets come from environment variables / .env."""
import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


SECRET_KEY = env("DJANGO_SECRET_KEY", "")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.redirects",
    "django.contrib.sitemaps",
    "django.contrib.humanize",
    # Project apps
    "apps.core",
    "apps.accounts",
    "apps.locations",
    "apps.properties",
    "apps.leads",
    "apps.pages",
    "apps.blog",
    "apps.dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.CampaignMiddleware",
    "apps.core.middleware.MaintenanceModeMiddleware",
    "django.contrib.redirects.middleware.RedirectFallbackMiddleware",
]

ROOT_URLCONF = "config.urls"
SITE_ID = 1

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
                "apps.dashboard.context_processors.dashboard_nav",
            ],
            "builtins": ["apps.core.templatetags.hm"],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database: SQLite locally, PostgreSQL in staging/production.
# DATABASE_URL (e.g. from Neon / Vercel) takes priority; otherwise DB_ENGINE=postgres + DB_* vars.
if env("DATABASE_URL"):
    _db = urlparse(env("DATABASE_URL"))
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _db.path.lstrip("/"),
            "USER": unquote(_db.username or ""),
            "PASSWORD": unquote(_db.password or ""),
            "HOST": _db.hostname,
            "PORT": _db.port or 5432,
            "OPTIONS": {key: values[0] for key, values in parse_qs(_db.query).items()},
            "CONN_MAX_AGE": int(env("DB_CONN_MAX_AGE", "0")),
            # Neon's pooled URL uses PgBouncer transaction pooling, which breaks server-side cursors
            # (used by .iterator() and form dropdowns): "cursor ... does not exist" 500s.
            "DISABLE_SERVER_SIDE_CURSORS": True,
        }
    }
elif env("DB_ENGINE", "sqlite") == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "hamara_makaan"),
            "USER": env("DB_USER", "hamara_makaan"),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "5432"),
            "CONN_MAX_AGE": int(env("DB_CONN_MAX_AGE", "60")),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "dashboard:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "dashboard:login"

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locale"]

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
IMAGE_OPTIMIZATION = False  # Vercel Image Optimization for uploaded photos (enabled in production on Vercel)
# Uploaded photos go to Vercel Blob when a token is configured (required on Vercel: its disk is ephemeral).
if env("BLOB_READ_WRITE_TOKEN"):
    STORAGES["default"] = {"BACKEND": "apps.core.storage.VercelBlobStorage"}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Uploads
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
MAX_IMAGE_UPLOAD_MB = int(env("MAX_IMAGE_UPLOAD_MB", "5"))
MAX_IMAGES_PER_SUBMISSION = int(env("MAX_IMAGES_PER_SUBMISSION", "10"))

# Email
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "no-reply@hamaramakaan.com")
LEAD_NOTIFICATION_EMAILS = env_list("LEAD_NOTIFICATION_EMAILS")

# Rate limiting for public forms (per IP)
FORM_RATE_LIMIT = int(env("FORM_RATE_LIMIT", "5"))  # submissions per window
FORM_RATE_WINDOW = int(env("FORM_RATE_WINDOW", "600"))  # seconds
LOGIN_FAILURE_LIMIT = int(env("LOGIN_FAILURE_LIMIT", "5"))
LOGIN_LOCKOUT_SECONDS = int(env("LOGIN_LOCKOUT_SECONDS", "900"))

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Non-obvious paths. Obscurity is NOT the security control; server-side permissions are.
DASHBOARD_PATH = env("DASHBOARD_PATH", "manage/")
DJANGO_ADMIN_PATH = env("DJANGO_ADMIN_PATH", "hm-system-admin/")

SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
}
