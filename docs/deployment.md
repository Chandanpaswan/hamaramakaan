# Deployment guide

## Option A: Vercel (current live deployment)

Live at **https://hamaramakaan.vercel.app**. The Vercel project `hamaramakaan` is connected to GitHub, and **every push to `main` deploys to production automatically**. Other branches get preview URLs.

| Piece | How it's set up |
|---|---|
| App | `api/index.py` (Django WSGI) with `vercel.json` sending every route to it. Function region `sin1` (Singapore). |
| Static files | Served by WhiteNoise from `static/` (no collectstatic step). Only `public/` is served as raw files. |
| Database | Neon Postgres (free plan, Singapore), via the `DATABASE_URL` env var |
| Photos | Vercel Blob (public store `hamaramakaan-media`), via `BLOB_READ_WRITE_TOKEN`, handled by `apps/core/storage.py` |
| Settings | `DJANGO_SETTINGS_MODULE=config.settings.production`, `DJANGO_SECRET_KEY`, `USE_X_FORWARDED_FOR=true` |

**Limits to know**
- A request body can be at most **4.5 MB**. Browsers resize photos to 1600px before upload, so this is normally fine.
- Functions time out after 30 seconds.

**Running management commands against production** (migrations, createsuperuser…):

```bash
vercel env pull .env.local          # downloads the DATABASE_URL and BLOB tokens (gitignored; never commit)
# then run manage.py with those variables exported, e.g. in Git Bash:
set -a; . ./.env.local; set +a
DJANGO_SETTINGS_MODULE=config.settings.production DJANGO_SECRET_KEY=local-maintenance DJANGO_ALLOWED_HOSTS=localhost \
  python manage.py migrate
```

- **After pulling a change that adds migrations:** run `migrate` as above, *before or right after* the deploy.
- **Custom domain:** in Vercel → Project → Settings → Domains, add `hamaramakaan.com`, then run `python manage.py seed_content --domain hamaramakaan.com` (same environment as above) so the sitemap uses the new domain.

---

## Option B: VPS (Hostinger KVM 1 · Ubuntu 24.04 · Nginx · Gunicorn · PostgreSQL) with GitHub Actions

| Branch | Site | Server folder | Service |
|---|---|---|---|
| `main` | https://hamaramakaan.com (www → bare domain) | `/srv/hamara_makaan/prod` | `hamara-makaan@prod` |
| `dev` | https://dev.hamaramakaan.com (password-protected, noindexed) | `/srv/hamara_makaan/dev` | `hamara-makaan@dev` |

Each environment has its own database, `.env`, media folder and Gunicorn service. Files: `deploy/` (server setup, Nginx, systemd, release script) and `.github/workflows/deploy.yml`.

**Every push** runs the tests. If they pass, a push to `main` or `dev` uploads the code over SSH (rsync) and runs `deploy/release.sh`. That script installs requirements, backs up the prod database, migrates, collects static files, reloads Gunicorn with zero downtime, and smoke-tests the site.

### One-time setup

