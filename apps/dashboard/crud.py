"""
Generic, permission-checked create/list/edit/delete screens for simple content models.
Each entry maps a URL slug to a model, its form and how it is listed.
"""
from dataclasses import dataclass, field

from django import forms
from django.contrib.redirects.models import Redirect
from django.contrib.sites.models import Site
from django.forms import modelform_factory

from apps.blog.models import BlogCategory, BlogPost, BlogTag
from apps.locations.models import City, Locality, State
from apps.pages.models import FAQ, Highlight, Page, Service, Testimonial
from apps.properties.models import Amenity, Project, PropertyType

from .forms import DashboardModelForm, RedirectForm


@dataclass
class Crud:
    slug: str
    model: type
    title: str
    group: str
    fields: list = None
    form_class: type = None
    list_display: list = field(default_factory=lambda: ["__str__"])
    search_fields: list = field(default_factory=list)
    filter_field: str = None
    select_related: list = field(default_factory=list)
    before_save: callable = None
    can_preview: bool = False
    help: str = ""

    @property
    def app_label(self):
        return self.model._meta.app_label

    @property
    def model_name(self):
        return self.model._meta.model_name

    @property
    def singular(self):
        return self.model._meta.verbose_name

    def perm(self, action):
        return f"{self.app_label}.{action}_{self.model_name}"

    def get_form_class(self):
        if self.form_class:
            return self.form_class
        return modelform_factory(self.model, form=DashboardModelForm, fields=self.fields)


def _set_author(request, obj, is_new):
    if is_new and not obj.author_id:
        obj.author = request.user


def _set_site(request, obj, is_new):
    obj.site = Site.objects.get_current()


class BlogPostForm(DashboardModelForm):
    class Meta:
        model = BlogPost
        fields = ["title", "slug", "excerpt", "body", "featured_image", "featured_image_alt", "category", "tags",
                  "status", "published_at", "is_featured", "author_display_name", "related_posts",
                  "seo_title", "seo_description", "canonical_url"]
        widgets = {"body": forms.Textarea(attrs={"rows": 16}), "excerpt": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["slug"].help_text = "Leave blank to generate from the title."
        if self.instance.pk:
            self.fields["related_posts"].queryset = BlogPost.objects.exclude(pk=self.instance.pk)

    def clean(self):
        data = super().clean()
        if data.get("status") == BlogPost.Status.SCHEDULED and not data.get("published_at"):
            self.add_error("published_at", "Choose when the scheduled post should go live.")
        return data


class ProjectForm(DashboardModelForm):
    class Meta:
        model = Project
        exclude = ["slug", "is_sample", "created_at", "updated_at"]
        widgets = {"description": forms.Textarea(attrs={"rows": 6}), "amenities": forms.CheckboxSelectMultiple}

    def clean(self):
        data = super().clean()
        lo, hi = data.get("price_from"), data.get("price_to")
        if lo is not None and hi is not None and hi < lo:
            self.add_error("price_to", "'Price to' must be more than 'price from'.")
        city, locality = data.get("city"), data.get("locality")
        if city and locality and locality.city_id != city.id:
            self.add_error("locality", "This locality belongs to a different city.")
        return data


class TestimonialForm(DashboardModelForm):
    class Meta:
        model = Testimonial
        fields = ["name", "location", "quote", "permission_confirmed", "is_published", "sort_order"]


CRUDS = [
    Crud("projects", Project, "New projects", "Listings", form_class=ProjectForm,
         list_display=["name", "builder_name", "city", "status", "is_published", "is_featured"],
         search_fields=["name", "builder_name", "rera_number"], filter_field="status", select_related=["city"],
         can_preview=True),
    Crud("property-types", PropertyType, "Property types", "Listings",
         fields=["name", "slug", "category", "illustration", "icon", "has_bedrooms", "sort_order", "is_active"],
         list_display=["name", "category", "is_active", "sort_order"], filter_field="category"),
    Crud("amenities", Amenity, "Amenities", "Listings", fields=["name", "slug", "icon", "sort_order"],
         list_display=["name", "icon", "sort_order"], search_fields=["name"]),
    Crud("states", State, "States", "Locations", fields=["name", "slug"], list_display=["name", "slug"]),
    Crud("cities", City, "Cities", "Locations",
         fields=["state", "name", "slug", "description", "is_active", "is_indexable", "show_in_footer", "sort_order",
                 "seo_title", "seo_description"],
         list_display=["name", "state", "is_active", "is_indexable", "show_in_footer"], search_fields=["name"],
         select_related=["state"], can_preview=True),
    Crud("localities", Locality, "Localities", "Locations",
         fields=["city", "name", "slug", "description", "is_active", "is_indexable", "is_popular",
                 "seo_title", "seo_description"],
         list_display=["name", "city", "is_active", "is_popular"], search_fields=["name", "city__name"],
         select_related=["city"], can_preview=True),
    Crud("blog-posts", BlogPost, "Blog posts", "Content", form_class=BlogPostForm,
         list_display=["title", "category", "status", "published_at", "is_featured"], search_fields=["title"],
         filter_field="status", select_related=["category"], before_save=_set_author, can_preview=True),
    Crud("blog-categories", BlogCategory, "Blog categories", "Content", fields=["name", "slug", "description"],
         list_display=["name", "slug"]),
    Crud("blog-tags", BlogTag, "Blog tags", "Content", fields=["name", "slug"], list_display=["name", "slug"]),
    Crud("pages", Page, "Pages", "Content",
         fields=["title", "slug", "intro", "body", "is_published", "show_in_footer", "is_legal", "legal_reviewed",
                 "sort_order", "seo_title", "seo_description"],
         list_display=["title", "slug", "is_published", "show_in_footer", "legal_reviewed"], search_fields=["title"],
         can_preview=True),
    Crud("faqs", FAQ, "FAQs", "Content",
         fields=["question", "answer", "category", "show_on_home", "is_published", "sort_order"],
         list_display=["question", "category", "show_on_home", "is_published"], search_fields=["question"],
         filter_field="category"),
    Crud("services", Service, "Services", "Content",
         fields=["title", "icon", "summary", "body", "is_published", "sort_order"],
         list_display=["title", "is_published", "sort_order"]),
    Crud("highlights", Highlight, "Why choose us", "Content",
         fields=["title", "text", "icon", "is_published", "sort_order"], list_display=["title", "is_published"],
         help="Keep these factual. Do not add statistics or claims that are not verified."),
    Crud("testimonials", Testimonial, "Testimonials", "Content", form_class=TestimonialForm,
         list_display=["name", "location", "permission_confirmed", "is_published"],
         help="Only publish genuine testimonials with the customer's written permission."),
    Crud("redirects", Redirect, "SEO redirects (301)", "System", form_class=RedirectForm,
         list_display=["old_path", "new_path"], search_fields=["old_path", "new_path"], before_save=_set_site),
]

CRUD_BY_SLUG = {c.slug: c for c in CRUDS}
