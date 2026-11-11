from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.blog.models import BlogPost
from apps.locations.models import City
from apps.pages.models import Testimonial
from apps.properties.models import Property

from .factories import make_location, make_property


class SitemapTests(TestCase):
    def test_sitemap_lists_public_content_only(self):
        live = make_property(title="Live home")
        hidden = make_property(title="Hidden home", status=Property.Status.PENDING)
        body = self.client.get("/sitemap.xml").content.decode()
        self.assertIn(live.get_absolute_url(), body)
        self.assertNotIn(hidden.get_absolute_url(), body)

    def test_empty_locations_excluded_and_noindexed(self):
        city, _ = make_location()
        empty = City.objects.create(state=city.state, name="Ballabhgarh")
        make_property()
        body = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("/locations/faridabad/", body)
        self.assertNotIn("/locations/ballabhgarh/", body)
        self.assertContains(self.client.get(empty.get_absolute_url()), 'content="noindex')


class CanonicalAndImageTests(TestCase):
    def setUp(self):
        from django.contrib.sites.models import Site
        from django.core.cache import cache

        Site.objects.update_or_create(pk=1, defaults={"domain": "hamaramakaan.com", "name": "HM"})
        cache.clear()

    def test_canonical_uses_site_domain_not_request_host(self):
        prop = make_property()
        html = self.client.get(prop.get_absolute_url()).content.decode()
        self.assertIn(f'rel="canonical" href="https://hamaramakaan.com{prop.get_absolute_url()}"', html)
        self.assertIn('"@type":"RealEstateListing"', html)
        self.assertIn('"priceCurrency":"INR"', html)

    def test_absolute_image_urls_are_not_double_prefixed(self):
        from django.template import Context, Template

        out = Template("{% absolute_url url %}").render(Context({"url": "https://x.public.blob.vercel-storage.com/a.jpg",
                                                                 "canonical_base": "https://hamaramakaan.com"}))
        self.assertEqual(out, "https://x.public.blob.vercel-storage.com/a.jpg")

    def test_image_optimization_urls(self):
        from types import SimpleNamespace

        from apps.core.templatetags.hm import img_src, img_srcset

        blob = SimpleNamespace(url="https://x.public.blob.vercel-storage.com/p/a b.jpg")
        with self.settings(IMAGE_OPTIMIZATION=True):
            self.assertEqual(img_src(blob, 400),
                             "/_vercel/image?url=https%3A%2F%2Fx.public.blob.vercel-storage.com%2Fp%2Fa%20b.jpg&w=400&q=75")
            self.assertTrue(img_srcset(blob, "400,800").endswith(" 800w"))
        with self.settings(IMAGE_OPTIMIZATION=False):
            self.assertEqual(img_src(blob, 400), blob.url)
            self.assertEqual(img_srcset(blob), "")


class SampleDataTests(TestCase):
    def test_sample_content_is_noindexed_and_kept_out_of_sitemap(self):
        sample = make_property(title="Sample home")
        Property.objects.filter(pk=sample.pk).update(is_sample=True)
        post = BlogPost.objects.create(title="Sample post", body="x", status=BlogPost.Status.PUBLISHED)
        BlogPost.objects.filter(pk=post.pk).update(is_sample=True)
        self.assertContains(self.client.get(sample.get_absolute_url()), 'content="noindex')
        self.assertContains(self.client.get(post.get_absolute_url()), 'content="noindex')
        body = self.client.get("/sitemap.xml").content.decode()
        self.assertNotIn(sample.get_absolute_url(), body)
        self.assertNotIn(post.get_absolute_url(), body)

    def test_seed_demo_refuses_production_without_flag(self):
        from django.core.management import CommandError, call_command

        with self.settings(DEBUG=False), self.assertRaises(CommandError):
            call_command("seed_demo", "--no-photos")


class BlogTests(TestCase):
    def test_draft_and_future_posts_hidden(self):
        draft = BlogPost.objects.create(title="Draft", body="x")
        future = BlogPost.objects.create(title="Future", body="x", status=BlogPost.Status.SCHEDULED,
                                         published_at=timezone.now() + timedelta(days=1))
        live = BlogPost.objects.create(title="Live", body="x", status=BlogPost.Status.PUBLISHED)
        self.assertEqual(list(BlogPost.objects.published()), [live])
        self.assertEqual(self.client.get(draft.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(future.get_absolute_url()).status_code, 404)
        response = self.client.get(live.get_absolute_url())
        self.assertContains(response, '"@type":"BlogPosting"')


class TrustTests(TestCase):
    def test_testimonial_needs_permission_to_publish(self):
        from django.core.exceptions import ValidationError

        t = Testimonial(name="A", quote="Great", is_published=True, permission_confirmed=False)
        with self.assertRaises(ValidationError):
            t.full_clean()

    def test_no_fake_aggregate_rating_schema(self):
        make_property()
        self.assertNotContains(self.client.get("/"), "aggregateRating")
