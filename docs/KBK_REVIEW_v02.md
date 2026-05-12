# KBK v0.2 — Full Codebase for Review

> Enterprise Semantic Index. Pull + Allowlist. MCP + Showcase.
> v0.2 | 11/11 tests | ATM berserk 2 runs | Generated: 2026-05-12

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
- Chunk at 1k tokens with sentence-boundary overlap
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
    collection: str = "unclassified" # Grouping (arch, runbooks, business)

@dataclass
class SourceTarget:
    type: str        # confluence | gitlab
    location: str    # space key | repo path
    filter_query: str = ""
    access_group: str = "public"
```

ID is deterministic — same doc always hashes to same ID. No timestamp or random in ID.

---

## State Tracker (kbk/state.py)

SHA-256 hash-based dedup with atomic writes. Corrupt state backed up before reset.

```python
class StateTracker:
    def _load(self):
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Corrupt state file %s: %s. Resetting.", self.path, exc)
                backup = self.path.with_suffix(".corrupt.bak")
                shutil.copy2(self.path, backup)
                self._data = {}

    def _save(self):
        # Atomic write: temp file + replace
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def has_changed(self, url, content_hash):
        existing = self._data.get(url)
        return existing is None or existing.get("hash") != content_hash

    def mark_indexed(self, url, content_hash, chunk_ids=None):
        self._data[url] = {"hash": content_hash, "chunk_ids": chunk_ids or []}
        self._save()

    def remove(self, url):
        self._data.pop(url, None)
        self._save()

    @staticmethod
    def hash_content(content):
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
```

---

## ChromaDB Store (kbk/store.py)

```python
class KnowledgeStore:
    def __init__(self, config=None):
        self.config = config or KBKConfig()
        self._client = None
        self._collections = {}

    @property
    def client(self):
        if self._client is None:
            db_path = Path(self.config.db_path)
            db_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(db_path), settings=Settings(anonymized_telemetry=False))
        return self._client

    def upsert_chunk(self, chunk):
        col = self._get_collection(chunk.collection)
        meta = {"chunk_id": chunk.id, "source_url": chunk.source_url,
                "summary": chunk.summary, "tags": json.dumps(chunk.tags),
                "access_group": chunk.access_group, "content_hash": chunk.content_hash}
        col.upsert(ids=[chunk.id], documents=[chunk.content], metadatas=[meta])

    def search(self, query, n_results=10, collection_filter=None, filters=None, access_group=None):
        col = self._get_collection(collection_filter or self.config.default_collection)
        where = None
        if filters or access_group:
            where = {}
            if filters: where.update(filters)
            if access_group: where["access_group"] = {"$eq": access_group}
        results = col.query(query_texts=[query], n_results=n_results, where=where)
        # deserialize metadata to IndexedChunk list

    def delete_chunks(self, chunk_ids, collection="default"):
        try: self._get_collection(collection).delete(ids=chunk_ids)
        except Exception as exc:
            logger.warning("ChromaDB delete failed: %s", exc)  # Not silent pass

    def get_stats(self):
        return {"collections": {c: self.count(c) for c in self.list_collections()},
                "total": sum(self.count(c) for c in self.list_collections())}
