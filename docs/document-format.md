# Формат документов

## Базовая структура

Каждый документ в системе — это экземпляр класса `Document`:

```python
@dataclass
class Document:
    id: str                      # уникальный идентификатор
    version: int = 1             # номер версии (начинается с 1)
    tags: list[str] = None       # теги для фильтрации
    metadata: dict = None        # произвольные метаданные
    content: str = ""            # содержимое документа
    collection: str = "default"  # логическая группа
    created_at: str = None       # ISO timestamp создания
    updated_at: str = None       # ISO timestamp последнего изменения
    previous_versions: list[str] = None  # ссылки на предыдущие версии
```

## Версионирование

Каждый документ имеет номер версии. При каждом обновлении:

1. Текущее состояние сохраняется в snapshot (коллекция/id/версия/)
2. version увеличивается на 1
3. updated_at обновляется
4. В previous_versions добавляется ссылка на предыдущую версию

Пример структуры снапшотов:

```
~/.local/share/kbk/snapshots/
  projects/
    foo/
      v1.json
      v2.json
      v3.json
    bar/
      v1.json
```

## Тегирование

Теги — строковые метки для фильтрации и организации документов. Рекомендации:

- Использовать kebab-case: `architecture`, `quest-system`, `v2-0`
- Теги версий: `v1.0`, `v2.0`, `v13.2`
- Теги категорий: `decision`, `architecture`, `people`, `config`, `meeting`
- Один документ может иметь несколько тегов

## Метаданные

Метаданные — произвольный JSON-объект. Рекомендуемые поля:

```json
{
  "source": "slack",           // откуда получено
  "author": "arslouskiy",      // кто добавил
  "project": "quest-system",   // связанный проект
  "date": "2026-05-11",        // дата источника
  "product_version": "v13.2",  // версия продукта (для тегирования)
  "confidence": 0.95           // уверенность в данных
}
```

## Формат экспорта (JSON)

При экспорте в git используется следующий формат:

```json
{
  "exported_at": "2026-05-11T14:22:42+02:00",
  "collections": {
    "projects": [
      {
        "id": "quest-system-v2",
        "version": 3,
        "tags": ["architecture", "v2.0"],
        "metadata": {
          "source": "meeting",
          "date": "2026-05-10"
        },
        "content": "Архитектура квестов: три слоя...",
        "collection": "projects",
        "created_at": "2026-05-01T10:00:00",
        "updated_at": "2026-05-11T14:00:00",
        "previous_versions": ["v1", "v2"]
      }
    ]
  }
}
```

## Пример добавления

```bash
kbk add \
  --collection architecture \
  --id "quest-service-design" \
  --content "Quest Service отвечает за lifecycle кампаний. Три компонента: Campaign Manager (создание/редактирование), Quest Engine (выполнение), Reward Distributor (награды). Кампания содержит N квестов с условиями и наградами." \
  --tag "quest-system" \
  --tag "v2.0" \
  --tag "architecture" \
  --metadata '{"source": "meeting-2026-05-10", "author": "igor", "confidence": 0.9}'
```
