# Knowledge Base Kit (KBK) — Architecture v2

## Концепция: Умный Индекс (Aggregator), не хранилище

**KBK — это не Source of Truth.** Source of Truth остаётся там, где родился:
- Confluence (документация, ADR)
- Jira (тикеты, задачи)
- Git (код, комментарии к MR)
- Slack (обсуждения, решения)

KBK — это **семантический индекс** над всеми этими источниками. Он слушает изменения, индексирует, классифицирует и предоставляет единую точку поиска.

```
Confluence ──┐
Jira ────────┤──→ [Connectors] ──→ [LLM Cleaner] ──→ [Embeddings] ──→ [ChromaDB]
Git ─────────┤                                              │
Slack ───────┘                                              ▼
                                              [Read-Only Confluence Space]
                                              (авто-генерируемая витрина)
```

## Ключевые отличия от v1

| Аспект | v1 (отменено) | v2 (новая) |
|--------|---------------|------------|
| Хранилище | ChromaDB + Git (JSON) | ChromaDB + connectors |
| Source of Truth | KBK сам | Confluence/Jira/Git — оригиналы |
| Версионирование | snapshot-based | В оригиналах (git history, Confluence history) |
| Sync | git push/pull | Webhooks + cron |
| Документ | Полный content + версии | Summary (LLM) + source_url + tags |
| CLI | 9 команд (sync, history, rollback) | 5 команд (index, search, status, connectors, explore) |
| Генерация документации | Нет | Read-Only Confluence space |

## Архитектура

### Слой Ingestion (connectors/)

```
connectors/
├── __init__.py
├── base.py           # AbstractConnector
├── confluence.py     # Confluence REST API → webhooks
├── jira.py           # Jira REST API → webhooks
├── gitlab.py         # GitLab webhooks
└── slack.py          # Slack events API
```

Каждый коннектор слушает webhook'и или ходит по расписанию (cron).
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
