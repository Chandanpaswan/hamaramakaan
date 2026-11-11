from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.core.models import SEOFieldsMixin, TimeStampedModel, phone_validator
from apps.core.utils import safe_upload_path, unique_slugify


class Category(models.TextChoices):
    RESIDENTIAL = "residential", "Residential"
    COMMERCIAL = "commercial", "Commercial"


class Illustration(models.TextChoices):
    """Brand placeholder artwork used when a listing has no photo yet."""

    TOWER = "tower", "Apartment / tower"
    HOUSE = "house", "House / villa"
    PLOT = "plot", "Plot / land"
    SHOP = "shop", "Shop / showroom"
    OFFICE = "office", "Office"
    WAREHOUSE = "warehouse", "Warehouse"


class PropertyType(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.RESIDENTIAL)
    illustration = models.CharField(max_length=20, choices=Illustration.choices, default=Illustration.TOWER)
    icon = models.CharField(
        max_length=40, default="apartment", help_text="Brand icon name, e.g. apartment, villa, plot, office-space"
    )
    has_bedrooms = models.BooleanField(default=True, help_text="Show BHK / bathroom fields for this type.")
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
        super().save(*args, **kwargs)


class Amenity(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True, blank=True)
    icon = models.CharField(max_length=40, default="badge-check")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "amenities"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
        super().save(*args, **kwargs)


class PropertyQuerySet(models.QuerySet):
    def public(self):
        return self.filter(status=Property.Status.PUBLISHED)

    def with_related(self):
        return self.select_related("property_type", "city", "locality", "city__state").prefetch_related("images")


