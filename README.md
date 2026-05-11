# Knowledge Base Kit

Векторная база знаний с версионированием, тегированием и синхронизацией между инстансами.

## Зачем

LLM агентам нужна память: факты о проекте, люди, принятые решения, архитектура. ChromaDB даёт поиск по смыслу, git даёт версионирование и синхронизацию. Этот проект соединяет их в единую систему.

## Быстрый старт

```bash
pip install knowledge-base-kit

# Инициализировать базу
kbk init --path ./my-knowledge-base

# Добавить документ
kbk add \
  --collection projects \
  --id "quest-system-v2" \
  --content "Архитектура квестов: Service → Campaign → Quest" \
  --tag "architecture" \
  --tag "v2.0"

# Поиск
kbk search "quest architecture"

# Синхронизация с git
kbk sync

# Статус
kbk status

# История версий
kbk history projects quest-system-v2

# Откат к предыдущей версии
kbk rollback projects quest-system-v2 --version 1
```

## Архитектура

```
┌─────────────┐     ┌──────────────┐     ┌───────────┐
│  Documents   │────▶│  ChromaDB    │────▶│  Search   │
│  (model)     │     │  (store)     │     │  (semantic)│
└─────────────┘     └──────────────┘     └───────────┘
       │                      │
       ▼                      ▼
┌─────────────┐     ┌──────────────┐
│  JSON Dump  │◀───▶│  Git Repo    │
│  (versions)  │     │  (sync)      │
└─────────────┘     └──────────────┘
```

Документы живут в ChromaDB для быстрого поиска. При каждом изменении создаётся JSON-слепок, который пушится в git. Между инстансами — синхронизация через git pull/push.

## Документация

- [Архитектура](docs/architecture.md)
- [Формат документов](docs/document-format.md)
- [Протокол синхронизации](docs/sync-protocol.md)
- [Установка и настройка](docs/setup.md)
