# Architecture Review: Knowledge Base Kit (GLM-5.1)

> Review by: GLM-5.1 via opencode.ai
> Date: 2026-05-11

# Architectural Review: Knowledge Base Kit (kbk)

## 1. What Breaks First in Production

**The `previous_versions` nesting kills you on day one.** Not eventually—immediately.

```python
# document.py — the time bomb
@dataclass
class Document:
    id: str
    version: int
    previous_versions: List[Document]  # ← each contains its own previous_versions
    content: str
    metadata: Dict
    # ...
```

A document at version 50 contains a Document at v49, which contains v48, which contains v47... The serialized JSON for a single document is the sum of 50+49+48+...+1 = 1,275 document snapshots. With 500 documents averaging 50 versions, you're not storing 25,000 versions—you're storing **~6.4 million** document copies in nested form.

This breaks in three specific ways, in this order:

**a) ChromaDB metadata bloat on read.** When you call `collection.get()` or `collection.query()`, ChromaDB returns the full metadata dict for every matching document. That metadata now contains the entire nested version chain as a serialized JSON string. A single `search` call returning 10 results could pull megabytes of nested JSON. ChromaDB's internal SQLite has practical metadata size limits. You'll hit `sqlite3.DatabaseError` or silent truncation.

**b) Deserialization stack overflow.** `dataclasses-json` recursively deserializes nested dataclasses. Deep version chains (50+) will blow the Python recursion limit or take seconds per document.

**c) Memory explosion on `list` or `export`.** Any operation that loads multiple documents into memory simultaneously is O(n × v²) where n=documents, v=avg versions. 500 docs × 50 versions = you're holding ~6.4M document objects in RAM.

**The second thing that breaks:** sync conflicts. Git merge on JSON blobs is line-based. Two users edit the same document, the JSON reorders keys or changes nested fields, and you get a conflict that's essentially unresolvable automatically. Your `ConflictError` will fire on nearly every concurrent edit, and manual resolution of JSON diffs is not viable for end users.

---

## 2. Top 5 Specific Fixes (Ranked by Impact)

### Fix 1: Flatten Version Storage — Eliminate `previous_versions`

```python
# BEFORE (broken)
@dataclass
class Document:
    previous_versions: List[Document]  # O(n²) nesting

# AFTER
@dataclass  
class Document:
    id: str
    version: int
    # No previous_versions field at all

@dataclass
class VersionRecord:
    doc_id: str
    version: int
    content: str
    metadata: Dict
    timestamp: datetime
    # Flat, no nesting
```

Store versions in a separate collection/table keyed by `(doc_id, version)`. Fetching history is a query, not a recursive descent. This alone reduces storage from O(n × v²) to O(n × v) and eliminates the recursion/deserialization problem.

### Fix 2: Stop Using ChromaDB as the Primary Data Store

```python
# store.py — current pattern (broken)
class DocumentStore:
    def add(self, doc: Document):
        self.collection.add(
            ids=[doc.id],
            documents=[doc.content],
            metadatas=[{...}]  # ← all version data in metadata
        )
```

ChromaDB is a **vector index**, not a database. It has:
- No transactions
- No referential integrity
- No multi-collection joins
- Metadata stored as flat strings (no indexing on nested fields)
- No write-ahead log (crash = data loss)

**Fix:** Use SQLite as the source of truth. ChromaDB becomes a read-optimized search index that gets rebuilt from SQLite.

```python
class DocumentStore:
    def __init__(self, path):
        self.db = sqlite3.connect(path / "kbk.db")  # source of truth
        self.chroma = chromadb.Client()              # search index only
    
    def add(self, doc: Document):
        # 1. Write to SQLite (transactional)
        with self.db:
            self.db.execute("INSERT INTO documents ...", ...)
            self.db.execute("INSERT INTO versions ...", ...)
        # 2. Update ChromaDB index (can be rebuilt from SQLite)
        self.chroma_collection.add(...)
```

### Fix 3: Replace Git-as-Database with Git-as-Transport

The current `sync.py` stores JSON blobs in git. This is wrong at a fundamental level. Git tracks line-oriented text. JSON is not line-oriented text.

**Two options, pick one:**

**Option A: Store documents as individual Markdown/YAML files (git-friendly):**
```
.kbk/
  collections/
    my-collection/
      doc-abc123.md      # content
      doc-abc123.yaml    # metadata + version pointer
```
Now `git diff` produces meaningful output. `git merge` has a fighting chance. This is how git-based wikis (Gollum, Obsidian Git) work.

**Option B: Ditch git, use a proper sync protocol:**
```python
# sync.py — replace pygit2 with HTTP-based sync
class SyncClient:
    def push(self, local_changes: List[VersionRecord]) -> SyncResult:
        # POST /sync/push with change vectors
        # Server returns conflicts or ACK
    def pull(self, since: datetime) -> List[VersionRecord]:
        # GET /sync/pull?since=...
```
This eliminates the C-library dependency (pygit2) and gives you proper conflict resolution semantics.

### Fix 4: Add Transaction Boundaries

Currently, `store.py` writes to ChromaDB and `sync.py` writes to git with no coordination. If the process crashes between them, you have inconsistent state.

```python
# versioning.py — add write-ahead log
class VersionManager:
    def save(self, doc: Document) -> Document:
        # 1. Write intent to WAL
        wal.write({"action": "save", "doc_id": doc.id, "version": doc.version + 1})
        # 2. Write to primary store (SQLite)
        db.execute("INSERT INTO versions ...")
        # 3. Update search index
        chroma.upsert(...)
        # 4. Commit WAL
        wal.commit(doc.id)
```

On startup, replay any uncommitted WAL entries. This is the minimum viable consistency guarantee.

### Fix 5: Add Idempotent Operations and Soft