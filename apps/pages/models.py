from django.db import models
from django.urls import NoReverseMatch, reverse

from apps.core.models import SEOFieldsMixin, TimeStampedModel
from apps.core.utils import unique_slugify

# Pages that have their own top-level URL. Any other page is served at /page/<slug>/.
TOP_LEVEL_PAGES = {
    "about-us": "pages:about",
    "services": "pages:services",
    "privacy-policy": "pages:privacy",
    "terms-and-conditions": "pages:terms",
    "disclaimer": "pages:disclaimer",
}


class Page(SEOFieldsMixin, TimeStampedModel):
    title = models.CharField(max_length=140)
    slug = models.SlugField(max_length=150, unique=True, blank=True)
    intro = models.CharField(max_length=300, blank=True, help_text="Short lead paragraph under the heading.")
    body = models.TextField(
        blank=True,
        help_text="Formatting: '## Heading', '### Subheading', '- bullet', '1. numbered', **bold**, [link](https://…).",
    )
    is_published = models.BooleanField(default=True)
    show_in_footer = models.BooleanField(default=False)
    is_legal = models.BooleanField(default=False)
    legal_reviewed = models.BooleanField(
        default=False, help_text="Tick once the text has been reviewed for the actual business process and Indian law."
    )
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        name = TOP_LEVEL_PAGES.get(self.slug)
        try:
            return reverse(name) if name else reverse("pages:page", args=[self.slug])
        except NoReverseMatch:
            return reverse("pages:page", args=[self.slug])


class FAQ(TimeStampedModel):
    class Category(models.TextChoices):
        GENERAL = "general", "General"
        BUYING = "buying", "Buying"
        RENTING = "renting", "Renting"
        SELLING = "selling", "Selling & listing"
        LEGAL = "legal", "Legal & documents"

    question = models.CharField(max_length=240)
    answer = models.TextField()
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.GENERAL)
    show_on_home = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["category", "sort_order", "id"]
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"

    def __str__(self):
        return self.question


class Service(TimeStampedModel):
    title = models.CharField(max_length=100)
    icon = models.CharField(max_length=40, default="apartment", help_text="Brand icon name")
    summary = models.CharField(max_length=240)
    body = models.TextField(blank=True)
    is_published = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "title"]

    def __str__(self):
        return self.title


class Highlight(TimeStampedModel):
    """'Why choose us' points. Keep them factual: no unverifiable statistics."""

    title = models.CharField(max_length=100)
    text = models.CharField(max_length=240)
    icon = models.CharField(max_length=40, default="shield-check")
    is_published = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "title"]

    def __str__(self):
        return self.title


class Testimonial(TimeStampedModel):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100, blank=True)
    quote = models.TextField(max_length=600)
    permission_confirmed = models.BooleanField(
        default=False, help_text="The customer gave written permission to publish this testimonial."
    )
    is_published = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "-created_at"]

    def __str__(self):
        return f"{self.name}: {self.quote[:40]}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.is_published and not self.permission_confirmed:
            raise ValidationError("A testimonial can only be published after the customer's permission is confirmed.")
