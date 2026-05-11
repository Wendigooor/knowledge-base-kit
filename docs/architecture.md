# Архитектура Knowledge Base Kit

## Концепция

Knowledge Base Kit — это система управления знаниями для LLM-агентов. Основная идея: **объединить семантический поиск ChromaDB с версионированием git**.

Документы хранятся в ChromaDB (векторная БД для поиска по смыслу). Каждое изменение создаёт JSON-слепок всей базы, который пушится в git. Это даёт историю изменений, откат к любой версии и возможность мержить данные между разными инстансами агентов.

## Слои

```
┌─────────────────────────────────────────────┐
│                  CLI (kbk)                   │
│          add, search, sync, status           │
├─────────────────────────────────────────────┤
│              Document Model                  │
│    id, version, tags, metadata, content      │
├──────────────────┬──────────────────────────┤
│   ChromaDB Store  │    Version Manager       │
│   CRUD + Search   │    Snapshots + History   │
├──────────────────┴──────────────────────────┤
│              Sync Manager                    │
│         Git Push + Pull + Conflicts          │
├─────────────────────────────────────────────┤
│         ChromaDB (persistent) │ Git (remote) │
└─────────────────────────────────────────────┘
```

### 1. Document Model (`kbk/document.py`)

Базовый класс для всех единиц знания. Каждый документ содержит:

- **id** — уникальный строковый идентификатор
- **version** — номер версии (int, начинается с 1)
- **tags** — список тегов (например, `["architecture", "v2.0", "quest-system"]`)
- **metadata** — произвольный словарь (источник, дата, автор, project_id)
- **content** — содержимое документа (текст)
- **collection** — логическая группа (проекты, люди, решения, архитектура)
- **created_at / updated_at** — таймстемпы
- **previous_versions** — ссылки на предыдущие версии

### 2. ChromaDB Store (`kbk/store.py`)

Постоянное хранилище документов с векторным поиском.

- `add()` — добавить новый документ
- `get()` — получить по id + collection
- `update()` — обновить (автоматически увеличивает version)
- `delete()` — удалить
- `search()` — семантический поиск по тексту
- `list_documents()` — все документы коллекции
- `export_to_json()` — экспорт всей базы в JSON для git

### 3. Version Manager (`kbk/versioning.py`)

Управление версиями документов.

- `save_snapshot()` — сохранить слепок документа при изменении
- `get_history()` — история версий
- `rollback()` — откат к предыдущей версии
- `diff()` — показать изменения между версиями

Версии хранятся в отдельной директории (`~/.local/share/kbk/snapshots/`).

### 4. Sync Manager (`kbk/sync.py`)

Синхронизация между инстансами через git.

- `push_to_git()` — экспортировать ChromaDB в JSON + git commit + push
- `pull_from_git()` — git pull + импорт JSON в ChromaDB
- `detect_conflicts()` — найти конфликты (документ изменён в обоих инстансах)
- `resolve_conflict()` — разрешить конфликт (по таймстемпам или ручной выбор)

## Data Flow

### Запись

```
kbk add --collection projects --id "foo" --content "..."
  → Document создаётся с version=1
  → Store.add() сохраняет в ChromaDB
  → VersionManager.save_snapshot() сохраняет в JSON
```

### Обновление

```
kbk add (с существующим id)
  → Store.update(): version увеличивается, old_version сохраняется
  → VersionManager.save_snapshot(): новая версия в истории
  → ChromaDB обновляет существующую запись
```

### Синхронизация (двухсторонняя)

```
Instance A:
  kbk sync
  → Экспорт ChromaDB → JSON
  → Git commit + push

Instance B:
  kbk sync
  → Git pull
  → Импорт JSON в ChromaDB
  → Если конфликт → разрешить
  → Экспорт ChromaDB → JSON
  → Git commit + push
```

## Директории

```
~/.config/kbk/config.yaml       — конфигурация
~/.local/share/kbk/chromadb/    — ChromaDB persistent data
~/.local/share/kbk/exports/     — JSON exports (для git)
~/.local/share/kbk/snapshots/   — Version history snapshots
~/knowledge-base/.git/          — Git repo (для синхронизации)
```
