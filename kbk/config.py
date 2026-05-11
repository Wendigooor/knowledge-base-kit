"""Configuration module for Knowledge Base Kit.

Loads and validates YAML/JSON configuration files.
Default config path: ~/.config/kbk/config.yaml
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class KBKConfig:
    """Main configuration dataclass for the knowledge base."""

    # Path to ChromaDB persistent storage
    db_path: str = os.path.expanduser("~/.kbk/chromadb")

    # Path to Git repository for sync
    repo_path: str = os.path.expanduser("~/.kbk/repo")

    # Default collection name
    default_collection: str = "default"

    # ChromaDB embedding model
    embedding_model: str = "all-MiniLM-L6-v2"

    # Number of search results by default
    top_k: int = 5

    # Versioning: max snapshots per document
    max_versions_per_doc: int = 50

    # Git sync settings
    git_remote_url: Optional[str] = None
    git_branch: str = "main"
    git_auto_push: bool = False

    # ChromaDB client settings
    chroma_settings: dict = field(default_factory=lambda: {
        "anonymized_telemetry": False,
    })
    # Versioning snapshot storage
    versions_dir: str = os.path.expanduser("~/.kbk/versions")

    # Default export path
    export_path: str = os.path.expanduser("~/.kbk/exports")

    @classmethod
    def load(cls, path: Optional[str] = None) -> "KBKConfig":
        """Load configuration from file or return defaults.

        Args:
            path: Explicit path to config file. If None, searches standard locations.

        Returns:
            KBKConfig instance with loaded or default values.
        """
        return load_config(path)


    @classmethod
    def from_dict(cls, data: dict) -> "KBKConfig":
        """Create config from dictionary, ignoring unknown keys."""
        valid_keys = set(cls.__dataclass_fields__.keys())
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

    def to_dict(self) -> dict:
        """Export config as dictionary."""
        result = {}
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            if isinstance(value, Path):
                value = str(value)
            result[field_name] = value
        return result


def _find_config_file() -> Optional[Path]:
    """Search for config file in standard locations."""
    candidates = [
        Path.cwd() / "kbk.yaml",
        Path.cwd() / "kbk.yml",
        Path.cwd() / "kbk.json",
        Path.cwd() / ".kbk.yaml",
        Path.cwd() / ".kbk.yml",
        Path.cwd() / ".kbk.json",
        Path.home() / ".config" / "kbk" / "config.yaml",
        Path.home() / ".config" / "kbk" / "config.yml",
        Path.home() / ".config" / "kbk" / "config.json",
        Path.home() / ".kbk" / "config.yaml",
        Path.home() / ".kbk" / "config.yml",
        Path.home() / ".kbk" / "config.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def load_config(path: Optional[str] = None) -> KBKConfig:
    """Load configuration from file or return defaults.

    Args:
        path: Explicit path to config file. If None, searches standard locations.

    Returns:
        KBKConfig instance with loaded or default values.

    Raises:
        FileNotFoundError: If explicit path is given but does not exist.
        ValueError: If file format is not recognised (.yaml/.yml/.json).
    """
    if path is not None:
        config_file = Path(path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
    else:
        found = _find_config_file()
        if found is None:
            return KBKConfig()
        config_file = found

    suffix = config_file.suffix.lower()
    raw = config_file.read_text(encoding="utf-8")

    if suffix in (".yaml", ".yml"):
        data = yaml.safe_load(raw)
    elif suffix == ".json":
        data = json.loads(raw)
    else:
        raise ValueError(f"Unsupported config format: {suffix}")

    if not isinstance(data, dict):
        return KBKConfig()

    return KBKConfig.from_dict(data)


def save_config(config: KBKConfig, path: str) -> None:
    """Save configuration to a YAML file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = config.to_dict()
    target.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8")
