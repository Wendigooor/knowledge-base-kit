# Unified Architecture Review: Knowledge Base Kit

## Consensus from 3 models

| Model | Verdict | Key Concern #1 | Key Concern #2 | Key Concern #3 |
|-------|---------|----------------|----------------|----------------|
| MiniMax M2.7 | 5/10 | Memory explosion (nested versions) | No transaction boundary | Git wrong backend for JSON |
| GLM-5.1 | 5/10 | No tests | State drift ChromaDB↔Git | No concurrent access |
| Kimi K2.5 | 5/10 | Nested previous_versions | No soft-delete | No idempotent sync |

**All 3 agree on:** Architecture is 5/10, functional prototype not production-ready.

## Unified Action Plan

### 🔴 DO NOW (this session)

| # | Fix | What | Files |
|---|-----|------|-------|
| 1 | Flat version storage | Replace nested `previous_versions` with flat `{version_id: snapshot}` dict, prune automatically | `document.py`, `versioning.py` |
| 2 | Error handling in CLI | Wrap all CLI commands in try/except | `cli.py` |
| 3 | pygit2 → optional | Try `import pygit2`, fall back to `git` CLI | `sync.py` |
| 4 | Basic smoke test | Test that CLI commands don't crash | `tests/test_smoke.py` |

### 🟡 NEXT (v0.2)

| # | Fix | Why |
|---|-----|-----|
| 5 | Soft-delete with tombstones | Deleted docs need representation in git |
| 6 | Idempotent sync | Rerunning sync shouldn't duplicate |
| 7 | Partial sync (`--since`) | Performance with 10k+ docs |
| 8 | Concurrent access (file locks) | Two processes can't write simultaneously |
| 9 | SQLite backend option | Replace git as document storage |
| 10 | Structured diffs (JSON Patch) | Semantic diff instead of string diff |

### 🟢 EVENTUAL (v1.0)

| # | Fix | Why |
|---|-----|-----|
| 11 | Content-addressed storage | SHA-256 as primary key |
| 12 | Event sourcing | Append-only log with snapshots |
| 13 | Web UI | Visual conflict resolution |
| 14 | Plugin system | Custom storage backends |
