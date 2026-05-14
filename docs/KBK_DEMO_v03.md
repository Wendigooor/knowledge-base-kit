# KBK v0.3 — Stakeholder Demo Script

> 9 minutes. 6 blocks. No code reading.
> Every block has a clear before/after.

---

## Setup (do once before the demo)

```bash
# Ensure Confluence has at least 3-5 approved/ADR pages
kbk init
kbk sync --dry-run   # preview cost
kbk sync              # full sync
kbk build-showcase    # generate showcase
kbk serve             # MCP server for agent demo
```

---

## Block 1: Source → Index (2 min)

**Narrative:** "Knowledge lives in Confluence. KBK pulls only what's approved."

**Script:**

1. Open a Confluence page with an ADR.
   ```
   "This is an architecture decision record. It lives in Confluence, labeled 'approved'."
   ```

2. Run `kbk status`:
   ```
   "KBK already indexed it. Let me show you what it looks like inside."
   ```

3. Run `kbk search "ADR payment service"`:
   ```
   "Found it. Summary, tags, collection — all generated automatically."
   ```
   ```
   Result:
   Summary: Architecture decision for payment service isolation
   Tags: architecture, payment, adr
   Collection: arch
   Source: https://confluence.../ADR-001
   ```

4. Click the source link → Confluence page opens.
   ```
   "The original is still the source of truth. KBK is an index, not a copy."
   ```

**What they see:** Knowledge flows from Confluence → structured index → searchable → linked back.

---

## Block 2: Change Propagation (1 min)

**Narrative:** "When knowledge changes, the index updates. Not everything — just what changed."

**Script:**

1. Edit the Confluence page (add a sentence).
   ```
   "I just updated this ADR. Let me sync."
   ```

2. Run `kbk sync`:
   ```
   "StateTracker detected the change by SHA-256 hash. Everything else — skipped."
   ```
   ```
   Result:
   3 documents checked, 1 changed, 0 new, 0 deleted
   0 unchanged skipped
   ```

3. Run `kbk search "payment service"`:
   ```
   "The new summary reflects the update. Cost of this sync: ~$0.0007."
   ```

**What they see:** Incremental updates. No full re-index. LLM costs stay near zero on unchanged content.

---

## Block 3: Agent MCP Retrieval (2 min)

**Narrative:** "An AI agent can ask KBK questions through a standard protocol — MCP."

**Script:**

1. Show the agent prompt:
   ```
   "I ask the agent: 'How do I deploy the payment service?'"
   ```

2. Agent calls `search_knowledge("deploy payment service")`:
   ```
   "The agent doesn't guess. It goes to KBK through MCP and gets real results."
   ```

3. Show the MCP response:
   ```
   Agent found 2 relevant documents:
   • "Payment Service Deployment Guide" — collection: runbooks
   • "ADR-001: Service Isolation" — collection: arch

   Source: https://confluence.../deployment-guide
   ```

4. Agent calls `get_document_summary(url)` and answers:
   ```
   "The payment service is deployed via CI/CD pipeline.
   Configuration is in the payment-deploy repo.
   For rollback, see the runbook.

   Source: [link to Confluence]"
   ```

**What they see:** Agent answers with sources. Not hallucinated. Every claim has a link back.

---

## Block 4: Collections Navigation (1 min)

**Narrative:** "Knowledge isn't a flat pile. It's organized into collections."

**Script:**

1. Run `list_collections`:
   ```
   "KBK organizes knowledge into logical groups."
   ```
   ```
   Collections:
   • arch (12 documents) — Architecture decisions
   • runbooks (8 documents) — Operational runbooks
   • org (5 documents) — Organization structure
   • decisions (3 documents) — Product decisions
   ```

2. Run `kbk search "deployment" --collection runbooks`:
   ```
   "You can scope searches to a collection. Faster, more relevant."
   ```

**What they see:** Structured knowledge. Not a search black box.

---

## Block 5: Human Showcase (2 min)

**Narrative:** "Not just for AI agents. Humans can browse the same index."

**Script:**

1. Open the Showcase page in Confluence (or browser).
   ```
   "This is the read-only Showcase. Auto-generated from the index."
   ```

2. Navigate:
   ```
   "Each collection is an expandable section.
   Each document has a summary, tags, and a link back to Confluence."
   ```

3. Click a document → read summary → click source link.
   ```
   "This is the same knowledge the agent uses. Humans and AI see the same index."
   ```

**What they see:** A clean, browsable knowledge base. No Confluence license needed for read access.

---

## Block 6: Roadmap (1 min)

**Narrative:** "This is where we are. Here's where we're going."

**Script:**

1. Show the architecture diagram:
   ```
   "Confluence works today. Jira and GitLab follow the same pipeline.
   The connector contract is already defined."
   ```

2. Three bullets:
   ```
   • Now: Confluence → index → MCP + Showcase
   • Next: Jira tickets → same pipeline → search across docs + issues
   • Later: GitLab wikis and merge requests → unified enterprise knowledge
   ```

**What they see:** Clear roadmap. Not a bottomless project.

---

## Quick Reference: CLI Commands for Demo

```bash
# Show what's indexed
kbk status

# Preview changes without spending LLM cost
kbk sync --dry-run

# Full sync
kbk sync

# Search across all collections
kbk search "query"

# Search scoped to a collection
kbk search "query" --collection runbooks

# List all collections
kbk list-collections

# Generate human-readable showcase
kbk build-showcase

# Start MCP server
kbk serve

# Show index statistics
kbk stats
```

## Success Criteria

The demo succeeds when a stakeholder can answer:

1. "Where does the knowledge come from?" → Confluence (Jira/GitLab next)
2. "How does it get into the system?" → kbk sync → allowlist → diff → index
3. "How does an agent use it?" → MCP → search → summary → source link
4. "How does a human use it?" → Showcase → browse → read → open original
5. "What's the roadmap?" → Confluence now, Jira next, GitLab later
