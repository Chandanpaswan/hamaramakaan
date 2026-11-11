"""Security and helper utilities shared across apps."""
import logging
import os
import uuid

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.deconstruct import deconstructible
from django.utils.text import slugify

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def get_client_ip(request):
    """Client IP. Behind Nginx, set USE_X_FORWARDED_FOR=true; we trust only the hop Nginx appended (rightmost)."""
    if os.environ.get("USE_X_FORWARDED_FOR", "").lower() in {"1", "true", "yes"}:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR")


def is_rate_limited(request, scope, limit=None, window=None):
    """Count one hit for this IP + scope and report whether the limit is exceeded."""
    limit = limit or settings.FORM_RATE_LIMIT
    window = window or settings.FORM_RATE_WINDOW
    key = f"hm:rl:{scope}:{get_client_ip(request)}"
    if cache.add(key, 1, window):
        return False
    try:
        count = cache.incr(key)
    except ValueError:  # Key expired between add() and incr().
        cache.set(key, 1, window)
        return False
    return count > limit


def log_action(request_or_user, action, obj=None, description="", target_type="", target_id=""):
    """Write an AuditLog row. Never pass passwords, OTPs or message bodies in `description`."""
    from apps.core.models import AuditLog

    user, ip = None, None
    if hasattr(request_or_user, "META"):
        ip = get_client_ip(request_or_user)
        user = getattr(request_or_user, "user", None)
    else:
        user = request_or_user
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None
    if obj is not None:
        target_type = target_type or obj._meta.verbose_name.title()
        target_id = target_id or str(obj.pk)
    return AuditLog.objects.create(
        actor=user,
        action=action,
        target_type=target_type[:60],
        target_id=str(target_id)[:40],
        description=description[:300],
        ip_address=ip,
    )


def unique_slugify(instance, value, slug_field="slug", max_length=80, queryset=None):
    base = slugify(value)[:max_length].strip("-") or "item"
    slug = base
    model = instance.__class__
    qs = queryset if queryset is not None else model._default_manager.all()
    if instance.pk:
        qs = qs.exclude(pk=instance.pk)
    n = 2
    while qs.filter(**{slug_field: slug}).exists():
        suffix = f"-{n}"
        slug = f"{base[: max_length - len(suffix)]}{suffix}"
        n += 1
    return slug


@deconstructible
class safe_upload_path:  # noqa: N801 - used like a function in model fields
    """upload_to callable that discards the visitor's filename and stores a random UUID name."""

    def __init__(self, folder):
        self.folder = folder

    def __call__(self, instance, filename):
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            ext = ".jpg"
        return f"{self.folder}/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}"

    def __eq__(self, other):
        return isinstance(other, safe_upload_path) and other.folder == self.folder


def validate_image_file(upload):
    """Validate extension, size and real image content (not just the client-supplied MIME type)."""
    from PIL import Image, UnidentifiedImageError

    if upload is None:
        return
    ext = os.path.splitext(upload.name)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError("Only JPG, PNG or WebP images are allowed.")
    max_bytes = settings.MAX_IMAGE_UPLOAD_MB * 1024 * 1024
    if upload.size > max_bytes:
        raise ValidationError(f"Each image must be smaller than {settings.MAX_IMAGE_UPLOAD_MB} MB.")
    try:
        upload.seek(0)
        with Image.open(upload) as img:
            img_format = img.format
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValidationError("This file is not a valid image.") from exc
    finally:
        upload.seek(0)
    if img_format not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError("Only JPG, PNG or WebP images are allowed.")


def notify(subject, body, recipients):
    """Send a plain-text notification. Failures are logged, never shown to visitors."""
    recipients = [r for r in recipients if r]
    if not recipients:
        return False
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False)
        return True
    except Exception:  # noqa: BLE001 - email must never break a form submission
        logger.exception("Notification email failed: %s", subject)
        return False
