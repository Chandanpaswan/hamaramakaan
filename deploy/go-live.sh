#!/usr/bin/env bash
# Switch https://hamaramakaan.com from the old site to this Django app, with HTTPS.
# Run as root on the VPS after server-setup.sh and a deploy of `main`:
#   CERTBOT_EMAIL=you@example.com bash /srv/hamara_makaan/prod/app/deploy/go-live.sh
# Safe to re-run. Other sites on this server (e.g. hamaramakaanproperties.com) are not touched.
set -euo pipefail

BASE=/srv/hamara_makaan
APP=$BASE/prod/app
HERE="$(cd "$(dirname "$0")" && pwd)"
fail() { echo "!! $*" >&2; exit 1; }
[ "$(id -u)" = 0 ] || fail "Run as root"

# --- Prerequisites ------------------------------------------------------------------------
id hm >/dev/null 2>&1 && [ -f "$BASE/prod/.env" ] \
    || fail "server-setup.sh has not been run yet (see docs/deployment.md, step 3)"
[ -f "$APP/manage.py" ] \
    || fail "No code in $APP. Deploy main first: GitHub -> Actions -> CI / Deploy -> Run workflow (branch main)"

# --- App: venv, migrate, collectstatic, start gunicorn, smoke test ------------------------
sudo -u hm bash "$APP/deploy/release.sh" prod "$(cat "$APP/REVISION" 2>/dev/null || echo manual)" \
    || { journalctl -u hamara-makaan@prod -n 40 --no-pager; fail "App failed to start (log above)"; }

# --- Nginx: serve the app instead of forwarding to the old server -------------------------
install -m 644 "$HERE/nginx/hamaramakaan.conf" /etc/nginx/sites-available/hamaramakaan.conf
rm -f /etc/nginx/sites-enabled/hamaramakaan-old-site.conf
ln -sf /etc/nginx/sites-available/hamaramakaan.conf /etc/nginx/sites-enabled/hamaramakaan.conf
# Another site claiming our name would make nginx pick the wrong one
others=$(grep -lE "server_name[^;]*[[:space:]](www\.)?hamaramakaan\.com[[:space:];]" /etc/nginx/sites-enabled/* \
         | grep -v -e hamaramakaan.conf -e dev.hamaramakaan.conf || true)
[ -z "$others" ] || fail "These nginx sites also claim hamaramakaan.com, remove that name from them: $others"
nginx -t
systemctl reload nginx

# --- HTTPS (certbot adds the 443 block to hamaramakaan.conf) ------------------------------
if [ -n "${CERTBOT_EMAIL:-}" ]; then acct=(-m "$CERTBOT_EMAIL"); else acct=(--register-unsafely-without-email); fi
certbot --nginx --non-interactive --agree-tos --redirect --expand "${acct[@]}" \
    -d hamaramakaan.com -d www.hamaramakaan.com
nginx -t
systemctl reload nginx

# --- Verify through nginx, the way a browser sees it --------------------------------------
code=$(curl -s -o /dev/null -w '%{http_code}' --resolve hamaramakaan.com:443:127.0.0.1 https://hamaramakaan.com/robots.txt)
[ "$code" = 200 ] || fail "https://hamaramakaan.com/robots.txt returned $code"
echo "Live: https://hamaramakaan.com"
