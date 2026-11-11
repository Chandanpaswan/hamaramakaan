"""Regression tests for fixes from the November 2026 QA pass (test-case IDs from the QA report)."""
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.core.utils import phone_key
from apps.leads.models import Lead
from apps.properties.models import Property

from .factories import make_location, make_property, make_type, make_user


class PhoneKeyTests(TestCase):
    def test_formats_compare_equal(self):
        self.assertEqual(phone_key("+91 98100 00000"), phone_key("098100-00000"))
        self.assertEqual(phone_key("9810000000"), "9810000000")


class DatabaseSettingsTests(TestCase):
    def test_pooled_postgres_disables_server_side_cursors(self):
        import importlib
        import os

        from config.settings import base

        os.environ["DATABASE_URL"] = "postgresql://u:p@ep-x-pooler.neon.tech/db?sslmode=require"
        try:
            importlib.reload(base)
            self.assertTrue(base.DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"])
        finally:
            del os.environ["DATABASE_URL"]
            importlib.reload(base)


class DuplicateSubmissionTests(TestCase):
    """HM-025 (duplicate property) and HM-035 (duplicate lead)."""

    def setUp(self):
        cache.clear()

    def post_property(self, phone):
        city, locality = make_location()
        return self.client.post("/post-property/", {
            "owner_name": "Ravi", "owner_phone": phone, "purpose": "sale", "property_type": make_type().pk,
            "city": city.pk, "locality": locality.pk, "address": "Flat 4B", "price": "5000000", "area": "1100",
            "area_unit": "sqft", "title": "2 BHK flat", "authorised": "on", "consent": "on", "website": "",
        })

    def test_duplicate_property_is_rejected_with_reference(self):
        self.assertEqual(self.post_property("+91 98100 11111").status_code, 302)
        ref = Property.objects.get().listing_id
        response = self.post_property("09810011111")  # same number, different format
        self.assertContains(response, f"reference {ref}")
        self.assertEqual(Property.objects.count(), 1)

    def test_repeat_enquiry_becomes_note_on_existing_lead(self):
        prop = make_property()
        data = {"name": "Asha", "phone": "+91 98100 00000", "message": "First", "preferred_contact_method": "phone",
                "consent": "on", "website": ""}
        self.client.post(prop.get_absolute_url(), data)
        self.client.post(prop.get_absolute_url(), {**data, "phone": "9810000000", "message": "Second"})
        self.assertEqual(Lead.objects.count(), 1)
        self.assertIn("Second", Lead.objects.get().notes.get().note)
        other = make_property(title="Other")
        self.client.post(other.get_absolute_url(), data)  # a different property is a new lead
        self.assertEqual(Lead.objects.count(), 2)


class UnderOfferTests(TestCase):
    def test_under_offer_stays_public_with_badge(self):
        prop = make_property(status=Property.Status.UNDER_OFFER)
        self.assertContains(self.client.get(prop.get_absolute_url()), "Under offer")
        self.assertIn(prop, self.client.get("/buy/").context["properties"])


class HeroBannerTests(TestCase):
    def test_placeholder_until_a_banner_is_uploaded(self):
        from apps.core.models import SiteSetting

        html = self.client.get("/").content.decode()
        self.assertIn("images/hero/hero-banner.jpg", html)
        self.assertIn("hero-banner-sm.webp", html)  # phone background
        site = SiteSetting.load()
        site.hero_image = "site/2026/11/banner.jpg"
        site.hero_image_alt = "Our office building"
        site.save()
        html = self.client.get("/").content.decode()
        self.assertIn("/media/site/2026/11/banner.jpg", html)
        self.assertIn('alt="Our office building"', html)
        self.assertNotIn("images/hero/hero-banner.jpg", html)


class PropertyDeleteTests(TestCase):
    """HM-040: delete needs permission and a confirmation step."""

    def test_delete_requires_permission_and_confirmation(self):
        prop = make_property()
        self.client.force_login(make_user("sales", "Sales Executive"))
        self.assertEqual(self.client.post(f"/manage/properties/{prop.pk}/delete/").status_code, 403)
        self.client.force_login(make_user("pm", "Property Manager"))
        self.assertContains(self.client.get(f"/manage/properties/{prop.pk}/delete/"), "Delete this property?")
        self.assertTrue(Property.objects.filter(pk=prop.pk).exists())  # GET alone deletes nothing
        self.assertRedirects(self.client.post(f"/manage/properties/{prop.pk}/delete/"), "/manage/properties/")
        self.assertFalse(Property.objects.filter(pk=prop.pk).exists())
