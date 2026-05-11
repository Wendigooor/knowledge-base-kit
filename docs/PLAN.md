# Knowledge Base Kit — Остаток работ

Запушено: https://github.com/Wendigooor/knowledge-base-kit

**Статус:** `git commit abffaed` (initial) + `2d8e959` (config.py + versioning.py fixes)

---

## ❌ Что осталось доделать (CRITICAL — 7 багов)

CLI и store/versioning не стыкуются. DeepSeek V4 Flash нашёл все проблемы.

### 1. `kbk/store.py` — добавить 3 метода

- `_init_client()` — пустышка: `_ = self.client`
- `export_to_json(path)` — выгрузить все документы в JSON
- `search()` — переделать сигнатуру под CLI: `n_results=` и `collection_filter=` вместо `top_k` и `collection`

### 2. `kbk/cli.py` — исправить 7 вызовов

- `cli()`: заменить `KBKConfig.load(config)` на `load_config(config)`, передавать `config=cfg` в `VersionManager`
- `init`: добавить `sync_mgr._get_or_init_repo()`
- `search`: использовать новую сигнатуру `store.search()`, убрать распаковку tuple
- `history`: убрать `collection` из вызова `versioning.get_history()`
- `rollback`: сначала получить Document через `store.get()`, потом вызвать `versioning.rollback(doc, version)`
- `sync`: передать документы в `push_to_git(all_docs)`
- `status`: убрать `versioning.snapshot_count()` — теперь работает

---

## ✅ Что уже сделано и запушено

| Файл | Изменения |
|------|-----------|
| `config.py` | Добавлены поля: `versions_dir`, `export_path`, метод `load()` |
| `versioning.py` | `__init__` принимает config, метод `snapshot_count()` |
| `pyproject.toml` | `build-backend` исправлен на `setuptools.build_meta` |
| `cli.py` | `click.eo` → `click.echo` |
| `.gitignore` | Базовый gitignore |
| GitHub repo | Создан, первый commit запушен |

---

## Когда делать

Когда скажешь «доделывай». Хочешь — сразу DeepSeek V4 Flash дёрну, хочешь — локальным Qwen доделаю (но будет больше итераций).

Ориентир: 30-40 минут через DeepSeek, ~2 часа на Qwen.