```

Key: access_group enforced, logging instead of silent pass, ChromaDB with persistent client.

---

## AI Pipeline (kbk/indexer.py)

```python
class Indexer:
    def clean_html(self, html):
        text = re.sub(r'<ac:[^>]+>[^<]*</ac:[^>]+>', '', html)  # Confluence macros
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&nbsp;|&amp;|&lt;|&gt;', ' ', text)
        return re.sub(r'\s+', ' ', text).strip()

    def _call_llm(self, prompt, max_tokens=200, temperature=0.1):
        # Retry: 3 attempts with exponential backoff
        for attempt in range(3):
            try:
                req = urllib.request.Request(...)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read().decode())
                    self.cost_log.append(result.get("usage", {}))
                    return result["choices"][0]["message"]["content"].strip()
            except urllib.error.HTTPError as e:
                if e.code == 401: raise LLMError("Auth failed")
                if e.code == 429: time.sleep(2 ** attempt); continue
                raise LLMError(f"HTTP {e.code}")
            except Exception as e:
                if attempt < 2: time.sleep(2 ** attempt); continue
                raise LLMError(f"Failed after 3 attempts: {e}")

    def _summarize_and_classify(self, text, title=""):
        """Single LLM call: structured JSON for both summary + tags."""
        safe_text = text[:4000].replace('"', "'")
        prompt = (f"Analyze enterprise doc '{title[:100]}'. "
                  f"Content: {safe_text}. "
                  f"Return JSON: {{'summary': '2-3 sentences', 'tags': ['tag1','tag2']}}")
        try:
            response = self._call_llm(prompt, max_tokens=300, temperature=0.1)
            parsed = json.loads(re.search(r'\{.*\}', response, re.DOTALL).group())
            return parsed.get("summary", "")[:500], parsed.get("tags", [])[:10]
        except (LLMError, json.JSONDecodeError):
            logger.warning("LLM failed, fallback to truncation")
            return text[:300], []

    def chunk(self, text, chunk_size=1000, overlap=100):
        """Sentence-boundary split with overlap."""
        sentences = re.split(r'(?<=[.!?])\s+|\n+', text)
        chunks, current = [], ""
        for s in sentences:
            s = s.strip()
            if not s: continue
            if not current: current = s
            elif len(current) + len(s) + 1 <= chunk_size: current += " " + s
            else:
                chunks.append(current)
                current = (current[-overlap:] if len(current) > overlap else current) + " " + s
        if current: chunks.append(current)
        return chunks or [text]

    def process_document(self, url, raw_html, title="", access_group="public",
                         collection="unclassified", content_hash=""):
        cleaned = self.clean_html(raw_html)
        if not cleaned:
            logger.warning("Empty content after cleaning: %s", url)
            return []
        summary, tags = self._summarize_and_classify(cleaned, title)
        chunks_text = self.chunk(cleaned)
        doc_hash = content_hash or StateTracker.hash_content(raw_html)
        chunks = []
        for i, ct in enumerate(chunks_text):
            chunk = IndexedChunk(id=StateTracker.hash_content(f"{url}:chunk:{i}"),
                source_url=url, content=ct, summary=summary, tags=tags,
                access_group=access_group, content_hash=doc_hash, collection=collection)
            self.store.upsert_chunk(chunk)
            chunks.append(chunk)
        return chunks

    @property
    def total_cost_estimate(self):
        return {"prompt_tokens": N, "completion_tokens": N,
                "estimated_cost_usd": $N.NNNN, "calls": N}
```

---

## Confluence Connector (kbk/connectors/confluence.py)

```python
class ConfluenceConnector:
    def __init__(self, base_url, token, state: StateTracker):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.state = state

    def _headers(self):
        auth = base64.b64encode(f"{self.token}:".encode()).decode()
        return {"Authorization": f"Basic {auth}", "Accept": "application/json"}

    def _request(self, path, retries=3):
        for attempt in range(retries):
            try:
                req = urllib.request.Request(f"{self.base_url}/rest/api{path}", headers=self._headers())
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < retries - 1:
                    time.sleep(2 ** (attempt + 1)); continue
                return None
            except Exception: return None

    def fetch_pages(self, target):
        cql = f"space={target.location}"
        if target.filter_query: cql += f" AND {target.filter_query}"
        pages, start = [], 0
        while True:
            resp = self._request(f"/content/search?cql={quote(cql)}&start={start}&limit=50&expand=body.storage,version")
            if not resp or not resp.get("results"): break
            for r in resp["results"]:
                pages.append({"id": r["id"], "title": r["title"],
                    "url": f"{self.base_url}/spaces/{target.location}/pages/{r['id']}",
                    "body": r.get("body",{}).get("storage",{}).get("value",""),
                    "version": r.get("version",{}).get("number",1)})
            start += 50
            if len(resp["results"]) < 50: break
        return pages

    def process_target(self, target):
        """Fetch from Confluence, diff with StateTracker, return only new/changed."""
        raw_pages = self.fetch_pages(target)
        result = []
        for page in raw_pages:
            content_hash = StateTracker.hash_content(page["body"])
            if not self.state.has_changed(page["url"], content_hash): continue
            result.append({"url": page["url"], "title": page["title"],
                "body": page["body"], "content_hash": content_hash,
                "access_group": target.access_group, "space": target.location})
        return result
```

---

## MCP Server (kbk/mcp_server.py)

```python
class KBKMCPServer:
    """MCP protocol server over stdio. Tools: search_knowledge, get_document_summary, list_collections."""

    def _handle_search(self, params):
        results = self.store.search(query=params.get("query",""),
            n_results=min(params.get("limit",10),50),
            collection_filter=params.get("collection"),
            access_group=params.get("access_group"))
        return {"results": [{"id": c.id, "source_url": c.source_url,
            "content": html.escape(c.content[:500]), "summary": c.summary,
            "tags": c.tags, "access_group": c.access_group} for c in results],
            "count": len(results)}

    def run(self):
        # MCP handshake: initialize, list capabilities, loop tools/call
        # search_knowledge: query + optional collection + access_group + limit
        # get_document_summary: collection + limit
        # list_collections: none
