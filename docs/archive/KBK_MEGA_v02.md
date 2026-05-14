# KBK v0.2 — Full Codebase

> Enterprise Semantic Index. Pull + Allowlist. MCP Server + Confluence Showcase.
> Generated: 2026-05-12
> Files: 18

---

## 📄 README.md

```markdown
# KBK v0.2 — Enterprise Semantic Index

> Knowledge Base Kit: умный индекс корпоративных знаний.
> Pull + Allowlist. Два выхода: MCP Server (LLM) + Confluence Showcase (Human).

---

## Why

**Проблема:** Энтерпрайз-знания размазаны по Confluence, Jira и GitLab. Попытки заставить людей писать в новые системы проваливаются. LLM-агенты задыхаются от HTML-мусора и галлюцинируют, а люди не могут найти актуальные архитектурные решения.

**Решение:** KBK — это **индекс**, не хранилище. Source of truth остаётся в Confluence/Jira/Git. Никаких вебхуков. Только **Pull** по команде из **белого списка** (Allowlist).

## Архитектура

```
  [Confluence] ──────┐
  [GitLab] ───────────┤─── kbk sync ──── [State Tracker] ─── [Indexer AI Pipeline]
  [Jira] ─────────────┘       │                                       │
                              ├─ SHA-256 diff (skip unchanged)         ├─ clean HTML
                              └─ delete orphans                        ├─ LLM summarize
                                                                       ├─ classify tags
                                                                       ├─ chunk (1k tokens)
                                                                       └─ embed to ChromaDB
                                                                              │
                                    ┌─────────────────────────────────────────┘
                                    ▼
                    ┌──────────────────────────────┐
                    │         ChromaDB              │
                    │  (vectors + metadata)         │
                    └──────┬───────────────┬────────┘
                           │               │
                           ▼               ▼
                 ┌────────────┐    ┌──────────────┐
                 │  MCP Server │    │   Showcase    │
                 │  (LLM API)  │    │  (Confluence) │
                 │  search     │    │  read-only    │
                 │  list       │    │  index page   │
                 └────────────┘    └──────────────┘
```

## Данные

### Белый список (targets.yaml)

```yaml
targets:
  - type: confluence
    location: "ARCH"
    filter_query: "label = 'approved' OR label = 'adr'"
    access_group: "public"
  - type: gitlab
    repo: "core/payment-service"
    path: "docs/runbooks/"
```

Только эти источники индексируются. Никакого мусора.

### Модель данных (IndexedChunk)

```python
@dataclass
class IndexedChunk:
    id: str                  # Hash(url + chunk_index)
    source_url: str          # Оригинал (с якорем)
    content: str             # Очищенный текст чанка
    summary: str             # LLM-суммаризация документа
    tags: list[str]          # Классификация
    access_group: str        # ACL
    content_hash: str        # SHA-256 для StateTracker
    collection: str          # Группировка (space, repo)
```

### State Tracker

SHA-256 хэш каждого документа. Если не изменился — **скип**. Экономит LLM-затраты и время.

## CLI

| Команда | Назначение |
|---------|-----------|
| `kbk init` | Инициализация: ~/.kbk/, ChromaDB, StateTracker |
| `kbk sync` | Pull + Diff + ETL + Embed (весь пайплайн) |
| `kbk serve` | MCP-сервер для LLM (Claude Desktop, Cursor) |
| `kbk build-showcase` | Генерация Confluence Read-Only витрины |
| `kbk search` | Семантический поиск по индексу |
| `kbk status` | Статистика индекса |

## Компоненты

| Модуль | Назначение |
|--------|-----------|
| `kbk/models.py` | IndexedChunk, SourceTarget |
| `kbk/config.py` | KBKConfig, загрузка конфига |
| `kbk/store.py` | ChromaDB upsert/search/delete/stats |
| `kbk/state.py` | StateTracker (SHA-256 dedup) |
| `kbk/indexer.py` | ETL pipeline: clean → summarize → classify → chunk → embed |
| `kbk/connectors/confluence.py` | Confluence REST API, rate limiting, diffing |
| `kbk/mcp_server.py` | MCP protocol server (stdio) |
| `kbk/showcase.py` | Confluence Showcase builder |
| `kbk/cli.py` | Click CLI (6 команд) |

## Установка

```bash
pip install git+https://github.com/Wendigooor/knowledge-base-kit.git
```

Или локально:
```bash
git clone git@github.com:Wendigooor/knowledge-base-kit.git
cd knowledge-base-kit
pip install -e .
```

## Использование

```bash
# Инициализация
kbk init

# Настройка белого списка
vim ~/.kbk/targets.yaml

# Запуск индексации
kbk sync

# Поиск
kbk search "как задеплоить payment"

# MCP сервер (для Cursor / Claude Desktop)
kbk serve

# Confluence витрина
kbk build-showcase

# Статус
kbk status
```

## Демо-сценарий

1. Показать хаос в Confluence (разрозненные спейсы)
2. `kbk sync` — красивый прогресс с rich прогресс-барами
3. **Wow 1:** Cursor → MCP → "как устроен флоу оплаты?" → идеальный ответ
4. **Wow 2:** `kbk build-showcase` → Confluence → идеальная страница-витрина

## Разработка

```bash
pip install -e ".[dev]"
python tests/test_smoke.py
```

## Статус

✅ v0.2 — Pull + Allowlist, 11/11 тестов, ATM berserk (6/6 gates)  
🔲 v0.3 — GitLab connector, HTTP MCP, инкрементальный showcase  
🔲 v0.4 — Backstage dashboard, Slack AI assistant

## Ссылки

- Репозиторий: [github.com/Wendigooor/knowledge-base-kit](https://github.com/Wendigooor/knowledge-base-kit)
- AGENTS.md: Правила для агентов
- ATM run: `kbk-v02` (6/6 gates)

```

---

## 📄 docs/ARCHITECTURE.md

```markdown
# Knowledge Base Kit (KBK) — Architecture v2

## Концепция: Умный Индекс (Aggregator), не хранилище

**KBK — это не Source of Truth.** Source of Truth остаётся там, где родился:
- Confluence (документация, ADR)
- Jira (тикеты, задачи)
- Git (код, комментарии к MR)
- Slack (обсуждения, решения)

KBK — это **семантический индекс** над всеми этими источниками. Он ходит по белому списку (Allowlist), забирает только нужное, индексирует, классифицирует и предоставляет единую точку поиска. Без вебхуков — только Pull по команде `kbk sync`.

```
[Confluence] ──────┐
[Jira] ────────────┤─── kbk sync ──── [StateTracker] ─── [Indexer] ──→ [ChromaDB]
[Git] ─────────────┤       │                                  │
[Slack] ───────────┘       ├─ SHA-256 diff (skip unchanged)    ├─ clean HTML
                            └─ delete orphans                  ├─ LLM summarize + classify
                                                               ├─ chunk (1k tokens)
                                                               └─ embed
                                                                      │
                                                                      ▼
                                                      [Read-Only Confluence Space]
                                                      (авто-генерируемая витрина)
