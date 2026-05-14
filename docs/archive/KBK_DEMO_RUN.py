#!/usr/bin/env python3.11
"""KBK v0.2 Demo — full walkthrough with realistic data (Confluence ADR + GitLab README)."""

import os, sys, json, tempfile

sys.path.insert(0, "/Users/iharzvezdzin/Documents/projects/knowledge-base-kit")
from kbk.config import KBKConfig
from kbk.store import KnowledgeStore
from kbk.state import StateTracker
from kbk.indexer import Indexer
from kbk.showcase import ShowcaseBuilder


def main():
    demo_dir = tempfile.mkdtemp(prefix="kbk-demo-")
    print(f"Demo directory: {demo_dir}\n")

    # ═══════════════════════════════════════════════════════════════
    # 1. INPUT DATA
    # ═══════════════════════════════════════════════════════════════
    print("=" * 60)
    print("STEP 1: Input Data (3 sources, 2 systems)")
    print("=" * 60)

    # ADR-007 from Confluence (with HTML macros and code blocks)
    adr_html = """<ac:structured-macro ac:name="info"><ac:rich-text-body><p>Status: <strong>APPROVED</strong></p></ac:rich-text-body></ac:structured-macro>
<h1>ADR-007: API Gateway Migration to Kubernetes</h1>
<p><strong>Context:</strong> Current NGINX-based gateway handles ~50k req/s. RabbitMQ reaching limits.</p>
<h2>Decision</h2>
<p>Migrate to <strong>Kong Gateway on K8s</strong> with Istio. Use <code>List&lt;String&gt; upstreams</code> for routing.</p>
<h2>Consequences</h2>
<ul><li>Horizontal scaling via HPA</li><li>Canary deployments via Istio</li><li>Migration window: Q3 2026</li></ul>"""

    # Runbook from Confluence (with code/pre blocks)
    runbook_html = """<h1>Runbook: Payment Service Deployment</h1>
<pre># Deploy payment-service v2.3.1
git checkout main && git pull
docker build -t payment-service:2.3.1 .
kubectl apply -f k8s/deployment.yaml
kubectl rollout status deployment/payment-service</pre>
<p><strong>Rollback:</strong> <code>kubectl rollout undo deployment/payment-service</code></p>
<p><strong>Health:</strong> <code>curl http://payment:8080/health</code></p>"""

    # GitLab README (technical docs with angle brackets)
    gitlab_readme = """<h1>payment-service</h1>
<p>Payment processing microservice. Built with <strong>Go 1.22</strong>, PostgreSQL 15, Redis 7.</p>
<h2>Endpoints</h2>
<pre>POST /api/v1/payments  - Create payment
GET  /api/v1/payments/:id - Get status
POST /api/v1/refunds   - Process refund</pre>
<p>See ADR-007 for API Gateway context.</p>"""

    sources = [
        ("Confluence (ARCH)", "ADR-007: API Gateway Migration to Kubernetes", adr_html,
         "https://confluence.softswiss.com/spaces/ARCH/pages/ADR-007"),
        ("Confluence (ENG)", "Runbook: Payment Service Deployment", runbook_html,
         "https://confluence.softswiss.com/spaces/ENG/pages/RUNBOOK-PAYMENT"),
        ("GitLab (core/payment-service)", "payment-service: Go microservice README", gitlab_readme,
         "https://gitlab.softswiss.com/core/payment-service/-/blob/main/README.md"),
    ]

    for source, title, html, url in sources:
        print(f"\n  [{source}]")
        print(f"    Title: {title}")
        print(f"    Size:  {len(html)} chars (raw HTML with Confluence macros)")

    print("\n" + "=" * 60)
    print("STEP 2: Indexing (ETL Pipeline)")
    print("=" * 60)

    cfg = KBKConfig(
        db_path=os.path.join(demo_dir, "chromadb"),
        state_path=os.path.join(demo_dir, "state.json"),
    )
    store = KnowledgeStore(cfg)
    state = StateTracker(cfg.state_path)
    indexer = Indexer(store, state, llm_api_key="")  # No LLM key = truncation fallback

    docs = [
        (adr_html,
         "https://confluence.softswiss.com/spaces/ARCH/pages/ADR-007",
         "ADR-007: API Gateway Migration to Kubernetes", "arch"),
        (runbook_html,
         "https://confluence.softswiss.com/spaces/ENG/pages/RUNBOOK-PAYMENT",
         "Runbook: Payment Service Deployment", "runbooks"),
        (gitlab_readme,
         "https://gitlab.softswiss.com/core/payment-service/-/blob/main/README.md",
         "payment-service: Go microservice", "platform"),
    ]

    for html, url, title, collection in docs:
        print(f"\n  Processing: {title[:50]}...")

        # Show cleaning effectiveness
        cleaned = indexer.clean_html(html)
        print(f"    Clean:  {len(html)} chars (raw) -> {len(cleaned)} chars (clean)")
        print(f"    Sample: {cleaned[:120]}...")

        # Show chunking
        chunks_text = indexer.chunk(cleaned, chunk_size=300)
        print(f"    Chunks: {len(chunks_text)} (size=300 chars)")

        # Index
        content_hash = StateTracker.hash_content(html)
        indexed = indexer.process_document(
            url=url, raw_html=html, title=title,
            collection=collection, content_hash=content_hash,
        )
        state.mark_indexed(url, content_hash, [c.id for c in indexed])
        print(f"    Summary: {indexed[0].summary[:150]}...")

    # ═══════════════════════════════════════════════════════════════
    # 3. STATS
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("STEP 3: Index Status (kbk status)")
    print("=" * 60)
    stats = store.get_stats()
    for col, cnt in stats["collections"].items():
        if cnt > 0:
            print(f"  [{col}]: {cnt} chunks")
    print(f"  Total: {stats['total']} chunks")

    # ═══════════════════════════════════════════════════════════════
    # 4. SEARCH
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("STEP 4: Semantic Search (kbk search)")
    print("=" * 60)

    queries = [
        "API Gateway migration Kubernetes",
        "how to deploy payment service",
        "rollback procedure kubectl",
        "Go microservice PostgreSQL architecture",
    ]

    for q in queries:
        print(f"\n  Query: \"{q}\"")
        for col in store.list_collections():
            for c in store.search(q, collection_filter=col, n_results=1):
                summary = c.summary[:150] + "..." if len(c.summary) > 150 else c.summary
                print(f"    [{col}] {summary}")
                print(f"      Source: {c.source_url}")

    # ═══════════════════════════════════════════════════════════════
    # 5. MCP OUTPUT (for LLM)
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("STEP 5: MCP Response (what an LLM receives)")
    print("=" * 60)

    results = store.search("payment architecture deployment", n_results=2)
    mcp_response = {
        "tool": "search_knowledge",
        "arguments": {"query": "payment architecture deployment"},
        "results": [
            {
                "source_url": c.source_url,
                "content_snippet": c.content[:300],
                "summary": c.summary,
                "tags": c.tags,
                "collection": c.collection,
            }
            for c in results
        ],
    }
    print(f"\n  {json.dumps(mcp_response, indent=2, ensure_ascii=False)[:1000]}")
    print()
    print("  The LLM now has:")
    print("  - Clean text (no HTML garbage)")
    print("  - Source URL to the original document")
    print("  - Tags for classification")

    # ═══════════════════════════════════════════════════════════════
    # 6. SHOWCASE
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("STEP 6: Confluence Showcase (what humans see)")
    print("=" * 60)

    builder = ShowcaseBuilder(store, cfg)
    print(f"\n  {builder.build_markdown()[:1000]}")

    # ═══════════════════════════════════════════════════════════════
    # 7. STATE TRACKER DEDUP
    # ═══════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("BONUS: StateTracker Dedup (second run = skip all)")
    print("=" * 60)

    for html, url, title, collection in docs:
        content_hash = StateTracker.hash_content(html)
        changed = state.has_changed(url, content_hash)
        print(f"  {title[:45]:45s} changed={changed}")

    print("\n  Second kbk sync: all documents skipped ('changed=False')")
    print("  No LLM calls, no ChromaDB overwrites. Zero cost.")

    print(f"\nDemo directory: {demo_dir}")
    print("Cleanup: rm -rf", demo_dir)
    print("Done.")


if __name__ == "__main__":
    main()
