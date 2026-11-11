"""
Development-only SAMPLE data so the UI can be reviewed before real inventory exists.
Every record is flagged `is_sample` and labelled “Sample” on the site. Refuses to run when DEBUG is False.
Remove with:  python manage.py seed_demo --clear
"""
import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.blog.models import BlogCategory, BlogPost
from apps.leads.models import Lead, LeadNote, LeadStatusHistory
from apps.locations.models import City, Locality
from apps.properties.models import Amenity, Project, Property, PropertyType

SAMPLE_NOTE = "\n\n(Sample listing for development and design review – not a real property.)"

LISTINGS = [
    # title, type slug, purpose, price, area, unit, beds, baths, locality, furnishing, construction, floor, total, featured
    ("3 BHK apartment with park view", "apartment", "sale", "8500000", "1450", "sqft", 3, 2, "Sector 85", "semi", "ready", 7, 14, True),
    ("2 BHK builder floor near market", "builder-floor", "sale", "5200000", "1100", "sqft", 2, 2, "Sector 21", "unfurnished", "ready", 2, 4, True),
    ("4 BHK independent house with terrace", "independent-house", "sale", "21000000", "300", "sqyd", 4, 4, "Sector 15", "furnished", "ready", None, None, True),
    ("Residential plot in gated township", "residential-plot", "sale", "6200000", "200", "sqyd", None, None, "Greater Faridabad (Neharpar)", "", "", None, None, True),
    ("2 BHK flat for rent, family preferred", "apartment", "rent", "18000", "1050", "sqft", 2, 2, "Sector 75", "semi", "ready", 4, 12, False),
    ("1 BHK furnished apartment on rent", "apartment", "rent", "12500", "650", "sqft", 1, 1, "Sector 88", "furnished", "ready", 9, 18, False),
    ("3 BHK under-construction apartment", "apartment", "sale", "9800000", "1650", "sqft", 3, 3, "Sector 88", "unfurnished", "under_construction", 11, 20, False),
    ("Ground-floor shop on main road", "shop-showroom", "sale", "11000000", "500", "sqft", None, None, "NIT", "", "ready", 0, 3, True),
    ("Furnished office space for lease", "office-space", "lease", "65000", "1200", "sqft", None, None, "Sector 15", "furnished", "ready", 3, 6, False),
    ("Warehouse with truck access", "warehouse", "rent", "120000", "8000", "sqft", None, None, "Greater Faridabad (Neharpar)", "", "ready", None, None, False),
    ("Villa with private garden", "villa", "sale", "32000000", "4000", "sqft", 4, 5, "Sector 21", "semi", "ready", None, None, False),
    ("2 BHK apartment near metro", "apartment", "sale", "6100000", "1150", "sqft", 2, 2, "Sector 15", "semi", "ready", 5, 10, False),
]

POSTS = [
    ("Documents to check before buying a flat in Faridabad", "Buying guides",
     "A practical checklist of title, approval and RERA documents to review before you pay any token amount."),
    ("How to prepare your home for a quick rental", "Renting",
     "Simple fixes and paperwork that help landlords find good tenants faster."),
    ("Understanding super area vs carpet area", "Legal & documents",
     "What each area measurement means and why it matters when you compare prices."),
]
POST_BODY = (
    "## Why it matters\nThis is sample article text for design review. Replace it with original content written by "
    "the Hamara Makaan team.\n\n## Checklist\n- First point to consider\n- Second point to consider\n- Third point to "
    "consider\n\n## Next steps\nTalk to our team if you have questions about a specific property."
)


