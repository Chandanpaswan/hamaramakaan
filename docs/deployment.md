# Deployment guide (Ubuntu 24.04 · Nginx · Gunicorn · PostgreSQL)

> Never use `runserver` in production. Production settings refuse to start without `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS`.

## 1. Server packages

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-dev build-essential \
     postgresql nginx certbot python3-certbot-nginx redis-server git
sudo adduser --system --group --home /srv/hamara_makaan hm
```

## 2. PostgreSQL

```bash
sudo -u postgres psql <<'SQL'
CREATE USER hamara_makaan WITH PASSWORD 'use-a-long-random-password';
CREATE DATABASE hamara_makaan OWNER hamara_makaan ENCODING 'UTF8';
SQL
```

## 3. Application

```bash
sudo -u hm -H bash
cd /srv/hamara_makaan
git clone <repository-url> app && cd app/hamara_makaan
python3 -m venv /srv/hamara_makaan/venv
/srv/hamara_makaan/venv/bin/pip install -r requirements/production.txt
cp .env.example .env && chmod 600 .env     # then edit .env
```

Minimum production `.env`:

```ini
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=<50+ random characters>
DJANGO_ALLOWED_HOSTS=hamaramakaan.com,www.hamaramakaan.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://hamaramakaan.com,https://www.hamaramakaan.com
USE_X_FORWARDED_FOR=true
DB_ENGINE=postgres
DB_PASSWORD=<postgres password>
REDIS_URL=redis://127.0.0.1:6379/1
MEDIA_ROOT=/srv/hamara_makaan/media
EMAIL_HOST=<smtp host>  EMAIL_HOST_USER=…  EMAIL_HOST_PASSWORD=…
LEAD_NOTIFICATION_EMAILS=sales@hamaramakaan.com
DASHBOARD_PATH=<non-obvious>/      # e.g. hm-staff-7q2/
DJANGO_ADMIN_PATH=<non-obvious>/
```

Then:

```bash
export $(grep -v '^#' .env | xargs)  # or let systemd load it
V=/srv/hamara_makaan/venv/bin/python
$V manage.py migrate
$V manage.py createcachetable         # only if REDIS_URL is not set
$V manage.py collectstatic --noinput
$V manage.py seed_content --domain hamaramakaan.com
$V manage.py createsuperuser
$V manage.py check --deploy
```

## 4. Gunicorn (systemd)

`/etc/systemd/system/hamara-makaan.service`

```ini
[Unit]
Description=Hamara Makaan Django app
After=network.target postgresql.service

[Service]
User=hm
Group=www-data
WorkingDirectory=/srv/hamara_makaan/app/hamara_makaan
EnvironmentFile=/srv/hamara_makaan/app/hamara_makaan/.env
ExecStart=/srv/hamara_makaan/venv/bin/gunicorn config.wsgi:application \
          --bind unix:/run/hamara-makaan.sock --workers 3 --timeout 60 --access-logfile -
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now hamara-makaan
```

## 5. Nginx

`/etc/nginx/sites-available/hamaramakaan`

```nginx
server {
    listen 80;
    server_name hamaramakaan.com www.hamaramakaan.com;
    client_max_body_size 60M;   # up to 10 photos × 5 MB

    location /media/ {
        alias /srv/hamara_makaan/media/;
        expires 30d;
        add_header X-Content-Type-Options nosniff;
        # Never execute anything from uploads
        location ~* \.(php|py|pl|sh|cgi|html?)$ { deny all; }
    }
    location / {
        proxy_pass http://unix:/run/hamara-makaan.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/hamaramakaan /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d hamaramakaan.com -d www.hamaramakaan.com   # HTTPS
```

Static files are served by WhiteNoise, with hashed filenames and long cache lifetimes.

Redirect the other domain:
- To send `www` to the bare domain, or the reverse, add a separate `server` block that returns `301`.
- Once the business decides `hamaramakaanproperties.com` should redirect, give it a `server` block with `return 301 https://hamaramakaan.com$request_uri;`.

## 6. Releasing an update

```bash
cd /srv/hamara_makaan/app && git pull
/srv/hamara_makaan/venv/bin/pip install -r hamara_makaan/requirements/production.txt
cd hamara_makaan && ../../venv/bin/python manage.py migrate && ../../venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart hamara-makaan
```

**Rollback:** take a database backup before running `migrate` (see `backup-restore.md`). Then `git checkout <previous tag>`, restore the backup if a migration changed data, and restart.

## 7. Monitoring

- **Uptime:** an external check on `/` and `/robots.txt`.
- **Errors:** add Sentry (`pip install sentry-sdk`) and initialise it in `config/settings/production.py` from a `SENTRY_DSN` env var.
- **Logs:** `journalctl -u hamara-makaan -f` and `/var/log/nginx/`.
- **Search:** watch Search Console coverage and 404s weekly for the first two months.