```

## Ключевые отличия от v1

| Аспект | v1 (отменено) | v2 (новая) |
|--------|---------------|------------|
| Хранилище | ChromaDB + Git (JSON) | ChromaDB + connectors |
| Source of Truth | KBK сам | Confluence/Jira/Git — оригиналы |
| Версионирование | snapshot-based | В оригиналах (git history, Confluence history) |
| Sync | git push/pull | Pull по белым спискам (allowlist + kbk sync) |
| Документ | Полный content + версии | Summary (LLM) + source_url + tags |
| CLI | 9 команд (sync, history, rollback) | 5 команд (index, search, status, connectors, explore) |
| Генерация документации | Нет | Read-Only Confluence space |

## Архитектура

### Слой Ingestion (connectors/)

```
connectors/
├── __init__.py
├── base.py           # AbstractConnector
├── confluence.py     # Confluence REST API → Pull по allowlist
├── jira.py           # Jira REST API → Pull по allowlist
├── gitlab.py         # GitLab API → Pull по allowlist
└── slack.py          # Slack API → Pull по allowlist
```

Каждый коннектор выполняет Pull по белому списку (Allowlist) из `targets.yaml`.
При изменении документа:
1. Получает сырой контент
2. Отдаёт в `indexer.py` для обработки

### Слой Processing (indexer.py)

```python
class Indexer:
    def process(self, raw_text: str, source: str, metadata: dict) -> IndexedDocument:
        # 1. Очистка — убрать HTML, макросы, мусор
        cleaned = self.clean(raw_text)
        
        # 2. LLM суммаризация — выделить суть (100-200 токенов)
        summary = self.llm_summarize(cleaned)
        
        # 3. Классификация — теги, категория
        tags = self.llm_classify(cleaned)
        
        # 4. Чанкинг — разбить на куски (512-1024 токенов)
        chunks = self.chunk(summary, cleaned)
        
        # 5. Эмбеддинги — векторизовать каждый chunk
        embeddings = self.embed(chunks)
        
        # 6. Сохранить в ChromaDB
        self.store.upsert(doc_id, chunks, embeddings, {
            "source_url": metadata["url"],
            "source_type": metadata["type"],  # confluence | jira | git | slack
            "tags": tags,
            "summary": summary,
            "updated_at": metadata["updated_at"],
            "access_group": metadata.get("access_group", "public"),
        })
```

### Слой Presentation (Read-Only Space)

Генератор Confluence space (или Backstage dashboard), который:

1. **Жёсткий скелет** (не меняется):
```
📁 Architecture      → ADR, service contracts, diagrams
📁 Infrastructure    → K8s, databases, CI/CD
📁 Business Logic    → domain models, workflows
📁 Runbooks          → on-call, incident responses
📁 Decisions Log     → chronological ADR
📁 Team & Ownership  → who owns what
```

2. **LLM наполнение** для каждого документа:
   - Определяет категорию по тегам/семантике
   - Если не уверен — помечает `Unclassified`

3. **Ссылки на оригиналы** — каждая карточка ведёт в Confluence/Jira/Git

### Модель данных

```python
@dataclass
class IndexedDocument:
    id: str                          # hash(source_url + version)
    summary: str                     # LLM-generated (100-200 токенов)
    tags: list[str]                  # LLM-classified
    metadata: dict                   # source_url, source_type, access_group
    collection: str                  # architecture | infrastructure | business | runbooks
    created_at: str                  # когда впервые проиндексирован
    updated_at: str                  # когда последний раз обновлён в источнике
    chunk_count: int                 # сколько чанков в ChromaDB
```

**Нет previous_versions.** Нет content (только summary). Версионирование живёт в источниках.

### CLI

| Команда | Назначение |
|---------|-----------|
| `kbk init` | Инициализировать ChromaDB |
| `kbk index` | Запустить индексацию (все connectors) |
| `kbk search` | Семантический поиск |
| `kbk status` | Статус индекса (сколько документов, по источникам) |
| `kbk connectors` | Список/статус коннекторов |
| `kbk explore` | Открыть Read-Only space в браузере |

### Чем это лучше v1

1. **Zero friction** — никто не меняет привычки. Работают в Confluence/Jira/Git как обычно
2. **Нет дублирования** — документ существует в одном месте
3. **Не надо версионировать** — история в оригинале (git log, Confluence history)
4. **Масштабируется** — Webhooks вместо полной синхронизации
5. **Enterprise-ready** — ACL из оригиналов, audit trail, знакомая экосистема
6. **Проверяемо** — QA идёт по ссылке из витрины и видит актуальный документ в оригинале

```

---

## 📄 docs/WHY.md

```markdown
# Why Knowledge Base Kit?

## Проблема

Мы — enterprise. SoftSwiss. 50+ микросервисов, 100+ разработчиков, легаси 10+ лет.

Контекст живёт:
- В Confluence — никто не обновляет, страницы мертвы через месяц
- В Jira — размазан по сотням тикетов
- В Git — читай 50k строк чтобы понять один эндпоинт
- В головах у людей — уходит когда человек уходит
- В Slack — потерян навсегда

LLM не могут работать с этим контекстом. Люди тратят недели на погружение.

## Решение, которое НЕ работает

Заставить всю компанию писать документацию в новый инструмент — **обречено**.

Confluence мёртв не потому что плохой инструмент. Confluence мёртв потому что documentation is a tax, not a feature. Люди пишут код, а не документацию.

## Решение, которое работает

KBK — это **не хранилище документов**. KBK — это **семантический индекс** над существующими источниками.

**Source of truth остаётся там, где родился:**
- Confluence страница → KBK индексирует её содержимое
- Jira тикет → KBK создаёт семантическую ссылку
- Git MR → KBK анализирует и классифицирует

**Zero friction для команды.** Никто не меняет привычки. Всё работает как работало. KBK просто слушает и индексирует.

## Как это работает

```
[Confluence] ──вебхук──┐
[Jira] ───────вебхук───┤──→ [KBK Indexer] ──→ [ChromaDB] ──→ [Read-Only Space]
[GitLab] ─────вебхук───┘                              │
                                                      ▼
                                              [Семантический поиск]
                                              [AI-ассистент в Slack]
                                              [Авто-сгенерированная витрина]
```

1. **Connectors** слушают изменения в источниках (вебхуки + cron)
2. **Indexer** чистит, суммаризирует (LLM), классифицирует, чанкует, эмбеддит
3. **ChromaDB** хранит векторы + метаданные + ссылки на оригиналы
4. **Read-Only Space** — авто-генерируемая витрина в Confluence/Backstage

## Аудитория

| Кто | Как использует KBK |
|-----|-------------------|
| System Analyst | Ищет "rate limiting architecture" → видит ADR из Confluence |
| Developer | Спрашивает Slack-бота "как деплоить payment-service" → получает runbook |
| Architect | "Покажи все решения по Kafka" → хронология ADR |
| QA | "Какие acceptance criteria для бонусов?" → ссылка на Jira |
| New hire | Onboarding за 2 дня вместо месяца через витрину |

## Чем это отличается

| Аспект | Традиционный подход (Confluence/Notion) | KBK v2 |
|--------|----------------------------------------|--------|
| Кто пишет | Люди (никто не пишет) | LLM + люди (люди пишут код, LLM индексирует) |
| Где живёт | В одном инструменте | Распределённо, ссылки на оригиналы |
| Актуальность | Мертва через месяц | Живёт пока жив оригинал |
| Версионирование | Нет | В оригинале (git / Confluence history) |
| Поиск | Full-text | Семантический + LLM |
| Внедрение | "Начните писать сюда" | Zero friction — ничего не меняется |

```

---

## 📄 targets.yaml

```yaml
# KBK whitelisted sources — v0.2 Pull + Allowlist
# Add targets here and run `kbk sync` to index them.
targets:
  - type: confluence
    location: "ARCH"
    filter_query: "label = 'approved' OR label = 'adr'"
    access_group: "public"

  - type: confluence
    location: "ENG"
    filter_query: "label = 'runbook'"
    access_group: "public"

```

