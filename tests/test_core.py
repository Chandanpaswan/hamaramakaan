from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.core.models import SiteSetting
from apps.core.templatetags.hm import indian_grouping, inr, inr_short, rich_text
from apps.core.utils import validate_image_file

from .factories import image_file


class FormattingTests(TestCase):
    def test_indian_grouping(self):
        self.assertEqual(indian_grouping(1234567), "12,34,567")
        self.assertEqual(indian_grouping(999), "999")
        self.assertEqual(inr(14500000), "₹ 1,45,00,000")

    def test_short_prices(self):
        self.assertEqual(inr_short(8500000), "₹ 85 Lakh")
        self.assertEqual(inr_short(14500000), "₹ 1.45 Cr")
        self.assertEqual(inr_short(28000), "₹ 28,000")
        self.assertEqual(inr_short(None), "")


class RichTextTests(TestCase):
    def test_escapes_html_and_scripts(self):
        html = rich_text("<script>alert(1)</script>\n[x](javascript:alert(1))")
        self.assertNotIn("<script>", html)
        self.assertNotIn('href="javascript', html)

    def test_supported_formatting(self):
        html = rich_text("## Title\n- one\n- two\n\nSee **bold** and [docs](https://example.com).")
        self.assertIn("<h2>Title</h2>", html)
        self.assertIn("<li>one</li>", html)
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn('href="https://example.com"', html)


class ImageValidationTests(TestCase):
    def test_accepts_real_images(self):
        validate_image_file(image_file())
        validate_image_file(image_file("p.png", "PNG"))

    def test_rejects_fake_image(self):
        fake = SimpleUploadedFile("evil.jpg", b"<?php echo 'hi'; ?>", content_type="image/jpeg")
        with self.assertRaises(ValidationError):
            validate_image_file(fake)

    def test_rejects_bad_extension(self):
        with self.assertRaises(ValidationError):
            validate_image_file(image_file("photo.svg"))

    @override_settings(MAX_IMAGE_UPLOAD_MB=0)
    def test_rejects_oversized(self):
        with self.assertRaises(ValidationError):
            validate_image_file(image_file())


class SiteBehaviourTests(TestCase):
    def test_robots_blocks_dashboard_and_lists_sitemap(self):
        body = self.client.get("/robots.txt").content.decode()
        self.assertIn("Disallow: /manage/", body)
        self.assertIn("Sitemap:", body)

    def test_custom_404(self):
        response = self.client.get("/does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "couldn’t find that page", status_code=404)

    def test_maintenance_mode_blocks_public_but_not_dashboard(self):
        site = SiteSetting.load()
        site.maintenance_mode = True
        site.save()
        self.assertEqual(self.client.get("/").status_code, 503)
        self.assertEqual(self.client.get("/manage/login/").status_code, 200)

    def test_contact_details_hidden_until_configured(self):
        response = self.client.get("/")
        self.assertNotContains(response, "tel:")
        site = SiteSetting.load()
        site.phone = "+91 98100 00000"
        site.save()
        self.assertContains(self.client.get("/"), "tel:+919810000000")
