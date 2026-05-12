"""Confluence connector for KBK — pull-based, with rate limiting and diffing."""
from __future__ import annotations
import json
import time
import urllib.request
import base64
from typing import Optional

from kbk.models import SourceTarget, IndexedChunk
from kbk.state import StateTracker


class ConfluenceConnector:
    """Pulls pages from Confluence spaces via REST API.

    Uses exponential backoff for rate limits.
    Only fetches pages matching the target's CQL filter.
    """

    def __init__(self, base_url: str, token: str, state: StateTracker):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.state = state

    def _headers(self) -> dict:
        auth = base64.b64encode(f"{self.token}:".encode()).decode()
        return {
            "Authorization": f"Basic {auth}",
            "Accept": "application/json",
        }

    def _request(self, path: str, retries: int = 3) -> Optional[dict]:
        url = f"{self.base_url}/rest/api{path}"
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers=self._headers())
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < retries - 1:
                    wait = 2 ** (attempt + 1)
                    time.sleep(wait)
                    continue
                return None
            except Exception:
                return None
        return None

    def fetch_pages(self, target: SourceTarget) -> list[dict]:
        """Fetch pages from a Confluence space using CQL filter."""
        cql = f"space={target.location}"
        if target.filter_query:
            cql += f" AND {target.filter_query}"
        cql_enc = urllib.parse.quote(cql)

        pages = []
        start = 0
        limit = 50

        while True:
            resp = self._request(
                f"/content/search?cql={cql_enc}&start={start}&limit={limit}"
                f"&expand=body.storage,version"
            )
            if not resp or not resp.get("results"):
                break
            for r in resp["results"]:
                body = (r.get("body", {})
                        .get("storage", {})
                        .get("value", ""))
                version = r.get("version", {}).get("number", 1)
                pages.append({
                    "id": r["id"],
                    "title": r["title"],
                    "url": f"{self.base_url}/spaces/{target.location}/pages/{r['id']}",
                    "body": body,
                    "version": version,
                    "space": target.location,
                })
            if len(resp["results"]) < limit:
                break
            start += limit
        return pages

    def process_target(self, target: SourceTarget) -> list[IndexedChunk]:
        """Fetch pages for a target and determine which need re-indexing."""
        raw_pages = self.fetch_pages(target)
        result = []
        for page in raw_pages:
            content_hash = StateTracker.hash_content(page["body"])
            url = page["url"]
            if not self.state.has_changed(url, content_hash):
                continue
            result.append({
                "url": url,
                "title": page["title"],
                "body": page["body"],
                "content_hash": content_hash,
                "access_group": target.access_group,
                "space": page["space"],
            })
        return result