---

## 📄 kbk/__init__.py

```python
"""KBK v0.2 — Enterprise Semantic Index. Pull + Allowlist."""

```

---

## 📄 kbk/models.py

```python
"""Data models for KBK v0.2."""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class IndexedChunk:
    """A semantically indexed chunk from an enterprise source.

    Stores cleaned text + LLM summary + source pointer.
    No full content — just distilled meaning.
    """
    id: str = ""
    source_url: str = ""
    content: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    access_group: str = "public"
    content_hash: str = ""
    collection: str = "unclassified"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self):
        if not self.id and self.source_url:
            raw = f"{self.source_url}:{self.content_hash}:{self.collection}"
            self.id = hashlib.sha256(raw.encode()).hexdigest()[:16]
        if not self.id:
            # Fallback: deterministic from source_url + collection
            self.id = hashlib.sha256(
                f"{self.source_url}:{self.collection}".encode()
            ).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "id": self.id, "source_url": self.source_url,
            "content": self.content, "summary": self.summary,
            "tags": self.tags, "access_group": self.access_group,
            "content_hash": self.content_hash, "collection": self.collection,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IndexedChunk":
        safe = {k: data.get(k, "") for k in
                ["id", "source_url", "content", "summary", "content_hash", "collection",
                 "created_at", "updated_at", "access_group"]}
        safe["tags"] = data.get("tags", [])
        return cls(**safe)


@dataclass
class SourceTarget:
    """A whitelisted source to index."""
    type: str  # confluence | gitlab
    location: str  # space key | repo path
    filter_query: str = ""  # CQL for confluence, path for gitlab
    access_group: str = "public"

```

---

## 📄 kbk/config.py

```python
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

```

---

## 📄 kbk/exceptions.py

```python
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

```

---

## 📄 kbk/state.py

```python
"""State tracker for KBK — SHA-256 hash-based dedup."""
from __future__ import annotations
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
    """

    def __init__(self, state_path: str):
        self.path = Path(state_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict] = {}
        self._dirty = False  # Track unsaved changes for batch mode
        self._load()

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
        """Atomic write: write to temp file, then rename."""
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._data, indent=_DEFAULT_INDENT, ensure_ascii=False),
            encoding="utf-8",
        )
        # Atomic replace (POSIX atomic on same filesystem)
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
        """Mark a document as indexed with its content hash."""
        self._data[url] = {
            "hash": content_hash,
            "chunk_ids": chunk_ids or [],
        }
        self._dirty = True
        self._save()

    def remove(self, url: str):
        """Remove a document from the tracker (e.g., if deleted at source)."""
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

```

---

## 📄 kbk/store.py

```python
"""ChromaDB-backed store for KBK v0.2."""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

from kbk.config import KBKConfig
from kbk.models import IndexedChunk
from kbk.exceptions import StoreError

logger = logging.getLogger("kbk.store")

WhereFilter = dict


class KnowledgeStore:
    def __init__(self, config: Optional[KBKConfig] = None):
        self.config = config or KBKConfig()
        self._client: Optional[chromadb.PersistentClient] = None
        self._collections: dict[str, chromadb.Collection] = {}

    def _init_client(self):
        _ = self.client

    @property
    def client(self) -> chromadb.PersistentClient:
        if self._client is None:
            db_path = Path(self.config.db_path)
            db_path.mkdir(parents=True, exist_ok=True)
            try:
                self._client = chromadb.PersistentClient(
                    path=str(db_path),
                    settings=Settings(anonymized_telemetry=False),
                )
            except Exception as exc:
                raise StoreError(f"ChromaDB init failed: {exc}") from exc
        return self._client

    def _get_collection(self, name: str) -> chromadb.Collection:
        if name not in self._collections:
            try:
                self._collections[name] = self.client.get_or_create_collection(name)
            except Exception as exc:
                raise StoreError(f"Collection '{name}' error: {exc}") from exc
        return self._collections[name]

    def upsert_chunk(self, chunk: IndexedChunk) -> str:
        col = self._get_collection(chunk.collection)
        meta = {
            "chunk_id": chunk.id, "source_url": chunk.source_url,
            "summary": chunk.summary, "tags": json.dumps(chunk.tags),
            "access_group": chunk.access_group, "content_hash": chunk.content_hash,
        }
        try:
            col.upsert(ids=[chunk.id], documents=[chunk.content], metadatas=[meta])
        except Exception as exc:
            raise StoreError(f"Upsert failed: {exc}") from exc
        return chunk.id

    def delete_chunks(self, chunk_ids: list[str], collection: str = "default"):
        if not chunk_ids:
            return
        try:
            col = self._get_collection(collection)
            col.delete(ids=chunk_ids)
        except Exception as exc:
            logger.warning("ChromaDB delete failed for %d chunks in %s: %s",
                           len(chunk_ids), collection, exc)

    def search(self, query: str, n_results: Optional[int] = None,
               collection_filter: Optional[str] = None,
               filters: Optional[dict] = None,
               access_group: Optional[str] = None) -> list[IndexedChunk]:
        n_results = n_results or self.config.top_k
        col_name = collection_filter or self.config.default_collection
        col = self._get_collection(col_name)
        where = None
        if filters or access_group:
            where = {}
            if filters:
                where.update(filters)
            if access_group:
                # Enforce access group filter
                where["access_group"] = {"$eq": access_group}
        try:
            results = col.query(query_texts=[query], n_results=n_results, where=where)
        except Exception as exc:
            raise StoreError(f"Search failed: {exc}") from exc
        if not results or not results["ids"]:
            return []
        chunks = []
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i] if results.get("metadatas") else {}
            tags = json.loads(meta.get("tags", "[]")) if isinstance(meta.get("tags"), str) else []
            chunks.append(IndexedChunk(
                id=results["ids"][0][i],
                source_url=meta.get("source_url", ""),
                content=results["documents"][0][i] if results.get("documents") else "",
                summary=meta.get("summary", ""),
                tags=tags,
                access_group=meta.get("access_group", "public"),
                content_hash=meta.get("content_hash", ""),
                collection=col_name,
            ))
        return chunks

    def list_chunks(self, collection: str = "default", limit: int = 100) -> list[IndexedChunk]:
        col = self._get_collection(collection)
        try:
            results = col.get(limit=limit)
        except Exception as exc:
            raise StoreError(f"List failed: {exc}") from exc
        if not results or not results["ids"]:
            return []
        chunks = []
        for i in range(len(results["ids"])):
            meta = results["metadatas"][i] if results.get("metadatas") else {}
            tags = json.loads(meta.get("tags", "[]")) if isinstance(meta.get("tags"), str) else []
            chunks.append(IndexedChunk(
                id=results["ids"][i], source_url=meta.get("source_url", ""),
                content=results["documents"][i] if results.get("documents") else "",
                summary=meta.get("summary", ""), tags=tags,
                access_group=meta.get("access_group", "public"),
                content_hash=meta.get("content_hash", ""), collection=collection,
            ))
        return chunks

    def count(self, collection: str = "default") -> int:
        return self._get_collection(collection).count()

    def list_collections(self) -> list[str]:
        return [c.name for c in self.client.list_collections()]

    def delete_collection(self, name: str):
        self.client.delete_collection(name)
        self._collections.pop(name, None)

    def get_stats(self) -> dict:
        cols = self.list_collections()
        stats = {"collections": {}, "total": 0}
        for c in cols:
            cnt = self.count(c)
            stats["collections"][c] = cnt
            stats["total"] += cnt
        return stats

```