1. **DNS** (at your domain registrar): add `A` records for `@`, `www` and `dev`, each pointing to the VPS IP. Remove any old `A`/`CNAME` records for those names (for example, Vercel's).
2. **Deploy key** (on your PC): `ssh-keygen -t ed25519 -f hm_deploy -N "" -C hm-deploy`. This creates `hm_deploy` (private) and `hm_deploy.pub`.
3. **Server** (VPS must be Ubuntu 24.04; reinstall the OS from hPanel if needed):
   ```bash
   scp -r deploy root@<VPS_IP>:/root/hm-deploy
   ssh root@<VPS_IP>
   cd /root/hm-deploy
   DEPLOY_PUBKEY="<paste the one line from hm_deploy.pub>" CERTBOT_EMAIL=<your email> bash server-setup.sh
   ```
   The script installs the packages, firewall, the `hm` user, both databases with random passwords, `/srv/hamara_makaan/{prod,dev}/.env`, systemd, Nginx and HTTPS. The dev site's login is saved in `/root/hamaramakaan-credentials.txt`.
4. **GitHub** → repo → Settings → Secrets and variables → Actions:
   - `VPS_HOST`: the VPS IP
   - `VPS_SSH_KEY`: the full contents of `hm_deploy` (the private key)
   - optional: `VPS_PORT` (if SSH is not on 22) and `VPS_KNOWN_HOSTS` (output of `ssh-keyscan <VPS_IP>`, which pins the host key)
5. **First deploys:** `git push origin dev` (creates the dev site), then push or merge to `main`.
6. **Once per environment** (example for prod):
   ```bash
   ssh root@<VPS_IP>
   sudo -iu hm
   cd prod/app
   set -a; . ../.env; set +a
   export DJANGO_SETTINGS_MODULE=config.settings.production
   ../venv/bin/python manage.py seed_content --domain hamaramakaan.com   # dev: --domain dev.hamaramakaan.com
   ../venv/bin/python manage.py createsuperuser
   ```
7. **Email:** fill in `EMAIL_*` and `LEAD_NOTIFICATION_EMAILS` in `/srv/hamara_makaan/prod/.env`, then run `systemctl restart hamara-makaan@prod`.

### Moving the live data off Vercel

Do this **before the first push to `main`**, so customers never see an empty site.

- **Database:** `pg_dump -Fc --no-owner --no-acl "<Neon DATABASE_URL>" -f hm.dump` on your PC. Copy it to the server with `scp`, then run:
  `pg_restore --clean --if-exists --no-owner --no-acl -h 127.0.0.1 -U hamara_makaan_prod -d hamara_makaan_prod hm.dump`
  (the password is `DB_PASSWORD` in `prod/.env`).
- **Photos:** the simplest option is to add the existing `BLOB_READ_WRITE_TOKEN=…` line to `prod/.env`. Photos then keep being served from Vercel Blob, unchanged. To move them onto the VPS later, download each blob into `/srv/hamara_makaan/prod/media/<same pathname>` and remove the token.
- **Then** in Vercel → Project → Settings → Git, disconnect the repository. Otherwise every push to `main` deploys to both places.

### Before go-live: hamaramakaan.com stays on the old site

`server-setup.sh` enables `deploy/nginx/hamaramakaan-old-site.conf` for `hamaramakaan.com` and `www` by default. That config forwards every request to the old server (`190.92.174.187`), so you can point `@`/`www` DNS at the VPS and visitors still see the current website. The Django code runs only on dev.hamaramakaan.com. Pushes to `main` still deploy to `/srv/hamara_makaan/prod`, but Nginx doesn't send any traffic there.

After moving `@`/`www` DNS to the VPS, get the HTTPS certificate right away (HTTPS shows a certificate warning until you do):

```bash
certbot --nginx --redirect -d hamaramakaan.com -d www.hamaramakaan.com
```

### Going live on hamaramakaan.com

Once the live data has been copied (see above):

```bash
rm /etc/nginx/sites-enabled/hamaramakaan-old-site.conf
ln -s /etc/nginx/sites-available/hamaramakaan.conf /etc/nginx/sites-enabled/
certbot --nginx --redirect -d hamaramakaan.com -d www.hamaramakaan.com   # reuses the existing certificate
nginx -t && systemctl reload nginx
```

(Re-running `server-setup.sh` with `PROD_LIVE=1` does the same thing.)

### Day to day

- **Release:** merge to `dev`, check https://dev.hamaramakaan.com, then merge `dev` into `main`.
- **Rollback:** revert the commit and push. If a migration changed data, first restore the latest `/srv/hamara_makaan/backups/pre-deploy-*.sql.gz` with `gunzip -c <file> | psql -h 127.0.0.1 -U hamara_makaan_prod hamara_makaan_prod`.
- **Running version:** `cat /srv/hamara_makaan/prod/app/REVISION`

### Monitoring

- **Uptime:** an external check on `/` and `/robots.txt`.
- **Errors:** add Sentry (`pip install sentry-sdk`) and initialise it in `config/settings/production.py` from a `SENTRY_DSN` env var.
- **Logs:** `journalctl -u hamara-makaan@prod -f` and `/var/log/nginx/`.
- **Search:** watch Search Console coverage and 404s weekly for the first two months.