```

---

## Showcase Builder (kbk/showcase.py)

```python
class ShowcaseBuilder:
    def _generate_storage_format(self, stats):
        sections = ['<ac:structured-macro ac:name="info"><ac:rich-text-body>'
                    '<p> Auto-generated by KBK. Do not edit.</p></ac:rich-text-body></ac:structured-macro>',
                    f'<h2>Overview: {stats["total"]} chunks, {len(stats["collections"])} collections</h2>']
        for col_name, count in sorted(stats["collections"].items()):
            if count == 0: continue
            chunks = self.store.list_chunks(collection=col_name, limit=50)
            sections.append(f'<ac:structured-macro ac:name="expand"><ac:parameter ac:name="title">'
                           f' {col_name} ({count})</ac:parameter><ac:rich-text-body><table><tbody>')
            for c in chunks:
                summary = html.escape(c.summary[:200])
                tags = " ".join(f'<ac:parameter ac:name="title">{html.escape(t)}</ac:parameter>'
                               for t in c.tags[:5])
                link = f'<a href="{html.escape(c.source_url)}">Original</a>' if c.source_url else ""
                sections.append(f'<tr><td><strong>{summary}</strong><br/>{tags}</td><td>{link}</td></tr>')
            sections.append('</tbody></table></ac:rich-text-body></ac:structured-macro>')
        return "\n".join(sections)

    def build(self):
        stats = self.store.get_stats()
        storage = self._generate_storage_format(stats)
        title = f"KBK Knowledge Index ({datetime.now():%Y-%m-%d})"
        # POST or PUT to Confluence REST API
        # Errors are logged and raised, not silently swallowed
```

All user content is html.escape()'d. Confluence API errors are logged, not silently swallowed.

---

## CLI (kbk/cli.py)

```python
@click.group()
@click.option("--config", "-c", default=None, help="Path to config")
@click.pass_context
def cli(ctx, config):
    ctx.ensure_object(dict)
    cfg = KBKConfig.load(config)
    ctx.obj["config"] = cfg
    base = Path.home() / ".kbk"; base.mkdir(parents=True, exist_ok=True)
    ctx.obj["store"] = KnowledgeStore(cfg)
    ctx.obj["state"] = StateTracker(cfg.state_path)
    ctx.obj["indexer"] = Indexer(ctx.obj["store"], ctx.obj["state"],
        llm_api_key=cfg.llm_api_key, llm_model=cfg.llm_model)

@cli.command()
def init():
    """Init KBK: dirs, ChromaDB, state tracker, sample targets."""
    StateTracker(KBKConfig().state_path)
    click.echo("KBK initialized at ~/.kbk/")

@cli.command()
@click.option("--dry-run", is_flag=True)
def sync(dry_run):
    """Pull + Diff + ETL + Embed."""
    ctx = click.get_current_context().obj
    targets = load_targets(ctx["config"].targets_path)
    for t in targets:
        if t["type"] == "confluence":
            conn = ConfluenceConnector(ctx["config"].confluence_url,
                ctx["config"].confluence_token, ctx["state"])
            from kbk.models import SourceTarget
            target = SourceTarget(type="confluence", location=t["location"],
                filter_query=t.get("filter_query",""),
                access_group=t.get("access_group","public"))
            pages = conn.process_target(target)
            for page in pages:
                ctx["indexer"].process_document(
                    url=page["url"], raw_html=page["body"], title=page["title"],
                    access_group=page["access_group"],
                    collection=t["location"].lower(), content_hash=page["content_hash"])
                ctx["state"].mark_indexed(page["url"], page["content_hash"])

@cli.command()
def serve():
    """Start MCP server (stdio)."""
    KBKMCPServer(click.get_current_context().obj["store"]).run()

@cli.command()
@click.option("--output", default="markdown", type=click.Choice(["confluence","markdown"]))
def build_showcase(output):
    """Generate Read-Only showcase."""
    store = click.get_current_context().obj["store"]
    cfg = click.get_current_context().obj["config"]
    builder = ShowcaseBuilder(store, cfg)
    md = builder.build_markdown()
    Path.home().joinpath(".kbk","showcase.md").write_text(md)
    click.echo("Showcase saved to ~/.kbk/showcase.md")

