def dashboard_nav(request):
    if not request.resolver_match or request.resolver_match.namespace != "dashboard":
        return {}
    user = request.user
    if not (user.is_authenticated and user.is_staff):
        return {}
    from apps.leads.models import Lead
    from apps.properties.models import Property

    from .views import sidebar_groups

    ctx = {"nav_groups": sidebar_groups(user)}
    if user.has_perm("properties.view_property"):
        ctx["nav_pending"] = Property.objects.filter(status=Property.Status.PENDING).count()
    if user.has_perm("leads.view_lead"):
        ctx["nav_new_leads"] = Lead.objects.visible_to(user).filter(status=Lead.Status.NEW, is_archived=False).count()
    return ctx
