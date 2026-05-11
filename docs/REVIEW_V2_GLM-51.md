# Architecture Review: KBK v2 (glm-5.1)

# Critical Review: KBK v2 Architecture

## 1. Is this better than v1? — Yes, fundamentally, but with new trade-offs

The v1 mistake was **owning the truth** — forcing people into a new workflow, duplicating content, managing versions in parallel. v2 correctly identifies that the winning move is **owning the index, not the document**. This is the right instinct.

**What's genuinely better:**
- Zero-friction adoption is not a nice-to-have; it's existential. v1 was dead on arrival because it required behavior change.
- Eliminating versioning is a massive simplification. You were building a poor man's git inside git.
- Webhooks over full sync is the correct direction for scale.

**But the new trade-offs are underappreciated:**

| v1 Problem | v2 "Solution" | Hidden Cost |
|---|---|---|
| Stale content | Webhooks | Webhooks are unreliable. Missed events = stale index. No reconciliation strategy mentioned. |
| No search | Semantic search over summaries | You're searching LLM summaries, not source content. Summary quality IS your search quality. |
| Duplication | Pointers to originals | When Confluence is down, search returns pointers to nothing. The index is useless in a crisis — exactly when you need it most. |

**Verdict:** Direction is correct. Execution plan is incomplete.

---

## 2. Top 3 Enterprise Risks

### Risk #1: Access Control Leakage (Severity: Critical)

```python
"access_group": metadata.get("access_group", "public")  # ← This is a fantasy
```

Confluence permissions are **not a single field**. They're:
- Space-level restrictions
- Page-level inheritance with overrides
- User/group/role-based with nested groups
- Different for view vs. edit

Jira issue-level security is even more complex. Your architecture indexes a document, generates a summary (which may **paraphrase restricted content**), and stores it in ChromaDB — which has **zero access control**.

**Scenario:** A Confluence page restricted to the security team contains incident response procedures for a vulnerability. KBK summarizes it, classifies it, and stores the summary. Anyone searching "vulnerability response" now sees the summary in results. You've just leaked restricted information through an LLM paraphrase.

**This is a compliance violation waiting to happen.** You need:
- Real-time ACL resolution at query time (not index time)
- Or: never index content the searcher can't access (requires per-user index views)
- Or: store only embeddings + metadata, return only `source_url`, and let the source system enforce access on click-through (but then the summary in search results is still a leak vector)

### Risk #2: LLM Non-Determinism on the Critical Path (Severity: High)

The indexer calls LLM **three times per document** (summarize, classify, tag). Problems:

- **Non-idempotent:** Same document processed twice produces different summaries/tags. Your index is mutable in unpredictable ways.
- **Cost at scale:** Enterprise Confluence has 50k-500k+ pages. At $0.03/call × 3 calls × 100k pages = **$9,000 for initial index**. And every edit triggers reprocessing.
- **Latency:** LLM calls add 2-10 seconds per document. A bulk reindex of 10k documents = 5-28 hours serial. No mention of parallelization or batching.
- **Hallucinated tags:** LLM classifies a security runbook as "business logic." It's now invisible to people searching for runbooks. **Silent failures are the worst kind.**

You need: deterministic fallbacks, human-in-the-loop for classification, caching, and a quality measurement framework.

### Risk #3: Index Drift Without Reconciliation (Severity: High)

The architecture assumes webhooks are reliable. They aren't:

- Webhooks get dropped (network errors, service restarts, rate limits)
- Confluence doesn't fire webhooks for permission changes, deletions of spaces, or bulk operations
- Cron-based polling has no defined SLA or reconciliation logic
- No mention of **deletion propagation** — when a page is deleted in Confluence, how does ChromaDB know?

**You need a full reconciliation loop:** periodic diff of "what exists in sources" vs. "what exists in ChromaDB." Without it, your index rots.

---

## 3. Is ChromaDB the Right Choice? — No, Not for This

ChromaDB is a **prototyping tool**, not an enterprise vector database:

| Concern | ChromaDB Reality | Enterprise Requirement |
|---|---|---|
| Scale | Single-node, SQLite-backed | 100k+ documents, horizontal scaling |
| Concurrency | Single-writer SQLite lock | Multiple indexers writing simultaneously |
| HA/DR | None. No replication. | RPO/RTO requirements |
| Access control | None | Per-collection or per-document ACL |
| Metadata filtering | Basic, slow on large sets | Complex boolean filters (source_type AND tags AND date range AND access_group) |
| Multi-tenancy | Not supported | Different teams, different visibility |
| Observability | Minimal | Metrics on query latency, index size, collection health |

**What happens at 200k documents with 5 concurrent searchers?** ChromaDB buckles. You'll be migrating under pressure.

**Better alternatives:**
- **Qdrant** — production-grade, filtering, payload-based ACL, horizontal scaling
- **Weaviate** — multi-tenancy, GraphQL, built-in vectorization pipeline (could replace your indexer's embed step)
- **Milvus** — if you need serious scale (millions of vectors)

ChromaDB is fine for the MVP. Document the migration path now, or you'll be stuck later.

---

## 4. What's Missing for Production

### Critical (Will Block Launch)

**1. Deletion handling**
No mention of what happens when a source document is deleted. You need:
- Webhook for deletion events
- Tombstone records or hard delete from ChromaDB
- Periodic reconciliation (source of truth scan vs. index)

**2. Error handling & dead letter queue**
What happens when:
- LLM call fails mid-indexing? (Partial state in ChromaDB?)
- Webhook payload is malformed?
- ChromaDB is down during upsert?
- Same document is processed twice concurrently?

You need: idempotent operations, retry with backoff, DLQ for failed documents, and atomicity guarantees (or at least "all or nothing" per document).

**3. Access control enforcement at query time**
See Risk #1. This isn't optional for enterprise.

**4. Observability**
Zero mention of:
- Index freshness metrics (how far behind is the index?)
- LLM call success/failure rates
- Search quality metrics (click-through, relevance feedback)
- Connector health (webhook delivery rates, last successful sync per source)

### Important (Will Cause Pain Quickly)

**5. Rate limiting & backpressure**
Confluence API: ~100 req/min. Jira: similar. You need token-bucket rate limiters per connector, and backpressure when the indexer can't keep up.

**6. LLM cost controls**
Budget caps, caching (don't re-summarize unchanged content), and a strategy for bulk initial indexing vs. incremental updates.

**7. Search quality framework**
How do you know search is good? You need:
- Hybrid search (keyword + semantic), not just vector similarity
- Re-ranking across source types (is a Jira ticket more relevant than a Confluence page?)
- Relevance testing / evaluation pipeline

**8. Configuration for the "Read-Only Space" skeleton**
The "hard skeleton" of 6 folders is hardcoded. In enterprise, different orgs have different taxonomies. This needs to be configurable, and the classification logic needs to be