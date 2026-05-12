# Why KBK (Knowledge Base Kit)?

## The Problem

Enterprise teams generate massive amounts of knowledge every day:
- **Architecture Decision Records (ADRs)** in Confluence
- **Runbooks and deployments** in Confluence
- **Code and technical documentation** in GitLab/GitHub
- **Tickets and decisions** in Jira

This knowledge is scattered, unstructured, and buried in HTML garbage.
Nobody can find anything. LLM agents hallucinate because they lack enterprise context.
New team members spend months ramping up.

## The False Start (v1 — Deprecated)

v1 tried to build a document store in ChromaDB + Git.
Users had to write documentation INTO KBK.
This failed because:
- Nobody wants to write documentation in yet another tool
- Maintaining sync between Git and ChromaDB was complex
- Versioning duplicated what already exists in git/Confluence history
- The "write to us" model is doomed in enterprise

## The Right Approach (v2)

KBK v2 takes a completely different approach:

**KBK is an index, not a store.**

The source of truth stays where it was born:
- Confluence (documentation, ADRs)
- Jira (tickets, tasks)
- Git (code, MR comments)

KBK walks a **whitelist** (Allowlist), fetches only what's approved,
cleans the HTML garbage, distills meaning through an LLM,
and provides **two outputs**:

1. **MCP Server (for machines)** — Cursor, Claude Desktop, and custom agents
   can query the index semantically and get clean, relevant context in milliseconds.
2. **Confluence Showcase (for humans)** — an auto-generated Read-Only page
   that proves the system works and gives managers visibility.

## Core Principles

1. **Zero Friction** — nobody changes their workflow. Work in Confluence as always.
2. **Pull, not Push** — no webhooks, no queues, no dead letters. Just `kbk sync`.
3. **Allowlist, not Firehose** — only whitelisted sources. No trash from random pages.
4. **Dedup by default** — SHA-256 hashing ensures unchanged docs are skipped.
5. **One LLM call per doc** — structured JSON output for both summary and tags.
6. **Source URL in every chunk** — every search result links back to the original.
