"""State tracker for KBK — SHA-256 hash-based dedup."""
from __future__ import annotations
import fcntl
import json
import hashlib
import logging
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger("kbk.state")

_DEFAULT_INDENT = 2


class StateTracker:
    """Tracks content hashes to avoid re-indexing unchanged documents.

    Each source document is identified by its URL.
    If the SHA-256 hash matches the stored hash, the document is skipped.

    Uses atomic write (temp file + replace) to prevent corruption.
    Backs up corrupt state files before resetting.
    Uses POSIX file locking (fcntl.flock) to prevent concurrent
    write conflicts from parallel kbk sync processes.
    """

    def __init__(self, state_path: str):
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict] = {}
        self._dirty = False  # Track unsaved changes for batch mode
        self._lock_file = self.path.with_suffix(".lock")
        self._lock_fd = None
        self._load()

    def acquire_lock(self, blocking: bool = True) -> bool:
        """Acquire an exclusive lock on the state file.

        Prevents concurrent kbk sync processes from corrupting state.
        Returns True if lock acquired, False if non-blocking and busy.
        """
        try:
            self._lock_fd = self._lock_file.open("w")
            flags = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
            fcntl.flock(self._lock_fd, flags)
            return True
        except (IOError, OSError, BlockingIOError):
            self._lock_fd = None
            return False

    def release_lock(self):
        """Release the file lock."""
        if self._lock_fd is not None:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                self._lock_fd.close()
            except (IOError, OSError):
                pass
            finally:
                self._lock_fd = None
        try:
            self._lock_file.unlink(missing_ok=True)
        except OSError:
            pass

    def _load(self):
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Corrupt state file %s: %s. Resetting.", self.path, exc)
                backup = self.path.with_suffix(".corrupt.bak")
                try:
                    shutil.copy2(self.path, backup)
                    logger.warning("Backup saved to %s", backup)
                except OSError:
                    logger.warning("Could not back up corrupt state file.")
                self._data = {}
        else:
            self._data = {}

    def _save(self):
        """Atomic write: write to temp file, then rename.

        Must be called while holding the lock (acquire_lock).
        """
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._data, indent=_DEFAULT_INDENT, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp.replace(self.path)
        self._dirty = False

    def has_changed(self, url: str, content_hash: str) -> bool:
        """Check if a document has changed since last index.

        Returns True if the document should be (re)indexed.
        """
        existing = self._data.get(url)
        if existing is None:
            return True
        return existing.get("hash") != content_hash

    def mark_indexed(self, url: str, content_hash: str, chunk_ids: list[str] = None):
        """Mark a document as indexed with its content hash.

        Must be called while holding the lock.
        """
        self._data[url] = {
            "hash": content_hash,
            "chunk_ids": chunk_ids or [],
        }
        self._dirty = True
        self._save()

    def remove(self, url: str):
        """Remove a document from the tracker (e.g., if deleted at source).

        Must be called while holding the lock.
        """
        self._data.pop(url, None)
        self._dirty = True
        self._save()

    def batch_save(self):
        """Explicit final save after batch operations."""
        if self._dirty:
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
