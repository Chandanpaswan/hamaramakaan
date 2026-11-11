from .development import *  # noqa: F401,F403
from .development import BASE_DIR

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
MEDIA_ROOT = BASE_DIR / "test_media"
LEAD_NOTIFICATION_EMAILS = ["leads@example.com"]
