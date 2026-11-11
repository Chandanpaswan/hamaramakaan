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
