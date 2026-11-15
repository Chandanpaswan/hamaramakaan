#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 24.04 VPS (e.g. Hostinger KVM 1) for prod + dev.
# Safe to re-run: existing .env files, databases and passwords are kept.
#
# Usage, as root on the VPS, from the folder that holds this script:
#   DEPLOY_PUBKEY="ssh-ed25519 AAAA... hm-deploy" CERTBOT_EMAIL=you@example.com bash server-setup.sh
# Leave CERTBOT_EMAIL empty if DNS does not point at this server yet (run certbot later).
# hamaramakaan.com is forwarded to the old site until you re-run with PROD_LIVE=1.
set -euo pipefail

: "${DEPLOY_PUBKEY:?Set DEPLOY_PUBKEY to the public key GitHub Actions will use}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"
SSH_PORT="${SSH_PORT:-22}"
BASE=/srv/hamara_makaan
HERE="$(cd "$(dirname "$0")" && pwd)"
[ "$(id -u)" = 0 ] || { echo "Run as root" >&2; exit 1; }

# --- Packages -----------------------------------------------------------------------------
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q python3 python3-venv python3-dev build-essential libpq-dev \
    postgresql redis-server nginx certbot python3-certbot-nginx apache2-utils \
    rsync curl ufw fail2ban unattended-upgrades

# --- Firewall -----------------------------------------------------------------------------
ufw allow "$SSH_PORT/tcp"
ufw allow "Nginx Full"
ufw --force enable

# --- Deploy user + folders ----------------------------------------------------------------
id hm >/dev/null 2>&1 || adduser --system --group --shell /bin/bash --home "$BASE" hm
install -d -o hm -g www-data -m 750 "$BASE"
install -d -o hm -g hm -m 700 "$BASE/.ssh" "$BASE/backups"
touch "$BASE/.ssh/authorized_keys"
grep -qxF "$DEPLOY_PUBKEY" "$BASE/.ssh/authorized_keys" || echo "$DEPLOY_PUBKEY" >> "$BASE/.ssh/authorized_keys"
chown hm:hm "$BASE/.ssh/authorized_keys"; chmod 600 "$BASE/.ssh/authorized_keys"

# hm may only reload its own two services
cat > /etc/sudoers.d/hamara-makaan <<'EOF'
hm ALL=(root) NOPASSWD: /usr/bin/systemctl reload-or-restart hamara-makaan@prod, /usr/bin/systemctl reload-or-restart hamara-makaan@dev
EOF
chmod 440 /etc/sudoers.d/hamara-makaan
visudo -cf /etc/sudoers.d/hamara-makaan

# --- Per-environment: folders, database, .env ---------------------------------------------
setup_env() {
    local t=$1 hosts=$2 origins=$3 redis_db=$4 workers=$5 extra=$6
    local db="hamara_makaan_$t" env_file="$BASE/$t/.env"
    install -d -o hm -g www-data -m 750 "$BASE/$t"
    install -d -o hm -g hm -m 755 "$BASE/$t/app"
    install -d -o hm -g www-data -m 2770 "$BASE/$t/media"

    if [ -f "$env_file" ]; then echo "Keeping existing $env_file"; return; fi
    local pw; pw="$(openssl rand -hex 24)"
    sudo -u postgres psql -q -v ON_ERROR_STOP=1 <<SQL
DO \$\$ BEGIN
  IF EXISTS (SELECT FROM pg_roles WHERE rolname = '$db') THEN ALTER ROLE $db LOGIN PASSWORD '$pw';
  ELSE CREATE ROLE $db LOGIN PASSWORD '$pw'; END IF;
END \$\$;
SQL
    sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname = '$db'" | grep -q 1 \
        || sudo -u postgres createdb -O "$db" -E UTF8 "$db"

    cat > "$env_file" <<EOF
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')
DJANGO_ALLOWED_HOSTS=$hosts
DJANGO_CSRF_TRUSTED_ORIGINS=$origins
USE_X_FORWARDED_FOR=true
DB_ENGINE=postgres
DB_NAME=$db
DB_USER=$db
DB_PASSWORD=$pw
DB_HOST=127.0.0.1
DB_PORT=5432
REDIS_URL=redis://127.0.0.1:6379/$redis_db
MEDIA_ROOT=$BASE/$t/media
WEB_CONCURRENCY=$workers
DEFAULT_FROM_EMAIL=no-reply@hamaramakaan.com
# Fill these in, then: sudo systemctl restart hamara-makaan@$t
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
LEAD_NOTIFICATION_EMAILS=
$extra
EOF
    chown hm:hm "$env_file"; chmod 600 "$env_file"
    echo "Created $env_file and database $db"
}

setup_env prod "hamaramakaan.com,www.hamaramakaan.com" \
    "https://hamaramakaan.com,https://www.hamaramakaan.com" 1 3 ""
# Dev prints emails to the log instead of sending them to real staff
setup_env dev "dev.hamaramakaan.com" "https://dev.hamaramakaan.com" 2 2 \
    "EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend"

# --- systemd ------------------------------------------------------------------------------
install -m 644 "$HERE/systemd/hamara-makaan@.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable hamara-makaan@prod hamara-makaan@dev   # started by the first deploy

# --- Nginx --------------------------------------------------------------------------------
install -m 644 "$HERE"/nginx/*.conf /etc/nginx/sites-available/
# Until PROD_LIVE=1, hamaramakaan.com is forwarded to the old server and our code runs only on dev
if [ "${PROD_LIVE:-0}" = 1 ]; then MAIN_SITE=hamaramakaan.conf; else MAIN_SITE=hamaramakaan-old-site.conf; fi
rm -f /etc/nginx/sites-enabled/hamaramakaan.conf /etc/nginx/sites-enabled/hamaramakaan-old-site.conf
ln -s "/etc/nginx/sites-available/$MAIN_SITE" /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/dev.hamaramakaan.conf /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
CREDS=/root/hamaramakaan-credentials.txt
if [ ! -f /etc/nginx/hamaramakaan-dev.htpasswd ]; then
    DEV_PW="$(openssl rand -base64 18)"
    htpasswd -bc /etc/nginx/hamaramakaan-dev.htpasswd hm "$DEV_PW"
    printf 'dev.hamaramakaan.com basic auth\n  user: hm\n  password: %s\n' "$DEV_PW" > "$CREDS"
    chmod 600 "$CREDS"
fi
chown root:www-data /etc/nginx/hamaramakaan-dev.htpasswd; chmod 640 /etc/nginx/hamaramakaan-dev.htpasswd
nginx -t
systemctl reload nginx

# --- HTTPS --------------------------------------------------------------------------------
if [ -n "$CERTBOT_EMAIL" ]; then
    # Separate certificates, so dev still gets HTTPS while @/www DNS points at the old server
    for domains in "-d dev.hamaramakaan.com" "-d hamaramakaan.com -d www.hamaramakaan.com"; do
        # shellcheck disable=SC2086
        certbot --nginx --non-interactive --agree-tos --redirect -m "$CERTBOT_EMAIL" $domains \
            || echo "!! certbot failed for: $domains (check that DNS points here, then re-run)"
    done
fi

echo
echo "Done. Dev site password is in $CREDS"
echo "Next: add the GitHub secrets and push to 'dev' / 'main' (see docs/deployment.md)."
