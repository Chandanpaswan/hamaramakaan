from django.apps import AppConfig, apps
from django.db.models.signals import post_migrate


def _sync_roles(sender, **kwargs):
    # post_migrate fires once per app; permissions for later apps only exist after their own signal,
    # so sync roles when the signal for the last installed app arrives.
    # Apps without a models module never send post_migrate, so compare with the last app that does.
    with_models = [cfg for cfg in apps.get_app_configs() if cfg.models_module is not None]
    if sender.label != with_models[-1].label:
        return
    from .roles import sync_roles

    sync_roles(verbosity=0)


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "Accounts"

    def ready(self):
        post_migrate.connect(_sync_roles, dispatch_uid="hm-sync-roles")
