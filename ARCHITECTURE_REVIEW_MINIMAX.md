# Architecture Review: Knowledge Base Kit (kbk)

> Review by: MiniMax M2.7 via Hermes Agent
> Date: 2026-05-11
> Model: minimax-m2.7 (opencode.ai/zen/go/v1)

## 1. Architecture Assessment

### Structure: Adequate, Not Excellent

```
cli.py → store.py / versioning.py / sync.py → ChromaDB / Git / Config
```

The layering is *conventional* but has muddied boundaries:

| Problem | Location | Impact |
|---------|----------|--------|
| `store.py` mixes ChromaDB CRUD with file I/O (`export_to_json`) | Single class | Violates SRP; hard to test |
| `sync.py` reads/writes JSON directly, bypassing `versioning.py` | Duplicated logic | Drift between versioning state and git state |
| `Document.previous_versions` implies recursive embedding | Data model | Memory/time explosion for deep history |

**Positive:** Clear exception taxonomy. Decent component separation overall.

**Concerning:** No transaction boundary spanning ChromaDB + Git. If `add()` succeeds but `git commit` fails, you have an inconsistent system with no rollback.

---

## 2. Top 3 Production Risks

### Risk 1: ChromaDB ↔ Git State Drift (HIGH)

```
Scenario: Process A syncs, pushes. Process B crashes mid-add.
Result: ChromaDB has doc X, git does not. No recovery mechanism.
```

**Mitigation needed:** Atomic operations across ChromaDB + git, or idempotent sync that can reconcile on restart.

### Risk 2: Unbounded `previous_versions` Memory Growth (HIGH)

```python
# Current model - every Document carries its full ancestry
class Document:
    previous_versions: List[Document]  # O(n) memory per doc per version
```

For a document with 100 versions, you load 100 Document objects into memory on every `get()`. With moderate usage (500 docs × 50 versions), you're holding 25,000 nested objects.

**Fix:** Flat storage model. Versions are separate records keyed by `(doc_id, version_id)`, never embedded.

### Risk 3: Git is the Wrong Storage Backend for This (MEDIUM)

You're using git blobs to store JSON snapshots. This works for prototypes but breaks at scale:

- Git is not designed for binary/compressed document storage
- No concurrent write safety without explicit file locking
- `git gc` becomes necessary but dangerous if clients hold references
- Rebasing history (common in personal repos) can corrupt client state

**Alternative:** SQLite with git for *metadata only*, or use git-lfs, or drop git entirely and use a proper document DB.

---

## 3. Sync Model Evaluation

**Current approach:** `pygit2` push/pull of JSON files in a git repo.

### Soundness: Partially

**Good:**
- Leverages existing git infrastructure
- Conflict detection via `DiffView` is appropriate
- No server required; works with existing git hosting

**Bad:**
- The sync logic operates directly on filesystem JSON, not through the versioning abstraction
- This bypasses `VersionManager` entirely. If `Document.to_dict()` format diverges from what `VersionManager` expects, silent corruption occurs.
- **No soft-delete handling:** Deleted docs in ChromaDB have no equivalent in git (what gets committed? Nothing? A tombstone?)
- **No partial sync:** `sync --since "2024-01-01"` doesn't exist. Full repo sync on every call.
- **Conflict resolution is ad-hoc:** `ConflictError` exists but there's no documented resolution strategy.

### Recommendation:
Define a sync protocol, not just "serialize everything to JSON and push." Consider:
1. Tombstone files for deletes
2. Merkle tree or checksum manifest to avoid unnecessary transfers
3. Lock files for concurrent access

---

## 4. Versioning Comparison

| Approach | Your Implementation | Better Alternatives |
|----------|---------------------|---------------------|
| **Content-addressable** (git) | No. Uses sequential versions | Use `hash(content)` as primary key |
| **Event sourcing** | No. Overwrites in place | Append-only log with snapshots |
| **Merkle tree** | No | Enables efficient partial sync |
| **Flat storage** | No. Nested `previous_versions` | Separate table/collection per version |

**Specific issues with current versioning:**

1. **No canonical version identifier:** `Document.version` is presumably an integer or string that you increment. What happens on concurrent edits?

2. **Diff is probably string-based:** This loses semantic structure. For document management, structural diffs (JSON-patch, RFC 6902) would be more useful.

3. **Prune is destructive:** No recovery mechanism after prune. Production systems need soft-prune or archived snapshots.

---

## 5. Missing for v0.2

### Critical (Must Have)

- [ ] **Idempotent sync:** Rerunning `sync` should not produce duplicate/divergent state
- [ ] **Backup/restore:** No way to recover from ChromaDB corruption
- [ ] **Concurrent access control:** File locks or SQLite-based serialization
- [ ] **Soft delete:** `delete()` removes from ChromaDB, what's in git?
- [ ] **Test coverage:** You mention 7 fixed bugs but don't mention tests. For a data management tool, this is alarming.

### Important (Should Have)

- [ ] **Batch operations:** `add_batch()` / `delete_batch()` for performance
- [ ] **Partial sync:** Sync only changed documents, not entire repo
- [ ] **Migration path:** Version field on config/schema for forward/backward compatibility
- [ ] **Observability:** Logging at operation boundaries, not just CLI output
- [ ] **Graceful degradation:** What happens when git is unavailable? When ChromaDB is corrupted?

### Nice to Have (v0.2+)

- [ ] **Structured diffs** (JSON Patch / RFC 6902)
- [ ] **Content hashing** as primary document identity (SHA-256 of content)
- [ ] **Collection-level operations:** Backup/restore/sync entire collections
- [ ] **Conflict resolution UI** (interactive merge for document conflicts)

---

## Summary Verdict

**Architecture:** 5/10 — Functional prototype, not production-ready. Boundaries are blurred, state management is fragile.

**Production Readiness:** 3/10 — State drift, memory explosion, and no concurrency control are blockers.

**Sync Model:** 6/10 — Conceptually sound, implementation needs rigor (tombstones, idempotency, partial sync).

**Recommendation:** Do not ship v0.2 until:
1. Flat version storage replaces nested `previous_versions`
2. Atomic sync operations with rollback on failure
3. Soft-delete with tombstones in git
4. Test suite covering core operations
5. Concurrent access strategy (locks or SQLite serialization)
