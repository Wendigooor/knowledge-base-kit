"""Data models for KBK v0.2."""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class IndexedChunk:
    """A semantically indexed chunk from an enterprise source.

    Stores cleaned text + LLM summary + source pointer.
    No full content — just distilled meaning.
    """
    id: str = ""
    source_url: str = ""
    content: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    access_group: str = "public"
    content_hash: str = ""
    collection: str = "unclassified"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self):
        if not self.id and self.source_url:
            raw = f"{self.source_url}:{self.content_hash or self.updated_at}"
            self.id = hashlib.sha256(raw.encode()).hexdigest()[:16]
        if not self.id:
            self.id = hashlib.sha256(
                f"{datetime.now(timezone.utc).isoformat()}:{id(self)}".encode()
            ).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "id": self.id, "source_url": self.source_url,
            "content": self.content, "summary": self.summary,
            "tags": self.tags, "access_group": self.access_group,
            "content_hash": self.content_hash, "collection": self.collection,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IndexedChunk":
        safe = {k: data.get(k, "") for k in
                ["id", "source_url", "content", "summary", "content_hash", "collection",
                 "created_at", "updated_at", "access_group"]}
        safe["tags"] = data.get("tags", [])
        return cls(**safe)


@dataclass
class SourceTarget:
    """A whitelisted source to index."""
    type: str  # confluence | gitlab
    location: str  # space key | repo path
    filter_query: str = ""  # CQL for confluence, path for gitlab
    access_group: str = "public"
