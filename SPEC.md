# Knowledge Base Kit — Fix & Ship Spec

## Scope
Довести проект до рабочего состояния и запуштить на GitHub.

## Current State
- `~/Documents/projects/knowledge-base-kit/` — полный код, 5 модулей (config, document, store, sync, versioning) + CLI + docs + scripts
- Нет `.git` репозитория
- Нет remote на GitHub
- `pyproject.toml` — сломан build-backend
- `.venv/` уже есть (Python 3.11)
- `kbk/exceptions.py` — существует

## Issues to Fix

### 1. pyproject.toml (CRITICAL)
```toml
# СТРОКА 3 — СЕЙЧАС (СЛОМАНО):
build-backend = "setuptools.backends._legacy:_Backend"
# ДОЛЖНО БЫТЬ:
build-backend = "setuptools.build_meta"
```

### 2. cli.py line 128 (BUG)
```python
# СЕЙЧАС (ОПЕЧАТКА):
click.eo("✅ Sync complete")
# ДОЛЖНО БЫТЬ:
click.echo("✅ Sync complete")
```

### 3. Git repo init + first commit
- Инициализировать `git init`
- Создать `.gitignore` (__pycache__, .venv, *.pyc, .DS_Store, .kbk/, chromadb/)
- `git add -A && git commit -m "Initial commit: KBK v0.1.0"`

### 4. GitHub remote
- Репозиторий: `git@github.com:Wendigooor/knowledge-base-kit.git`
- `git remote add origin git@github.com:Wendigooor/knowledge-base-kit.git`
- `git push -u origin main`

### 5. Verify
- `pip install -e .` должен работать
- `kbk --help` должен показывать help
- `kbk init --path /tmp/test-kbk && kbk status` — тест E2E

## Notes
- Python 3.11, macOS
- Зависимости: chromadb>=0.4.0, click>=8.1, pyyaml>=6.0, pygit2>=1.12, rich>=13.0
- SSH ключ настроен на GitHub (Wendigooor)
