# Hamara Makaan Properties: website & property portal

Django website for **Hamara Makaan Properties**. It combines an agency site with an admin-managed property portal: approved listings, search, enquiries, owner submissions with review, lead management, a blog, location pages and a secure staff dashboard.

Built to the *Project Requirement & Development Blueprint v1.0* and the official brand book (colours, Poppins/Inter, Lucide icons, logos and patterns).

## Stack

- Python 3.12+ (tested on 3.14) and Django 5.2 LTS
- Server-rendered Django templates, Bootstrap 5.3 (vendored, no CDN), and vanilla JavaScript (progressive enhancement only)
- SQLite for local development; PostgreSQL for staging and production
- Nginx + Gunicorn + WhiteNoise for static files

## Quick start (local)

```bash
cd hamara_makaan
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements/development.txt
cp .env.example .env                                   # defaults work for local dev
python manage.py migrate                               # also creates the 7 staff roles
python manage.py seed_content                          # property types, locations, pages, FAQs…
python manage.py createsuperuser
python manage.py runserver
```

- Website: <http://127.0.0.1:8000/>
- Staff dashboard: <http://127.0.0.1:8000/manage/>
- Django system admin (superusers only): `/hm-system-admin/`

### Optional sample data (development only)

```bash
python manage.py seed_demo          # 13 sample listings, 2 projects, 3 posts, leads, demo staff users
python manage.py seed_demo --clear  # remove it all again
```

Sample records are flagged `is_sample` and show a **Sample** badge on the site. The command refuses to run when `DEBUG=False`. The dashboard launch checklist warns while any sample data remains.

## Tests

```bash
python manage.py test tests --settings=config.settings.test
```

48 tests cover:
- models, search and filter combinations, enquiries, spam and rate limits
- post-property uploads and validation
- the approval workflow and role permissions (lead visibility, export, approval)
- login lockout, the audit log, CSV-injection protection, sitemap and noindex rules, blog scheduling, and maintenance mode

## Project layout

```
config/            settings (base / development / production / test), urls, wsgi
apps/core          site settings, audit log, security utils, template tags, home, sitemaps, seed commands
apps/accounts      custom User model, role → permission matrix (synced after migrate)
apps/locations     State / City / Locality and location landing pages
apps/properties    Property, images, types, amenities, projects; search, detail, post-property
apps/leads         Lead, notes, status history, assignments, WhatsApp click tracking, enquiry forms
apps/pages         CMS pages, FAQs, services, highlights, testimonials, contact
apps/blog          posts, categories, tags (draft / scheduled / published)
apps/dashboard     the /manage/ staff dashboard (all permission checks live here)
templates/         public templates, includes, dashboard
static/            brand CSS/JS, logos, patterns, icons, vendored Bootstrap
docs/              deployment, admin guide, backup & restore, SEO migration
```

## Key decisions

These follow §28/§29 of the blueprint.

- **Agency site plus admin-managed portal.** Visitors browse and enquire without accounts. Buyer, owner and agent accounts are Phase 2.
- **Every owner submission is "Pending review".** Nothing is auto-published.
- **Staff see only their assigned leads** unless their role has *view all leads*.
- **No invented content.** No listing counts, ratings, testimonials or contact details are hard-coded. Contact fields stay blank, and hidden on the site, until verified values are entered in **Dashboard → Website settings**. "Verified" badges appear only when staff with the verify permission tick them.
- **Rich text is a safe Markdown subset.** Everything is HTML-escaped, so content editors cannot inject scripts.

## Before launch

1. Enter the verified phone, WhatsApp, email, address and hours in Website settings.
2. Have the Privacy Policy, Terms and Disclaimer reviewed (see the `legal_reviewed` flag on each page).
3. Remove sample data, load real inventory and photos, and set up GA4 and Search Console.
4. Crawl the old site and add 301s under **Dashboard → SEO redirects** (see `docs/seo-migration.md`).
5. Follow `docs/deployment.md`, then test backups using `docs/backup-restore.md`.

See [docs/admin-guide.md](docs/admin-guide.md) for day-to-day use of the dashboard.
