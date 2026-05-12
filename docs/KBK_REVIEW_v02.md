# KBK v0.2 — Full Review Package

> Enterprise Semantic Index. Pull + Allowlist. MCP + Showcase.
> v0.2 | 11/11 tests | ATM berserk 3 runs | Generated: 2026-05-12

---

## Architecture

```
[Confluence] --------+ kbk sync ----- [StateTracker SHA-256] --- [Indexer AI Pipeline]
[GitLab] ------------+                      |                        |
                     |                diff/skip                  clean to LLM to chunk to embed
                     +---------------------------------------------- ChromaDB
                                                                      |
                                                            +---------+----------+
                                                            |                    |
                                                      MCP Server        Confluence Showcase
                                                      (search, list)    (read-only index page)
```

**Key decisions:**
- Pull only (no webhooks) — zero infrastructure, cron or manual trigger
- Allowlist in targets.yaml — no accidental indexing of draft/trash pages
- SHA-256 dedup — skip unchanged docs, save LLM cost
- One LLM call per doc (summarize + classify combined) — ~$0.002/doc
- Chunk at 1k tokens with word-boundary overlap
- ChromaDB for vectors, metadata carries source_url + access_group

---

## targets.yaml (Allowlist)

```yaml
targets:
  - type: confluence
    location: "ARCH"
    filter_query: "label = 'approved' OR label = 'adr'"
    access_group: "public"
  - type: confluence
    location: "ENG"
    filter_query: "label = 'runbook'"
    access_group: "public"
```

---

## Data Model (kbk/models.py)

```python
@dataclass
class IndexedChunk:
    id: str = ""                    # Deterministic: sha256(source_url:content_hash:collection)
    source_url: str = ""            # Link to original (Confluence/GitLab)
    content: str = ""               # Cleaned text chunk
    summary: str = ""               # LLM-generated summary (2-3 sentences)
    tags: list[str] = field(default_factory=list)
    access_group: str = "public"    # ACL field (enforced in search)
    content_hash: str = ""          # SHA-256 of raw document
    collection: str = "unclassified" # Grouping (arch, runbooks, platform)
```

ID is deterministic — same doc always produces the same ID.

---

## State Tracker (kbk/state.py)

SHA-256 hash-based dedup with atomic writes and file locking.

```python
def _save(self):
    # Atomic write: temp file + replace
    tmp = self.path.with_suffix(".tmp")
    tmp.write_text(json.dumps(self._data, indent=2))
    tmp.replace(self.path)

def has_changed(self, url, content_hash):
    existing = self._data.get(url)
    return existing is None or existing.get("hash") != content_hash

def mark_indexed(self, url, content_hash, chunk_ids=None):
    self._data[url] = {"hash": content_hash, "chunk_ids": chunk_ids or []}
    self._save()

def acquire_lock(self, blocking=True):
    # POSIX fcntl.flock prevents concurrent sync corruption
```

---

## ChromaDB Store (kbk/store.py)

```python
class KnowledgeStore:
    def upsert_chunk(self, chunk):
        meta = {"chunk_id": chunk.id, "source_url": chunk.source_url,
                "summary": chunk.summary, "tags": json.dumps(chunk.tags),
                "access_group": chunk.access_group, "content_hash": chunk.content_hash}
        col.upsert(ids=[chunk.id], documents=[chunk.content], metadatas=[meta])

    def search(self, query, n_results=10, collection_filter=None,
               filters=None, access_group=None):
        where = None
        if access_group: where = {"access_group": {"$eq": access_group}}
        results = col.query(query_texts=[query], n_results=n_results, where=where)
```

access_group enforced at search level. Logging instead of silent pass for delete failures.

---

## AI Pipeline (kbk/indexer.py)

