import shutil
from decimal import Decimal

from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.test import TestCase

from apps.leads.models import Lead
from apps.properties.models import Property

from .factories import image_file, make_location, make_property, make_type, make_user


class PropertyModelTests(TestCase):
    def test_listing_id_and_slug_generated(self):
        p = make_property()
        self.assertRegex(p.listing_id, r"^HM\d{6}$")
        self.assertEqual(p.slug, "3-bhk-apartment")
        self.assertEqual(make_property().slug, "3-bhk-apartment-2")

    def test_price_per_unit_and_rental(self):
        p = make_property(price=Decimal("1450000"), area=Decimal("1450"))
        self.assertEqual(p.price_per_unit, Decimal("1000"))
        rent = make_property(purpose=Property.Purpose.RENT, price=Decimal("20000"))
        self.assertIsNone(rent.price_per_unit)


class ListingPageTests(TestCase):
    def setUp(self):
        self.two_bhk = make_property(title="Two", bedrooms=2, price=Decimal("4000000"))
        self.three_bhk = make_property(title="Three", bedrooms=3, price=Decimal("9000000"))
        self.rental = make_property(title="Rental", purpose=Property.Purpose.RENT, price=Decimal("20000"))
        self.pending = make_property(title="Pending one", status=Property.Status.PENDING)
        self.office = make_property(title="Office", property_type=make_type("office-space", "commercial"),
                                    category="commercial", bedrooms=None)

    def titles(self, url):
        return {p.title for p in self.client.get(url).context["properties"]}

    def test_only_published_listings_are_public(self):
        self.assertNotIn("Pending one", self.titles("/properties/"))

    def test_sections(self):
        self.assertNotIn("Rental", self.titles("/buy/"))
        self.assertEqual(self.titles("/rent/"), {"Rental"})
        self.assertEqual(self.titles("/commercial/"), {"Office"})

    def test_combined_filters(self):
        self.assertEqual(self.titles("/buy/?bhk=3&max_price=9500000"), {"Three"})
        self.assertEqual(self.titles("/buy/?bhk=2&bhk=3&min_price=5000000"), {"Three"})

    def test_invalid_range_is_ignored_not_crashing(self):
        response = self.client.get("/buy/?min_price=9000000&max_price=10")
        self.assertEqual(response.status_code, 200)
        self.assertIn("max_price", response.context["form"].errors)

    def test_filtered_pages_are_noindexed(self):
        self.assertContains(self.client.get("/buy/?bhk=3"), 'content="noindex')
        self.assertNotContains(self.client.get("/buy/"), 'content="noindex')

    def test_sorting(self):
        titles = [p.title for p in self.client.get("/buy/?category=residential&sort=price_desc").context["properties"]]
        self.assertEqual(titles, ["Three", "Two"])

    def test_city_and_type_filters_apply(self):
        # Regression: model-choice filters must validate against their real querysets.
        self.assertEqual(self.titles("/buy/?city=faridabad&type=office-space"), {"Office"})
        self.assertIn("Office", self.titles(f"/properties/?locality={self.office.locality_id}"))

    def test_budget_preset_redirects_to_explicit_filters(self):
        response = self.client.get("/buy/?budget=5000000-10000000")
        self.assertRedirects(response, "/buy/?min_price=5000000&max_price=10000000")


class DetailAndEnquiryTests(TestCase):
    def setUp(self):
        cache.clear()  # rate-limit counters live in the cache
        self.prop = make_property()

    def post_enquiry(self, **extra):
        data = {"name": "Asha", "phone": "+91 98100 00000", "message": "Hi", "preferred_contact_method": "phone",
                "consent": "on", "website": ""}
        data.update(extra)
        return self.client.post(self.prop.get_absolute_url(), data)

    def test_detail_page_hides_private_owner_details(self):
        self.prop.owner_phone = "+91 90000 12345"
        self.prop.address = "House 12, Secret Lane"
        self.prop.save()
        response = self.client.get(self.prop.get_absolute_url())
        self.assertNotContains(response, "90000 12345")
        self.assertNotContains(response, "Secret Lane")

    def test_unpublished_listing_404_for_public_but_previewable_by_staff(self):
        draft = make_property(title="Draft", status=Property.Status.DRAFT)
        self.assertEqual(self.client.get(draft.get_absolute_url()).status_code, 404)
        self.client.force_login(make_user("pm", "Property Manager"))
        self.assertContains(self.client.get(draft.get_absolute_url()), "Preview")

    def test_enquiry_creates_lead_and_notifies(self):
        response = self.post_enquiry()
        self.assertEqual(response.status_code, 302)
        lead = Lead.objects.get()
        self.assertEqual(lead.source, Lead.Source.PROPERTY)
        self.assertEqual(lead.interested_property, self.prop)
        self.assertTrue(lead.consent)
        self.assertRegex(lead.lead_id, r"^L\d{6}$")
        self.assertEqual(lead.status_history.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("98100", mail.outbox[0].body)  # contact details stay in the dashboard

    def test_enquiry_requires_consent(self):
        self.post_enquiry(consent="")
        self.assertFalse(Lead.objects.exists())

    def test_honeypot_blocks_bots(self):
        self.post_enquiry(website="http://spam.example")
        self.assertFalse(Lead.objects.exists())

    def test_rate_limit(self):
        with self.settings(FORM_RATE_LIMIT=2):
            for _ in range(4):
                self.post_enquiry()
        self.assertEqual(Lead.objects.count(), 2)


class PostPropertyTests(TestCase):
    def tearDown(self):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)

    def payload(self, **extra):
        city, locality = make_location()
        data = {
            "owner_name": "Ravi", "owner_phone": "+91 98100 11111", "owner_email": "ravi@example.com",
            "purpose": "sale", "property_type": make_type().pk, "city": city.pk, "locality": locality.pk,
            "address": "Flat 4B", "price": "5000000", "area": "1100", "area_unit": "sqft", "bedrooms": "2",
            "bathrooms": "2", "title": "2 BHK flat", "authorised": "on", "consent": "on", "website": "",
        }
        data.update(extra)
        return data

    def test_submission_is_pending_never_public(self):
        response = self.client.post("/post-property/", self.payload(photos=[image_file(), image_file("b.png", "PNG")]))
        self.assertRedirects(response, "/post-property/thank-you/", fetch_redirect_response=False)
        prop = Property.objects.get()
        self.assertEqual(prop.status, Property.Status.PENDING)
        self.assertEqual(prop.source, Property.Source.OWNER)
        self.assertFalse(prop.is_featured or prop.is_verified)
        self.assertEqual(prop.images.count(), 2)
        self.assertTrue(prop.images.first().image.name.startswith("properties/"))
        self.assertNotIn("photo", prop.images.first().image.name)  # original filename discarded
        self.assertEqual(Lead.objects.get().source, Lead.Source.POST_PROPERTY)
        self.assertEqual(self.client.get(prop.get_absolute_url()).status_code, 404)

    def test_rejects_non_image_upload(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        bad = SimpleUploadedFile("x.jpg", b"not an image", content_type="image/jpeg")
        response = self.client.post("/post-property/", self.payload(photos=[bad]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Property.objects.exists())

    def test_requires_authorisation_confirmation(self):
        self.client.post("/post-property/", self.payload(authorised=""))
        self.assertFalse(Property.objects.exists())
