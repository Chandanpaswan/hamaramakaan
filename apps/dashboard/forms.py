from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.contrib.auth.models import Group
from django.contrib.redirects.models import Redirect
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

from apps.core.forms import BootstrapFormMixin, MultipleImageField
from apps.core.models import SiteSetting
from apps.core.utils import validate_image_file
from apps.leads.models import Lead, LeadNote
from apps.locations.models import Locality
from apps.properties.models import Property

User = get_user_model()


class DashboardModelForm(BootstrapFormMixin, forms.ModelForm):
    """Base for every dashboard form: native date pickers and strict image validation."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, forms.DateTimeField):
                field.widget = forms.DateTimeInput(
                    attrs={"type": "datetime-local", "class": "form-control"}, format="%Y-%m-%dT%H:%M"
                )
            elif isinstance(field, forms.DateField):
                field.widget = forms.DateInput(attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d")
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("rows", 4)
            if isinstance(field, forms.ModelMultipleChoiceField):
                field.widget.attrs.setdefault("size", 6)

    def clean(self):
        data = super().clean()
        for name, field in self.fields.items():
            value = data.get(name)
            if isinstance(field, forms.ImageField) and isinstance(value, UploadedFile):
                try:
                    validate_image_file(value)
                except ValidationError as exc:
                    self.add_error(name, exc)
        return data


class DashboardLoginForm(BootstrapFormMixin, AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise ValidationError("This account does not have dashboard access.", code="no_access")


class PropertyAdminForm(DashboardModelForm):
    class Meta:
        model = Property
        exclude = ["listing_id", "slug", "verified_at", "verified_by", "owner_is_authorised", "created_by",
                   "is_sample", "view_count", "category"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "address": forms.Textarea(attrs={"rows": 2}),
            "nearby_landmarks": forms.Textarea(attrs={"rows": 3}),
            "review_note": forms.Textarea(attrs={"rows": 2}),
            "amenities": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["locality"].queryset = Locality.objects.select_related("city").filter(is_active=True)
        self.fields["city"].widget.attrs.update({"data-city-select": "id_locality", "data-city-key": "id"})
        self.fields["assigned_to"].queryset = User.objects.filter(is_active=True, is_staff=True)
        self.fields["published_at"].required = False
        if user is not None:
            if not user.has_perm("properties.approve_property"):
                allowed = [Property.Status.DRAFT, Property.Status.PENDING]
                current = self.instance.status if self.instance.pk else None
                if current and current not in allowed:
                    allowed.append(current)
                self.fields["status"].choices = [c for c in Property.Status.choices if c[0] in allowed]
            if not user.has_perm("properties.feature_property"):
                self.fields["is_featured"].disabled = True
            if not user.has_perm("properties.verify_property"):
                self.fields["is_verified"].disabled = True
                self.fields["is_verified"].help_text = "Only staff with verification permission can change this."

    def clean(self):
        data = super().clean()
        city, locality = data.get("city"), data.get("locality")
        if city and locality and locality.city_id != city.id:
            self.add_error("locality", "This locality belongs to a different city.")
        floor, total = data.get("floor_number"), data.get("total_floors")
        if floor is not None and total is not None and floor > total:
            self.add_error("floor_number", "Floor cannot be higher than total floors.")
        if data.get("show_map") and (data.get("latitude") is None or data.get("longitude") is None):
            self.add_error("show_map", "Add latitude and longitude before showing the map.")
        return data

    def save(self, commit=True):
        prop = super().save(commit=False)
        prop.category = prop.property_type.category
        if commit:
            prop.save()
            self.save_m2m()
        return prop


class PropertyImageUploadForm(BootstrapFormMixin, forms.Form):
    photos = MultipleImageField(label="Add photos", required=True)


class PropertyReviewForm(BootstrapFormMixin, forms.Form):
    ACTIONS = [("approve", "Approve & publish"), ("correction", "Return for correction"), ("reject", "Reject")]
    action = forms.ChoiceField(choices=ACTIONS, widget=forms.RadioSelect)
    note = forms.CharField(label="Note (internal; shared with the owner when returning or rejecting)",
                           required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        data = super().clean()
        if data.get("action") in ("correction", "reject") and not data.get("note"):
            self.add_error("note", "Please add a reason.")
        return data


class LeadUpdateForm(DashboardModelForm):
    class Meta:
        model = Lead
        fields = ["status", "priority", "next_follow_up", "requirement", "budget_min", "budget_max", "preferred_location"]

    def clean(self):
        data = super().clean()
        lo, hi = data.get("budget_min"), data.get("budget_max")
        if lo is not None and hi is not None and hi < lo:
            self.add_error("budget_max", "Maximum must be more than the minimum.")
        return data


class LeadCreateForm(LeadUpdateForm):
    class Meta:
        model = Lead
        fields = ["name", "phone", "email", "requirement", "source", "message", "interested_property",
                  "budget_min", "budget_max", "preferred_location", "preferred_contact_method", "priority",
                  "next_follow_up", "assigned_to", "consent"]
        labels = {"consent": "Customer agreed to be contacted"}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["interested_property"].queryset = Property.objects.order_by("-created_at")
        self.fields["assigned_to"].queryset = User.objects.filter(is_active=True, is_staff=True)
        if user is not None and not user.has_perm("leads.assign_lead"):
            del self.fields["assigned_to"]


class LeadNoteForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = LeadNote
        fields = ["note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 3, "placeholder": "Call summary, next steps…"})}
        labels = {"note": "Add a follow-up note"}


class LeadAssignForm(BootstrapFormMixin, forms.Form):
    assigned_to = forms.ModelChoiceField(queryset=User.objects.none(), required=False, label="Assign to",
                                         empty_label="Unassigned")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = User.objects.filter(is_active=True, is_staff=True)


class UserForm(DashboardModelForm):
    role = forms.ModelChoiceField(queryset=Group.objects.order_by("name"), required=False,
                                  help_text="Roles control what this person can see and change.")
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput, required=False,
                                help_text="Required for new users. At least 10 characters.")

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "phone", "designation", "is_active"]

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        if self.instance.pk:
            del self.fields["password1"]
            self.fields["role"].initial = self.instance.groups.first()
        else:
            self.fields["password1"].required = True
        if not (actor and actor.is_superuser):
            # Only super admins may hand out the Super Admin role.
            self.fields["role"].queryset = Group.objects.exclude(name="Super Admin").order_by("name")

    def clean_password1(self):
        from django.contrib.auth.password_validation import validate_password

        pw = self.cleaned_data.get("password1")
        if pw:
            validate_password(pw, self.instance)
        return pw

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        if self.cleaned_data.get("password1"):
            user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            role = self.cleaned_data.get("role")
            user.groups.set([role] if role else [])
        return user


class AdminSetPasswordForm(BootstrapFormMixin, SetPasswordForm):
    pass


class SiteSettingForm(DashboardModelForm):
    class Meta:
        model = SiteSetting
        exclude = ["created_at", "updated_at"]
        widgets = {"address": forms.Textarea(attrs={"rows": 2}), "footer_about": forms.Textarea(attrs={"rows": 2})}

    def clean_map_embed_url(self):
        url = self.cleaned_data.get("map_embed_url", "")
        if url and not url.startswith(("https://www.google.com/maps/embed", "https://maps.google.com/")):
            raise ValidationError("Paste the src URL from Google Maps → Share → Embed a map.")
        return url


class RedirectForm(DashboardModelForm):
    class Meta:
        model = Redirect
        fields = ["old_path", "new_path"]
        help_texts = {
            "old_path": "Old URL path, e.g. /old-page/ (must start with /).",
            "new_path": "New path (/new-page/) or full URL. Leave blank to return 410 Gone.",
        }

    def clean_old_path(self):
        from django.contrib.sites.models import Site

        path = self.cleaned_data["old_path"]
        if not path.startswith("/"):
            raise ValidationError("The old path must start with '/'.")
        qs = Redirect.objects.filter(site=Site.objects.get_current(), old_path=path)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A redirect for this path already exists.")
        return path
