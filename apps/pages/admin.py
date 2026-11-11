from django.contrib import admin

from .models import FAQ, Highlight, Page, Service, Testimonial

for model in (Page, FAQ, Service, Highlight, Testimonial):
    admin.site.register(model)