class Property(SEOFieldsMixin, TimeStampedModel):
    class Purpose(models.TextChoices):
        SALE = "sale", "Sale"
        RENT = "rent", "Rent"
        LEASE = "lease", "Lease"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending review"
        CORRECTION = "correction", "Returned for correction"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"
        SOLD = "sold", "Sold"
        RENTED = "rented", "Rented out"
        ARCHIVED = "archived", "Archived"

    class Source(models.TextChoices):
        STAFF = "staff", "Added by staff"
        OWNER = "owner", "Owner submission"

    class AreaUnit(models.TextChoices):
        SQFT = "sqft", "sq ft"
        SQYD = "sqyd", "sq yd"
        SQM = "sqm", "sq m"
        ACRE = "acre", "acre"

    class Furnishing(models.TextChoices):
        UNFURNISHED = "unfurnished", "Unfurnished"
        SEMI = "semi", "Semi-furnished"
        FURNISHED = "furnished", "Fully furnished"

    class Construction(models.TextChoices):
        READY = "ready", "Ready to move"
        UNDER_CONSTRUCTION = "under_construction", "Under construction"

    class Condition(models.TextChoices):
        NEW = "new", "New"
        RESALE = "resale", "Resale"

    class Facing(models.TextChoices):
        NORTH = "north", "North"
        SOUTH = "south", "South"
        EAST = "east", "East"
        WEST = "west", "West"
        NORTH_EAST = "north_east", "North-East"
        NORTH_WEST = "north_west", "North-West"
        SOUTH_EAST = "south_east", "South-East"
        SOUTH_WEST = "south_west", "South-West"

    listing_id = models.CharField(max_length=12, unique=True, editable=False, blank=True)
    title = models.CharField(max_length=140)
    slug = models.SlugField(max_length=160, unique=True, blank=True)
    purpose = models.CharField(max_length=10, choices=Purpose.choices, default=Purpose.SALE)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.RESIDENTIAL)
    property_type = models.ForeignKey(PropertyType, on_delete=models.PROTECT, related_name="properties")
    description = models.TextField(blank=True)

    price = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))],
        help_text="Sale price, or monthly rent for rentals. Leave blank to show 'Contact for price'.",
    )
    price_note = models.CharField(max_length=120, blank=True, help_text="e.g. Negotiable, plus registration")
    security_deposit = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))]
    )
    maintenance_charges = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))],
        help_text="Monthly maintenance, if applicable.",
    )

    area = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    area_unit = models.CharField(max_length=6, choices=AreaUnit.choices, default=AreaUnit.SQFT)
    carpet_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    bedrooms = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(20)])
    bathrooms = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(20)])
    balconies = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(20)])
    floor_number = models.SmallIntegerField(null=True, blank=True, help_text="0 = ground floor")
    total_floors = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(200)])
    furnishing = models.CharField(max_length=12, choices=Furnishing.choices, blank=True)
    construction_status = models.CharField(max_length=20, choices=Construction.choices, blank=True)
    condition = models.CharField(max_length=10, choices=Condition.choices, blank=True)
    possession_date = models.DateField(null=True, blank=True)
    available_from = models.DateField(null=True, blank=True, help_text="For rentals.")
    facing = models.CharField(max_length=12, choices=Facing.choices, blank=True)
    parking = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(50)])
    amenities = models.ManyToManyField(Amenity, blank=True, related_name="properties")

    city = models.ForeignKey("locations.City", on_delete=models.PROTECT, related_name="properties")
    locality = models.ForeignKey(
        "locations.Locality", on_delete=models.SET_NULL, null=True, blank=True, related_name="properties"
    )
    address = models.TextField(blank=True, help_text="Private by default; never shown publicly unless allowed below.")
    show_address = models.BooleanField(default=False, help_text="Show the full address publicly.")
    project_name = models.CharField(max_length=120, blank=True, help_text="Society / project name, if any.")
    nearby_landmarks = models.TextField(blank=True, help_text="Verified landmarks only, one per line.")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    show_map = models.BooleanField(default=False, help_text="Show an approximate map pin publicly.")

    rera_number = models.CharField("RERA registration no.", max_length=80, blank=True)
    is_verified = models.BooleanField(
        default=False, help_text="Tick only after the documented verification process is complete."
    )
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", editable=False
    )

    # Owner details are private and only visible to authorised staff.
    owner_name = models.CharField(max_length=120, blank=True)
    owner_phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    owner_email = models.EmailField(blank=True)
    owner_is_authorised = models.BooleanField(default=False, editable=False)

    source = models.CharField(max_length=10, choices=Source.choices, default=Source.STAFF)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_properties"
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_properties"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    review_note = models.TextField(blank=True, help_text="Internal: reason for rejection or requested corrections.")
    is_featured = models.BooleanField(default=False)
    is_sample = models.BooleanField(default=False, editable=False, help_text="Development sample data.")
    published_at = models.DateTimeField(null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0, editable=False)

    objects = PropertyQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-created_at"]
        verbose_name_plural = "properties"
        permissions = [
            ("approve_property", "Can approve or reject submitted properties"),
            ("feature_property", "Can mark properties as featured"),
            ("verify_property", "Can mark properties as verified"),
        ]
        indexes = [
            models.Index(fields=["status", "purpose"]),
            models.Index(fields=["status", "category"]),
            models.Index(fields=["city", "status"]),
            models.Index(fields=["locality", "status"]),
            models.Index(fields=["price"]),
            models.Index(fields=["published_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(price__isnull=True) | Q(price__gte=0), name="property_price_non_negative"),
            models.CheckConstraint(condition=Q(area__gt=0), name="property_area_positive"),
            models.CheckConstraint(
                condition=Q(total_floors__isnull=True) | Q(floor_number__isnull=True) | Q(floor_number__lte=models.F("total_floors")),
                name="property_floor_within_total",
            ),
        ]

    def __str__(self):
        return f"{self.listing_id or 'New'} · {self.title}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.title, max_length=150)
        if self.status == self.Status.PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        if self.property_type_id and not self.category:
            self.category = self.property_type.category
        super().save(*args, **kwargs)
        if not self.listing_id:
            self.listing_id = f"HM{self.pk:06d}"
            Property.objects.filter(pk=self.pk).update(listing_id=self.listing_id)

    def get_absolute_url(self):
        return reverse("properties:detail", args=[self.slug])

    @property
    def is_public(self):
        return self.status == self.Status.PUBLISHED

    @property
    def is_rental(self):
        return self.purpose in (self.Purpose.RENT, self.Purpose.LEASE)

    @property
    def primary_image(self):
        images = list(self.images.all())  # uses prefetch cache when available
        for img in images:
            if img.is_primary:
                return img
        return images[0] if images else None

    @property
    def price_per_unit(self):
        if self.price and self.area and not self.is_rental:
            return (self.price / self.area).quantize(Decimal("1"))
        return None

    @property
    def bhk_label(self):
        return f"{self.bedrooms} BHK" if self.bedrooms else ""

    @property
    def location_label(self):
        parts = [self.locality.name if self.locality else "", self.city.name]
        return ", ".join(p for p in parts if p)

    @property
    def floor_label(self):
        if self.floor_number is None:
            return ""
        floor = "Ground" if self.floor_number == 0 else str(self.floor_number)
        return f"{floor} of {self.total_floors}" if self.total_floors else floor

    @property
    def landmarks_list(self):
        return [line.strip() for line in self.nearby_landmarks.splitlines() if line.strip()]

    @property
    def key_facts(self):
        """Up to three short facts for listing cards."""
        facts = []
        if self.bedrooms:
            facts.append(("bed-double", f"{self.bedrooms} Beds"))
        if self.bathrooms:
            facts.append(("bath", f"{self.bathrooms} Baths"))
        from apps.core.templatetags.hm import num

        facts.append(("ruler", f"{num(self.area)} {self.get_area_unit_display()}"))
        if len(facts) < 3 and self.furnishing:
            facts.append(("sofa", self.get_furnishing_display()))
        if len(facts) < 3 and self.parking:
            facts.append(("car", f"{self.parking} Parking"))
        if len(facts) < 3 and self.floor_number is not None:
            if self.floor_number == 0:
                facts.append(("layers", "Ground floor"))
            else:
                total = f"/{self.total_floors}" if self.total_floors else ""
                facts.append(("layers", f"Floor {self.floor_number}{total}"))
        return facts[:3]


class PropertyImage(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=safe_upload_path("properties"), width_field="width", height_field="height")
    width = models.PositiveIntegerField(null=True, editable=False)
    height = models.PositiveIntegerField(null=True, editable=False)
    alt_text = models.CharField(max_length=160, blank=True)
    caption = models.CharField(max_length=160, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "sort_order", "id"]

    def __str__(self):
        return f"Image {self.pk} for {self.property_id}"

    def alt(self):  # plain method: the `property` field shadows the builtin decorator here
        return self.alt_text or f"{self.property.title} – photo"

    def delete(self, *args, **kwargs):
        storage, name = self.image.storage, self.image.name
        super().delete(*args, **kwargs)
        if name:
            storage.delete(name)


class ProjectQuerySet(models.QuerySet):
    def public(self):
        return self.filter(is_published=True)


class Project(SEOFieldsMixin, TimeStampedModel):
    class Status(models.TextChoices):
        UPCOMING = "upcoming", "Upcoming"
        NEW_LAUNCH = "new_launch", "New launch"
        UNDER_CONSTRUCTION = "under_construction", "Under construction"
        READY = "ready", "Ready to move"

    name = models.CharField(max_length=140)
    slug = models.SlugField(max_length=160, unique=True, blank=True)
    builder_name = models.CharField(max_length=120, blank=True)
    city = models.ForeignKey("locations.City", on_delete=models.PROTECT, related_name="projects")
    locality = models.ForeignKey("locations.Locality", on_delete=models.SET_NULL, null=True, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.RESIDENTIAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNDER_CONSTRUCTION)
    configurations = models.CharField(max_length=120, blank=True, help_text="e.g. 2 & 3 BHK apartments")
    price_from = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    price_to = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    possession_date = models.DateField(null=True, blank=True)
    rera_number = models.CharField("RERA registration no.", max_length=80, blank=True)
    description = models.TextField(blank=True)
    amenities = models.ManyToManyField(Amenity, blank=True)
    cover_image = models.ImageField(upload_to=safe_upload_path("projects"), blank=True)
    cover_image_alt = models.CharField(max_length=160, blank=True)
    is_artist_impression = models.BooleanField(default=False, help_text="Label the cover as an artist's impression.")
    is_published = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    is_sample = models.BooleanField(default=False, editable=False)

    objects = ProjectQuerySet.as_manager()

    class Meta:
        ordering = ["-is_featured", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(price_from__isnull=True) | Q(price_to__isnull=True) | Q(price_to__gte=models.F("price_from")),
                name="project_price_range_valid",
            )
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name, max_length=150)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("properties:project_detail", args=[self.slug])

    @property
    def location_label(self):
        return ", ".join(p for p in [self.locality.name if self.locality else "", self.city.name] if p)