```python
class Indexer:
    def clean_html(self, html):
        # Preserve code blocks: replace <> inside <code>/<pre>/<tt>
        text = re.sub(r'<code>(.*?)</code>', lambda m: protect_code(m.group(1)), html, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)  # Strip tags
        text = text.replace("<<<LT>>>", "<").replace(">>>GT>>>", ">")  # Restore code brackets

    def _call_llm(self, prompt):
        # 3 attempts with exponential backoff. 401 raises immediately.
        for attempt in range(3):
            try: return requests.post(...).json()
            except HTTPError as e:
                if e.code == 401: raise LLMError("Auth failed")
                if e.code == 429: time.sleep(2**attempt)
                raise

    def _extract_json(self, text):
        # 5 fallback strategies: direct -> strip fences -> balanced braces -> trailing commas -> Python nulls
        for fixer in [direct, strip_fences, find_balanced, fix_trailing_commas, fix_python_nulls]:
            try: return json.loads(fixer(text))
            except: continue
        return None

    def _summarize_and_classify(self, text, title=""):
        # Single LLM call: structured JSON for both summary + tags
        prompt = f"Analyze '{title}'. Return JSON: {{summary: '...', tags: [...]}}"
        parsed = self._extract_json(self._call_llm(prompt))
        return parsed.get("summary","")[:500], parsed.get("tags",[])[:10]

    def chunk(self, text, chunk_size=1000, overlap=100):
        # Sentence-boundary split with word-boundary overlap
        sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
        for s in sentences:
            if len(current) + len(s) > chunk_size:
                # Take overlap from end, extend to word boundary
                word_boundary = current.find(' ', len(current) - overlap)
                overlap_text = current[word_boundary+1:] if word_boundary > 0 else current[-overlap:]
                current = overlap_text + " " + s
```

---

## Confluence Connector (kbk/connectors/confluence.py)

- Exponential backoff for 429 rate limits
- Pagination with early exit (no extra call when results < limit)
- Safety cap at 10k pages
- Version.number preserved in metadata
- `list_known_urls()` for orphan reconciliation

---

## MCP Server (kbk/mcp_server.py)

MCP protocol over stdio. Three tools:

- **search_knowledge(query, collection, limit, access_group)** — semantic search
- **get_document_summary(collection, limit)** — list documents
- **list_collections()** — list available collections

access_group enforced. Results capped at 50.

---

## Showcase Builder (kbk/showcase.py)

Confluence Storage Format HTML with expand/collapse sections per collection.
All user content is `html.escape()`'d. Confluence API errors logged + raised.

---

## CLI (kbk/cli.py)

```
kbk init              Create ChromaDB, StateTracker, sample targets
kbk sync              Pull + Diff + ETL + Embed (--dry-run for cost)
kbk serve             MCP stdio server (for Cursor/Claude)
kbk build-showcase    Generate Confluence showcase or Markdown
kbk search <query>    Semantic search
kbk status            Index stats
```

Error handling: KeyboardInterrupt -> exit(130), StoreError -> user message, generic -> user message.

---

## Edge Cases Handled

| Edge Case | Solution |
|-----------|----------|
| API Rate Limits (Confluence) | Exponential backoff (2^attempt) |
| LLM Cost Runaway | StateTracker dedup + --dry-run + single LLM call |
| Context Loss (chunking) | Summary per chunk, word-boundary overlap |
| HTML Garbage | Code/pre/tt protection, ac:macro removal, entities |
| Broken State File | Atomic write (tmp+replace), corrupt backup to .corrupt.bak |
| Empty Content | Early return empty list |
| XSS (Showcase) | html.escape() on all user-originated data |
| ACL Bypass | access_group enforced at store.search + MCP level |
| KeyboardInterrupt | Not caught, clean exit(130) |
| Confluence API Failure | Logged + re-raised (not silent None) |
| Duplicate IDs | Deterministic hash: same doc = same ID |
| LLM Auth Error | 401 raises immediately (no retry) |
| Concurrent Sync | fcntl.flock — second gets "already running" |
| LLM JSON Parse Failure | 5-strategy robust extraction |
| Orphan Documents | Reconciliation in kbk sync |

---

## ATM Runs (3 runs, 18/18 gates total)

| Run | Gates | Description |
|-----|-------|-------------|
| kbk-v02 | 6/6 | Initial implementation |
| kbk-v02-fixes | 6/6 | 15 fixes from GLM-5.1 + Kimi K2.5 |
| kbk-v02-review-fixes | 6/6 | 7 fixes from Gemini review |

---

## GitHub

https://github.com/Wendigooor/knowledge-base-kit