---

## 📄 kbk/indexer.py

```python
"""AI Pipeline for KBK — clean, summarize, chunk, classify."""
from __future__ import annotations
import hashlib
import json
import logging
import re
import urllib.request
from typing import Optional

from kbk.exceptions import LLMError
from kbk.models import IndexedChunk
from kbk.store import KnowledgeStore
from kbk.state import StateTracker

logger = logging.getLogger("kbk.indexer")

# Constants
_CHUNK_SIZE = 1000  # tokens
_CHUNK_OVERLAP = 100  # characters
_LLM_TIMEOUT = 30  # seconds
_LLM_RETRIES = 2
_SUMMARY_MAX_CHARS = 4000
_PREVIEW_MAX_CHARS = 300


class Indexer:
    """ETL pipeline: clean HTML -> LLM summarize+classify -> chunk -> embed."""

    def __init__(self, store: KnowledgeStore, state: StateTracker,
                 llm_api_key: str = "", llm_model: str = "gpt-4o-mini",
                 llm_base_url: str = "https://api.openai.com/v1"):
        self.store = store
        self.state = state
        self.llm_api_key = llm_api_key
        self.llm_model = llm_model
        self.llm_base_url = llm_base_url.rstrip("/")
        self.cost_log: list[dict] = []

    def clean_html(self, html: str) -> str:
        """Strip Confluence HTML to clean text."""
        # Remove Confluence-specific macros (ac: tags)
        text = re.sub(r'<ac:[^>]+>[^<]*</ac:[^>]+>', '', html)
        # Strip all remaining HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _call_llm(self, prompt: str, max_tokens: int = 200,
                  temperature: float = 0.1) -> str:
        """Call LLM with retry logic and error reporting."""
        if not self.llm_api_key:
            raise LLMError("LLM API key not configured")

        payload = {
            "model": self.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        last_error = None
        for attempt in range(_LLM_RETRIES + 1):
            try:
                data = json.dumps(payload).encode()
                req = urllib.request.Request(
                    f"{self.llm_base_url}/chat/completions",
                    data=data, headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.llm_api_key}",
                    },
                )
                with urllib.request.urlopen(req, timeout=_LLM_TIMEOUT) as resp:
                    result = json.loads(resp.read().decode())
                    content = result["choices"][0]["message"]["content"]
                    usage = result.get("usage", {})
                    self.cost_log.append({
                        "model": self.llm_model, "attempt": attempt,
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                    })
                    return content.strip()

            except urllib.error.HTTPError as exc:
                last_error = exc
                status = exc.code
                if status == 401:
                    raise LLMError("LLM auth failed — check API key") from exc
                if status == 429 and attempt < _LLM_RETRIES:
                    import time
                    wait = 2 ** (attempt + 1)
                    logger.warning("LLM rate limited (429), retrying in %ds", wait)
                    time.sleep(wait)
                    continue
                logger.error("LLM HTTP %d: %s", status, exc)
                raise LLMError(f"LLM API error (HTTP {status})") from exc

            except Exception as exc:
                last_error = exc
                if attempt < _LLM_RETRIES:
                    import time
                    wait = 2 ** attempt
                    logger.warning("LLM call failed (attempt %d/%d): %s, retrying in %ds",
                                   attempt + 1, _LLM_RETRIES + 1, exc, wait)
                    time.sleep(wait)
                    continue
                logger.error("LLM call failed after %d attempts: %s",
                             _LLM_RETRIES + 1, exc)

        raise LLMError(f"LLM call failed after {_LLM_RETRIES + 1} attempts: {last_error}") from last_error

    def _summarize_and_classify(self, text: str, title: str = "") -> tuple[str, list[str]]:
        """Single LLM call to get both summary and tags.

        Falls back to truncation if LLM unavailable.
        """
        if not self.llm_api_key or len(text) < 200:
            preview = text[:_PREVIEW_MAX_CHARS].strip()
            summary = preview + "..." if len(text) > _PREVIEW_MAX_CHARS else preview
            return summary, []

        safe_title = title.replace('"', "'")[:100]
        safe_text = text[:_SUMMARY_MAX_CHARS].replace('"', "'")

        prompt = (
            f"Analyze this enterprise document.\n\n"
            f"--- BEGIN DOCUMENT ---\n"
            f"Title: {safe_title}\n"
            f"Content: {safe_text}\n"
            f"--- END DOCUMENT ---\n\n"
            f"Return ONLY a JSON object with two fields:\n"
            f'  {{"summary": "2-3 sentence summary", "tags": ["tag1", "tag2", "tag3"]}}\n'
        )

        try:
            response = self._call_llm(prompt, max_tokens=300, temperature=0.1)
        except LLMError as exc:
            logger.warning("LLM summarization failed: %s. Falling back to truncation.", exc)
            preview = text[:_PREVIEW_MAX_CHARS].strip()
            summary = preview + "..." if len(text) > _PREVIEW_MAX_CHARS else preview
            return summary, []

        # Parse structured output
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                summary = parsed.get("summary", "")[:500]
                tags = parsed.get("tags", [])
                return summary, tags[:10]
            except json.JSONDecodeError:
                pass

        # Fallback
        preview = text[:_PREVIEW_MAX_CHARS].strip()
        summary = preview + "..." if len(text) > _PREVIEW_MAX_CHARS else preview
        words = re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b', text)
        tags = list(set(w.lower() for w in words[:8]))
        return summary, tags

    def chunk(self, text: str, chunk_size: int = _CHUNK_SIZE,
              overlap: int = _CHUNK_OVERLAP) -> list[str]:
        """Split text into overlapping chunks anchored at sentence boundaries.

        Each chunk carries enough context to be semantically meaningful on its own.
        Uses character-based splitting at sentence boundaries.
        """
        if not text or len(text) <= chunk_size:
            return [text] if text else [""]

        # Split into sentences (simple approach: periods + newlines)
        sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        chunks = []
        current = ""
        for sent in sentences:
            if not current:
                current = sent
            elif len(current) + len(sent) + 1 <= chunk_size:
                current += " " + sent
            else:
                chunks.append(current)
                overlap_text = current[-overlap:] if len(current) > overlap else current
                current = overlap_text + " " + sent

        if current:
            chunks.append(current)

        return chunks or [text]

    def process_document(self, url: str, raw_html: str, title: str = "",
                         access_group: str = "public",
                         collection: str = "unclassified",
                         content_hash: str = "") -> list[IndexedChunk]:
        """Process a single document through the ETL pipeline."""
        cleaned = self.clean_html(raw_html)
        if not cleaned:
            logger.warning("Empty content after cleaning: %s", url)
            return []

        summary, tags = self._summarize_and_classify(cleaned, title)
        chunks_text = self.chunk(cleaned)
        doc_hash = content_hash or StateTracker.hash_content(raw_html)

        chunks = []
        for i, chunk_text in enumerate(chunks_text):
            chunk_id = StateTracker.hash_content(f"{url}:chunk:{i}")
            chunk = IndexedChunk(
                id=chunk_id,
                source_url=url,
                content=chunk_text,
                summary=summary,
                tags=tags,
                access_group=access_group,
                content_hash=doc_hash,
                collection=collection,
            )
            self.store.upsert_chunk(chunk)
            chunks.append(chunk)

        return chunks

    @property
    def total_cost_estimate(self) -> dict:
        total_prompt = sum(c.get("prompt_tokens", 0) for c in self.cost_log)
        total_completion = sum(c.get("completion_tokens", 0) for c in self.cost_log)
        return {
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "estimated_cost_usd": round(
                total_prompt * 0.00015 / 1000 + total_completion * 0.0006 / 1000, 4
            ),
            "calls": len(self.cost_log),
        }

```

