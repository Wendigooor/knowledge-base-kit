"""KBK exceptions."""
from __future__ import annotations


class KBKError(Exception):
    """Base error for KBK."""


class StoreError(KBKError):
    """ChromaDB operation failed."""


class ConnectorError(KBKError):
    """Connector (Confluence/GitLab) operation failed."""


class LLMError(KBKError):
    """LLM API call failed (auth, rate limit, or network)."""


class AuthenticationError(KBKError):
    """API key or token is invalid/missing."""


class ConfigurationError(KBKError):
    """Config file is invalid or missing required field."""
