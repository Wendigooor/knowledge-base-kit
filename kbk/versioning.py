"""Versioning subsystem for Knowledge Base Kit.

Handles snapshot creation, history tracking, rollback, and diff operations.
"""

from __future__ import annotations

import difflib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from kbk.document import Document
from kbk.exceptions import VersioningError


class VersionManager:
    """Manages document versioning with snapshot persistence.

    Snapshots are stored as individual JSON files in a dedicated
    `.kbk/versions/` directory, keyed by document ID.
    """

    def __init__(self, versions_dir: Optional[str] = None):
        """Initialise the version manager.

        Args:
            versions_dir: Path to the directory where version snapshots
                          are stored. Defaults to ~/.kbk/versions/.
        """
        self.versions_dir = Path(
            versions_dir or Path.home() / ".kbk" / "versions"
        )
        self.versions_dir.mkdir(parents=True, exist_ok=True)

    def _snapshot_path(self, doc_id: str) -> Path:
        """Return the path to a document's snapshot file."""
        return self.versions_dir / f"{doc_id}.json"

    def save_snapshot(self, document: Document) -> None:
        """Save the current state of a document as a version snapshot.

        The entire document (including previous_versions) is persisted
        so full rollback is always possible.

        Args:
            document: Document instance to snapshot.
        """
        path = self._snapshot_path(document.id)
        data = document.to_dict()
        data["_snapshot_timestamp"] = datetime.now(timezone.utc).isoformat()
        try:
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            raise VersioningError(
                f"Failed to save snapshot for {document.id}: {exc}"
            ) from exc

    def get_history(self, doc_id: str) -> list[dict]:
        """Retrieve the full version history for a document.

        Returns:
            List of version entries, each containing version number,
            timestamp, and a preview of the content.

        Raises:
            VersioningError: If no history exists for this document.
        """
        path = self._snapshot_path(doc_id)
        if not path.exists():
            raise VersioningError(
                f"No version history found for document '{doc_id}'"
            )

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise VersioningError(
                f"Corrupt snapshot file for {doc_id}: {exc}"
            ) from exc

        history = []

        # Current version
        history.append({
            "version": data.get("version", "?"),
            "updated_at": data.get("updated_at", "unknown"),
            "preview": data.get("content", "")[:100],
            "is_current": True,
        })

        # Previous versions (from newest to oldest)
        for prev in reversed(data.get("previous_versions", [])):
            history.append({
                "version": prev.get("version", "?"),
                "updated_at": prev.get("updated_at", "unknown"),
                "preview": prev.get("content", "")[:100],
                "is_current": False,
            })

        return history

    def rollback(
        self,
        document: Document,
        target_version: int,
    ) -> Document:
        """Roll back a document to a previous version.

        The current state is saved into previous_versions before rollback.

        Args:
            document: The current Document instance.
            target_version: Version number to restore.

        Returns:
            A new Document instance with the rolled-back state.

        Raises:
            VersioningError: If target version is not found in history.
        """
        if target_version == document.version:
            return document  # Already at this version

        # Snapshot current state before rollback
        snapshot = {
            "version": document.version,
            "content": document.content,
            "tags": list(document.tags),
            "metadata": dict(document.metadata),
            "updated_at": document.updated_at,
        }

        # Check previous versions for the target
        for prev in document.previous_versions:
            if prev.get("version") == target_version:
                # Build the rollback document
                rolled = Document(
                    id=document.id,
                    version=target_version,
                    tags=prev.get("tags", []),
                    metadata=prev.get("metadata", {}),
                    content=prev.get("content", ""),
                    collection=document.collection,
                    created_at=document.created_at,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    previous_versions=list(document.previous_versions) + [snapshot],
                )
                return rolled

        raise VersioningError(
            f"Version {target_version} not found in history of document "
            f"'{document.id}'. Available versions: "
            f"{[v['version'] for v in document.previous_versions]}"
        )

    def diff(
        self,
        doc_id: str,
        version_a: int,
        version_b: int,
    ) -> str:
        """Compute a unified diff between two versions of a document.

        Args:
            doc_id: Document identifier.
            version_a: First version number.
            version_b: Second version number.

        Returns:
            Unified diff string, or a message if versions are identical.

        Raises:
            VersioningError: If either version cannot be found.
        """
        path = self._snapshot_path(doc_id)
        if not path.exists():
            raise VersioningError(
                f"No snapshot found for document '{doc_id}'"
            )

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise VersioningError(
                f"Corrupt snapshot for {doc_id}: {exc}"
            ) from exc

        # Build version -> content mapping
        versions: dict[int, str] = {}

        current_ver = data.get("version", 0)
        current_content = data.get("content", "")
        versions[current_ver] = current_content

        for prev in data.get("previous_versions", []):
            v = prev.get("version")
            c = prev.get("content", "")
            versions[v] = c

        if version_a not in versions:
            raise VersioningError(
                f"Version {version_a} not found for document '{doc_id}'"
            )
        if version_b not in versions:
            raise VersioningError(
                f"Version {version_b} not found for document '{doc_id}'"
            )

        content_a = versions[version_a]
        content_b = versions[version_b]

        if content_a == content_b:
            return "Contents are identical."

        diff_lines = difflib.unified_diff(
            content_a.splitlines(keepends=True),
            content_b.splitlines(keepends=True),
            fromfile=f"v{version_a}",
            tofile=f"v{version_b}",
            lineterm="",
        )
        return "".join(diff_lines)

    def prune(self, doc_id: str, max_versions: int = 50) -> int:
        """Remove oldest snapshots beyond max_versions.

        Args:
            doc_id: Document identifier.
            max_versions: Maximum number of versions to keep.

        Returns:
            Number of versions pruned.
        """
        path = self._snapshot_path(doc_id)
        if not path.exists():
            return 0

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return 0

        prev = data.get("previous_versions", [])
        if len(prev) <= max_versions:
            return 0

        # Keep the most recent max_versions entries
        to_remove = len(prev) - max_versions
        data["previous_versions"] = prev[to_remove:]
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return to_remove
