# Knowledge Base Kit (KBK)

> База знаний для enterprise-контекста. Читаема людям, обновляема LLM, версионирована, ищется семантически.

```bash
pip install knowledge-base-kit
kbk init
kbk add --collection architecture --content "API Gateway переезжает на K8s" --tag adr
kbk search "миграция PostgreSQL"
kbk sync
```

## Проблема

Enterprise: 50+ сервисов, 100+ разработчиков, контекст в головах и Confluence. LLM не видят контекст, люди тратят недели на погружение.

**KBK решает это** — структурированное, обновляемое, ищимое хранилище фактов о системе.

Подробнее: [`docs/WHY.md`](docs/WHY.md)

## Структура

```
kbk/                          # Ядро
├── cli.py                    # Click CLI (9 команд)
├── store.py                  # ChromaDB CRUD
├── versioning.py             # Версионирование (snapshot-based)
├── sync.py                   # Git sync (pygit2 / git CLI)
├── config.py                 # YAML/JSON конфигурация
├── document.py               # Document dataclass
└── exceptions.py             # StoreError, VersioningError, SyncError

docs/                         # Документация
├── WHY.md                    # Vision & problem statement
├── architecture.md           # Архитектура
├── document-format.md        # Формат документов
├── setup.md                  # Установка
├── sync-protocol.md          # Протокол синхронизации
├── reviews/                  # Архитектурные ревью (3 модели)
│   ├── ARCHITECTURE_REVIEW_MINIMAX.md
│   ├── ARCHITECTURE_REVIEW_GLM51.md
│   └── ARCHITECTURE_REVIEW_KIMI.md
├── UNIFIED_PLAN.md           # План фиксов
└── specs/                    # Спецификации

tests/test_smoke.py           # 10 smoke тестов
scripts/sync.sh               # Скрипт синхронизации
```

## Быстрый старт

```bash
# Установка
pip install knowledge-base-kit

# Инициализация
kbk init

# Добавить документ
kbk add --collection architecture --content "API Gateway on K8s" --tag adr

# Поиск
kbk search "миграция PostgreSQL"

# Экспорт
kbk export

# Статус
kbk status
```

## Требования

- Python >= 3.11
- ChromaDB (устанавливается автоматически)
- pygit2 (опционально — для git sync через git CLI)

## Концепция

KBK хранит документы в ChromaDB для семантического поиска и дублирует их в Git для версионирования и синхронизации. Каждый документ имеет:

- **id** — уникальный идентификатор
- **version** — номер версии (инкрементируется при каждом изменении)
- **tags** — теги для категоризации
- **metadata** — произвольные ключ-значение
- **content** — основное содержание в Markdown
- **collection** — логическая группа (architecture, adr, runbook, ...)
- **previous_versions** — история изменений (авто-prune до 50 версий)

## Команды CLI

| Команда | Назначение |
|---------|-----------|
| `kbk init` | Инициализировать базу знаний |
| `kbk add` | Добавить документ |
| `kbk search` | Семантический поиск |
| `kbk sync` | Синхронизация с Git |
| `kbk history` | История версий документа |
| `kbk rollback` | Откат к предыдущей версии |
| `kbk status` | Статус базы знаний |
| `kbk export` | Экспорт всех документов в JSON |
| `kbk seed` | Восстановление из JSON экспорта |

## Модель синхронизации

```
ChromaDB → export → JSON → git commit → git push → GitHub
GitHub → git pull → JSON → seed → ChromaDB
```

Документы хранятся в ChromaDB (первичное хранилище) и экспортируются в git как JSON (для синхронизации и бэкапа).

## Статус

**v0.1** — Functional prototype. Architecture reviewed by 3 models (MiniMax M2.7, GLM-5.1, Kimi K2.5):
- Architecture: 5/10
- Production Readiness: 3/10

Следующие шаги: [`docs/UNIFIED_PLAN.md`](docs/UNIFIED_PLAN.md)

## License

MIT
