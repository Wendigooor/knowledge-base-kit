# KBK v2 — Demo

## Narrative



## CLI Session

```
$ kbk init
✅ Knowledge index initialized at ~/.kbk/chromadb

$ kbk index --text "ADR-007: API Gateway переезжает на K8s. Причина: масштабирование. RabbitMQ не справляется с нагрузкой 50k rps. Kafka рассмотрен, rejected из-за сложности. K8s HPA + istio выбраны." --source confluence --url "https://confluence.softswiss.com/pages/ADR-007" --collection architecture
✅ Indexed a1b2c3d4... → architecture [ADR, API, Gateway, K8s, Migration]

$ kbk index --text "Runbook: Payment Service деплой. 1. git pull 2. docker build 3. kubectl apply 4. проверить pod статус 5. smoke test" --source confluence --url "https://confluence.softswiss.com/pages/RUNBOOK-PAYMENT" --collection runbooks
✅ Indexed e5f6g7h8... → runbooks [Payment, Service, Deploy, Docker, K8s]

$ kbk index --text "QA-451: Проверка бонусного калькулятора. 1. Создать пользователя 2. Начислить бонус 3. Проверить баланс 4. Проверить историю" --source jira --url "https://jira.softswiss.com/browse/QA-451" --collection business
✅ Indexed i9j0k1l2... → business [Bonus, Calculator, QA, Check]

$ kbk search "API Gateway architecture" --collection architecture
  [architecture] a1b2c3d4... [ADR, API, Gateway]
    ADR-007: API Gateway переезжает на K8s. Причина: масштабирование...
    🔗 https://confluence.softswiss.com/pages/ADR-007

$ kbk search "как деплоить payment" --collection runbooks
  [runbooks] e5f6g7h8... [Payment, Service, Deploy]
    Runbook: Payment Service деплой. 1. git pull 2. docker build...
    🔗 https://confluence.softswiss.com/pages/RUNBOOK-PAYMENT

$ kbk status
📊 Knowledge Index Status
  Collections:
    📁 architecture: 1 docs
    📁 runbooks: 1 docs
    📁 business: 1 docs
  Total: 3 documents

$ kbk connectors
🔌 Available Connectors
  confluence
  jira
  gitlab
  slack

$ kbk explore
📖 Knowledge Space
  Read-Only Confluence space: https://confluence.softswiss.com/spaces/KBK
  Structure:
    📁 Architecture
    📁 Infrastructure
    📁 Business
    📁 Runbooks
    📁 Decisions
    📁 Team
```

## Summary

KBK v2 индексирует 3 документа из разных источников (Confluence ADR, Confluence runbook, Jira QA ticket)
в единый семантический индекс. Поиск работает по смыслу, не по ключевым словам.
Каждый результат содержит ссылку на оригинал — пользователь переходит в Confluence/Jira для деталей.
