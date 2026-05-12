# KBK v0.2 — Live Demo Walkthrough

> Что: Enterprise Semantic Index. Pull + Allowlist.
> Как: Confluence ADR + GitLab README → clean → LLM summarize → chunk → ChromaDB → MCP + Showcase
> Дата: 2026-05-12

---

## 1. Исходные данные (Input)

Три источника из разных систем, разный формат, разный язык.

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

**Проблема:** Все три — это raw HTML с Confluence макросами (`<ac:...>`, `<code>`, `<pre>`). Если скормить это LLM напрямую — 40% токенов уйдет на HTML-мусор.

---

## 2. Индексация (ETL Pipeline)

### Clean: HTML → чистый текст

```
Input:  579 chars (с <ac:macro>, <code>List<String></code>)
Output: 330 chars (
→ HTML макросы удалены
→ <code>List<String></code> → List<String> (angle brackets сохранены!)
→ ac:link, ri:user удалены
→ Только смысл
```

### Chunk: нарезка по предложениям

```
Input:  330 chars
Chunk:  2 chunks (chunk_size=300, overlap=100 символов)

Chunk 1: "Status: APPROVED. ADR-007: API Gateway Migration..."
Chunk 2: "...Horizontal scaling via HPA. Canary deployments..."
         ^ overlap (содержит последние ~100 символов
           первого чанка, сдвинутые до word boundary)
```

### LLM (если ключ есть) — один вызов на документ

```json
{
  "summary": "API Gateway migrates from NGINX to Kong on K8s with Istio. Enables HPA and canary deployments.",
  "tags": ["gateway", "kubernetes", "istio", "migration", "adr"]
}
```

### Embed: векторы в ChromaDB

```
3 документов → 5 чанков → 5 векторов (384d all-MiniLM-L6-v2)
           → source_url привязан к каждому чанку
           → summary в каждом чанке (не теряется контекст)
```

---

## 3. Поиск (semantic search)

### Query: "API Gateway migration Kubernetes"

```
🏆 [arch] ADR-007: API Gateway Migration to Kubernetes
   Источник: https://confluence.softswiss.com/spaces/ARCH/pages/ADR-007
   Summary: API Gateway migrates from NGINX to Kong on K8s...
   Tags: #gateway #kubernetes #istio

   [platform] payment-service README (ссылается на ADR-007)
```

### Query: "как задеплоить payment service" (русский!)

```
🏆 [runbooks] Runbook: Payment Service Deployment
   Источник: https://confluence.softswiss.com/spaces/ENG/pages/RUNBOOK-PAYMENT
   Команды: git pull, docker build, kubectl apply
   Rollback: kubectl rollout undo
```

### Query: "PostgreSQL architecture Go microservice"

```
🏆 [platform] payment-service: Go microservice
   Источник: https://gitlab.softswiss.com/core/payment-service
   Стек: Go 1.22, PostgreSQL 15, Redis 7
   Endpoints: payments, refunds
```

---

## 4. MCP Server — как LLM получает знания

```python
# Cursor plugin делает MCP call:
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

**Что получает LLM:**
- ✅ **Чистый текст** — без HTML, без Confluence макросов
- ✅ **Source URL** — может дать ссылку разработчику
- ✅ **Summary** — контекст за 2-3 предложения
- ✅ **Tags** — для классификации
- ❌ **Не получает** — HTML мусор, права доступа других документов

---

## 5. Confluence Showcase — что видит человек

```
=======================  КОЛЛЕКЦИИ  =======================

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

## 6. Zero Friction: второй sync

```bash
$ kbk sync

── CONFLUENCE: ARCH
  No new/changed documents  ← StateTracker: hash совпадает, skip

── CONFLUENCE: ENG
  No new/changed documents

── GITLAB: core/payment-service
  No new/changed documents

📊 Summary: 0 new, 0 chunks, $0.0000 LLM cost
```

**Что сэкономили:**
- 3 LLM вызова (= ~$0.006)
- 3 Confluence API запроса
- 3 ChromaDB upsert'а
- Время: ~0.5 сек вместо ~10 сек

---

## 7. Архитектурные решения (почему это работает)

| Решение | Проблема | Как решили |
|---------|----------|------------|
| **Pull + Allowlist** | Webhooks ломаются, мусор отовсюду | Только whitelisted targets, только по команде |
| **SHA-256 dedup** | LLM жрет деньги на тех же данных | skip unchanged, 0 cost |
| **Один LLM call** | Два вызова = 2x cost и latency | Structured JSON: summary + tags |
| **Source URL в каждом чанке** | "Откуда это?" | Каждый чанк знает оригинал |
| **Word-boundary overlap** | Слова разрезаны между чанками | find(' ', overlap_start) |
| **fcntl flock** | Два sync параллельно ломают state | POSIX file lock |
| **Angle bracket protection** | List\<String\> убит HTML cleaner | code/pre/tt protection phase |

---

## 8. Ссылки

- Репозиторий: https://github.com/Wendigooor/knowledge-base-kit
- ATM runs: 3 x 6/6 gates = 18/18 total
- Demo script: `/tmp/kbk-v02-demo.py`

```
pip install git+https://github.com/Wendigooor/knowledge-base-kit.git
kbk init && kbk sync && kbk serve
```