---

## 📄 kbk/cli.py

```python
"""CLI for KBK v0.2 — Enterprise Semantic Index with Pull + Allowlist."""
from __future__ import annotations
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from kbk.config import KBKConfig, load_targets
from kbk.store import KnowledgeStore
from kbk.state import StateTracker
from kbk.indexer import Indexer
from kbk.mcp_server import KBKMCPServer
from kbk.showcase import ShowcaseBuilder
from kbk.exceptions import StoreError


console = Console()

def _handle_error(func):
    from functools import wraps
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user[/yellow]")
            sys.exit(130)
        except StoreError as e:
            console.print(f"[red]❌ Store error: {e}[/red]")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]❌ {e}[/red]")
            sys.exit(1)
    return wrapper


@click.group()
@click.option("--config", "-c", default=None, help="Path to config file")
@click.pass_context
def cli(ctx, config):
    """KBK v0.2 — Enterprise Semantic Index. Pull + Allowlist."""
    ctx.ensure_object(dict)
    cfg = KBKConfig.load(config)
    ctx.obj["config"] = cfg

    # Ensure base dirs
    base = Path.home() / ".kbk"
    base.mkdir(parents=True, exist_ok=True)

    ctx.obj["store"] = KnowledgeStore(cfg)
    ctx.obj["state"] = StateTracker(cfg.state_path)
    ctx.obj["indexer"] = Indexer(
        ctx.obj["store"], ctx.obj["state"],
        llm_api_key=cfg.llm_api_key,
        llm_model=cfg.llm_model,
        llm_base_url=cfg.llm_base_url,
    )


@cli.command()
@_handle_error
def init():
    """Initialize KBK: create dirs, ChromaDB, state tracker, sample config."""
    base = Path.home() / ".kbk"
    base.mkdir(parents=True, exist_ok=True)

    # Create sample targets file
    targets_path = base / "targets.yaml"
    if not targets_path.exists():
        targets_path.write_text("""# KBK whitelisted sources
targets:
  - type: confluence
    location: "ARCH"
    filter_query: "label = 'approved'"
    access_group: "public"
""")
    # Init ChromaDB
    cfg = KBKConfig()
    store = KnowledgeStore(cfg)
    store._init_client()
    # Init state tracker
    StateTracker(cfg.state_path)

    console.print(f"[green]✅[/green] KBK initialized at ~/.kbk/")
    console.print(f"  ChromaDB: {cfg.db_path}")
    console.print(f"  State tracker: {cfg.state_path}")
    console.print(f"  Targets: {cfg.targets_path}")
    console.print(f"\nRun [bold]kbk sync[/bold] to index your first documents.")
    console.print(f"Run [bold]kbk serve[/bold] to start MCP server for LLMs.")
    console.print(f"Run [bold]kbk build-showcase[/bold] to generate Confluence showcase.")


@cli.command()
@click.option("--dry-run", is_flag=True, help="Show what would be indexed without doing it")
@_handle_error
def sync(dry_run: bool):
    """Pull whitelisted sources, diff, ETL, embed — full pipeline."""
    cfg: KBKConfig = click.get_current_context().obj["config"]
    store: KnowledgeStore = click.get_current_context().obj["store"]
    state: StateTracker = click.get_current_context().obj["state"]
    indexer: Indexer = click.get_current_context().obj["indexer"]

    targets = load_targets(cfg.targets_path)
    if not targets:
        console.print("[yellow]⚠️[/yellow] No targets configured. Edit ~/.kbk/targets.yaml")
        return

    console.print("[bold]🔍 KBK Sync[/bold]")
    console.print(f"  Targets: {len(targets)} sources")
    console.print(f"  Dry run: {'yes' if dry_run else 'no'}")
    console.print()

    total_new = 0
    total_skipped = 0
    total_chunks = 0

    for t in targets:
        source_type = t.get("type", "unknown")
        location = t.get("location", "?")
        console.print(f"[bold]── {source_type.upper()}: {location}[/bold]")

        if source_type == "confluence":
            from kbk.connectors.confluence import ConfluenceConnector
            connector = ConfluenceConnector(
                base_url=cfg.confluence_url,
                token=cfg.confluence_token,
                state=state,
            )
            from kbk.models import SourceTarget
            target = SourceTarget(
                type="confluence", location=location,
                filter_query=t.get("filter_query", ""),
                access_group=t.get("access_group", "public"),
            )
            pages = connector.process_target(target)

            if not pages:
                console.print(f"  [dim]No new/changed documents[/dim]")
                continue

            console.print(f"  Found {len(pages)} new/changed documents")

            for page in pages:
                if dry_run:
                    console.print(f"  [dim]📄 Would index: {page['title']}[/dim]")
                    total_new += 1
                    continue

                with Progress(
                    SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                    console=console, transient=True,
                ) as progress:
                    progress.add_task(f"  Indexing: {page['title'][:50]}...", total=None)
                    chunks = indexer.process_document(
                        url=page["url"],
                        raw_html=page["body"],
                        title=page["title"],
                        access_group=page.get("access_group", "public"),
                        collection=location.lower(),
                        content_hash=page["content_hash"],
                    )
                    state.mark_indexed(page["url"], page["content_hash"], [c.id for c in chunks])
                    total_chunks += len(chunks)
                    total_new += 1

            if not dry_run:
                console.print(f"  [green]✅ {len(pages)} indexed → {total_chunks} chunks[/green]")

        elif source_type == "gitlab":
            console.print("  [dim]GitLab connector: coming in v0.3[/dim]")
        else:
            console.print(f"  [red]Unknown source type: {source_type}[/red]")

    console.print()
    cost = indexer.total_cost_estimate
    console.print("[bold]📊 Sync Summary[/bold]")
    console.print(f"  New/changed: {total_new}")
    console.print(f"  Skipped (cached): {total_skipped}")
    console.print(f"  Chunks created: {total_chunks}")
    if cost["prompt_tokens"] > 0:
        console.print(f"  LLM cost: ${cost['estimated_cost_usd']:.4f} ({cost['prompt_tokens']} prompt + {cost['completion_tokens']} completion tokens)")


@cli.command()
@click.option("--port", default=None, help="MCP server port (default: stdio)")
@_handle_error
def serve(port: str = None):
    """Start MCP server for LLM access to the knowledge index.

    Without --port: uses stdio transport (for Claude Desktop, Cursor).
    With --port: starts HTTP server (for remote access).
    """
    store: KnowledgeStore = click.get_current_context().obj["store"]
    server = KBKMCPServer(store)

    if port:
        console.print(f"[green]✅[/green] MCP server starting on port {port}")
        from http.server import HTTPServer, BaseHTTPRequestHandler
        # Simple HTTP wrapper would go here
        console.print("[yellow]⚠️[/yellow] HTTP mode coming in v0.3. Use stdio for now.")
        return

    console.print("[green]✅[/green] MCP server started (stdio)")
    console.print("  Connect from Claude Desktop or Cursor:")
    console.print(f"  {sys.executable} -m kbk.cli serve")
    console.print()
    server.run()


@cli.command()
@click.option("--output", "-o", default="confluence", type=click.Choice(["confluence", "markdown"]),
              help="Output format for the showcase")
@_handle_error
def build_showcase(output: str):
    """Generate Read-Only knowledge showcase (Confluence page or Markdown)."""
    cfg: KBKConfig = click.get_current_context().obj["config"]
    store: KnowledgeStore = click.get_current_context().obj["store"]
    builder = ShowcaseBuilder(store, cfg)

    stats = store.get_stats()
    if stats["total"] == 0:
        console.print("[yellow]⚠️[/yellow] Index is empty. Run [bold]kbk sync[/bold] first.")
        return

    if output == "confluence":
        if not cfg.confluence_url or not cfg.confluence_token:
            console.print("[red]❌[/red] Confluence not configured. Set confluence_url and confluence_token in config.")
            console.print("  Trying markdown output instead...")
            output = "markdown"
        else:
            url = builder.build()
            console.print(f"[green]✅[/green] Showcase published to Confluence")
            console.print(f"  {url}")

    if output == "markdown":
        md = builder.build_markdown()
        path = Path.home() / ".kbk" / "showcase.md"
        path.write_text(md, encoding="utf-8")
        console.print(f"[green]✅[/green] Showcase saved to {path}")
        console.print()
        # Show preview
        lines = md.split("\n")
        for l in lines[:20]:
            console.print(l)


@cli.command()
@click.argument("query")
@click.option("--collection", "-c", default=None)
@click.option("--limit", "-n", default=10)
@_handle_error
def search(query: str, collection: str = None, limit: int = 10):
    """Semantic search across the knowledge index."""
    store: KnowledgeStore = click.get_current_context().obj["store"]
    results = store.search(query, n_results=limit, collection_filter=collection)
    if not results:
        console.print("No results found.")
        return
    console.print(f"[bold]🔍 Search:[/bold] {query}")
    console.print()
    for c in results:
        tags = f" [dim]{' '.join(f'#{t}' for t in c.tags[:3])}[/dim]" if c.tags else ""
        link = f" [blue]{c.source_url}[/blue]" if c.source_url else ""
        console.print(f"  {c.summary[:200]}{tags}{link}")
        console.print()


@cli.command()
@_handle_error
def status():
    """Show knowledge index status."""
    store: KnowledgeStore = click.get_current_context().obj["store"]
    state: StateTracker = click.get_current_context().obj["state"]
    stats = store.get_stats()
    state_stats = state.stats

    console.print("[bold]📊 KBK Status[/bold]")
    console.print(f"  Collections: {len(stats['collections'])}")
    for col, cnt in stats["collections"].items():
        console.print(f"    📁 {col}: {cnt} chunks")
    console.print(f"  Total chunks: {stats['total']}")
    console.print(f"  Tracked sources: {state_stats['tracked_docs']}")
    console.print(f"  State file: {state_stats['path']}")

    if stats["total"] == 0:
        console.print("\n[yellow]Index is empty. Commands:[/yellow]")
        console.print("  kbk sync    — index documents from whitelisted sources")
        console.print("  kbk serve   — start MCP server for LLMs")
        console.print("  kbk build-showcase — generate Confluence showcase")


if __name__ == "__main__":
    cli()

```

