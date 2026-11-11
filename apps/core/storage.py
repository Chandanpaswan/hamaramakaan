"""
Django storage backend for Vercel Blob (public store), using only the standard library.

Activated automatically when BLOB_READ_WRITE_TOKEN is set (see settings). Protocol mirrors the
official @vercel/blob client (API version 13):
  PUT  https://vercel.com/api/blob/?pathname=<name>   -> upload
  POST https://vercel.com/api/blob/delete {"urls": []} -> delete
Public files are served from https://<storeId>.public.blob.vercel-storage.com/<pathname>.
"""
import json
import mimetypes
import os
import urllib.error
import urllib.parse
import urllib.request

from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import ContentFile
from django.contrib.staticfiles.storage import StaticFilesStorage
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


class VersionedStaticFilesStorage(StaticFilesStorage):
    """Appends ?v=<git commit> to static URLs (Vercel has no collectstatic/manifest step)."""

    # shortcut: images referenced inside CSS url() are not versioned, rename the file when one changes.

    def url(self, name):
        url = super().url(name)
        version = os.environ.get("VERCEL_GIT_COMMIT_SHA", "")[:8]
        return f"{url}?v={version}" if version else url

API_URL = os.environ.get("VERCEL_BLOB_API_URL", "https://vercel.com/api/blob")
API_VERSION = "13"


@deconstructible
class VercelBlobStorage(Storage):
    def __init__(self, token=None, timeout=30):
        self.token = token or os.environ.get("BLOB_READ_WRITE_TOKEN", "")
        self.timeout = timeout
        if not self.token:
            raise ImproperlyConfigured("BLOB_READ_WRITE_TOKEN is required for VercelBlobStorage.")
        # Token format: vercel_blob_rw_<storeId>_<secret>
        parts = self.token.split("_")
        self.store_id = parts[3] if len(parts) > 4 else ""
        if not self.store_id:
            raise ImproperlyConfigured("BLOB_READ_WRITE_TOKEN is not a valid read-write token.")

    # -- helpers ---------------------------------------------------------------------------
    def _headers(self, extra=None):
        headers = {
            "authorization": f"Bearer {self.token}",
            "x-api-version": API_VERSION,
            "x-vercel-blob-store-id": self.store_id,
        }
        headers.update(extra or {})
        return headers

    def _request(self, path, data, method, headers):
        req = urllib.request.Request(f"{API_URL}{path}", data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:300].decode("utf-8", "replace")
            raise OSError(f"Vercel Blob {method} failed ({exc.code}): {detail}") from exc
        return json.loads(body) if body else {}

    # -- Storage API -----------------------------------------------------------------------
    def _save(self, name, content):
        name = name.replace("\\", "/").lstrip("/")
        content.seek(0)
        data = content.read()
        content_type = getattr(content, "content_type", None) or mimetypes.guess_type(name)[0] or "application/octet-stream"
        query = urllib.parse.urlencode({"pathname": name})
        self._request(f"/?{query}", data, "PUT", self._headers({
            "x-vercel-blob-access": "public",
            "x-content-type": content_type,
            "x-add-random-suffix": "0",
            "x-allow-overwrite": "0",
            "x-cache-control-max-age": "31536000",
        }))
        return name

    def _open(self, name, mode="rb"):
        with urllib.request.urlopen(self.url(name), timeout=self.timeout) as resp:
            return ContentFile(resp.read(), name=name)

    def delete(self, name):
        if not name:
            return
        body = json.dumps({"urls": [self.url(name)]}).encode()
        self._request("/delete", body, "POST", self._headers({"content-type": "application/json"}))

    def exists(self, name):
        # Upload names are random UUIDs (see core.utils.safe_upload_path); overwrites are refused server-side.
        return False

    def size(self, name):
        req = urllib.request.Request(self.url(name), method="HEAD")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return int(resp.headers.get("content-length", 0))

    def url(self, name):
        path = urllib.parse.quote(name.replace("\\", "/").lstrip("/"))
        return f"https://{self.store_id}.public.blob.vercel-storage.com/{path}"
