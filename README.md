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
