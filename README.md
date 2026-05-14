# KBK v0.3 — Enterprise Semantic Index

> Knowledge Base Kit: an intelligent index of enterprise knowledge.
> Pull + Allowlist. MCP Server (for LLMs) + Showcase (for humans).

---

## Why

**Problem:** Enterprise knowledge is scattered across Confluence, Jira, and GitLab. People won't adopt new writing tools. LLM agents choke on HTML garbage and hallucinate. Humans can't find current decisions.

**Solution:** KBK is an **index**, not a store. The source of truth stays in Confluence/Jira/Git. No webhooks. Only **Pull** from an **allowlist** defined in `targets.yaml`. Unchanged content is skipped (SHA-256 diff). Changed content goes through an AI pipeline: clean → summarize → classify → chunk → embed → ChromaDB.

## Architecture

```
Sources → allowlist → sync → StateTracker diff → Indexer → ChromaDB → API Gateway → MCP + Showcase
```

Detailed architecture and roadmap: [`docs/ADR-0001-v03-memorybank.md`](docs/ADR-0001-v03-memorybank.md)

## Demo

[5-minute stakeholder demo](docs/KBK_DEMO_v03.md):
1. Showcase — browsable knowledge, collection navigation, source links (2 min)
2. How it works — pre-recorded walkthrough of sync, index, agent retrieval (2 min)
3. Roadmap — what's next (1 min)

## CLI

| Command | Description |
|---------|-------------|
| `kbk init` | Initialize: `~/.kbk/`, ChromaDB, StateTracker |
| `kbk sync` | Pull + Diff + ETL + Embed. `--dry-run` for cost preview |
| `kbk serve` | MCP server (stdio) for agents |
| `kbk build-showcase` | Generate human-readable index |
| `kbk search <query>` | Semantic search |
| `kbk status` | Index statistics |

## Roadmap

- **v0.3** (current): Confluence connector, collections, AuthZ at retrieval, observability, 5-min demo
- **v0.4**: Jira/GitLab connectors, HTTP MCP, incremental showcase

## ATM Runs

| Run | Gates | Description |
|-----|-------|-------------|
| `kbk-v02` | 6/6 | Initial implementation |
| `kbk-v02-fixes` | 6/6 | 15 fixes from GLM-5.1 + Kimi K2.5 review |
| `kbk-v02-review-fixes` | 6/6 | 7 fixes from Gemini review |
| **Total** | **18/18** | |

## Links

- Repository: [github.com/Wendigooor/knowledge-base-kit](https://github.com/Wendigooor/knowledge-base-kit)
- ADR v0.3: [`docs/ADR-0001-v03-memorybank.md`](docs/ADR-0001-v03-memorybank.md)
- Demo script: [`docs/KBK_DEMO_v03.md`](docs/KBK_DEMO_v03.md)
- Architecture detail: [`docs/architecture.md`](docs/architecture.md)
- Why KBK: [`docs/WHY.md`](docs/WHY.md)
