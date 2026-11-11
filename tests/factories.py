"""Small helpers to build test data without external libraries."""
import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.locations.models import City, Locality, State
from apps.properties.models import Property, PropertyType


def make_location():
    state, _ = State.objects.get_or_create(name="Haryana")
    city, _ = City.objects.get_or_create(state=state, name="Faridabad")
    locality, _ = Locality.objects.get_or_create(city=city, name="Sector 85")
    return city, locality


def make_type(slug="apartment", category="residential"):
    ptype, _ = PropertyType.objects.get_or_create(slug=slug, defaults={"name": slug.title(), "category": category})
    return ptype


def make_property(**kwargs):
    city, locality = make_location()
    defaults = dict(
        title="3 BHK apartment", property_type=make_type(), purpose=Property.Purpose.SALE, price=Decimal("8500000"),
        area=Decimal("1450"), bedrooms=3, bathrooms=2, city=city, locality=locality, status=Property.Status.PUBLISHED,
    )
    defaults.update(kwargs)
    return Property.objects.create(**defaults)


def make_user(username, role=None, **kwargs):
    user = get_user_model().objects.create_user(username=username, password="Str0ng-pass-123", is_staff=True, **kwargs)
    if role:
        user.groups.add(Group.objects.get(name=role))
    return user


def image_file(name="photo.jpg", fmt="JPEG", size=(40, 30)):
    buf = io.BytesIO()
    Image.new("RGB", size, (29, 78, 216)).save(buf, fmt)
    content_type = {"JPEG": "image/jpeg", "PNG": "image/png"}[fmt]
    return SimpleUploadedFile(name, buf.getvalue(), content_type=content_type)
