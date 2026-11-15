#!/usr/bin/env bash
# Runs on the VPS as user `hm` after CI has rsynced the code into /srv/hamara_makaan/<env>/app.
# Usage: release.sh prod|dev [git-sha]
set -euo pipefail

TARGET="${1:-}"
SHA="${2:-unknown}"
case "$TARGET" in prod|dev) ;; *) echo "usage: $0 prod|dev [sha]" >&2; exit 2 ;; esac

ROOT=/srv/hamara_makaan/$TARGET
VENV=$ROOT/venv
PY=$VENV/bin/python
cd "$ROOT/app"

[ -x "$PY" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --disable-pip-version-check -r requirements/production.txt

set -a; . "$ROOT/.env"; set +a
export DJANGO_SETTINGS_MODULE=config.settings.production

# Back up production before migrations touch it (keeps the last 10)
if [ "$TARGET" = prod ]; then
    mkdir -p /srv/hamara_makaan/backups
    PGPASSWORD="$DB_PASSWORD" pg_dump -h "$DB_HOST" -U "$DB_USER" "$DB_NAME" \
        | gzip > "/srv/hamara_makaan/backups/pre-deploy-$(date +%Y%m%d-%H%M%S)-${SHA:0:8}.sql.gz"
    ls -1t /srv/hamara_makaan/backups/pre-deploy-*.sql.gz | tail -n +11 | xargs -r rm --
fi

"$PY" manage.py migrate --noinput
"$PY" manage.py collectstatic --noinput -v 0
[ -n "${REDIS_URL:-}" ] || "$PY" manage.py createcachetable
echo "$SHA" > REVISION

sudo /usr/bin/systemctl reload-or-restart "hamara-makaan@$TARGET"

# Smoke test straight through the Gunicorn socket (bypasses Nginx / basic auth)
HOST="${DJANGO_ALLOWED_HOSTS%%,*}"
for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -fsS -o /dev/null --unix-socket "/run/hamara-makaan-$TARGET/gunicorn.sock" \
            -H "Host: $HOST" -H "X-Forwarded-Proto: https" http://localhost/robots.txt; then
        echo "Deployed ${SHA:0:8} to $TARGET ($HOST)"
        exit 0
    fi
    sleep 2
done
echo "Smoke test failed; see: journalctl -u hamara-makaan@$TARGET -n 100" >&2
exit 1
