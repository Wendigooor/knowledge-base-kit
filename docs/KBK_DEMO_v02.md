# KBK v0.2 — Live Demo Walkthrough

> What: Enterprise Semantic Index. Pull + Allowlist.
> Flow: Confluence ADR + GitLab README → clean → LLM summarize → chunk → ChromaDB → MCP + Showcase
> Date: 2026-05-12

---

## 1. Input Data

Three sources from different systems, different formats, different languages.

### 🏛️ Confluence (ARCH) — ADR-007

```
Status: APPROVED
ADR-007: API Gateway Migration to Kubernetes
Context: Current API Gateway (NGINX-based) handles ~50k req/s.
         RabbitMQ reaching limits.
Decision: Migrate to Kong Gateway on K8s with Istio.
          Use List<String> upstreams for routing.
Consequences: HPA, canary deployments via Istio, Q3 2026.
```

### 📘 Confluence (ENG) — Runbook

```
Runbook: Payment Service Deployment
# Deploy payment-service v2.3.1
git checkout main && git pull
docker build -t payment-service:2.3.1 .
kubectl apply -f k8s/deployment.yaml
kubectl rollout status deployment/payment-service
Rollback: kubectl rollout undo deployment/payment-service
Health: curl http://payment:8080/health
```

### 🦊 GitLab (core/payment-service)

```
payment-service
Payment processing microservice. Go 1.22, PostgreSQL 15, Redis 7.
Endpoints:
  POST /api/v1/payments   - Create payment
  GET  /api/v1/payments/:id - Get status
  POST /api/v1/refunds    - Process refund
```

**The Problem:** All three are raw HTML with Confluence macros (`<ac:...>`, `<code>`, `<pre>`). Feeding this directly to an LLM wastes 40% of tokens on HTML garbage.

---

## 2. Indexing (ETL Pipeline)

### Clean: HTML → plain text

```
Input:  579 chars (with <ac:macro>, <code>List<String></code>)
Output: 330 chars (
→ HTML macros removed
→ <code>List<String></code> → List<String> (angle brackets preserved!)
→ ac:link, ri:user tags stripped
→ Only meaningful content remains
```

### Chunk: Sentence-boundary split

```
Input:  330 chars
Chunks: 2 (chunk_size=300, overlap=100 chars)

Chunk 1: "Status: APPROVED. ADR-007: API Gateway Migration..."
Chunk 2: "...Horizontal scaling via HPA. Canary deployments..."
         ^ overlap (last ~100 chars from chunk 1,
           extended to the next word boundary)
```

### LLM (if API key configured) — one call per document

```json
{
  "summary": "API Gateway migrates from NGINX to Kong on K8s with Istio. Enables HPA and canary deployments.",
  "tags": ["gateway", "kubernetes", "istio", "migration", "adr"]
}
```

### Embed: Vectors into ChromaDB

```
3 documents → 5 chunks → 5 vectors (384d all-MiniLM-L6-v2)
           → source_url attached to every chunk
           → summary attached to every chunk (context preserved)
```

---

## 3. Semantic Search

### Query: "API Gateway migration Kubernetes"

```
🏆 [arch] ADR-007: API Gateway Migration to Kubernetes
   Source: https://confluence.softswiss.com/spaces/ARCH/pages/ADR-007
   Summary: API Gateway migrates from NGINX to Kong on K8s...
   Tags: #gateway #kubernetes #istio

   [platform] payment-service README (cross-references ADR-007)
```

### Query: "how to deploy payment service" (semantic, not keyword!)

```
🏆 [runbooks] Runbook: Payment Service Deployment
   Source: https://confluence.softswiss.com/spaces/ENG/pages/RUNBOOK-PAYMENT
   Commands: git pull, docker build, kubectl apply
   Rollback: kubectl rollout undo
```

### Query: "PostgreSQL architecture Go microservice"

```
🏆 [platform] payment-service: Go microservice
   Source: https://gitlab.softswiss.com/core/payment-service
   Stack: Go 1.22, PostgreSQL 15, Redis 7
   Endpoints: payments, refunds
```

---

## 4. MCP Server — How LLMs Consume KBK

```python
# Cursor plugin makes an MCP call:
result = mcp_call("search_knowledge", {
    "query": "payment service architecture",
    "limit": 3
})
```

**MCP Response:**
```json
{
  "results": [
    {
      "source_url": "https://confluence.softswiss.com/spaces/ENG/pages/RUNBOOK-PAYMENT",
      "content": "Runbook: Payment Service Deployment... kubectl apply...",
      "summary": "Deployment procedure for payment-service v2.3.1",
      "tags": ["runbook", "deploy", "k8s"]
    },
    {
      "source_url": "https://gitlab.softswiss.com/core/payment-service",
      "content": "Payment microservice. Go 1.22, PostgreSQL 15...",
      "summary": "Payment service architecture and API",
      "tags": ["go", "microservice", "payment"]
    }
  ]
}
```

**What the LLM gets:**
- ✅ **Clean text** — no HTML, no Confluence macros
- ✅ **Source URL** — can provide a link back to the developer
- ✅ **Summary** — context in 2-3 sentences
- ✅ **Tags** — for classification
- ❌ **Not exposed** — HTML garbage, other documents' access groups

---

## 5. Confluence Showcase — What Humans See

```
=======================  COLLECTIONS  =======================

📁 Arch (1 chunks)
  ADR-007: API Gateway Migration to Kubernetes
  🔗 https://confluence/ARCH/ADR-007

📁 Platform (1 chunks)
  payment-service: Go microservice
  🔗 https://gitlab/core/payment-service

📁 Runbooks (1 chunks)
  Runbook: Payment Service Deployment
  🔗 https://confluence/ENG/RUNBOOK-PAYMENT

============================================================
🤖 Auto-generated by KBK. Last updated: 2026-05-12
```

---

## 6. Zero Friction: Second Sync

```bash
$ kbk sync

── CONFLUENCE: ARCH
  No new/changed documents  ← StateTracker: hash matches, skip

── CONFLUENCE: ENG
  No new/changed documents

── GITLAB: core/payment-service
  No new/changed documents

📊 Summary: 0 new, 0 chunks, $0.0000 LLM cost
```

**What we saved:**
- 3 LLM calls (= ~$0.006)
- 3 Confluence API requests
- 3 ChromaDB upserts
- Time: ~0.5s instead of ~10s

---

## 7. Architecture Decisions (Why It Works)

| Decision | Problem | How We Solved It |
|----------|---------|------------------|
| **Pull + Allowlist** | Webhooks break, trash everywhere | Only whitelisted targets, only on demand |
| **SHA-256 dedup** | LLM burns money on same data | skip unchanged, 0 cost on re-run |
| **Single LLM call** | Two calls = 2x cost + latency | Structured JSON output: summary + tags |
| **Source URL per chunk** | "Where does this come from?" | Every chunk knows its origin |
| **Word-boundary overlap** | Words cut between chunks | `find(' ', overlap_start)` |
| **fcntl flock** | Two sync processes corrupt state | POSIX file locking |
| **Angle bracket protection** | List\<String\> killed by HTML cleaner | code/pre/tt protection phase |

---

## 8. Links

- Repository: https://github.com/Wendigooor/knowledge-base-kit
- ATM runs: 3 x 6/6 gates = 18/18 total
- Runnable demo: `python3.11 docs/KBK_DEMO_RUN.py`

```
pip install git+https://github.com/Wendigooor/knowledge-base-kit.git
kbk init && kbk sync && kbk serve
```
