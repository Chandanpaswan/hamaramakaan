from django.urls import path

from . import views

app_name = "properties"

urlpatterns = [
    path("properties/", views.property_list, {"section": "all"}, name="list"),
    path("properties/<slug:city_slug>/", views.property_list, {"section": "all"}, name="list_city"),
    path("buy/", views.property_list, {"section": "buy"}, name="buy"),
    path("buy/<slug:city_slug>/", views.property_list, {"section": "buy"}, name="buy_city"),
    path("rent/", views.property_list, {"section": "rent"}, name="rent"),
    path("rent/<slug:city_slug>/", views.property_list, {"section": "rent"}, name="rent_city"),
    path("commercial/", views.property_list, {"section": "commercial"}, name="commercial"),
    path("commercial/<slug:city_slug>/", views.property_list, {"section": "commercial"}, name="commercial_city"),
    path("property/<slug:slug>/", views.property_detail, name="detail"),
    path("new-projects/", views.project_list, name="projects"),
    path("new-projects/<slug:slug>/", views.project_detail, name="project_detail"),
    path("post-property/", views.post_property, name="post_property"),
    path("post-property/thank-you/", views.post_property_thanks, name="post_property_thanks"),
]
