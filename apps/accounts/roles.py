"""
Role → permission matrix (requirements §13). Groups are (re)synced after every `migrate`.
Permissions are always enforced server-side in the dashboard views.
"""

CRUD = ("add", "change", "delete", "view")


def _crud(app, *models, actions=CRUD):
    return [f"{app}.{action}_{model}" for model in models for action in actions]


PROPERTY_MODELS = ("property", "propertyimage", "propertytype", "amenity", "project")
LOCATION_MODELS = ("state", "city", "locality")
LEAD_MODELS = ("lead", "leadnote")
CONTENT_MODELS_PAGES = ("page", "faq", "service", "highlight", "testimonial")
CONTENT_MODELS_BLOG = ("blogpost", "blogcategory", "blogtag")

ROLES = {
    "Super Admin": "__all__",
    "Admin": (
        _crud("properties", *PROPERTY_MODELS)
        + ["properties.approve_property", "properties.feature_property", "properties.verify_property"]
        + _crud("locations", *LOCATION_MODELS)
        + _crud("leads", *LEAD_MODELS)
        + ["leads.view_all_leads", "leads.assign_lead", "leads.export_lead", "leads.view_whatsappclick"]
        + _crud("pages", *CONTENT_MODELS_PAGES)
        + _crud("blog", *CONTENT_MODELS_BLOG)
        + ["core.view_sitesetting", "core.change_sitesetting", "core.view_auditlog", "core.view_reports"]
        + ["accounts.view_user"]
        + _crud("redirects", "redirect")
    ),
    "Property Manager": (
        _crud("properties", *PROPERTY_MODELS)
        + ["properties.approve_property", "properties.feature_property"]
        + _crud("locations", *LOCATION_MODELS, actions=("add", "change", "view"))
    ),
    "Sales Manager": (
        ["leads.view_lead", "leads.change_lead", "leads.add_lead", "leads.add_leadnote", "leads.view_leadnote"]
        + ["leads.view_all_leads", "leads.assign_lead", "leads.export_lead", "leads.view_whatsappclick"]
        + ["core.view_reports", "properties.view_property", "properties.view_project"]
    ),
    "Sales Executive": [
        "leads.view_lead",
        "leads.change_lead",
        "leads.add_leadnote",
        "leads.view_leadnote",
        "properties.view_property",
        "properties.view_project",
    ],
    "Content Editor": (
        _crud("blog", *CONTENT_MODELS_BLOG)
        + _crud("pages", *CONTENT_MODELS_PAGES)
        + ["properties.view_property"]
    ),
    "Viewer": [
        "properties.view_property",
        "properties.view_project",
        "blog.view_blogpost",
        "pages.view_page",
    ],
}


def sync_roles(verbosity=0):
    from django.contrib.auth.models import Group, Permission

    for role, perms in ROLES.items():
        group, _ = Group.objects.get_or_create(name=role)
        if perms == "__all__":
            group.permissions.set(Permission.objects.all())
            continue
        objs = []
        for code in perms:
            app_label, codename = code.split(".", 1)
            perm = Permission.objects.filter(content_type__app_label=app_label, codename=codename).first()
            if perm is None:
                if verbosity:
                    print(f"  [roles] permission not found yet: {code}")
                continue
            objs.append(perm)
        group.permissions.set(objs)
