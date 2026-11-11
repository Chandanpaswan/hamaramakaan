from django import forms

from apps.core.forms import BootstrapFormMixin, HoneypotMixin, TelInput
from apps.core.models import phone_validator

from .models import Lead

CONSENT_LABEL = "I agree to be contacted by Hamara Makaan Properties about my enquiry."


class BaseLeadForm(BootstrapFormMixin, HoneypotMixin, forms.ModelForm):
    consent = forms.BooleanField(label=CONSENT_LABEL, required=True)

    class Meta:
        model = Lead
        fields = ["name", "phone", "email"]
        widgets = {
            "name": forms.TextInput(attrs={"autocomplete": "name"}),
            "phone": TelInput(),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }
        labels = {"name": "Your name", "phone": "Mobile number", "email": "Email (optional)"}

    def clean_phone(self):
        value = self.cleaned_data["phone"].strip()
        phone_validator(value)
        return value


class EnquiryForm(BaseLeadForm):
    """Property / project detail enquiry."""

    class Meta(BaseLeadForm.Meta):
        fields = ["name", "phone", "email", "message", "preferred_contact_method"]
        widgets = {**BaseLeadForm.Meta.widgets, "message": forms.Textarea(attrs={"rows": 3})}
        labels = {**BaseLeadForm.Meta.labels, "message": "Your requirement", "preferred_contact_method": "Contact me by"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["message"].required = False


class ContactForm(BaseLeadForm):
    class Meta(BaseLeadForm.Meta):
        fields = ["name", "phone", "email", "requirement", "preferred_location", "message", "preferred_contact_method"]
        widgets = {**BaseLeadForm.Meta.widgets, "message": forms.Textarea(attrs={"rows": 4})}
        labels = {
            **BaseLeadForm.Meta.labels,
            "requirement": "I am looking to",
            "preferred_location": "Preferred location",
            "message": "Message",
            "preferred_contact_method": "Contact me by",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["requirement"].choices = [
            (k, v) for k, v in Lead.Requirement.choices if k not in ("site_visit", "callback")
        ]
        self.fields["message"].required = False


class CallbackForm(BaseLeadForm):
    class Meta(BaseLeadForm.Meta):
        fields = ["name", "phone"]
