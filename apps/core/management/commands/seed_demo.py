"""
SAMPLE data so the UI can be reviewed before real inventory exists.
Every record is flagged `is_sample`, labelled "Sample" on the site, noindexed and left out of the sitemap.
Runs when DEBUG is True, or on production only with --allow-production (demo staff accounts are never
created there). Photos are CC0 (public domain, no credit required), sourced via Openverse.
Remove everything with:  python manage.py seed_demo --clear
"""
import io
import secrets
import urllib.request
from datetime import timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from PIL import Image

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
from apps.properties.models import Amenity, Project, Property, PropertyImage, PropertyType

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

# CC0 1.0 photos (public domain) found via Openverse; key -> (image URL, source page).
# StockSnap's CDN refuses scripted downloads, so those are fetched through Openverse's image proxy.
OV = "https://api.openverse.org/v1/images/"
PHOTOS = {
    "tower-white": ("https://images.rawpixel.com/editor_1024/cHJpdmF0ZS9sci9pbWFnZXMvd2Vic2l0ZS8yMDIyLTA1L3Vwd2s2MTkwOTQzMC13aWtpbWVkaWEtaW1hZ2Uta293ZXFmMDguanBn.jpg", "https://www.rawpixel.com/image/3285824"),
    "flats-colourful": (OV + "03a918e7-3077-4b46-8e19-3ff65d867817/thumb/?full_size=true", "https://stocksnap.io/photo/colorful-buildings-VLZ1NCPYDR"),
    "flats-modern": (OV + "e517cec6-4866-4fb3-8791-58dd6b8e5cd2/thumb/?full_size=true", "https://stocksnap.io/photo/modern-design-DTZVUDUTRV"),
    "flats-balcony": (OV + "b918d04b-6b09-4801-b883-44f474f5c17c/thumb/?full_size=true", "https://stocksnap.io/photo/apartments-condos-DVE0MEACPS"),
    "flats-blue": (OV + "901ee435-0675-4150-a757-8800895ec071/thumb/?full_size=true", "https://stocksnap.io/photo/architecture-buildings-XVS8FFEABO"),
    "house": ("https://images.rawpixel.com/editor_1024/cHJpdmF0ZS9zdGF0aWMvaW1hZ2Uvd2Vic2l0ZS8yMDIyLTA0L2xyL2ZyYnJpY2tfaG91c2VfZXN0YXRlX3Jlc2lkZW50aWFsLWltYWdlLWt5YmU3OHByLmpwZw.jpg", "https://www.rawpixel.com/image/6040724"),
    "villa-white": ("https://images.rawpixel.com/editor_1024/cHJpdmF0ZS9zdGF0aWMvaW1hZ2Uvd2Vic2l0ZS8yMDIyLTA0L2xyL2ZsMzcxNjM0Nzc3NDEtaW1hZ2Uta3ljajg3MTAuanBn.jpg", "https://www.rawpixel.com/image/6078516"),
    "villa-garden": ("https://images.rawpixel.com/editor_1024/czNmcy1wcml2YXRlL3Jhd3BpeGVsX2ltYWdlcy93ZWJzaXRlX2NvbnRlbnQvbHIvZmwzNjkwNDA3NTkyMC1pbWFnZS1reWJlam5xYS5qcGc.jpg", "https://www.rawpixel.com/image/6043060"),
    "villa-pool": (OV + "d6a90e22-f5da-44c8-8d94-306473b902c9/thumb/?full_size=true", "https://stocksnap.io/photo/modern-house-UIU7D31EDY"),
    "land": (OV + "192cc57b-baa0-4e43-bb13-f39eef2c1dc0/thumb/?full_size=true", "https://stocksnap.io/photo/rainbow-sky-PAQC3Z5YDJ"),
    "shop": ("https://images.rawpixel.com/editor_1024/czNmcy1wcml2YXRlL3Jhd3BpeGVsX2ltYWdlcy93ZWJzaXRlX2NvbnRlbnQvbHIvcHgxNjk4OTItaW1hZ2Uta3d5cGhrNGkuanBn.jpg", "https://www.rawpixel.com/image/5951325"),
    "office": (OV + "e5ebaabd-fc1e-4f51-b35f-de1f17f5a3d1/thumb/?full_size=true", "https://stocksnap.io/photo/office-interior-NSQTXCLWQ5"),
    "warehouse": (OV + "1c14f234-1c40-476e-bde1-b9c42610b451/thumb/?full_size=true", "https://stocksnap.io/photo/warehouse-building-2EEE2092E1"),
    "living-1": ("https://images.rawpixel.com/editor_1024/czNmcy1wcml2YXRlL3Jhd3BpeGVsX2ltYWdlcy93ZWJzaXRlX2NvbnRlbnQvbHIvcHUyMzM1MTgwLWltYWdlLWt3dndpYmE1LmpwZw.jpg", "https://www.rawpixel.com/image/5915137"),
    "living-2": ("https://images.rawpixel.com/editor_1024/cHJpdmF0ZS9sci9pbWFnZXMvd2Vic2l0ZS8yMDIyLTA1L2lzMTU3OTYtaW1hZ2Uta3d2eWhleG0uanBn.jpg", "https://www.rawpixel.com/image/5927318"),
    "living-3": ("https://images.rawpixel.com/editor_1024/czNmcy1wcml2YXRlL3Jhd3BpeGVsX2ltYWdlcy93ZWJzaXRlX2NvbnRlbnQvbHIvaXMxNTcxOC1pbWFnZS1rd3Z3dXcwZC5qcGc.jpg", "https://www.rawpixel.com/image/5917348"),
    "living-4": ("https://images.rawpixel.com/editor_1024/czNmcy1wcml2YXRlL3Jhd3BpeGVsX2ltYWdlcy93ZWJzaXRlX2NvbnRlbnQvbHIvaXMxNTc5OC1pbWFnZS1rd3Z5Z29ycy5qcGc.jpg", "https://www.rawpixel.com/image/5927053"),
    "living-5": ("https://images.rawpixel.com/editor_1024/czNmcy1wcml2YXRlL3Jhd3BpeGVsX2ltYWdlcy93ZWJzaXRlX2NvbnRlbnQvbHIvYTAwNS1zY290dHctMjg3LmpwZw.jpg", "https://www.rawpixel.com/image/430394"),
    "living-6": ("https://images.rawpixel.com/editor_1024/czNmcy1wcml2YXRlL3Jhd3BpeGVsX2ltYWdlcy93ZWJzaXRlX2NvbnRlbnQvbHIvaXMxMzYwNy1pbWFnZS1rd3lzZTcwdi5qcGc.jpg", "https://www.rawpixel.com/image/5970065"),
    "bedroom-1": ("https://images.rawpixel.com/editor_1024/czNmcy1wcml2YXRlL3Jhd3BpeGVsX2ltYWdlcy93ZWJzaXRlX2NvbnRlbnQvcHg5NDUzOTMtaW1hZ2Uta3d2dXI4YjYuanBn.jpg", "https://www.rawpixel.com/image/5903851"),
    "bedroom-2": ("https://images.rawpixel.com/editor_1024/cHJpdmF0ZS9zdGF0aWMvaW1hZ2Uvd2Vic2l0ZS8yMDIyLTA0L2xyL2lzMTU3NjAtaW1hZ2Uta3d2d3ZwcGsuanBn.jpg", "https://www.rawpixel.com/image/5917601"),
    "bedroom-3": ("https://images.rawpixel.com/editor_1024/cHJpdmF0ZS9zdGF0aWMvaW1hZ2Uvd2Vic2l0ZS8yMDIyLTA0L2xyL3B4ODY3ODI3LWltYWdlLWt3dnhkdTZnLmpwZw.jpg", "https://www.rawpixel.com/image/5920688"),
    "kitchen-1": ("https://images.rawpixel.com/editor_1024/czNmcy1wcml2YXRlL3Jhd3BpeGVsX2ltYWdlcy93ZWJzaXRlX2NvbnRlbnQvbHIvZmwzNjQ5MTQxMTM5My1pbWFnZS1reWJlank0aS5qcGc.jpg", "https://www.rawpixel.com/image/6043001"),
    "kitchen-2": ("https://images.rawpixel.com/editor_1024/czNmcy1wcml2YXRlL3Jhd3BpeGVsX2ltYWdlcy93ZWJzaXRlX2NvbnRlbnQvbHIvcHgxMjczNjAzLWltYWdlLWt3dnkwOHJnLmpwZw.jpg", "https://www.rawpixel.com/image/5924425"),
    "kitchen-3": ("https://images.rawpixel.com/editor_1024/cHJpdmF0ZS9zdGF0aWMvaW1hZ2Uvd2Vic2l0ZS8yMDIyLTA0L2xyL3B4MTI3NDc2NS1pbWFnZS1rd3Z3NXJ4dy5qcGc.jpg", "https://www.rawpixel.com/image/5912749"),
    "kitchen-4": ("https://images.rawpixel.com/editor_1024/czNmcy1wcml2YXRlL3Jhd3BpeGVsX2ltYWdlcy93ZWJzaXRlX2NvbnRlbnQvbHIvcHgxMTA0NjM4LWltYWdlLWt3dndhdnZqLmpwZw.jpg", "https://www.rawpixel.com/image/5913547"),
    "patio": (OV + "58682ac8-75ad-403a-8f84-413f10cdd203/thumb/?full_size=true", "https://stocksnap.io/photo/furniture-patio-KOIAWLY3SU"),
}
# Listing title -> photo keys (first = main photo).
LISTING_PHOTOS = {
    "3 BHK apartment with park view": ["tower-white", "living-2", "bedroom-3", "kitchen-3"],
    "2 BHK builder floor near market": ["flats-colourful", "living-3", "kitchen-1"],
    "4 BHK independent house with terrace": ["house", "living-4", "bedroom-2", "kitchen-4"],
    "Residential plot in gated township": ["land"],
    "2 BHK flat for rent, family preferred": ["flats-balcony", "living-5", "bedroom-1"],
    "1 BHK furnished apartment on rent": ["living-1", "kitchen-2"],
    "3 BHK under-construction apartment": ["flats-blue", "kitchen-2"],
    "Ground-floor shop on main road": ["shop"],
    "Furnished office space for lease": ["office"],
    "Warehouse with truck access": ["warehouse"],
    "Villa with private garden": ["villa-white", "villa-garden", "villa-pool", "living-6"],
    "2 BHK apartment near metro": ["flats-modern", "living-6", "bedroom-3"],
}
PROJECT_PHOTOS = {"Sample Greens Residency": "flats-blue", "Sample Heights": "tower-white"}
POST_PHOTOS = {
    "Documents to check before buying a flat in Faridabad": "patio",
    "How to prepare your home for a quick rental": "living-3",
    "Understanding super area vs carpet area": "kitchen-3",
}

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
        parser.add_argument("--clear", action="store_true", help="Delete all sample data, its photos and demo users.")
        parser.add_argument("--allow-production", action="store_true",
                            help="Allow running with DEBUG=False (sample records stay labelled and noindexed).")
        parser.add_argument("--no-photos", action="store_true", help="Skip downloading the CC0 sample photos.")

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["allow_production"]:
            raise CommandError("DEBUG is False. Re-run with --allow-production to load clearly labelled sample data.")
        if options["clear"]:
            return self.clear()
        call_command("seed_content", verbosity=0)
        with transaction.atomic():
            self.create_listings()
            self.create_projects()
            self.create_posts()
            users = self.create_users() if settings.DEBUG else {}  # never create demo logins on a live site
            self.create_leads(users)
        if not options["no_photos"]:
            self.attach_photos()

    def clear(self):
        # Delete photo files explicitly: queryset deletes skip model delete() and would orphan stored files.
        for image in PropertyImage.objects.filter(property__is_sample=True):
            image.delete()
        for obj, field in [*((p, "cover_image") for p in Project.objects.filter(is_sample=True)),
                           *((b, "featured_image") for b in BlogPost.objects.filter(is_sample=True))]:
            getattr(obj, field).delete(save=False)
        Lead.objects.filter(email__endswith="@example.com").delete()
        Property.objects.filter(is_sample=True).delete()
        Project.objects.filter(is_sample=True).delete()
        BlogPost.objects.filter(is_sample=True).delete()
        get_user_model().objects.filter(username__startswith="demo-").delete()
        self.stdout.write(self.style.SUCCESS("Sample data and photos removed."))

    # -- photos ------------------------------------------------------------------------------
    def _photo(self, key):
        """Download a CC0 photo once, verify it is a real image and return it as a <=1600px JPEG."""
        cache = self.__dict__.setdefault("_photo_cache", {})
        if key not in cache:
            url, _source = PHOTOS[key]
            req = urllib.request.Request(url, headers={"User-Agent": "sample-data-seeder/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read(10 * 1024 * 1024)
            with Image.open(io.BytesIO(raw)) as img:
                img = img.convert("RGB")
                img.thumbnail((1600, 1600))
                out = io.BytesIO()
                img.save(out, "JPEG", quality=82, optimize=True)
            cache[key] = out.getvalue()
        return ContentFile(cache[key], name=f"{key}.jpg")

    def attach_photos(self):
        added, failed = 0, []
        for prop in Property.objects.filter(is_sample=True, title__in=LISTING_PHOTOS).prefetch_related("images"):
            if prop.images.exists():
                continue
            for order, key in enumerate(LISTING_PHOTOS[prop.title]):
                try:
                    PropertyImage.objects.create(
                        property=prop, image=self._photo(key), sort_order=order, is_primary=order == 0,
                        alt_text=f"{prop.title} – sample photo {order + 1}"[:160],
                        caption="Sample photo (CC0, public domain)",
                    )
                    added += 1
                except Exception as exc:  # noqa: BLE001 - a missing photo must not stop the seed
                    failed.append(f"{key}: {exc}")
        for model, mapping, field, alt_field, name_field in [
            (Project, PROJECT_PHOTOS, "cover_image", "cover_image_alt", "name"),
            (BlogPost, POST_PHOTOS, "featured_image", "featured_image_alt", "title"),
        ]:
            for obj in model.objects.filter(is_sample=True, **{f"{name_field}__in": mapping}):
                if getattr(obj, field):
                    continue
                try:
                    getattr(obj, field).save(f"{mapping[getattr(obj, name_field)]}.jpg",
                                             self._photo(mapping[getattr(obj, name_field)]), save=False)
                    setattr(obj, alt_field, f"{getattr(obj, name_field)} – sample photo")
                    obj.save()
                    added += 1
                except Exception as exc:  # noqa: BLE001
                    failed.append(f"{obj}: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Sample photos attached: {added}."))
        for line in failed:
            self.stdout.write(self.style.WARNING(f"  skipped {line}"))

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
            post, created = BlogPost.objects.get_or_create(title=title, defaults=dict(
                excerpt=excerpt, body=POST_BODY, category=BlogCategory.objects.get(name=cat),
                status=BlogPost.Status.PUBLISHED, published_at=timezone.now() - timedelta(days=3 * i), is_featured=i == 0,
            ))
            if created or "sample article text" in post.body:  # also flags posts made by older versions of this seed
                BlogPost.objects.filter(pk=post.pk).update(is_sample=True)

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
