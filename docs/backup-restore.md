# Backup & restore

Back up both the **database** (listings, leads, content, users) and the **media folder** (uploaded photos). Backups contain personal data, so store them encrypted and with restricted access.

## Nightly backup script

`/srv/hamara_makaan/backup.sh` (owned by `hm`, `chmod 700`):

```bash
#!/usr/bin/env bash
set -euo pipefail
STAMP=$(date +%Y%m%d-%H%M)
DEST=/srv/hamara_makaan/backups
mkdir -p "$DEST"
# Database (custom format: compressed, supports selective restore)
PGPASSWORD="$DB_PASSWORD" pg_dump -h localhost -U hamara_makaan -Fc hamara_makaan > "$DEST/db-$STAMP.dump"
# Media
tar -czf "$DEST/media-$STAMP.tar.gz" -C /srv/hamara_makaan media
# Keep 14 days locally
find "$DEST" -type f -mtime +14 -delete
# Copy off-server (e.g. rclone to encrypted object storage):
# rclone copy "$DEST" remote:hamara-makaan-backups --max-age 25h
```

Cron (`sudo -u hm crontab -e`):

```
30 2 * * * set -a; . /srv/hamara_makaan/app/hamara_makaan/.env; set +a; /srv/hamara_makaan/backup.sh >> /srv/hamara_makaan/backup.log 2>&1
```

## Restore

```bash
sudo systemctl stop hamara-makaan
# Database
sudo -u postgres dropdb hamara_makaan && sudo -u postgres createdb -O hamara_makaan hamara_makaan
PGPASSWORD=… pg_restore -h localhost -U hamara_makaan -d hamara_makaan --no-owner db-YYYYMMDD-HHMM.dump
# Media
sudo -u hm tar -xzf media-YYYYMMDD-HHMM.tar.gz -C /srv/hamara_makaan
sudo systemctl start hamara-makaan
```

## Test the restore

Before launch, and then every quarter:

1. Restore the latest backup onto staging.
2. Log in to the dashboard. Check that listings, photos, leads and blog posts are present.
3. Record the date and the result. Launch acceptance requires a tested restore.

## Local development (SQLite)

```bash
python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.permission -e sessions --indent 2 > backup.json
python manage.py loaddata backup.json
```

## Data retention

Agree a retention period for enquiries with the business, for example 24 months after the last contact. Archive or delete older leads, and update the Privacy Policy to match.
