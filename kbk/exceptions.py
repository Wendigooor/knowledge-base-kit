"""Custom exceptions for Knowledge Base Kit."""

from __future__ import annotations


class KBKError(Exception):
    """Base exception for all KBK errors."""


class DocumentError(KBKError):
    """Raised on document-related errors (validation, not found, etc.)."""


class StoreError(KBKError):
    """Raised on storage-level errors (ChromaDB failures, connection issues)."""


class VersioningError(KBKError):
    """Raised on version-related errors (missing snapshot, corrupt history)."""


class SyncError(KBKError):
    """Raised on synchronisation errors (git failure, merge conflict)."""


class ConfigError(KBKError):
    """Raised on configuration loading/validation errors."""


class ConflictError(SyncError):
    """Raised when a synchronisation conflict cannot be auto-resolved."""
