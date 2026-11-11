from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, SECRET_KEY, STORAGES, env, env_bool

DEBUG = False

# --- Vercel (serverless) ---------------------------------------------------------------
ON_VERCEL = bool(env("VERCEL"))
if ON_VERCEL:
    vercel_hosts = [env(k) for k in ("VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_URL", "VERCEL_BRANCH_URL") if env(k)]
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, *vercel_hosts]
    CSRF_TRUSTED_ORIGINS = [*CSRF_TRUSTED_ORIGINS, *[f"https://{h}" for h in vercel_hosts]]
    # No collectstatic step on Vercel: WhiteNoise serves files straight from the app's static folders.
    # Static URLs carry ?v=<commit> so browsers can cache them for a year and still get each new deploy.
    WHITENOISE_USE_FINDERS = True
    STORAGES["staticfiles"] = {"BACKEND": "apps.core.storage.VersionedStaticFilesStorage"}
    if env("VERCEL_GIT_COMMIT_SHA"):
        WHITENOISE_MAX_AGE = 31536000
    IMAGE_OPTIMIZATION = env_bool("IMAGE_OPTIMIZATION", True)

if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set in production.")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set in production.")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)

# A shared cache is required so rate limits and login lockouts work across workers / serverless instances.
if env("REDIS_URL"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": env("REDIS_URL")}}
else:
    # Run `python manage.py createcachetable` once after deploying.
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "hm_cache"}}
