"""Document model for Knowledge Base Kit.

Defines the Document dataclass used throughout the system.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Document:
    """Represents a single knowledge document.

    Attributes:
        id: Unique document identifier.
        version: Current version number (starts at 1).
        tags: List of tags for categorisation.
        metadata: Arbitrary key-value metadata.
        content: The main text content of the document.
        collection: Name of the ChromaDB collection this doc belongs to.
        created_at: ISO-8601 timestamp of creation.
        updated_at: ISO-8601 timestamp of last update.
        previous_versions: Ordered list of historical snapshots.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: int = 1
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    content: str = ""
    collection: str = "default"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    previous_versions: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate document fields after initialisation."""
        if not self.id:
            self.id = str(uuid.uuid4())
        if self.version < 1:
            raise ValueError("Version must be >= 1")
        if not isinstance(self.tags, list):
            raise TypeError("tags must be a list")
        if not isinstance(self.metadata, dict):
            raise TypeError("metadata must be a dict")

    def update(
        self,
        content: Optional[str] = None,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
        increment_version: bool = True,
    ) -> "Document":
        """Create a new version of this document.

        Saves the current state into previous_versions before applying changes.

        Args:
            content: New content (or None to keep current).
            tags: New tags (or None to keep current).
            metadata: New metadata (or None to keep current).
            increment_version: Whether to bump version number.

        Returns:
            Self for chaining.
        """
        snapshot = {
            "version": self.version,
            "content": self.content,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
            "updated_at": self.updated_at,
        }
        self.previous_versions.append(snapshot)

        if content is not None:
            self.content = content
        if tags is not None:
            self.tags = list(tags)
        if metadata is not None:
            self.metadata = dict(metadata)

        if increment_version:
            self.version += 1

        self.updated_at = datetime.now(timezone.utc).isoformat()
        return self

    def to_dict(self) -> dict:
        """Convert document to a JSON-serialisable dictionary."""
        return {
            "id": self.id,
            "version": self.version,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
            "content": self.content,
            "collection": self.collection,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "previous_versions": list(self.previous_versions),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Document":
        """Create a Document from a dictionary.

        Handles both full and partial data gracefully.
        """
        safe = {
            "id": data.get("id", str(uuid.uuid4())),
            "version": data.get("version", 1),
            "tags": data.get("tags", []),
            "metadata": data.get("metadata", {}),
            "content": data.get("content", ""),
            "collection": data.get("collection", "default"),
            "created_at": data.get(
                "created_at", datetime.now(timezone.utc).isoformat()
            ),
            "updated_at": data.get(
                "updated_at", datetime.now(timezone.utc).isoformat()
            ),
            "previous_versions": data.get("previous_versions", []),
        }
        return cls(**safe)

    @property
    def summary(self) -> str:
        """Short summary string for display."""
        preview = self.content[:80].replace("\n", " ").strip()
        if len(self.content) > 80:
            preview += "…"
        return f"[v{self.version}] {preview}"

    def __repr__(self) -> str:
        return (
            f"Document(id={self.id!r}, version={self.version}, "
            f"collection={self.collection!r}, tags={self.tags})"
        )
