from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import AuditLog
from .utils import log_action


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    log_action(request, AuditLog.Action.LOGIN, target_type="User", target_id=user.pk, description=user.get_username())


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if user is not None:
        log_action(request, AuditLog.Action.LOGOUT, target_type="User", target_id=user.pk)


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    # Only the attempted username is stored; passwords are never logged.
    username = str(credentials.get("username", ""))[:150]
    if request is not None:
        log_action(request, AuditLog.Action.LOGIN_FAILED, target_type="User", description=f"username={username}")


def _clear_public_caches(**kwargs):
    cache.delete_many(["hm:footer-data", "hm:home-data"])


def connect_cache_invalidation():
    from apps.locations.models import City
    from apps.pages.models import Page

    for model in (City, Page):
        post_save.connect(_clear_public_caches, sender=model, dispatch_uid=f"hm-cache-save-{model.__name__}")
        post_delete.connect(_clear_public_caches, sender=model, dispatch_uid=f"hm-cache-del-{model.__name__}")