class Command(BaseCommand):
    help = "Load clearly-labelled SAMPLE listings, projects, posts, leads and demo staff (development only)."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Delete all sample data and demo users.")

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo only runs with DEBUG=True. Never load sample data in production.")
        if options["clear"]:
            return self.clear()
        call_command("seed_content", verbosity=0)
        with transaction.atomic():
            self.create_listings()
            self.create_projects()
            self.create_posts()
            users = self.create_users()
            self.create_leads(users)

    def clear(self):
        Lead.objects.filter(email__endswith="@example.com").delete()
        Property.objects.filter(is_sample=True).delete()
        Project.objects.filter(is_sample=True).delete()
        BlogPost.objects.filter(body__contains="sample article text").delete()
        get_user_model().objects.filter(username__startswith="demo-").delete()
        self.stdout.write(self.style.SUCCESS("Sample data removed."))

    def create_listings(self):
        city = City.objects.get(slug="faridabad")
        amenities = list(Amenity.objects.all()[:8])
        now = timezone.now()
        for i, row in enumerate(LISTINGS):
            title, type_slug, purpose, price, area, unit, beds, baths, loc, furn, cons, floor, total, featured = row
            if Property.objects.filter(title=title, is_sample=True).exists():
                continue
            ptype = PropertyType.objects.get(slug=type_slug)
            prop = Property.objects.create(
                title=title, property_type=ptype, category=ptype.category, purpose=purpose,
                price=Decimal(price), area=Decimal(area), area_unit=unit, bedrooms=beds, bathrooms=baths,
                balconies=1 if beds else None, floor_number=floor, total_floors=total, furnishing=furn,
                construction_status=cons, parking=1 if beds else None, city=city,
                locality=Locality.objects.get(city=city, name=loc),
                description=(f"Well-maintained {ptype.name.lower()} in {loc}, Faridabad. Close to schools, markets "
                             "and public transport." + SAMPLE_NOTE),
                security_deposit=Decimal(price) * 2 if purpose != "sale" else None,
                status=Property.Status.PUBLISHED, is_featured=featured, is_sample=True,
                published_at=now - timedelta(days=i), owner_name="Sample Owner", owner_phone="+91 90000 00000",
            )
            prop.amenities.set(amenities[: 3 + i % 5])
        # One owner submission waiting for review, to demo the approval workflow.
        if not Property.objects.filter(is_sample=True, status=Property.Status.PENDING).exists():
            Property.objects.create(
                title="2 BHK flat submitted by owner", property_type=PropertyType.objects.get(slug="apartment"),
                purpose="sale", price=Decimal("4800000"), area=Decimal("980"), bedrooms=2, bathrooms=2, city=city,
                locality=Locality.objects.get(city=city, name="Sector 75"), address="Sample address (private)",
                status=Property.Status.PENDING, source=Property.Source.OWNER, is_sample=True,
                owner_name="Sample Owner", owner_phone="+91 90000 00001", description="Owner submission." + SAMPLE_NOTE,
            )

    def create_projects(self):
        city = City.objects.get(slug="faridabad")
        for name, loc, status, conf, lo, hi in [
            ("Sample Greens Residency", "Sector 88", "under_construction", "2 & 3 BHK apartments", "6500000", "12000000"),
            ("Sample Heights", "Greater Faridabad (Neharpar)", "new_launch", "3 & 4 BHK apartments", "9500000", "18000000"),
        ]:
            Project.objects.get_or_create(name=name, defaults=dict(
                city=city, locality=Locality.objects.get(city=city, name=loc), status=status, configurations=conf,
                price_from=Decimal(lo), price_to=Decimal(hi), builder_name="Sample Builder",
                description="Sample project for design review – not a real development." , is_published=True,
                is_featured=True, is_sample=True, possession_date=timezone.localdate() + timedelta(days=700),
            ))

    def create_posts(self):
        for i, (title, cat, excerpt) in enumerate(POSTS):
            BlogPost.objects.get_or_create(title=title, defaults=dict(
                excerpt=excerpt, body=POST_BODY, category=BlogCategory.objects.get(name=cat),
                status=BlogPost.Status.PUBLISHED, published_at=timezone.now() - timedelta(days=3 * i), is_featured=i == 0,
            ))

    def create_users(self):
        User = get_user_model()
        created = {}
        roles = {"demo-admin": "Admin", "demo-sales-manager": "Sales Manager", "demo-sales": "Sales Executive",
                 "demo-property": "Property Manager", "demo-editor": "Content Editor"}
        for username, role in roles.items():
            user, new = User.objects.get_or_create(username=username, defaults={
                "first_name": role.split()[0], "last_name": "(demo)", "is_staff": True, "email": f"{username}@example.com"})
            if new:
                password = secrets.token_urlsafe(10)
                user.set_password(password)
                user.save()
                user.groups.set([Group.objects.get(name=role)])
                created[username] = password
        if created:
            self.stdout.write(self.style.WARNING("Demo staff accounts (development only):"))
            for username, password in created.items():
                self.stdout.write(f"  {username:<22} {password}")
        return {u.username: u for u in User.objects.filter(username__startswith="demo-")}

    def create_leads(self, users):
        if Lead.objects.filter(email__endswith="@example.com").exists():
            return
        props = list(Property.objects.filter(is_sample=True, status=Property.Status.PUBLISHED)[:6])
        sales = users.get("demo-sales")
        samples = [
            ("Aman (sample)", "buy", "property", "new", props[0] if props else None, sales),
            ("Priya (sample)", "rent", "property", "contacted", props[4] if len(props) > 4 else None, sales),
            ("Rahul (sample)", "sell", "contact", "qualified", None, None),
            ("Neha (sample)", "callback", "callback", "new", None, None),
            ("Vikram (sample)", "buy", "property", "site_visit", props[1] if len(props) > 1 else None, sales),
        ]
        for i, (name, req, source, status, prop, assignee) in enumerate(samples):
            lead = Lead.objects.create(
                name=name, phone=f"+91 90000 0001{i}", email=f"sample{i}@example.com", requirement=req, source=source,
                status=status, interested_property=prop, assigned_to=assignee, consent=True,
                next_follow_up=timezone.localdate() + timedelta(days=i - 2), message="Sample enquiry for testing.",
            )
            LeadStatusHistory.objects.create(lead=lead, to_status=status)
            if assignee:
                LeadNote.objects.create(lead=lead, author=assignee, note="Sample follow-up note.")
        self.stdout.write(self.style.SUCCESS(f"Sample data loaded: {len(LISTINGS) + 1} listings, 2 projects, 3 posts, 5 leads."))
