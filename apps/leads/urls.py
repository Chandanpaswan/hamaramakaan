from django.urls import path

from . import views

app_name = "leads"

urlpatterns = [
    path("request-callback/", views.callback_request, name="callback"),
    path("go/whatsapp/", views.whatsapp_redirect, name="whatsapp"),
]
