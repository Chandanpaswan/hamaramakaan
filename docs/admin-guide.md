# Staff dashboard guide

Log in at `/<DASHBOARD_PATH>` (default `/manage/`). What you see depends on your role. Ask a Super Admin if something is missing.

## Roles

| Role | Can do |
|---|---|
| Super Admin | Everything, including staff accounts and roles |
| Admin | Listings, approvals, leads (all), content, locations, settings, reports, audit log, redirects |
| Property Manager | Create and edit listings and projects, approve owner submissions, mark featured |
| Sales Manager | See **all** leads, assign them, export CSV, view reports |
| Sales Executive | See and update **only leads assigned to them**; add notes |
| Content Editor | Blog posts, pages, FAQs, services, testimonials |
| Viewer | Read-only listings, projects, blog and pages |

After 5 failed logins, an account (and the IP it's used from) is locked for 15 minutes. Every login, failed login, export, approval and permission change is recorded under **Security & audit**.

## Listings

1. **Properties → Add property.** Fill in the basics, price, specifications and location. Owner details are private and never shown on the website.
2. Save, then **upload photos** on the property page:
   - Use daylight photos, ideally 4:3, with no watermarks.
   - Use *Make main* to pick the cover photo.
   - Add alt text describing each photo.
3. Set **Status → Published** when the listing is ready. Without photos, the site shows a brand illustration.
4. **Verified** may be ticked only after the documented verification process is complete, and only by roles allowed to verify.
5. When a property sells or rents, set the status to *Sold* or *Rented*. It disappears from the website but its history is kept. Use *Archived* rather than deleting.

### Owner submissions (Post Property form)

- Each submission arrives as **Pending review**, plus a high-priority lead.
- Open it from **Overview → Recent owner submissions** or the *Pending review* tab.
- Call the owner if needed, then choose one of:
  - **Approve & publish**
  - **Return for correction** (a note is required)
  - **Reject** (a note is required)
- If email is configured and the owner gave an email address, they receive the decision automatically.

## Leads

- Leads come from property and project enquiries, the contact page, callback requests and Post Property. You can also add them manually (walk-ins, phone campaigns).
- Use the filters to narrow the list: search by name, phone or lead ID; status; source; assigned person; date range; *follow-up due*.
- On a lead:
  - update the **status**, **priority** and **next follow-up date**
  - add **notes** after every call
  - **assign** the lead (managers only)
- The activity timeline keeps the full status and assignment history.
- **Export CSV** follows your current filters. Every export is logged, so only export what you need.

## Content

- **Pages** (About, Services, Privacy, Terms, Disclaimer) and **Blog posts** support simple formatting: `## Heading`, `### Subheading`, `- bullet`, `1. numbered`, `**bold**`, `[link text](https://…)`.
- Blog statuses:
  - *Draft*: hidden from the public
  - *Scheduled*: goes live at the publish time you set
  - *Published*: live now
- Fill in the **SEO title** (≤ 70 characters) and **meta description** (≤ 160 characters) for important pages and posts.
- **Testimonials** can only be published once *permission confirmed* is ticked.
- **Why choose us** items must be factual. Do not add statistics you cannot prove.

## Locations

- Add cities and localities under **Locations**.
- A location page is automatically hidden from search engines while it has no live listings, or when *indexable* is unticked.
- Write original, useful descriptions. Don't copy text between locations.
- Tick *popular* on a locality to show it as a quick-search chip on the home page.

## Website settings

Settings include phone, WhatsApp, email, address, office hours, map embed, social links, home-page headings, GA4 ID, Search Console verification and **maintenance mode**.

- A blank contact field is simply hidden on the site.
- Maintenance mode shows a "back soon" page to visitors. Logged-in staff can still browse the site.

## SEO redirects

When a page URL changes or an old-site URL needs preserving, add a redirect under **System → SEO redirects (301)**. For example, old path `/property-detail/123` → new path `/property/3-bhk-apartment-sector-85/`.
