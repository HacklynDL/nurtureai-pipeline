# NurtureAI — Autonomous B2B Lead Qualification Pipeline

![Status](https://img.shields.io/badge/status-production-brightgreen)
![Python](https://img.shields.io/badge/python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791)
![Claude](https://img.shields.io/badge/Claude-Sonnet--4-CC785C)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

> Autonomous pipeline that transforms raw contact data into scored, enriched, CRM-ready leads — with zero manual intervention.

**Webhook → Validate → Enrich → Score (AI) → PostgreSQL → Brevo CRM**

---

## Architecture
```mermaid
flowchart TD
    A([📋 Lead Source\nLinkedIn / Form / CSV]) -->|POST /leads| B

    subgraph API ["🔌 FastAPI Webhook"]
        B[Receive & Authenticate]
        B --> C[Background Task Queue]
    end

    subgraph PIPELINE ["⚙️ Processing Pipeline"]
        C --> D[📧 Email Validation\nHunter.io]
        D -->|Score < 70 or catch-all| REJECT([❌ Rejected])
        D -->|Valid| E[🔍 Company Enrichment\nPerplexity API]
        E --> F[🤖 AI Lead Scoring\nClaude Sonnet]
        F --> G[(🗄️ PostgreSQL\nleads · scores · enrichments)]
    end

    subgraph OUTPUT ["📤 Output"]
        G --> H[📊 Brevo CRM Export\nCSV ; UTF-8]
        G --> I[📈 Stats Dashboard\nGET /stats]
        H --> J[📬 Email Campaign\nMulti-touch sequence]
    end
```

---

## Repository Structure
