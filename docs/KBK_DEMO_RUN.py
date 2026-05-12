#!/usr/bin/env python3.11
"""KBK v0.2 Demo — полный walkthrough с реальными данными."""

import os, sys, json, tempfile

# HACK: add the project to path
sys.path.insert(0, "/Users/iharzvezdzin/Documents/projects/knowledge-base-kit")

from kbk.config import KBKConfig
from kbk.store import KnowledgeStore
from kbk.state import StateTracker
from kbk.indexer import Indexer
from kbk.showcase import ShowcaseBuilder

def main():
    demo_dir = tempfile.mkdtemp(prefix="kbk-demo-")
    print(f"📂 Demo directory: {demo_dir}")
    print()

    # ═══════════════════════════════════════════════════════════════
    # 1. INPUT DATA
    # ═══════════════════════════════════════════════════════════════
    print("=" * 60)
    print("📥 STEP 1: Исходные данные (Input)")
    print("=" * 60)
    print()

    # ADR-007 from Confluence
    adr_html = """<ac:structured-macro ac:name="info"><ac:rich-text-body><p>Status: <strong>APPROVED</strong></p></ac:rich-text-body></ac:structured-macro>
<h1>ADR-007: API Gateway Migration to Kubernetes</h1>
<p><strong>Context:</strong> Current API Gateway (NGINX-based) handles ~50k req/s. RabbitMQ reaching limits.</p>
<h2>Decision</h2>
<p>Migrate to <strong>Kong Gateway on K8s</strong> with Istio. Use <code>List&lt;String&gt; upstreams</code> for routing.</p>
<h2>Consequences</h2>
<ul><li>Horizontal scaling via HPA</li><li>Canary deployments via Istio</li><li>Migration: Q3 2026</li></ul>"""

    runbook_html = """<h1>Runbook: Payment Service Deployment</h1>
<pre># Deploy payment-service v2.3.1
git checkout main && git pull
docker build -t payment-service:2.3.1 .
kubectl apply -f k8s/deployment.yaml
kubectl rollout status deployment/payment-service</pre>
<p><strong>Rollback:</strong> <code>kubectl rollout undo deployment/payment-service</code></p>
<p><strong>Health:</strong> <code>curl http://payment:8080/health</code></p>"""

    gitlab_readme = """<h1>payment-service</h1>
<p>Payment processing microservice. Built with <strong>Go 1.22</strong>, PostgreSQL 15, Redis 7.</p>
<h2>Endpoints</h2>
<pre>POST /api/v1/payments  - Create
GET  /api/v1/payments/:id - Status
POST /api/v1/refunds   - Refund</pre>
<p>See ADR-007 for API Gateway context.</p>"""

    sources = [
        ("🏛️ Confluence (ARCH)", "ADR-007: API Gateway Migration to Kubernetes", adr_html,
         "https://confluence.softswiss.com/spaces/ARCH/pages/ADR-007"),
        ("📘 Confluence (ENG)", "Runbook: Payment Service Deployment", runbook_html,
         "https://confluence.softswiss.com/spaces/ENG/pages/RUNBOOK-PAYMENT"),
        ("🦊 GitLab (core/payment-service)", "payment-service: Go microservice README", gitlab_readme,
         "https://gitlab.softswiss.com/core/payment-service/-/blob/main/README.md"),
    ]

    for source, title, html, url in sources:
        print(f"  {source}")
        print(f"    Title: {title}")
        print(f"    URL:   {url}")
        print(f"    Size:  {len(html)} chars (raw HTML with Confluence macros)")
        print()

    # ═══════════════════════════════════════════════════════════════
    # 2. INDEXING (ETL Pipeline)
    # ═══════════════════════════════════════════════════════════════
    print("=" * 60)
    print("⚙️  STEP 2: Индексация (ETL Pipeline)")
    print("=" * 60)
    print()

    cfg = KBKConfig(
        db_path=os.path.join(demo_dir, "chromadb"),
        state_path=os.path.join(demo_dir, "state.json"),
    )
    store = KnowledgeStore(cfg)
    state = StateTracker(cfg.state_path)
    indexer = Indexer(store, state, llm_api_key="")

    docs = [
        (adr_html, "https://confluence.softswiss.com/spaces/ARCH/pages/ADR-007",
         "ADR-007: API Gateway Migration to Kubernetes", "arch"),
        (runbook_html, "https://confluence.softswiss.com/spaces/ENG/pages/RUNBOOK-PAYMENT",
         "Runbook: Payment Service Deployment", "runbooks"),
        (gitlab_readme, "https://gitlab.softswiss.com/core/payment-service/-/blob/main/README.md",
         "payment-service: Go microservice", "platform"),
    ]

    for html, url, title, collection in docs:
        print(f"  📄 {title[:50]}...")

        # Show cleaning
        cleaned = indexer.clean_html(html)
        print(f"     Clean: {len(html)} chars -> {len(cleaned)} chars")
        print(f"     Sample: {cleaned[:100]}...")

        # Show chunking
        chunks = indexer.chunk(cleaned, chunk_size=300)
        print(f"     Chunks: {len(chunks)} (chunk_size=300)")

        # Show first chunk
        print(f"     Chunk 1: {chunks[0][:100]}...")

        # Index
        content_hash = StateTracker.hash_content(html)
        indexed = indexer.process_document(
            url=url, raw_html=html, title=title,
            collection=collection, content_hash=content_hash,
        )
        state.mark_indexed(url, content_hash, [c.id for c in indexed])

        # Show summary
        print(f"     Summary: {indexed[0].summary[:120]}...")
        if indexed[0].tags:
            print(f"     Tags: {', '.join(indexed[0].tags[:5])}")
        print()

    # ═══════════════════════════════════════════════════════════════
    # 3. STATS
    # ═══════════════════════════════════════════════════════════════
    print("=" * 60)
    print("📊 STEP 3: Состояние индекса (kbk status)")
    print("=" * 60)
    stats = store.get_stats()
    print(f"  Collections: {len(stats['collections'])}")
    for col, cnt in stats['collections'].items():
        print(f"    [{col}]: {cnt} chunks")
    print(f"  Total: {stats['total']} chunks")
    print()

    # ═══════════════════════════════════════════════════════════════
    # 4. SEARCH
    # ═══════════════════════════════════════════════════════════════
    print("=" * 60)
    print("🔍 STEP 4: Семантический поиск (kbk search)")
    print("=" * 60)
    print()

    queries = [
        "API Gateway architecture migration Kubernetes",
        "как задеплоить payment service",
        "rollback procedure",
        "payment processing Go microservice",
        "postgresql redis architecture",
    ]

    for q in queries:
        print(f"  Query: \"{q}\"")
        results = store.search(q, n_results=2)
        if results:
            for c in results:
                summary = c.summary[:150] + "..." if len(c.summary) > 150 else c.summary
                print(f"    [{c.collection}] {summary}")
                print(f"      Source: {c.source_url}")
                if c.tags:
                    print(f"      Tags: {' '.join(f'#{t}' for t in c.tags[:3])}")
        else:
            print("    (no results)")
        print()

    # ═══════════════════════════════════════════════════════════════
    # 5. MCP OUTPUT (for LLM)
    # ═══════════════════════════════════════════════════════════════
    print("=" * 60)
    print("🤖 STEP 5: MCP Server — что получает LLM")
    print("=" * 60)
    print()

    # Scenario: Cursor developer asks about payment architecture
    llm_prompt = "Developer asks Cursor: 'What's the architecture for payment processing?'"
    print(f"  LLM prompt: \"{llm_prompt}\"")
    print()

    results = store.search("payment architecture processing", n_results=2)
    mcp_response = {
        "tool": "search_knowledge",
        "arguments": {"query": "payment architecture processing"},
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
    print(f"  MCP Response ({len(results)} results):")
    print(f"  ```json")
    print(json.dumps(mcp_response, indent=2, ensure_ascii=False))
    print(f"  ```")
    print()
    print(f"  LLM теперь может ответить разработчику, имея:")
    print(f"  - Очищенный контент (без HTML мусора)")
    print(f"  - Ссылку на оригинал в Confluence/GitLab")
    print(f"  - Tags для классификации")
    print()

    # ═══════════════════════════════════════════════════════════════
    # 6. SHOWCASE
    # ═══════════════════════════════════════════════════════════════
    print("=" * 60)
    print("👤 STEP 6: Confluence Showcase — что видит человек")
    print("=" * 60)
    print()

    builder = ShowcaseBuilder(store, cfg)
    md = builder.build_markdown()
    print(md)
    print()

    # ═══════════════════════════════════════════════════════════════
    # 7. STATE (dedup works)
    # ═══════════════════════════════════════════════════════════════
    print("=" * 60)
    print("♻️  BONUS: StateTracker dedup (второй sync — скип)")
    print("=" * 60)
    print()

    for html, url, title, collection in docs:
        content_hash = StateTracker.hash_content(html)
        changed = state.has_changed(url, content_hash)
        print(f"  {title[:40]:40s} hash={content_hash[:12]}... changed={changed}")
    print()
    print("  Второй вызов kbk sync: все документы skip ('changed=False')")
    print("  LLM не вызывается, ChromaDB не перезаписывается.")
    print()

    # ═══════════════════════════════════════════════════════════════
    # CLEANUP
    # ═══════════════════════════════════════════════════════════════
    print(f"📂 Demo dir: {demo_dir}")
    print(f"   Чтобы удалить: rm -rf {demo_dir}")
    print("✅ Demo complete")


if __name__ == "__main__":
    main()
