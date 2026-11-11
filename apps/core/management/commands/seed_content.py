"""
Baseline reference content: property types, amenities, locations, pages, services, FAQs and blog categories.
Idempotent and safe in every environment. It never creates listings, statistics, reviews or contact details.
"""
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.blog.models import BlogCategory
from apps.core.models import SiteSetting
from apps.locations.models import City, Locality, State
from apps.pages.models import FAQ, Highlight, Page, Service
from apps.properties.models import Amenity, PropertyType

PROPERTY_TYPES = [
    # name, slug, category, illustration, icon, has_bedrooms
    ("Apartment", "apartment", "residential", "tower", "apartment", True),
    ("Builder floor", "builder-floor", "residential", "tower", "apartment", True),
    ("Independent house", "independent-house", "residential", "house", "independent-house", True),
    ("Villa", "villa", "residential", "house", "villa", True),
    ("Residential plot", "residential-plot", "residential", "plot", "plot", False),
    ("PG / co-living", "pg-co-living", "residential", "tower", "pg", True),
    ("Office space", "office-space", "commercial", "office", "office-space", False),
    ("Shop / showroom", "shop-showroom", "commercial", "shop", "commercial-shop", False),
    ("Warehouse / godown", "warehouse", "commercial", "warehouse", "warehouse", False),
    ("Commercial land", "commercial-land", "commercial", "plot", "plot", False),
]

AMENITIES = [
    ("Gated security", "shield-check"), ("Power backup", "bell"), ("Lift", "layers"),
    ("Covered parking", "car"), ("Park / garden", "compass"), ("Clubhouse", "user"),
    ("Modular kitchen", "sofa"), ("Near metro", "map"), ("Gym", "star"), ("Swimming pool", "star"),
    ("Water supply 24×7", "badge-check"), ("CCTV", "eye"),
]

LOCATIONS = {
    "Haryana": {
        "Faridabad": ["Greater Faridabad (Neharpar)", "Sector 15", "Sector 21", "Sector 75", "Sector 85", "Sector 88", "NIT"],
        "Ballabhgarh": [],
        "Gurugram": [],
    },
    "Delhi": {"Delhi": []},
    "Uttar Pradesh": {"Noida": []},
}
POPULAR = {"Greater Faridabad (Neharpar)", "Sector 85", "Sector 75"}

PAGES = [
    ("About us", "about-us", False,
     "Hamara Makaan Properties helps families buy, sell and rent property with honest, local guidance.",
     "## Who we are\n"
     "Hamara Makaan means “our home”. We help home-seekers, owners and investors find the right property and "
     "complete their transactions with clear information at every step.\n\n"
     "## Our mission\n"
     "Help every family buy, rent or sell property with trust, transparency and zero hassle.\n\n"
     "## Our values\n"
     "- **Honest by default** – accurate listings and straightforward advice.\n"
     "- **Family first** – we treat every client’s home decision as our own.\n"
     "- **Local expertise** – we know the sectors, societies and builders we work with.\n"
     "- **Simple to the keys** – from the first call to the final paperwork.\n\n"
     "## Where we work\n"
     "Our focus is Faridabad and the wider Delhi NCR. Contact us to discuss your requirement."),
    ("Services", "services", False, "How we can help you buy, sell, rent or lease property.", ""),
    ("Privacy policy", "privacy-policy", True, "How we collect, use and protect your information.",
     "## Information we collect\n"
     "When you submit an enquiry, request a callback or post a property, we collect the details you provide, "
     "such as your name, phone number, email address, requirement and property information.\n\n"
     "## How we use it\n"
     "- To respond to your enquiry and help with your property requirement.\n"
     "- To review, verify and publish properties you submit.\n"
     "- To improve our website and services.\n\n"
     "We do not sell your personal information. Owner contact details and full addresses are not shown publicly "
     "unless you give permission.\n\n"
     "## Retention\nWe keep enquiry records only as long as needed for the purposes above or as required by law.\n\n"
     "## Your choices\nYou can ask us to update or delete your information by contacting us.\n\n"
     "## Contact\nFor privacy questions, please use the contact details on our Contact page."),
    ("Terms and conditions", "terms-and-conditions", True, "Rules for using this website and listing property.",
     "## Use of the website\nBy using this website you agree to these terms. Listings are provided for information "
     "and may change without notice.\n\n"
     "## Listing rules\n"
     "- You must be the owner of a property, or authorised by the owner, to submit it.\n"
     "- Information and photographs must be accurate and must not infringe anyone’s rights.\n"
     "- We may edit, decline or remove any listing at our discretion.\n\n"
     "## Liability\nBuyers and tenants should independently verify title, approvals and RERA details before any payment."),
    ("Disclaimer", "disclaimer", True, "Important information about property listings.",
     "Property details, prices, areas and images are provided by owners, builders or our team and are indicative. "
     "They do not constitute an offer or contract. Please verify all information, documents and RERA registration "
     "independently before making any decision or payment. Artist’s impressions are labelled where used."),
]

