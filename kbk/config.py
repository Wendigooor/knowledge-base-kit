"""Configuration for KBK v0.2."""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class KBKConfig:
    db_path: str = os.path.expanduser("~/.kbk/chromadb")
    state_path: str = os.path.expanduser("~/.kbk/state.json")
    targets_path: str = os.path.expanduser("~/.kbk/targets.yaml")
    default_collection: str = "default"
    top_k: int = 10
    chroma_settings: dict = field(default_factory=lambda: {"anonymized_telemetry": False})
    # LLM settings
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    # Confluence settings
    confluence_url: str = ""
    confluence_token: str = ""
    # GitLab settings
    gitlab_url: str = ""
    gitlab_token: str = ""
    # Showcase settings
    showcase_space: str = "KBK_INDEX"
    showcase_parent_page: str = ""

    @classmethod
    def load(cls, path: Optional[str] = None) -> "KBKConfig":
        return load_config(path)

    @classmethod
    def from_dict(cls, data: dict) -> "KBKConfig":
        valid_keys = set(cls.__dataclass_fields__.keys())
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)

    def to_dict(self) -> dict:
        return {f: getattr(self, f) for f in self.__dataclass_fields__}


def _find_config_file() -> Optional[Path]:
    candidates = [
        Path.cwd() / "kbk.yaml", Path.cwd() / "kbk.yml",
        Path.home() / ".config" / "kbk" / "config.yaml",
        Path.home() / ".kbk" / "config.yaml",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def load_config(path: Optional[str] = None) -> KBKConfig:
    if path is not None:
        config_file = Path(path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config not found: {path}")
    else:
        found = _find_config_file()
        if found is None:
            return KBKConfig()
        config_file = found
    raw = config_file.read_text(encoding="utf-8")
    data = yaml.safe_load(raw) if config_file.suffix in (".yaml", ".yml") else {}
    if not isinstance(data, dict):
        return KBKConfig()
    return KBKConfig.from_dict(data)


def load_targets(path: Optional[str] = None) -> list[dict]:
    """Load whitelisted sources from targets YAML."""
    from kbk.models import SourceTarget
    p = Path(path or KBKConfig().targets_path)
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return data.get("targets", [])
