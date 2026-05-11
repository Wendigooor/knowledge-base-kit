"""Knowledge Base Kit — инструмент для управления персональными базами знаний.

Пакет предоставляет:
- Хранение и индексацию документов через ChromaDB
- Версионирование документов с историей изменений
- Синхронизацию через Git
- CLI интерфейс для повседневных задач
"""

__version__ = "0.1.0"
__author__ = "Ihar Zvezdzin"

from kbk.config import load_config, KBKConfig
from kbk.document import Document
from kbk.store import KnowledgeStore
from kbk.versioning import VersionManager
from kbk.sync import SyncManager

__all__ = [
    "load_config",
    "KBKConfig",
    "Document",
    "KnowledgeStore",
    "VersionManager",
    "SyncManager",
]
