from django.urls import path

from . import views

app_name = "locations"

urlpatterns = [
    path("<slug:city_slug>/", views.city_detail, name="city"),
    path("<slug:city_slug>/<slug:locality_slug>/", views.locality_detail, name="locality"),
]
