from django.db import models
from django.urls import reverse

from apps.core.models import SEOFieldsMixin, TimeStampedModel
from apps.core.utils import unique_slugify


class State(TimeStampedModel):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
        super().save(*args, **kwargs)


class City(SEOFieldsMixin, TimeStampedModel):
    state = models.ForeignKey(State, on_delete=models.PROTECT, related_name="cities")
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    description = models.TextField(blank=True, help_text="Original, useful local information for the city page.")
    is_active = models.BooleanField(default=True)
    is_indexable = models.BooleanField(
        default=True, help_text="Allow search engines to index this page (it is also noindexed when empty)."
    )
    show_in_footer = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "cities"
        constraints = [models.UniqueConstraint(fields=["state", "name"], name="uniq_city_per_state")]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("locations:city", args=[self.slug])


class Locality(SEOFieldsMixin, TimeStampedModel):
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="localities")
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_indexable = models.BooleanField(default=True)
    is_popular = models.BooleanField(default=False, help_text="Show as a quick search chip on the home page.")

    class Meta:
        ordering = ["city__name", "name"]
        verbose_name_plural = "localities"
        constraints = [
            models.UniqueConstraint(fields=["city", "slug"], name="uniq_locality_slug_per_city"),
            models.UniqueConstraint(fields=["city", "name"], name="uniq_locality_name_per_city"),
        ]

    def __str__(self):
        return f"{self.name}, {self.city.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name, queryset=Locality.objects.filter(city_id=self.city_id))
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("locations:locality", args=[self.city.slug, self.slug])
