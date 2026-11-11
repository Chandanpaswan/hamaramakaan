from datetime import timedelta
from decimal import Decimal

from django import forms
from django.db.models import Q
from django.utils import timezone

from apps.core.forms import BootstrapFormMixin, HoneypotMixin, MultipleImageField
from apps.locations.models import City, Locality

from .models import Amenity, Category, Property, PropertyType

SORT_CHOICES = [
    ("latest", "Latest first"),
    ("price_asc", "Price: low to high"),
    ("price_desc", "Price: high to low"),
    ("area_asc", "Area: low to high"),
    ("featured", "Featured first"),
]
SORT_ORDERING = {
    "latest": ["-published_at", "-id"],
    "price_asc": ["price", "-published_at"],
    "price_desc": ["-price", "-published_at"],
    "area_asc": ["area", "-published_at"],
    "featured": ["-is_featured", "-published_at"],
}
BHK_CHOICES = [("1", "1 BHK"), ("2", "2 BHK"), ("3", "3 BHK"), ("4", "4 BHK"), ("5", "5+ BHK")]

# Budget presets used by the home-page search ("min-max" in rupees; empty side = open-ended).
SALE_BUDGETS = [
    ("", "Any budget"),
    ("-3000000", "Under ₹ 30 Lakh"),
    ("3000000-5000000", "₹ 30 – 50 Lakh"),
    ("5000000-10000000", "₹ 50 Lakh – 1 Cr"),
    ("10000000-20000000", "₹ 1 – 2 Cr"),
    ("20000000-", "Above ₹ 2 Cr"),
]
RENT_BUDGETS = [
    ("", "Any budget"),
    ("-10000", "Under ₹ 10,000"),
    ("10000-20000", "₹ 10,000 – 20,000"),
    ("20000-40000", "₹ 20,000 – 40,000"),
    ("40000-75000", "₹ 40,000 – 75,000"),
    ("75000-", "Above ₹ 75,000"),
]
MAX_PRICE = Decimal("999999999999")


class LocalityChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.name}, {obj.city.name}"


