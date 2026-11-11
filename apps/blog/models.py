from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.core.models import SEOFieldsMixin, TimeStampedModel
from apps.core.utils import safe_upload_path, unique_slugify


class BlogCategory(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    description = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "blog categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("blog:category", args=[self.slug])


class BlogTag(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
        super().save(*args, **kwargs)


class BlogPostQuerySet(models.QuerySet):
    def published(self):
        return self.filter(
            Q(status=BlogPost.Status.PUBLISHED) | Q(status=BlogPost.Status.SCHEDULED),
            published_at__lte=timezone.now(),
        )


class BlogPost(SEOFieldsMixin, TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    excerpt = models.CharField(max_length=300, blank=True)
    body = models.TextField(
        help_text="Formatting: '## Heading', '### Subheading', '- bullet', '1. numbered', **bold**, [link](https://…)."
    )
    featured_image = models.ImageField(upload_to=safe_upload_path("blog"), blank=True)
    featured_image_alt = models.CharField(max_length=160, blank=True)
    category = models.ForeignKey(BlogCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="posts")
    tags = models.ManyToManyField(BlogTag, blank=True, related_name="posts")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    author_display_name = models.CharField(max_length=100, blank=True, help_text="Overrides the author's name.")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)
    published_at = models.DateTimeField(
        null=True, blank=True, help_text="For scheduled posts, the post goes live at this time."
    )
    is_featured = models.BooleanField(default=False)
    canonical_url = models.URLField(blank=True, help_text="Only if this article's original lives at another URL.")
    related_posts = models.ManyToManyField("self", blank=True, symmetrical=False)
    is_sample = models.BooleanField(default=False, editable=False, help_text="Sample content (noindexed).")

    objects = BlogPostQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [models.Index(fields=["status", "published_at"])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.title, max_length=160)
        if self.status == self.Status.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("blog:detail", args=[self.slug])

    @property
    def is_live(self):
        return self.status != self.Status.DRAFT and self.published_at is not None and self.published_at <= timezone.now()

    @property
    def author_name(self):
        if self.author_display_name:
            return self.author_display_name
        if self.author:
            return self.author.get_full_name() or "Hamara Makaan team"
        return "Hamara Makaan team"

    @property
    def reading_minutes(self):
        return max(1, round(len(self.body.split()) / 200))
