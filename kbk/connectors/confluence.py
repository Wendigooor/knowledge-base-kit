"""Confluence connector for KBK — pull-based, with rate limiting and diffing."""
from __future__ import annotations
import json
import time
import urllib.request
import urllib.parse
import base64
from typing import Optional

from kbk.models import SourceTarget
from kbk.state import StateTracker

_PAGE_LIMIT = 50
_RETRIES = 3
_TIMEOUT = 30


class ConfluenceConnector:
    """Pulls pages from Confluence spaces via REST API.

    Uses exponential backoff for rate limits.
    Only fetches pages matching the target's CQL filter.
    Safe pagination with limit-aware loop termination.
    Returns version number in metadata for debugging/showcase.
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

    def _request(self, path: str, retries: int = _RETRIES) -> Optional[dict]:
        url = f"{self.base_url}/rest/api{path}"
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers=self._headers())
                with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
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
        """Fetch pages from a Confluence space using CQL filter.

        Paginates safely: if API returns exactly PAGE_LIMIT results,
        there may be more pages. If fewer, stops immediately.
        Avoids one extra network call on exact page boundaries.
        """
        cql = f"space={target.location}"
        if target.filter_query:
            cql += f" AND {target.filter_query}"
        cql_enc = urllib.parse.quote(cql)

        pages = []
        start = 0

        while True:
            resp = self._request(
                f"/content/search?cql={cql_enc}&start={start}&limit={_PAGE_LIMIT}"
                f"&expand=body.storage,version"
            )
            if not resp:
                logger = __import__("logging").getLogger("kbk.confluence")
                logger.warning("Confluence API returned no data for %s (start=%d)", target.location, start)
                break

            results = resp.get("results", [])
            if not results:
                break

            for r in results:
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

            # If we got fewer than limit, no more pages
            if len(results) < _PAGE_LIMIT:
                break

            start += _PAGE_LIMIT

            # Safety cap: 10k pages max
            if start >= 10000:
                break

        return pages

    def process_target(self, target: SourceTarget) -> list[dict]:
        """Fetch pages for a target and determine which need re-indexing.

        Returns only new/changed documents with metadata including version.
        """
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
                "version": page.get("version", 1),
            })
        return result

    def list_known_urls(self, target: SourceTarget) -> set[str]:
        """Fetch ALL page URLs from Confluence (for orphan reconciliation).

        Returns the set of all page URLs matching the target's CQL.
        Used by cli.py sync to detect deleted pages.
        """
        cql = f"space={target.location}"
        if target.filter_query:
            cql += f" AND {target.filter_query}"
        cql_enc = urllib.parse.quote(cql)

        urls = set()
        start = 0

        while True:
            resp = self._request(
                f"/content/search?cql={cql_enc}&start={start}&limit={_PAGE_LIMIT}"
            )
            if not resp or not resp.get("results"):
                break
            for r in resp["results"]:
                urls.add(f"{self.base_url}/spaces/{target.location}/pages/{r['id']}")
            if len(resp["results"]) < _PAGE_LIMIT:
                break
            start += _PAGE_LIMIT
            if start >= 10000:
                break

        return urls
