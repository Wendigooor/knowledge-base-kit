"""Document model for Knowledge Base Kit v2 — Enterprise Semantic Index."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class IndexedDocument:
    """Represents an indexed document from an external source.

    KBK does NOT store full content. It stores an LLM-generated summary
    plus metadata pointing to the original source (Confluence, Jira, Git, etc.).

    Attributes:
        id: Hash of source_url + source_version (immutable identifier).
        summary: LLM-generated summary (100-200 tokens) of the original content.
        tags: LLM-classified tags for categorization.
        metadata: source_url, source_type, access_group, original_title.
        collection: Logical group — architecture | infrastructure | business | runbooks.
        created_at: When first indexed.
        updated_at: When last updated in the original source.
        chunk_count: Number of vector chunks in ChromaDB.
    """
    id: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    collection: str = "unclassified"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    chunk_count: int = 0

    def __post_init__(self) -> None:
        if not self.id and "source_url" in self.metadata:
            raw = f"{self.metadata['source_url']}:{self.updated_at}"
            self.id = hashlib.sha256(raw.encode()).hexdigest()[:16]
        if not self.id:
            self.id = hashlib.sha256(
                f"{datetime.now(timezone.utc).isoformat()}:{id(self)}".encode()
            ).hexdigest()[:16]

    @property
    def source_url(self) -> str:
        return self.metadata.get("source_url", "")

    @property
    def source_type(self) -> str:
        return self.metadata.get("source_type", "unknown")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "summary": self.summary,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
            "collection": self.collection,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "chunk_count": self.chunk_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IndexedDocument":
        safe = {
            "id": data.get("id", ""),
            "summary": data.get("summary", ""),
            "tags": data.get("tags", []),
            "metadata": data.get("metadata", {}),
            "collection": data.get("collection", "unclassified"),
            "created_at": data.get("created_at", datetime.now(timezone.utc).isoformat()),
            "updated_at": data.get("updated_at", datetime.now(timezone.utc).isoformat()),
            "chunk_count": data.get("chunk_count", 0),
        }
        return cls(**safe)

    def __repr__(self) -> str:
        return f"IndexedDocument(id={self.id!r}, collection={self.collection!r}, tags={self.tags})"
