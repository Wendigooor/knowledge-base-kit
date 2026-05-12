# KBK v0.2 — Enterprise Semantic Index

> Knowledge Base Kit: an intelligent index of enterprise knowledge.
> Pull + Allowlist. Two outputs: MCP Server (for LLMs) + Confluence Showcase (for humans).

---

## Why

**Problem:** Enterprise knowledge is scattered across Confluence, Jira, and GitLab. Trying to get people to write in new systems fails every time. LLM agents choke on HTML garbage and hallucinate, while humans can't find current architectural decisions.

**Solution:** KBK is an **index**, not a store. The source of truth stays in Confluence/Jira/Git. No webhooks. Only **Pull** on demand from a **whitelist** (Allowlist) defined in `targets.yaml`.

## Architecture

```
[Confluence] --------+
[GitLab] ------------+--- kbk sync --- [StateTracker SHA-256] --- [Indexer AI Pipeline]
[Jira] --------------+       |                                       |
                             |-- SHA-256 diff (skip unchanged)        |-- clean HTML
                             +-- delete orphans                       |-- LLM summarize + classify
                                                                      |-- chunk (1k tokens)
                                                                      +-- embed to ChromaDB
                                                                             |
                                                             +---------------+------------+
                                                             |                            |
                                                       MCP Server               Confluence Showcase
                                                       (for Cursor,              (Read-Only index page)
                                                        Claude Desktop)           for humans
```

## Data

### Whitelist (targets.yaml)

```yaml
targets:
  - type: confluence
    location: "ARCH"
    filter_query: "label = 'approved' OR label = 'adr'"
    access_group: "public"
  - type: gitlab
    repo: "core/payment-service"
    path: "docs/runbooks/"
```

Only these sources are indexed. No trash, no draft pages, no noise.

### Data Model (IndexedChunk)

| Field | Description |
|-------|-------------|
| `id` | Deterministic: `sha256(source_url:content_hash:collection)` |
| `source_url` | Link to the original document |
| `content` | Cleaned text chunk (no HTML) |
| `summary` | LLM-generated summary (2-3 sentences) |
| `tags` | LLM-classified tags |
| `access_group` | ACL label (e.g. "public", "finance") |
| `content_hash` | SHA-256 of the raw document for dedup |
| `collection` | Grouping (arch, runbooks, platform) |

### State Tracker

SHA-256 hash of each document. If unchanged — **skip**. Saves LLM costs and time.

```
First sync:  3 docs indexed, 12 chunks, $0.0021 LLM cost
Second sync: 0 docs indexed (all skipped), $0.0000 cost
```

## CLI

| Command | Description |
|---------|-------------|
| `kbk init` | Initialize: creates `~/.kbk/`, ChromaDB, StateTracker |
| `kbk sync` | Pull + Diff + ETL + Embed (full pipeline). `--dry-run` for cost preview |
| `kbk serve` | MCP server (stdio) for Cursor / Claude Desktop |
| `kbk build-showcase` | Generate Read-Only Confluence showcase or Markdown |
| `kbk search <query>` | Semantic search across the index |
| `kbk status` | Index statistics |

## Components

| Module | Purpose |
|--------|---------|
| `kbk/models.py` | IndexedChunk, SourceTarget data models |
| `kbk/config.py` | KBKConfig, YAML config loader |
| `kbk/store.py` | ChromaDB wrapper: upsert/search/delete/stats |
| `kbk/state.py` | StateTracker: SHA-256 dedup with atomic writes + file locking |
| `kbk/indexer.py` | AI pipeline: clean HTML → LLM (summarize+classify one call) → chunk → embed |
| `kbk/connectors/confluence.py` | Confluence REST API client with rate limiting, pagination, orphan detection |
| `kbk/mcp_server.py` | MCP protocol server (stdio): search_knowledge, get_document_summary |
| `kbk/showcase.py` | Confluence Showcase: generates Read-Only index page with expand/collapse sections |
| `kbk/cli.py` | Click CLI: init, sync, serve, build-showcase, search, status |

## Edge Cases Handled

| Edge Case | Solution |
|-----------|----------|
| API Rate Limits (Confluence) | Exponential backoff (2^attempt) |
| LLM Cost Runaway | StateTracker dedup + --dry-run + single LLM call per doc |
| Context Loss (chunking) | Summary attached to each chunk, word-boundary overlap |
| HTML Garbage | Code/pre/tt protection, ac:macro removal, HTML entities |
| Corrupt State File | Atomic write (tmp+replace), corrupt backup to .corrupt.bak |
| Short Content (<200 chars) | Skip LLM, fallback to truncation |
| Empty Content | Early return with empty list |
| XSS (Showcase) | html.escape() on all user data |
| ACL Bypass | access_group enforced at store.search + MCP level |
| Concurrent Sync | POSIX fcntl.flock — second process gets "already running" |
| Confluence API Failure | Logged with error code, re-raised (not silent None) |
| LLM JSON Parsing | 5-strategy extraction: fences, balanced braces, trailing commas, Python→JSON nulls |
| Orphan Documents | Reconciliation: list_known_urls → diff → delete_chunks |

## Installation

```bash
pip install git+https://github.com/Wendigooor/knowledge-base-kit.git
```

Or locally:
```bash
git clone git@github.com:Wendigooor/knowledge-base-kit.git
cd knowledge-base-kit
pip install -e .
```

## Usage

```bash
# Initialize
kbk init

# Configure whitelist
vim ~/.kbk/targets.yaml

# Index documents
kbk sync

# Search
kbk search "how to deploy payment service"

# MCP server (for Cursor / Claude Desktop)
kbk serve

# Confluence showcase
kbk build-showcase

# Status
kbk status
```

## Demo

See `docs/KBK_DEMO_v02.md` for a complete walkthrough with real data (Confluence ADR + GitLab README → index → search → MCP response).

Or run it:
```bash
python3.11 docs/KBK_DEMO_RUN.py
```

## Development

```bash
pip install -e ".[dev]"
python3.11 tests/test_smoke.py
```

## ATM Runs

| Run | Gates | Description |
|-----|-------|-------------|
| `kbk-v02` | 6/6 | Initial implementation |
| `kbk-v02-fixes` | 6/6 | 15 fixes from GLM-5.1 + Kimi K2.5 review |
| `kbk-v02-review-fixes` | 6/6 | 7 fixes from Gemini code review |
| **Total** | **18/18** | |

## Roadmap

- [ ] v0.3: GitLab connector, HTTP MCP, incremental showcase
- [ ] v0.4: Backstage dashboard, Slack AI assistant, Qdrant/Milvus support

## Links

- Repository: [github.com/Wendigooor/knowledge-base-kit](https://github.com/Wendigooor/knowledge-base-kit)
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Demo: [docs/KBK_DEMO_v02.md](docs/KBK_DEMO_v02.md)
- AGENTS.md: Agent instructions for autonomous development
