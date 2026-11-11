from django import forms
from django.conf import settings

from .utils import validate_image_file


class BootstrapFormMixin:
    """Adds Bootstrap 5 classes to every widget so templates stay simple."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput,)):
                css = "form-check-input"
            elif isinstance(widget, (forms.CheckboxSelectMultiple, forms.RadioSelect)):
                css = ""
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                css = "form-select"
            else:
                css = "form-control"
            if css:
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()
            if field.required and not isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("required", "required")

    def full_clean(self):
        # Mark invalid widgets after validation. (Never validate in __init__: subclasses still
        # adjust querysets after calling super().__init__.)
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                attrs = self.fields[name].widget.attrs
                attrs["class"] = f"{attrs.get('class', '')} is-invalid".strip()
                attrs["aria-invalid"] = "true"


class HoneypotMixin(forms.Form):
    """Hidden field that humans never fill in. Bots that do are rejected silently."""

    website = forms.CharField(
        required=False,
        label="Leave this field empty",
        widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}),
    )

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise forms.ValidationError("Spam detected.")
        return ""


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.FileField):
    """Accepts several images in one input; each file is validated individually."""

    def __init__(self, *args, max_files=None, **kwargs):
        self.max_files = max_files or settings.MAX_IMAGES_PER_SUBMISSION
        kwargs.setdefault("widget", MultipleImageInput(attrs={"accept": "image/jpeg,image/png,image/webp"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        files = [f for f in files if f]
        if self.required and not files:
            raise forms.ValidationError("Please add at least one photo.")
        if len(files) > self.max_files:
            raise forms.ValidationError(f"You can upload up to {self.max_files} photos.")
        errors = []
        for f in files:
            super().clean(f, initial)
            try:
                validate_image_file(f)
            except forms.ValidationError as exc:
                errors.append(f"{f.name}: {exc.messages[0]}")
        if errors:
            raise forms.ValidationError(errors)
        return files
