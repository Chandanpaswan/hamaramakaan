from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.home, name="home"),
    # Properties
    path("properties/", views.property_list, name="property_list"),
    path("properties/new/", views.property_create, name="property_create"),
    path("properties/<int:pk>/", views.property_detail, name="property_detail"),
    path("properties/<int:pk>/edit/", views.property_edit, name="property_edit"),
    path("properties/<int:pk>/review/", views.property_review, name="property_review"),
    path("properties/<int:pk>/delete/", views.property_delete, name="property_delete"),
    path("properties/<int:pk>/photos/", views.property_images_upload, name="property_images_upload"),
    path("properties/<int:pk>/photos/<int:image_pk>/", views.property_image_action, name="property_image_action"),
    # Leads
    path("leads/", views.lead_list, name="lead_list"),
    path("leads/new/", views.lead_create, name="lead_create"),
    path("leads/export/", views.lead_export, name="lead_export"),
    path("leads/<int:pk>/", views.lead_detail, name="lead_detail"),
    # Users
    path("users/", views.user_list, name="user_list"),
    path("users/new/", views.user_create, name="user_create"),
    path("users/<int:pk>/", views.user_edit, name="user_edit"),
    path("users/<int:pk>/password/", views.user_password, name="user_password"),
    # System
    path("settings/", views.site_settings, name="settings"),
    path("reports/", views.reports, name="reports"),
    path("audit-log/", views.audit_log, name="audit_log"),
    # Generic content modules
    path("m/<slug:slug>/", views.crud_list, name="crud_list"),
    path("m/<slug:slug>/new/", views.crud_form, name="crud_create"),
    path("m/<slug:slug>/<int:pk>/", views.crud_form, name="crud_edit"),
    path("m/<slug:slug>/<int:pk>/delete/", views.crud_delete, name="crud_delete"),
]