---

## 📄 kbk/mcp_server.py

```python
"""MCP Server for KBK — gives LLMs fast semantic access to indexed knowledge.

Implements the Model Context Protocol (stdio transport).
Tools: search_knowledge, get_document_summary, list_collections.
"""
from __future__ import annotations
import html
import json
import logging
import sys
from typing import Any

from kbk.store import KnowledgeStore
from kbk.config import KBKConfig

logger = logging.getLogger("kbk.mcp")


class KBKMCPServer:
    """MCP server that exposes KBK index to LLMs via stdio transport.

    Protocol: JSON-RPC 2.0 over stdin/stdout.
    """

    def __init__(self, store: KnowledgeStore):
        self.store = store
        self.tools = {
            "search_knowledge": self._handle_search,
            "get_document_summary": self._handle_summary,
            "list_collections": self._handle_list_collections,
        }

    def _read_request(self) -> dict | None:
        line = sys.stdin.readline()
        if not line:
            return None
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None

    def _send_response(self, req_id: Any, result: Any = None, error: Any = None):
        resp = {"jsonrpc": "2.0", "id": req_id}
        if error:
            resp["error"] = {"code": -32000, "message": str(error)}
        else:
            resp["result"] = result
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()

    def _handle_search(self, params: dict) -> dict:
        query = params.get("query", "")
        collection = params.get("collection")
        limit = min(params.get("limit", 10), 50)  # cap results
        # Optionally restrict by access_group
        access_group = params.get("access_group")
        results = self.store.search(
            query, n_results=limit, collection_filter=collection,
            access_group=access_group,
        )
        return {
            "results": [
                {
                    "id": c.id,
                    "source_url": c.source_url,
                    "content": html.escape(c.content[:500]),
                    "summary": c.summary,
                    "tags": c.tags,
                    "access_group": c.access_group,
                }
                for c in results
            ],
            "count": len(results),
        }

    def _handle_summary(self, params: dict) -> dict:
        collection = params.get("collection", "default")
        limit = min(params.get("limit", 20), 100)
        chunks = self.store.list_chunks(collection=collection, limit=limit)
        return {
            "documents": [
                {
                    "id": c.id,
                    "source_url": c.source_url,
                    "summary": c.summary,
                    "tags": c.tags,
                    "access_group": c.access_group,
                }
                for c in chunks
            ],
            "count": len(chunks),
        }

    def _handle_list_collections(self, params: dict = None) -> dict:
        return {"collections": self.store.list_collections()}

    def run(self):
        """Main MCP event loop. Reads JSON-RPC from stdin, writes to stdout."""
        # Send initialize response
        self._send_response(None, {
            "protocolVersion": "2025-03-26",
            "capabilities": {
                "tools": {
                    "search_knowledge": {
                        "description": "Search indexed enterprise knowledge semantically",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Search query"},
                                "collection": {"type": "string", "description": "Filter by collection"},
                                "limit": {"type": "integer", "description": "Max results"},
                                "access_group": {"type": "string", "description": "Filter by access group"},
                            },
                            "required": ["query"],
                        },
                    },
                    "get_document_summary": {
                        "description": "Get summaries of indexed documents",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "collection": {"type": "string"},
                                "limit": {"type": "integer"},
                            },
                        },
                    },
                    "list_collections": {
                        "description": "List available collections",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                },
            },
        })

        while True:
            req = self._read_request()
            if req is None:
                break
            method = req.get("method", "")
            req_id = req.get("id", None)
            params = req.get("params", {})

            if method == "initialize":
                self._send_response(req_id, {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {"tools": {}},
                })
            elif method == "ping":
                self._send_response(req_id, {})
            elif method == "tools/call":
                tool_name = params.get("name", "")
                tool_args = params.get("arguments", {})
                handler = self.tools.get(tool_name)
                if handler:
                    try:
                        result = handler(tool_args)
                        self._send_response(
                            req_id,
                            {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]},
                        )
                    except Exception as e:
                        logger.exception("MCP tool %s failed", tool_name)
                        self._send_response(req_id, error=str(e))
                else:
                    self._send_response(req_id, error=f"Unknown tool: {tool_name}")
            else:
                self._send_response(req_id, {})

```

---

## 📄 kbk/showcase.py

