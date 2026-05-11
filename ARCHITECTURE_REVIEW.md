# Architecture Review: Knowledge Base Kit (kbk)

> Review date: 2026-05-11
> Reviewed by: Hermes Agent (after fixing 7 critical bugs)
> Requested model: GLM-5.1 (unavailable — 403 Forbidden via opencode-go)
> Actual: manual review based on code analysis

---

## Summary

KBK is a CLI tool for managing versioned document stores with ChromaDB backend, git sync, and semantic search. ~1500 lines of Python across 7 modules.

**Verdict:** v0.1 — works, but needs hardening. The architecture is sound for a prototype. 3 real problems would block production use.

---

## 1. Separation of Concerns — OK with one exception

`store.py` (ChromaDB CRUD) and `versioning.py` (snapshot management) are cleanly separated. `cli.py` delegates to both correctly after the bugfixes.

**Problem:** `sync.py` has too many responsibilities:
- Git repo init/management
- Document export/import to JSON files
- Push/pull to remote
- Conflict detection AND resolution
- Status reporting

Should be split: `sync.py` (git operations) + `conflict.py` (detection/resolution).

## 2. Sync Model — fragile but workable

The sync model is: ChromaDB is source of truth → export to JSON → commit to git → push.

**Problems:**
1. **pygit2 dependency** — heavy, requires libgit2 system library. `pip install pygit2` fails on many systems. Alternatives: `gitpython` (pure Python), or shell out to `git` CLI (zero dependencies).
2. **JSON export as sync format** — each document is a separate JSON file. With 10k documents, `git status` is slow. Better: single NDJSON file per collection, or use ChromaDB's native export.
3. **No sync locking** — if two instances push simultaneously, the second push fails (no `pull --rebase`). The `Hermes sync-and-push.sh` handles this with retries; kbk doesn't.
4. **Git remote URL is optional** — `git_remote_url: Optional[str]` means the entire sync layer is no-op if not configured. This is fine for local-first but confusing: `sync` command succeeds without doing anything.

## 3. Versioning — works but wasteful

Each document's full version history is stored as a single JSON blob in `~/.kbk/versions/<doc_id>.json`. The entire history (current + all previous versions) is rewritten on every save.

**Problems:**
1. **Write amplification** — saving a 1MB document with 50 versions rewrites 50MB every time.
2. **No compression** — for knowledge base documents that grow over time (meeting notes, specs), version bloat is real.
3. **`max_versions_per_doc`** exists in config but `prune()` is never called automatically. Versions pile up forever.
4. **Rollback is destructive** — `versioning.rollback()` saves the current state before restoring, which is correct. But `store.update(restored)` in `cli.py:rollback` overwrites the DB entry. If rollback fails midway, the document is in an inconsistent state.

**Fix:** call `prune()` after every `save_snapshot()`. Add a `--force` flag to rollback for safety. Consider git-based versioning instead of JSON snapshots.

## 4. Error Handling — minimal

- `store.py` wraps ChromaDB errors in `StoreError` — ✅
- `versioning.py` raises `VersioningError` — ✅
- `sync.py` raises `SyncError` — ✅
- `cli.py` — most commands don't catch exceptions 🚩

```python
# cli.py currently:
doc = store.get(doc_id, collection)  # returns None → handled
results = store.search(...)  # raises StoreError → NOT handled 🚩
```

**Fix:** wrap all CLI command bodies in `try/except (StoreError, VersioningError, SyncError) as e: click.echo(f"❌ {e}", err=True); sys.exit(1)`

## 5. Security — no concerns, but...

- No credentials stored in code ✅
- pygit2 uses default SSH/HTTPS auth ✅
- Config file can contain `git_remote_url` with embedded tokens — **document that this is a risk** 🚩
- No input validation on document content (XSS if displayed in web UI) — not relevant for CLI ✅

## 6. Portability — good for a prototype

- Pure Python, pip installable ✅
- ChromaDB as only heavy dependency ❌ (~200MB with sentence-transformers)
- pygit2 requires C library ❌
- Config paths are `~/.kbk/` — predictable, portable ✅

**Fix:** make pygit2 optional, fall back to `git` CLI. Swap sentence-transformers for a smaller embedding model (e.g., `all-MiniLM-L6-v2` is already configured — good).

## 7. Testing — none

Zero tests. Not even a smoke test. A `kbk add` without a running ChromaDB gives a cryptic error.

**Must have before v0.2:**
- `test_store.py` — CRUD + search
- `test_versioning.py` — save, history, rollback, prune
- `test_cli.py` — Click runner tests
- `test_sync.py` — git operations in temp dir

---

## Action Items

| Priority | What | Why |
|----------|------|-----|
| 🔴 HIGH | Add error handling to CLI commands | Currently crashes on ChromaDB failure |
| 🔴 HIGH | Add basic tests | Can't refactor confidently |
| 🟡 MEDIUM | Make pygit2 optional | Portability |
| 🟡 MEDIUM | Auto-call prune() after save_snapshot() | Version bloat |
| 🟢 LOW | Split sync.py into sync + conflict | Cleaner architecture |
| 🟢 LOW | Replace pygit2 with git CLI calls | Zero dependencies |
| 🟢 LOW | Add sync locking (pull before push) | Cross-instance safety |

---

## Comparison: kbk vs Hermes-native sync

| Aspect | KBK | Hermes-native (this repo) |
|--------|-----|--------------------------|
| Storage | ChromaDB + JSON | ChromaDB + git |
| Sync | pygit2 push/pull | sync-and-push.sh |
| Versioning | JSON snapshots | ChromaDB export timestamps |
| CLI | Click (8 commands) | cron + Telegram |
| Portability | pip install | git clone |
| Tests | ❌ None | ⚠️ Manual QA only |

KBK makes sense as a standalone product for external use. For internal Hermes sync, the native system is simpler and already works.
