from django.urls import path

from . import views

app_name = "pages"

urlpatterns = [
    path("about-us/", views.about, name="about"),
    path("services/", views.services, name="services"),
    path("contact-us/", views.contact, name="contact"),
    path("faq/", views.faq, name="faq"),
    path("privacy-policy/", views.legal, {"slug": "privacy-policy"}, name="privacy"),
    path("terms-and-conditions/", views.legal, {"slug": "terms-and-conditions"}, name="terms"),
    path("disclaimer/", views.legal, {"slug": "disclaimer"}, name="disclaimer"),
    path("page/<slug:slug>/", views.page_detail, name="page"),
]
