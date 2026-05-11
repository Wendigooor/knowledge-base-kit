# Установка и настройка

## Требования

- Python 3.10+
- ChromaDB (устанавливается автоматически)
- Git 2.30+
- (Опционально) ssh-key для доступа к приватному репозиторию

## Установка

```bash
# Через pip
pip install knowledge-base-kit

# Или из исходников
git clone https://github.com/Wendigooor/knowledge-base-kit.git
cd knowledge-base-kit
pip install -e .
```

## Инициализация

```bash
# Создать новую базу знаний
kbk init --path ~/my-knowledge-base

# Инициализировать git-репозиторий для синхронизации
cd ~/my-knowledge-base
git init
git remote add origin git@github.com:your-org/knowledge-base.git
```

## Конфигурация

Конфигурационный файл: `~/.config/kbk/config.yaml`

```yaml
# Knowledge Base Kit Configuration

# Путь к ChromaDB persistent storage
db_path: ~/.local/share/kbk/chromadb

# Путь к JSON-экспортам (для git sync)
export_path: ~/my-knowledge-base/exports

# Путь к снапшотам версий
snapshot_path: ~/.local/share/kbk/snapshots

# Git remote URL (опционально)
git_remote: git@github.com:your-org/knowledge-base.git

# Стратегия разрешения конфликтов
conflict_strategy: last-writer-wins  # last-writer-wins | keep-local | keep-remote | manual
```

## Настройка cron (автоматическая синхронизация)

```bash
# Добавить в crontab
crontab -e

# Строка: каждые 30 минут
*/30 * * * * cd ~/my-knowledge-base && kbk sync > ~/my-knowledge-base/sync-log.txt 2>&1
```

Или использовать скрипт `scripts/sync.sh`:

```bash
# Добавить в crontab
*/30 * * * * /usr/local/bin/bash ~/my-knowledge-base/scripts/sync.sh
```

## Бустрап нового инстанса

При развёртывании нового агента:

```bash
# 1. Клонировать базу знаний
git clone git@github.com:your-org/knowledge-base.git ~/knowledge-base

# 2. Инициализировать kbk
kbk init --path ~/knowledge-base

# 3. Засеять ChromaDB из последнего экспорта
kbk seed --seed-file ~/knowledge-base/exports/chromadb-export.json

# 4. Настроить cron
crontab -e
# */30 * * * * cd ~/knowledge-base && kbk sync
```

## Добавление документов

```bash
# Простое добавление
kbk add \
  --collection projects \
  --id "quest-system-v2" \
  --content "Quest System v2: архитектура с тремя слоями..." \
  --tag "architecture" \
  --tag "v2.0"

# С метаданными
kbk add \
  --collection decisions \
  --id "use-postgres-over-mongo" \
  --content "Решение: используем PostgreSQL 16 для хранения квестов, потому что..." \
  --tag "database" \
  --tag "decision" \
  --tag "2026-05-11" \
  --metadata '{"author": "igor", "source": "meeting", "confidence": 0.95}'
```

## Поиск

```bash
# Семантический поиск по всем коллекциям
kbk search "quest architecture design"

# Поиск в конкретной коллекции
kbk search "quest" --collection projects

# Ограничить количество результатов
kbk search "quest" --limit 5
```

## Пример рабочего процесса

```bash
# 1. Новый инстанс
git clone git@github.com:org/knowledge.git ~/kb
cd ~/kb && kbk init --path . && kbk seed

# 2. Работа: добавить знание
kbk add --collection decisions --id "use-crdt" \
  --content "Решили использовать CRDT для разрешения конфликтов..." \
  --tag "architecture" --tag "v2"

# 3. Синхронизация (ручная или cron)
kbk sync

# 4. Другой инстанс через 30 минут:
#    cron запускает kbk sync → получает новые документы
```