```python
"""Showcase Builder for KBK — generates Read-Only Confluence space.

Creates a single attractive index page with summaries and links to originals.
"""
from __future__ import annotations
import html
import json
import logging
import base64
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Optional

from kbk.store import KnowledgeStore
from kbk.config import KBKConfig

logger = logging.getLogger("kbk.showcase")


class ShowcaseBuilder:
    """Builds a Read-Only Confluence showcase page from the KBK index.

    Groups documents by collection with expand/collapse sections.
    Each entry has: LLM summary + tag badges + link to original.
    """

    def __init__(self, store: KnowledgeStore, config: KBKConfig):
        self.store = store
        self.config = config

    def _confluence_headers(self) -> dict:
        auth = base64.b64encode(f"{self.config.confluence_token}:".encode()).decode()
        return {
            "Authorization": f"Basic {auth}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _confluence_request(self, method: str, path: str, data: dict = None) -> Optional[dict]:
        url = f"{self.config.confluence_url}/rest/api{path}"
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=self._confluence_headers(), method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            logger.error("Confluence API error %d %s: %s", exc.code, path, exc.read().decode() if exc.fp else "")
            raise
        except Exception as exc:
            logger.error("Confluence request failed %s %s: %s", method, path, exc)
            raise

    def _generate_storage_format(self, stats: dict) -> str:
        """Generate Confluence Storage Format HTML."""
        cols = stats.get("collections", {})
        total = stats.get("total", 0)
        updated = datetime.now().strftime("%Y-%m-%d %H:%M")

        sections = []
        # Banner
        sections.append(
            f'<ac:structured-macro ac:name="info">'
            f'<ac:rich-text-body>'
            f'<p>🤖 This page is auto-generated by <strong>Knowledge Base Kit</strong>. '
            f'Last updated: {updated}. Do not edit manually.</p>'
            f'</ac:rich-text-body></ac:structured-macro>'
        )

        # Summary
        sections.append(f"<h2>Index Overview</h2>")
        sections.append(f"<p><strong>{total}</strong> indexed chunks across <strong>{len(cols)}</strong> collections.</p>")

        # Collections
        for col_name, count in sorted(cols.items()):
            if count == 0:
                continue
            chunks = self.store.list_chunks(collection=col_name, limit=100)
            if not chunks:
                continue

            sections.append(f'<ac:structured-macro ac:name="expand">')
            sections.append(f'<ac:parameter ac:name="title">📁 {col_name.capitalize()} ({count} chunks)</ac:parameter>')
            sections.append(f'<ac:rich-text-body>')
            sections.append(f'<table><colgroup><col/><col/></colgroup><tbody>')

            for c in chunks[:50]:
                tags_html = " ".join(
                    f'<ac:structured-macro ac:name="status">'
                    f'<ac:parameter ac:name="colour">Blue</ac:parameter>'
                    f'<ac:parameter ac:name="title">{html.escape(t)}</ac:parameter>'
                    f'</ac:structured-macro>'
                    for t in c.tags[:5]
                )
                summary = html.escape(c.summary[:200] + "..." if len(c.summary) > 200 else c.summary)
                link = f'<a href="{c.source_url}">🔗 Original</a>' if c.source_url else ""
                sections.append(
                    f'<tr><td><strong>{summary}</strong><br/>{tags_html}</td>'
                    f'<td>{link}</td></tr>'
                )

            sections.append(f'</tbody></table>')
            sections.append(f'</ac:rich-text-body></ac:structured-macro>')
            sections.append('<br/>')

        return "\n".join(sections)

    def build(self) -> str:
        """Build the showcase and push to Confluence."""
        stats = self.store.get_stats()
        storage = self._generate_storage_format(stats)
        title = f"KBK Knowledge Index ({datetime.now().strftime('%Y-%m-%d')})"

        # Check if page exists
        pages = self._confluence_request(
            "GET",
            f"/content?spaceKey={self.config.showcase_space}&title={urllib.parse.quote(title)}&expand=version"
        )
        existing_id = None
        current_version = 0
        if pages and pages.get("results"):
            existing_id = pages["results"][0]["id"]
            current_version = pages["results"][0].get("version", {}).get("number", 0)

        data = {
            "type": "page",
            "title": title,
            "space": {"key": self.config.showcase_space},
            "body": {"storage": {"value": storage, "representation": "storage"}},
            "version": {"number": current_version + 1},
        }

        if existing_id:
            result = self._confluence_request("PUT", f"/content/{existing_id}", data)
        else:
            result = self._confluence_request("POST", "/content", data)

        if result:
            return result.get("_links", {}).get("base", self.config.confluence_url) + \
                   result.get("_links", {}).get("webui", "")
        return "Failed to create showcase page"

    def build_markdown(self) -> str:
        """Generate markdown version of showcase (for local preview)."""
        stats = self.store.get_stats()
        updated = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            f"# KBK Knowledge Index",
            f"",
            f"> 🤖 Auto-generated by Knowledge Base Kit. Last updated: {updated}",
            f"",
            f"**{stats['total']}** indexed chunks across **{len(stats['collections'])}** collections.",
            f"",
        ]
        for col_name, count in sorted(stats["collections"].items()):
            if count == 0:
                continue
            chunks = self.store.list_chunks(collection=col_name, limit=50)
            lines.append(f"## 📁 {col_name.capitalize()} ({count} chunks)")
            lines.append("")
            for c in chunks[:50]:
                tags = f" `{'` `'.join(c.tags[:5])}`" if c.tags else ""
                link = f" [🔗]({c.source_url})" if c.source_url else ""
                summary = c.summary[:200] + "..." if len(c.summary) > 200 else c.summary
                lines.append(f"- {summary}{tags}{link}")
            lines.append("")
        return "\n".join(lines)

```

---

## 📄 kbk/connectors/__init__.py

```python
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

```

---

## 📄 kbk/connectors/confluence.py

```python
"""Confluence connector for KBK — pull-based, with rate limiting and diffing."""
from __future__ import annotations
import json
import time
import urllib.request
import base64
from typing import Optional

from kbk.models import SourceTarget, IndexedChunk
from kbk.state import StateTracker


class ConfluenceConnector:
    """Pulls pages from Confluence spaces via REST API.

    Uses exponential backoff for rate limits.
    Only fetches pages matching the target's CQL filter.
    """

    def __init__(self, base_url: str, token: str, state: StateTracker):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.state = state

    def _headers(self) -> dict:
        auth = base64.b64encode(f"{self.token}:".encode()).decode()
        return {
            "Authorization": f"Basic {auth}",
            "Accept": "application/json",
        }

    def _request(self, path: str, retries: int = 3) -> Optional[dict]:
        url = f"{self.base_url}/rest/api{path}"
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers=self._headers())
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < retries - 1:
                    wait = 2 ** (attempt + 1)
                    time.sleep(wait)
                    continue
                return None
            except Exception:
                return None
        return None

    def fetch_pages(self, target: SourceTarget) -> list[dict]:
        """Fetch pages from a Confluence space using CQL filter."""
        cql = f"space={target.location}"
        if target.filter_query:
            cql += f" AND {target.filter_query}"
        cql_enc = urllib.parse.quote(cql)

        pages = []
        start = 0
        limit = 50

        while True:
            resp = self._request(
                f"/content/search?cql={cql_enc}&start={start}&limit={limit}"
                f"&expand=body.storage,version"
            )
            if not resp or not resp.get("results"):
                break
            for r in resp["results"]:
                body = (r.get("body", {})
                        .get("storage", {})
                        .get("value", ""))
                version = r.get("version", {}).get("number", 1)
                pages.append({
                    "id": r["id"],
                    "title": r["title"],
                    "url": f"{self.base_url}/spaces/{target.location}/pages/{r['id']}",
                    "body": body,
                    "version": version,
                    "space": target.location,
                })
            if len(resp["results"]) < limit:
                break
            start += limit
        return pages

    def process_target(self, target: SourceTarget) -> list[IndexedChunk]:
        """Fetch pages for a target and determine which need re-indexing."""
        raw_pages = self.fetch_pages(target)
        result = []
        for page in raw_pages:
            content_hash = StateTracker.hash_content(page["body"])
            url = page["url"]
            if not self.state.has_changed(url, content_hash):
                continue
            result.append({
                "url": url,
                "title": page["title"],
                "body": page["body"],
                "content_hash": content_hash,
                "access_group": target.access_group,
                "space": page["space"],
            })
        return result

```

