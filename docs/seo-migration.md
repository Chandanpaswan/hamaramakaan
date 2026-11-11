# SEO & URL migration plan

## New URL structure

| Content | URL |
|---|---|
| All properties | `/properties/`, `/properties/<city>/` |
| Sale / rent / commercial | `/buy/`, `/buy/<city>/`, `/rent/<city>/`, `/commercial/<city>/` |
| Property detail | `/property/<slug>/` |
| New projects | `/new-projects/`, `/new-projects/<slug>/` |
| Locations | `/locations/<city>/`, `/locations/<city>/<locality>/` |
| Blog | `/blog/`, `/blog/<slug>/`, `/blog/category/<slug>/` |
| Pages | `/about-us/`, `/services/`, `/contact-us/`, `/faq/`, `/privacy-policy/`, `/terms-and-conditions/`, `/disclaimer/` |
| Sitemap / robots | `/sitemap.xml`, `/robots.txt` |

## Built-in SEO behaviour

- Every page has a unique `<title>`, meta description, canonical URL and Open Graph tags. Each can be overridden per listing, project, page, post and location.
- One H1 per page, with a logical H2/H3 hierarchy and breadcrumbs (plus BreadcrumbList JSON-LD).
- Structured data is limited to what's accurate:
  - Organization and WebSite on the home page
  - BlogPosting on articles
  - FAQPage on the FAQ page
  - **No** ratings, reviews or offer markup.
- These pages are `noindex`:
  - filtered search results
  - empty or opted-out location pages
  - previews
  - FAQ search results
- The sitemap includes only live listings, projects, posts, pages and locations that have inventory.
- `robots.txt` blocks the dashboard, admin and tracking redirects.
- Images are lazy-loaded with explicit dimensions to reduce layout shift.

## Migration steps

1. **Crawl** the live sites (`hamaramakaan.com`, `www.hamaramakaan.com/blog/`, `hamaramakaanproperties.com`) with Screaming Frog or a similar tool. Export every URL with its status, title, meta description and inlinks.
2. **Prioritise.** From Search Console (last 16 months) and a backlink tool, mark URLs that have clicks, impressions or backlinks.
3. **Map** each valuable old URL to its best new equivalent in a sheet with columns `old_path, new_path, reason`. Re-create useful blog posts with original wording before mapping them.
4. **Implement** the map under **Dashboard → System → SEO redirects (301)**. For large maps, bulk-import into `django_redirect` with a one-off script.
5. **Decide the domain.** Pick the canonical host and 301 everything else to it at the Nginx level (see `deployment.md`).
6. **Launch.** Submit `/sitemap.xml` in Search Console and request indexing of the home page and key category pages.
7. **Monitor.** Check daily for the first week, then weekly: Search Console coverage, 404s (add redirects as they appear) and organic clicks against the baseline.
