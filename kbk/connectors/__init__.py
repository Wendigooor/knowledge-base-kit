"""Connectors for KBK v2 — ingest from external sources."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class SourceEvent:
    """A change event from an external source."""
    source_type: str       # confluence | jira | git | slack
    event_type: str        # created | updated | deleted
    source_url: str        # URL to the original
    raw_content: str       # Raw content from the source
    metadata: dict         # Source-specific metadata (author, project, etc.)
    occurred_at: str       # When the change happened


class BaseConnector(ABC):
    """Abstract connector for external knowledge sources."""

    @abstractmethod
    def poll(self) -> list[SourceEvent]:
        """Poll for new changes since last check. Called by cron."""
        ...

    @abstractmethod
    def handle_webhook(self, payload: dict) -> Optional[SourceEvent]:
        """Handle an incoming webhook event. Returns None if not relevant."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Connector name (confluence, jira, etc.)."""
        ...

    @property
    @abstractmethod
    def status(self) -> dict:
        """Connector status: last_poll, events_processed, errors."""
        ...