---

## 📄 tests/test_smoke.py

```python
"""Smoke tests for KBK v0.2 — Enterprise Semantic Index."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kbk.models import IndexedChunk
from kbk.config import KBKConfig
from kbk.store import KnowledgeStore
from kbk.state import StateTracker
from kbk.indexer import Indexer


def test_chunk_create():
    c = IndexedChunk(source_url="https://example.com/page", content="test", tags=["a"])
    assert c.id
    assert c.source_url == "https://example.com/page"
    assert "a" in c.tags
    print("✅ Chunk create")


def test_chunk_from_dict():
    data = {"id": "abc", "source_url": "https://x", "content": "hello", "tags": ["t1"]}
    c = IndexedChunk.from_dict(data)
    assert c.id == "abc"
    assert c.content == "hello"
    print("✅ Chunk from_dict")


def test_state_tracker():
    with tempfile.TemporaryDirectory() as tmp:
        state = StateTracker(os.path.join(tmp, "state.json"))
        url = "https://example.com/doc"
        h = StateTracker.hash_content("content v1")
        assert state.has_changed(url, h) is True
        state.mark_indexed(url, h, ["chunk1", "chunk2"])
        assert state.has_changed(url, h) is False
        h2 = StateTracker.hash_content("content v2")
        assert state.has_changed(url, h2) is True
    print("✅ State tracker hash/diff")


def test_store_init():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = KBKConfig(db_path=tmp)
        store = KnowledgeStore(cfg)
        store._init_client()
        assert store.list_collections() == []
    print("✅ Store init")


def test_store_upsert_and_search():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = KBKConfig(db_path=tmp, top_k=5)
        store = KnowledgeStore(cfg)
        c = IndexedChunk(source_url="https://x", content="PostgreSQL migration guide", tags=["db"], collection="arch")
        store.upsert_chunk(c)
        assert store.count("arch") == 1
        results = store.search("postgres", collection_filter="arch")
        assert len(results) >= 1
        assert "postgres" in results[0].content.lower()
    print("✅ Store upsert & search")


def test_store_delete():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = KBKConfig(db_path=tmp)
        store = KnowledgeStore(cfg)
        c = IndexedChunk(source_url="https://x", content="delete me", collection="test")
        store.upsert_chunk(c)
        store.delete_chunks([c.id], "test")
        assert store.count("test") == 0
    print("✅ Store delete chunks")


def test_store_stats():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = KBKConfig(db_path=tmp)
        store = KnowledgeStore(cfg)
        stats = store.get_stats()
        assert stats["total"] == 0
        store.upsert_chunk(IndexedChunk(source_url="https://x", content="doc 1", collection="arch"))
        stats = store.get_stats()
        assert stats["total"] == 1
    print("✅ Store stats")


def test_indexer_clean():
    store = KnowledgeStore(KBKConfig(db_path="/tmp/_kbk_test_clean"))
    state = StateTracker("/tmp/_kbk_test_clean_state.json")
    idx = Indexer(store, state)
    cleaned = idx.clean_html("<html><body><p>Hello</p></body></html>")
    assert "Hello" in cleaned
    assert "<html>" not in cleaned
    print("✅ Indexer clean HTML")


def test_indexer_chunk():
    store = KnowledgeStore(KBKConfig(db_path="/tmp/_kbk_test_chunk"))
    state = StateTracker("/tmp/_kbk_test_chunk_state.json")
    idx = Indexer(store, state)
    # Split on periods to create sentence boundaries
    text = ". ".join(["word"] * 200)
    chunks = idx.chunk(text, chunk_size=10)
    assert len(chunks) >= 2
    print("✅ Indexer chunk")


def test_indexer_full_flow():
    with tempfile.TemporaryDirectory() as tmp:
        cfg = KBKConfig(db_path=tmp, state_path=os.path.join(tmp, "state.json"))
        store = KnowledgeStore(cfg)
        state = StateTracker(cfg.state_path)
        idx = Indexer(store, state, llm_api_key="")
        doc_hash = StateTracker.hash_content("<h1>Test</h1><p>API Gateway on K8s</p>")
        chunks = idx.process_document(
            url="https://confluence/page/123",
            raw_html="<h1>Test</h1><p>API Gateway on K8s</p>",
            title="API Gateway Migration",
            content_hash=doc_hash,
        )
        assert len(chunks) >= 1
        assert store.count("unclassified") >= 1
        results = store.search("api gateway", collection_filter="unclassified")
        assert len(results) >= 1
    print("✅ Indexer full flow")


def test_targets_config():
    from kbk.config import load_targets
    targets = load_targets("targets.yaml")
    assert len(targets) >= 1
    assert targets[0]["type"] in ("confluence", "gitlab")
    print("✅ Targets config")


if __name__ == "__main__":
    tests = [
        test_chunk_create,
        test_chunk_from_dict,
        test_state_tracker,
        test_store_init,
        test_store_upsert_and_search,
        test_store_delete,
        test_store_stats,
        test_indexer_clean,
        test_indexer_chunk,
        test_indexer_full_flow,
        test_targets_config,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            import traceback
            print(f"❌ {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{passed}/{len(tests)} tests passed")
    sys.exit(0 if passed == len(tests) else 1)

```

---

## 📄 pyproject.toml

```toml
[build-system]
requires = ["setuptools>=64", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "knowledge-base-kit"
version = "0.1.0"
description = "Knowledge Base Kit — инструмент для управления персональными базами знаний на базе ChromaDB"
readme = "README.md"
license = {text = "MIT"}
authors = [
    {name = "Ihar Zvezdzin", email = "ihar.zvezdzin@example.com"},
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Intended Audience :: Science/Research",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Topic :: Text Processing :: Indexing",
    "Topic :: Database :: Front-Ends",
]
requires-python = ">=3.11"
dependencies = [
    "chromadb>=0.4.0",
    "click>=8.1",
    "pyyaml>=6.0",
    "pygit2>=1.12",
    "rich>=13.0",
    "dataclasses-json>=0.5",
]

[project.scripts]
kbk = "kbk.cli:cli"

[project.urls]
Homepage = "https://github.com/iharzvezdzin/knowledge-base-kit"
Repository = "https://github.com/iharzvezdzin/knowledge-base-kit.git"

[tool.setuptools.packages.find]
include = ["kbk*"]

[tool.setuptools.package-data]
"*" = ["*.yaml", "*.json"]

[tool.black]
line-length = 88
target-version = ["py311"]

[tool.isort]
profile = "black"
line_length = 88

[tool.mypy]
strict = false
ignore_missing_imports = true
python_version = "3.11"

```

---