SERVICES = [
    ("Buying assistance", "apartment", "Shortlist homes that fit your budget and needs, arrange site visits and guide you through documentation."),
    ("Selling your property", "post-property", "Price guidance, listing, buyer screening and support until registration."),
    ("Rentals & leasing", "rent", "Find tenants or a home on rent, with clear agreements and move-in support."),
    ("Commercial property", "office-space", "Offices, shops, showrooms and warehouses for sale or lease."),
    ("New projects", "new-projects", "Information on new launches and under-construction projects, including RERA details."),
    ("Home loan guidance", "home-loan", "Help understanding loan eligibility and connecting with lenders of your choice."),
]

HIGHLIGHTS = [
    ("Every listing reviewed", "Our team reviews each property before it is published on the website.", "shield-check"),
    ("Local know-how", "Practical knowledge of Faridabad sectors, societies and builders.", "map-pin"),
    ("Clear communication", "Straight answers on price, paperwork and timelines – no hidden surprises.", "message-circle"),
    ("Your details stay private", "Owner phone numbers and addresses are never shown publicly without consent.", "user"),
]

FAQS = [
    ("How do I list my property?", "Use the Post Property form. Our team reviews every submission and contacts you if anything needs confirming before the listing goes live.", "selling", True),
    ("Is there a fee to post a property?", "Please contact our team for current terms before you list.", "selling", False),
    ("Are listings published immediately?", "No. Every property is reviewed by our team before it appears on the website.", "selling", True),
    ("What should I check before paying a token amount?", "Verify the seller’s ownership documents, approvals and, for projects, the RERA registration on the state RERA website. Never pay without written receipts.", "legal", True),
    ("Can I schedule a site visit?", "Yes. Send an enquiry from the property page or call us and we’ll arrange a convenient time.", "buying", True),
    ("Which areas do you cover?", "Our main focus is Faridabad and Delhi NCR.", "general", True),
    ("What documents does a tenant need?", "Typically a photo ID, address proof and, for companies, a letter of employment. The landlord may ask for police verification as per local rules.", "renting", False),
]

BLOG_CATEGORIES = ["Buying guides", "Renting", "Selling tips", "Faridabad", "Legal & documents", "New projects"]


class Command(BaseCommand):
    help = "Create baseline reference content (idempotent; safe for production)."

    def add_arguments(self, parser):
        parser.add_argument("--domain", default="", help="Set the Sites framework domain, e.g. hamaramakaan.com")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["domain"]:
            Site.objects.update_or_create(pk=1, defaults={"domain": options["domain"], "name": "Hamara Makaan Properties"})
        SiteSetting.load()

        for i, (name, slug, cat, illus, icon, beds) in enumerate(PROPERTY_TYPES):
            PropertyType.objects.get_or_create(slug=slug, defaults=dict(
                name=name, category=cat, illustration=illus, icon=icon, has_bedrooms=beds, sort_order=i))
        for i, (name, icon) in enumerate(AMENITIES):
            Amenity.objects.get_or_create(name=name, defaults={"icon": icon, "sort_order": i})

        order = 0
        for state_name, cities in LOCATIONS.items():
            state, _ = State.objects.get_or_create(name=state_name)
            for city_name, localities in cities.items():
                city, _ = City.objects.get_or_create(state=state, name=city_name, defaults={
                    "sort_order": order, "show_in_footer": True})
                order += 1
                for loc in localities:
                    Locality.objects.get_or_create(city=city, name=loc, defaults={"is_popular": loc in POPULAR})

        for i, (title, slug, legal, intro, body) in enumerate(PAGES):
            Page.objects.get_or_create(slug=slug, defaults=dict(
                title=title, intro=intro, body=body, is_legal=legal, show_in_footer=legal, sort_order=i))
        for i, (title, icon, summary) in enumerate(SERVICES):
            Service.objects.get_or_create(title=title, defaults={"icon": icon, "summary": summary, "sort_order": i})
        for i, (title, text, icon) in enumerate(HIGHLIGHTS):
            Highlight.objects.get_or_create(title=title, defaults={"text": text, "icon": icon, "sort_order": i})
        for i, (q, a, cat, home) in enumerate(FAQS):
            FAQ.objects.get_or_create(question=q, defaults={"answer": a, "category": cat, "show_on_home": home, "sort_order": i})
        for name in BLOG_CATEGORIES:
            BlogCategory.objects.get_or_create(name=name)

        self.stdout.write(self.style.SUCCESS(
            "Baseline content ready. Next: add verified phone/WhatsApp/email/address in Dashboard > Settings, "
            "and have the legal pages reviewed."))