class PropertySearchForm(BootstrapFormMixin, forms.Form):
    q = forms.CharField(label="Keyword", max_length=100, required=False,
                        widget=forms.TextInput(attrs={"placeholder": "Locality, project or keyword"}))
    purpose = forms.ChoiceField(label="Buy or rent", required=False,
                                choices=[("", "Buy or rent")] + list(Property.Purpose.choices))
    category = forms.ChoiceField(label="Residential / commercial", required=False,
                                 choices=[("", "Residential & commercial")] + list(Category.choices))
    city = forms.ModelChoiceField(label="City", required=False, to_field_name="slug", empty_label="All cities",
                                  queryset=City.objects.none())
    locality = LocalityChoiceField(label="Locality / sector", required=False, empty_label="All localities",
                                   queryset=Locality.objects.none())
    type = forms.ModelChoiceField(label="Property type", required=False, to_field_name="slug",
                                  empty_label="All property types", queryset=PropertyType.objects.none())
    budget = forms.CharField(required=False, max_length=30, widget=forms.HiddenInput)
    min_price = forms.DecimalField(label="Min budget (₹)", required=False, min_value=0, max_value=MAX_PRICE,
                                   decimal_places=0, widget=forms.NumberInput(attrs={"placeholder": "Min", "step": "1000"}))
    max_price = forms.DecimalField(label="Max budget (₹)", required=False, min_value=0, max_value=MAX_PRICE,
                                   decimal_places=0, widget=forms.NumberInput(attrs={"placeholder": "Max", "step": "1000"}))
    bhk = forms.MultipleChoiceField(label="Bedrooms", required=False, choices=BHK_CHOICES,
                                    widget=forms.CheckboxSelectMultiple)
    baths = forms.TypedChoiceField(label="Bathrooms", required=False, coerce=int, empty_value=None,
                                   choices=[("", "Any"), ("1", "1+"), ("2", "2+"), ("3", "3+"), ("4", "4+")])
    min_area = forms.DecimalField(label="Min area", required=False, min_value=0, max_digits=10, decimal_places=2)
    max_area = forms.DecimalField(label="Max area", required=False, min_value=0, max_digits=10, decimal_places=2)
    area_unit = forms.ChoiceField(label="Area unit", required=False, choices=Property.AreaUnit.choices)
    furnishing = forms.ChoiceField(label="Furnishing", required=False,
                                   choices=[("", "Any")] + list(Property.Furnishing.choices))
    construction = forms.ChoiceField(label="Availability", required=False,
                                     choices=[("", "Any")] + list(Property.Construction.choices))
    condition = forms.ChoiceField(label="Condition", required=False,
                                  choices=[("", "Any")] + list(Property.Condition.choices))
    possession_by = forms.DateField(label="Possession by", required=False,
                                    widget=forms.DateInput(attrs={"type": "date"}))
    parking = forms.BooleanField(label="With parking", required=False)
    amenities = forms.ModelMultipleChoiceField(label="Amenities", required=False, to_field_name="slug",
                                               queryset=Amenity.objects.none(), widget=forms.CheckboxSelectMultiple)
    posted = forms.ChoiceField(label="Posted", required=False,
                               choices=[("", "Any time"), ("1", "Last 24 hours"), ("7", "Last 7 days"), ("30", "Last 30 days")])
    verified = forms.BooleanField(label="Verified listings only", required=False)
    sort = forms.ChoiceField(label="Sort by", required=False, choices=SORT_CHOICES)

    # Fields that count as "filters" (used for the active-filter badge and noindex decisions).
    FILTER_FIELDS = ("q", "purpose", "category", "city", "locality", "type", "min_price", "max_price", "bhk", "baths",
                     "min_area", "max_area", "furnishing", "construction", "condition", "possession_by", "parking",
                     "amenities", "posted", "verified")

    def __init__(self, *args, city=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["city"].queryset = City.objects.filter(is_active=True)
        self.fields["city"].widget.attrs.update({"data-city-select": "id_locality", "data-city-key": "slug"})
        localities = Locality.objects.filter(is_active=True, city__is_active=True).select_related("city")
        self.fields["locality"].queryset = localities.filter(city=city) if city else localities
        self.fields["type"].queryset = PropertyType.objects.filter(is_active=True)
        self.fields["amenities"].queryset = Amenity.objects.all()

    @staticmethod
    def parse_budget(value):
        if not value or "-" not in value:
            return None, None
        low, _, high = value.partition("-")
        try:
            low = Decimal(low) if low else None
            high = Decimal(high) if high else None
        except Exception:  # noqa: BLE001
            return None, None
        if (low is not None and low < 0) or (high is not None and high < 0):
            return None, None
        return low, high

    def clean(self):
        data = super().clean()
        if data.get("budget") and data.get("min_price") is None and data.get("max_price") is None:
            data["min_price"], data["max_price"] = self.parse_budget(data["budget"])
        lo, hi = data.get("min_price"), data.get("max_price")
        if lo is not None and hi is not None and lo > hi:
            self.add_error("max_price", "Maximum budget must be more than the minimum.")
        lo, hi = data.get("min_area"), data.get("max_area")
        if lo is not None and hi is not None and lo > hi:
            self.add_error("max_area", "Maximum area must be more than the minimum.")
        return data

    def active_filter_count(self):
        if not hasattr(self, "cleaned_data"):
            return 0
        return sum(1 for f in self.FILTER_FIELDS if self.cleaned_data.get(f) not in (None, "", [], False)
                   and not (f == "amenities" and not self.cleaned_data[f].exists()))

    def filter_queryset(self, qs):
        """Apply every valid filter. Invalid fields are skipped rather than failing the whole search."""
        if not self.is_bound:
            return qs.order_by(*SORT_ORDERING["latest"])
        self.is_valid()
        d = self.cleaned_data
        if d.get("q"):
            q = d["q"]
            qs = qs.filter(Q(title__icontains=q) | Q(locality__name__icontains=q) | Q(city__name__icontains=q)
                           | Q(project_name__icontains=q) | Q(listing_id__iexact=q) | Q(description__icontains=q))
        if d.get("purpose"):
            qs = qs.filter(purpose=d["purpose"])
        if d.get("category"):
            qs = qs.filter(category=d["category"])
        if d.get("city"):
            qs = qs.filter(city=d["city"])
        if d.get("locality"):
            qs = qs.filter(locality=d["locality"])
        if d.get("type"):
            qs = qs.filter(property_type=d["type"])
        if d.get("min_price") is not None and "max_price" not in self.errors:
            qs = qs.filter(price__gte=d["min_price"])
        if d.get("max_price") is not None and "max_price" not in self.errors:
            qs = qs.filter(price__lte=d["max_price"])
        if d.get("bhk"):
            cond = Q()
            for value in d["bhk"]:
                cond |= Q(bedrooms__gte=5) if value == "5" else Q(bedrooms=int(value))
            qs = qs.filter(cond)
        if d.get("baths"):
            qs = qs.filter(bathrooms__gte=d["baths"])
        unit = d.get("area_unit") or Property.AreaUnit.SQFT
        if d.get("min_area") is not None and "max_area" not in self.errors:
            qs = qs.filter(area_unit=unit, area__gte=d["min_area"])
        if d.get("max_area") is not None and "max_area" not in self.errors:
            qs = qs.filter(area_unit=unit, area__lte=d["max_area"])
        if d.get("furnishing"):
            qs = qs.filter(furnishing=d["furnishing"])
        if d.get("construction"):
            qs = qs.filter(construction_status=d["construction"])
        if d.get("condition"):
            qs = qs.filter(condition=d["condition"])
        if d.get("possession_by"):
            qs = qs.filter(Q(possession_date__lte=d["possession_by"]) | Q(construction_status=Property.Construction.READY))
        if d.get("parking"):
            qs = qs.filter(parking__gte=1)
        amenities = d.get("amenities")
        if amenities is not None and amenities.exists():
            for amenity in amenities:
                qs = qs.filter(amenities=amenity)
        if d.get("posted"):
            qs = qs.filter(published_at__gte=timezone.now() - timedelta(days=int(d["posted"])))
        if d.get("verified"):
            qs = qs.filter(is_verified=True)
        return qs.distinct().order_by(*SORT_ORDERING.get(d.get("sort") or "latest"))


class PostPropertyForm(BootstrapFormMixin, HoneypotMixin, forms.ModelForm):
    """Public owner submission. Saved as 'Pending review'; never published automatically."""

    owner_name = forms.CharField(label="Your name", max_length=120)
    owner_phone = forms.CharField(label="Mobile number", max_length=20,
                                  widget=forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel"}))
    owner_email = forms.EmailField(label="Email", required=False,
                                   widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    photos = MultipleImageField(label="Property photos", required=False,
                                help_text="Up to 10 photos · JPG, PNG or WebP · max 5 MB each.")
    authorised = forms.BooleanField(
        label="I am the owner of this property or authorised by the owner to list it.", required=True)
    consent = forms.BooleanField(
        label="I agree to be contacted by Hamara Makaan Properties about this listing and to the processing of "
              "these details as described in the Privacy Policy.", required=True)

    class Meta:
        model = Property
        fields = [
            "purpose", "property_type", "city", "locality", "project_name", "address",
            "price", "area", "area_unit", "bedrooms", "bathrooms", "furnishing", "construction_status",
            "floor_number", "total_floors", "title", "description",
        ]
        labels = {
            "purpose": "I want to",
            "price": "Expected price / monthly rent (₹)",
            "address": "Full address (kept private)",
            "title": "Listing headline",
            "construction_status": "Availability",
            "project_name": "Society / project name",
        }
        widgets = {
            "address": forms.Textarea(attrs={"rows": 2}),
            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "Layout, condition, nearby schools, transport…"}),
            "title": forms.TextInput(attrs={"placeholder": "e.g. 3 BHK apartment in Sector 85"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["purpose"].choices = [("sale", "Sell"), ("rent", "Rent out"), ("lease", "Lease")]
        self.fields["property_type"].queryset = PropertyType.objects.filter(is_active=True)
        self.fields["city"].queryset = City.objects.filter(is_active=True)
        self.fields["city"].widget.attrs.update({"data-city-select": "id_locality", "data-city-key": "id"})
        self.fields["locality"].queryset = Locality.objects.filter(is_active=True).select_related("city")
        self.fields["locality"].label_from_instance = lambda obj: f"{obj.name}, {obj.city.name}"
        self.fields["locality"].required = False
        self.fields["price"].required = True
        self.fields["address"].required = True
        self.fields["description"].required = False

    def clean(self):
        data = super().clean()
        city, locality = data.get("city"), data.get("locality")
        if city and locality and locality.city_id != city.id:
            self.add_error("locality", "This locality is not in the selected city.")
        floor, total = data.get("floor_number"), data.get("total_floors")
        if floor is not None and total is not None and floor > total:
            self.add_error("floor_number", "Floor cannot be higher than total floors.")
        ptype = data.get("property_type")
        if ptype:
            data["category"] = ptype.category
        return data

    def save(self, commit=True):
        prop = super().save(commit=False)
        prop.owner_name = self.cleaned_data["owner_name"]
        prop.owner_phone = self.cleaned_data["owner_phone"]
        prop.owner_email = self.cleaned_data.get("owner_email", "")
        prop.owner_is_authorised = True
        prop.category = prop.property_type.category
        prop.status = Property.Status.PENDING
        prop.source = Property.Source.OWNER
        prop.is_featured = False
        prop.is_verified = False
        if commit:
            prop.save()
        return prop

    def clean_owner_phone(self):
        from apps.core.models import phone_validator

        value = self.cleaned_data["owner_phone"].strip()
        phone_validator(value)
        return value
