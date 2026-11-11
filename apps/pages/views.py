from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.core.utils import is_rate_limited
from apps.leads.forms import ContactForm
from apps.leads.models import Lead
from apps.leads.services import create_lead_from_form

from .models import FAQ, Highlight, Page, Service


def _get_page(request, slug):
    page = Page.objects.filter(slug=slug).first()
    if page is None:
        raise Http404
    if not page.is_published and not (request.user.is_authenticated and request.user.has_perm("pages.view_page")):
        raise Http404
    return page


def page_detail(request, slug):
    page = _get_page(request, slug)
    return render(request, "pages/page.html", {"page": page, "noindex": not page.is_published})


def about(request):
    page = _get_page(request, "about-us")
    return render(request, "pages/about.html", {
        "page": page,
        "highlights": Highlight.objects.filter(is_published=True),
        "services": Service.objects.filter(is_published=True)[:6],
    })


def services(request):
    page = Page.objects.filter(slug="services", is_published=True).first()
    return render(request, "pages/services.html", {"page": page, "services": Service.objects.filter(is_published=True)})


def faq(request):
    faqs = FAQ.objects.filter(is_published=True)
    q = request.GET.get("q", "").strip()[:100]
    if q:
        faqs = faqs.filter(question__icontains=q) | faqs.filter(answer__icontains=q, is_published=True)
    grouped = {}
    for item in faqs:
        grouped.setdefault(item.get_category_display(), []).append(item)
    return render(request, "pages/faq.html", {"grouped": grouped, "q": q, "noindex": bool(q)})


@require_http_methods(["GET", "POST"])
def contact(request):
    form = ContactForm(request.POST or None, initial={"requirement": request.GET.get("requirement", "buy")})
    if request.method == "POST":
        if is_rate_limited(request, "contact"):
            messages.error(request, "Too many messages from your connection. Please try again in a few minutes.")
        elif form.is_valid():
            create_lead_from_form(request, form, Lead.Source.CONTACT)
            messages.success(request, "Thank you for getting in touch. Our team will contact you soon.")
            return redirect("pages:contact")
        else:
            messages.error(request, "Please correct the highlighted fields.")
    return render(request, "pages/contact.html", {"form": form})


def legal(request, slug):
    page = get_object_or_404(Page, slug=slug, is_published=True)
    return render(request, "pages/page.html", {"page": page})