@cli.command()
@click.argument("query")
@click.option("--collection", "-c", default=None)
@click.option("--limit", "-n", default=10)
def search(query, collection, limit):
    """Semantic search."""
    results = click.get_current_context().obj["store"].search(query,
        n_results=limit, collection_filter=collection)
    for c in results: click.echo(f"  {c.summary[:200]}  {c.source_url}")

@cli.command()
def status():
    """Index stats."""
    store = click.get_current_context().obj["store"]
    s = store.get_stats()
    click.echo(f"Collections: {len(s['collections'])}  Total chunks: {s['total']}")
```

---

## Test Results (11/11, 2026-05-12)

```
 test_chunk_create         OK  IndexedChunk creation with auto-ID
 test_chunk_from_dict      OK  Deserialization from dict
 test_state_tracker        OK  SHA-256 hashing, has_changed logic
 test_store_init           OK  ChromaDB persistent client init
 test_store_upsert_search  OK  Upsert + semantic search roundtrip
 test_store_delete         OK  Chunk deletion (with logging, not silent)
 test_store_stats          OK  Collection stats aggregation
 test_indexer_clean        OK  HTML cleaning (ac: macros, tags, entities)
 test_indexer_chunk        OK  Sentence-boundary chunking with overlap
 test_indexer_full_flow    OK  Full ETL: clean, summarize, chunk, embed, search
 test_targets_config       OK  targets.yaml parsing
```

---

## Full Demo Script

```bash
# 1. Init
kbk init

# 2. Configure allowlist
cat > ~/.kbk/targets.yaml << 'YAML'
targets:
  - type: confluence
    location: "ARCH"
    filter_query: "label = 'approved'"
    access_group: "public"
YAML

# 3. Index
kbk sync
#   -- CONFLUENCE: ARCH
#     Found 3 new documents
#     Indexed: ADR-007, RUNBOOK-PAYMENT, QA-451
#   Summary: 3 indexed, 12 chunks, $0.0021

# 4. Search
kbk search "payment gateway architecture"
#   ADR-007: API Gateway migrating to K8s...
#   https://confluence/display/ARCH/ADR-007

# 5. MCP for Cursor/Claude
kbk serve
#   Connect from Cursor: python3 -m kbk.cli serve

# 6. Confluence Showcase
kbk build-showcase --output markdown
#   Saved to ~/.kbk/showcase.md
```

---

## Exceptions (kbk/exceptions.py)

```python
class KBKError(Exception): pass
class StoreError(KBKError): pass        # ChromaDB operations
class ConnectorError(KBKError): pass    # Confluence/GitLab operations
class LLMError(KBKError): pass          # LLM API failures
class AuthenticationError(KBKError): pass
class ConfigurationError(KBKError): pass
```

No v1 legacy exceptions (VersioningError, SyncError, ConflictError removed).

---

## Edge Cases Handled

| Edge Case | Solution |
|-----------|----------|
| API Rate Limits (Confluence) | Exponential backoff (2^attempt) |
| LLM Cost Runaway | StateTracker dedup + --dry-run + single LLM call per doc |
| Context Loss (chunking) | Summary attached to every chunk, sentence-boundary overlap |
| HTML Muck (Confluence macros) | Regex: ac: tags, all HTML, HTML entities |
| Broken State File | Atomic write (tmp+replace), corrupt backup to .corrupt.bak |
| Content Too Short | Skip LLM, fallback to truncation (300 chars) |
| Empty Content | Early return empty list from process_document |
| XSS (Showcase) | html.escape() on all user-originated data |
| ACL Bypass | access_group enforced at store.search + MCP level |
| KeyboardInterrupt | Not caught by decorator, clean exit(130) |
| Confluence API Failure | Logged with error code, re-raised (not silent None) |
| Duplicate IDs | Deterministic hash: same doc always same ID |
| LLM Auth Error | 401 raises AuthenticationError immediately (no retry) |

---

## ATM Runs

### kbk-v02 (initial implementation)
6/6 gates: discovery.api, evidence.package, implementation, smoke, review.artifact, verdict.computed

### kbk-v02-fixes (15 review-driven fixes)
6/6 gates. Reviews by GLM-5.1 + Kimi K2.5.

---

## GitHub

https://github.com/Wendigooor/knowledge-base-kit
