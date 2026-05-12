"""State tracker for KBK — SHA-256 hash-based dedup."""
from __future__ import annotations
import json
import hashlib
from pathlib import Path
from typing import Optional


class StateTracker:
    """Tracks content hashes to avoid re-indexing unchanged documents.

    Each source document is identified by its URL.
    If the SHA-256 hash matches the stored hash, the document is skipped.
    """

    def __init__(self, state_path: str):
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def _save(self):
        self.path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def has_changed(self, url: str, content_hash: str) -> bool:
        """Check if a document has changed since last index.
        
        Returns True if the document should be (re)indexed.
        """
        existing = self._data.get(url)
        if existing is None:
            return True
        return existing.get("hash") != content_hash

    def mark_indexed(self, url: str, content_hash: str, chunk_ids: list[str] = None):
        """Mark a document as indexed with its content hash."""
        self._data[url] = {
            "hash": content_hash,
            "chunk_ids": chunk_ids or [],
        }
        self._save()

    def remove(self, url: str):
        """Remove a document from the tracker (e.g., if deleted at source)."""
        self._data.pop(url, None)
        self._save()

    def get_chunk_ids(self, url: str) -> list[str]:
        """Get stored chunk IDs for a document."""
        entry = self._data.get(url)
        return entry.get("chunk_ids", []) if entry else []

    def all_urls(self) -> list[str]:
        """Return all tracked URLs."""
        return list(self._data.keys())

    @staticmethod
    def hash_content(content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @property
    def stats(self) -> dict:
        return {"tracked_docs": len(self._data), "path": str(self.path)}
