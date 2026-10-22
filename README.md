# Sagent (Smart Autonomous Gateway for Enterprise Network Ticketing)

An enterprise-grade, autonomous Ticket Triage AI multi-agent platform that ingests incoming customer and technical support tickets, classifies intent/urgency, retrieves grounding knowledge via hybrid RAG (pgvector dense embeddings + PostgreSQL FTS BM25 keyword search), coordinates resolution actions via multi-agent orchestration, protects users with comprehensive security guardrails, and provides continuous quality gating through systematic AI evaluations (Evals) and real-time operational telemetry.

🔗 **Live:** [sagent-ph.vercel.app](https://sagent-ph.vercel.app/)
🔗 **API:** [sagent-3o6a.onrender.com](https://sagent-3o6a.onrender.com/)
---

## System Architecture Overview

```
                            [ Incoming Support Ticket ]
                                        │
                                        ▼
                            ┌───────────────────────┐
                            │  Triage Orchestrator  │
                            └───────────┬───────────┘
                                        │
             ┌──────────────────────────┼──────────────────────────┐
             ▼                          ▼                          ▼
    ┌────────────────┐         ┌────────────────┐         ┌────────────────┐
    │  Triage Agent  │         │Researcher Agent│         │Resolution Agent│
    │ (Intent/Urgency│         │ (Hybrid RAG)   │         │ (Reply/Action) │
    └────────┬───────┘         └────────┬───────┘         └────────┬───────┘
             │                          │                          │
             └──────────────────────────┼──────────────────────────┘
                                        ▼
                             ┌─────────────────────┐
                             │    Gemini Client    │
                             │ (3x Backoff+Jitter) │
                             └──────────┬──────────┘
                                        │
                         ┌──────────────┴──────────────┐
                         ▼                             ▼
                 [ Google Gemini ]           [ Neon / pgvector ]
                 (Dynamic Model)             (Hybrid Dense + FTS)
```

### Key Technical Pillars
1. **Dynamic Model Switching**: The active Gemini model is configured exclusively in `.env` (e.g. `GEMINI_MODEL=gemini-2.5-flash` or `gemini-1.5-pro`). Changing `.env` and restarting is instantly reflected on `GET /api/v1/config` and in the frontend header badge.
2. **Resilience & Error Transparency**: All outbound Gemini calls are protected by a 3-retry exponential backoff with random jitter. Quota/rate-limit errors (HTTP 429) return typed JSON error envelopes (`RATE_LIMIT_EXCEEDED`) and surface contextual, dismissible UI banners.
3. **Hybrid RAG**: Combines 768-dimensional dense vector embeddings (`gemini-embedding-001`) with PostgreSQL native `tsvector` full-text search using Reciprocal Rank Fusion (RRF) and Relative-Score Pruning.
4. **Multi-Agent Orchestration**: Autonomous pipeline comprising `TriageAgent` (classification & query generation), `ResearcherAgent` (runbook retrieval), and `ResolutionAgent` (grounded response synthesis).

---

## Hybrid RAG Search Architecture & Logic

Sagent implements a full-stack Hybrid Search pipeline that fuses **dense vector search** (semantic conceptual similarity) with **sparse keyword search** (exact lexical / BM25 matching) using **Reciprocal Rank Fusion (RRF)**, backed by **Relative-Score Pruning**.

### 1. Dual Search Engines

| Engine | Technology | Representation | Target Indexed Fields | Best Suited For |
| :--- | :--- | :--- | :--- | :--- |
| **Dense Vector Search** | Google Gemini `gemini-embedding-001` + `pgvector` | 768-dimensional float embeddings | `content` (cosine distance `<=>`) | Paraphrased queries, conceptual synonyms, conversational intent |
| **Sparse Keyword Search** | PostgreSQL Full-Text Search (`to_tsvector` + `plainto_tsquery`) | Lexical tokens & lexemes (`tsvector`) | `document_title` + `content` (`ts_rank_cd`) | Error codes (HTTP 403, 40P01), protocol names (SAML, SSO, S3, IAM), exact IDs |

### 2. Reciprocal Rank Fusion (RRF) Formula

To combine rank lists from dense vector search and sparse keyword search without requiring fragile cross-engine score normalization, candidates are fused using the standard **Reciprocal Rank Fusion (RRF)** formula:

$$\text{score}(d) = \frac{\text{dense\_weight}}{k + \text{dense\_rank}} + \frac{\text{sparse\_weight}}{k + \text{sparse\_rank}}$$

#### Parameter Configuration
- **$k = 60$**: Standard RRF smoothing constant that prevents top-rank positions from overpowering the fused score distribution while rewarding items that rank well across both modalities.
- **$\text{dense\_weight} = 0.6$**: Weight assigned to semantic vector proximity.
- **$\text{sparse\_weight} = 0.4$**: Weight assigned to exact full-text keyword matches.
- If a document is retrieved by only one branch, the missing rank contribution is evaluated as $0.0$.

#### The "Double-Winner Bonus"
When a document is validated by **both** dense semantic search and sparse keyword matching, its reciprocal scores compound:
- **Rank 1 in Dense + Rank 1 in Sparse**:
  $$\text{score} = \frac{0.6}{60 + 1} + \frac{0.4}{60 + 1} = \frac{1.0}{61} \approx \mathbf{0.01639}$$
- **Rank 2 in Dense only (0 Sparse match)**:
  $$\text{score} = \frac{0.6}{60 + 2} + 0 = \frac{0.6}{62} \approx \mathbf{0.00968}$$
*(The dual-confirmed match scores **~70% higher** than a single-branch match).*

### 3. Relative-Score Pruning & Precision Gating

In production RAG pipelines, returning a fixed `top_k` can introduce noisy or semantically adjacent trailing candidates (e.g., pulling generic access runbooks into an exact S3 bucket query). Sagent applies post-RRF **Relative-Score Pruning**:

1. **Dual-Agreement Dominance**: If Rank #1 has strong dual confirmation (`keyword_score > 0` and high vector similarity), any trailing candidate that has zero keyword confirmation (`keyword_score == 0.0`) and scores $< 70\%$ of Rank #1 is automatically pruned.
2. **Relative Drop-off Gate**: Any trailing candidate whose composite score falls below $50\%$ of the top score is dropped.
3. **Similarity Gating**: A baseline vector floor ($\ge 0.58$) and sparse floor ($\ge 0.01$) prevent off-topic queries (such as queries about topics absent from the knowledge base) from returning hallucinated documents, returning an empty set (`[]`) instead.

---

## Enterprise Security & Guardrails Architecture

Sagent implements defense-in-depth across the ingestion, reasoning, retrieval, and response synthesis lifecycles.

```
                           [ Incoming Support Ticket ]
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │   Stage 1: Ingestion & Auth Gate  │
                     │  - API Key / Auth Verification    │
                     │  - Rate Limiter (Sliding Window)  │
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │   Stage 2: PII Redaction Engine   │
                     │  - Regex & Algorithmic Scrubbing  │
                     │  - Mask API Keys, Passwords, CCs  │
                     │  - In-Memory Safe Token Map       │
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │ Stage 3: Prompt Injection Guard   │
                     │  - Jailbreak & Override Detection │
                     │  - Strict <user_ticket_content>   │
                     │  - Instant Quarantining (0.5ms)   │
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │ Multi-Agent Triage & Hybrid RAG   │
                     │  (Grounded on Sanitized Inputs)   │
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                     ┌───────────────────────────────────┐
                     │ Stage 4: Output Policy Shield     │
                     │  - System Prompt Leak Prevention  │
                     │  - Financial / Refund Cap Check   │
                     │  - Safe De-anonymization          │
                     └─────────────────┬─────────────────┘
                                       │
                                       ▼
                     [ Safe Customer Reply & Audit Log ]
```

### Security Pillars

1. **PII Masking & Anonymization Engine (`backend/app/services/security/pii_scrubber.py`)**:
   - Detects and redacts credentials before LLM calls and persistent logging.
   - Types scrubbed: AWS Access Keys (`AKIA...`), Stripe Keys (`sk_live_...`), GitHub Tokens, JWTs, Bearer Tokens, Plaintext Passwords (`password: ...`), Social Security Numbers, Emails, Phone Numbers, and Luhn-validated Credit Card numbers.
   - Replaces entities with typed placeholders (`[REDACTED_AWS_ACCESS_KEY_1]`, `[REDACTED_CREDIT_CARD_1]`).

2. **Prompt Injection & Jailbreak Defense (`backend/app/services/security/injection_guard.py`)**:
   - High-speed heuristic and pattern scanner detecting instruction resets (*"Ignore previous instructions"*), jailbreak personas (*"DAN"*, *"Developer Mode"*), system overrides (*"sudo mode on"*), and delimiter escaping.
   - Instant quarantine ($0.5\text{ms}$) preventing malicious prompts from consuming LLM tokens.
   - Cognitive delimiter isolation: Encloses user inputs in `<user_ticket_content>` tags with `[ESCAPED_DELIMITER]` neutralization.

3. **Output Policy Shield & Hallucination Guard (`backend/app/services/security/output_guard.py`)**:
   - Scans synthesized replies for internal database connection strings (`postgresql://...`) and accidental prompt instruction leakage.
   - Enforces business bounds: Automated refund promises exceeding \$250 USD trigger policy intercept and supervisory review notices.

4. **API Authentication & Rate Limiting (`backend/app/core/security.py`)**:
   - Per-IP sliding-window rate limiter (120 RPM default) preventing denial-of-wallet and brute-force spikes.
   - Optional API Key / Bearer token gate (`X-API-Key` or `Authorization: Bearer <key>`).

---

## Systematic AI Evaluations (Evals), Telemetry & Observability

Sagent implements rigorous, quantitative quality gates, token cost accounting, and real-time production observability to prevent regressions across model upgrades or knowledge base updates.

### 1. Golden Evaluation Suite (`backend/tests/evals/golden_dataset.json`)
A curated benchmark suite of 20 diverse, realistic support scenarios covering:
- Complex technical errors (PostgreSQL connection pool exhaustions, deadlocks, 429 rate limits)
- Billing edge cases and refund claims exceeding automated caps
- Auth & SSO federation errors (expired SAML certificates, clock skew)
- Real-world prompt injection payloads and delimiter breakout attempts
- PII and credentials accidentally pasted in ticket descriptions

### 2. Automated Quality Gates
Every evaluation run grades the multi-agent pipeline against strict enterprise thresholds:

| Quality & Safety Gate | Target Threshold | Description |
| :--- | :--- | :--- |
| **Overall Benchmark Pass** | $\ge 85.0\%$ | Aggregate passing percentage across all golden test cases |
| **Intent Classification Accuracy** | $\ge 80.0\%$ | Precision/Recall for category and urgency prioritization |
| **Hybrid RAG Grounding Precision** | $\ge 85.0\%$ | Retrieval precision verifying runbook citations are relevant |
| **Injection Quarantine Rate** | $100.0\%$ | Zero-tolerance containment for adversarial injection attacks |
| **PII Scrubbing Sanitization Rate** | $100.0\%$ | 100% masking of raw credentials, AWS keys, Stripe tokens, and CCs |
| **Financial Cap Policy Adherence** | $100.0\%$ | Enforces supervisor verification whenever compensation exceeds $\$250$ |

### 3. Running Systematic AI Evaluations (CLI)
You can run the eval benchmark anytime locally or in CI:

```bash
# Run benchmark with default 85% threshold
python backend/scripts/run_evals.py

# Run in CI mode with custom threshold and markdown export
python backend/scripts/run_evals.py --ci --threshold 85.0 --output eval_report.md
```

### 4. Real-Time Telemetry & Token Cost Engine (`GET /api/v1/metrics`)
Sagent continuously profiles every pipeline stage and accumulates token consumption into sub-cent financial accounting:
- **Latencies**: Real-time p50, p95, p99, and average response times across all agents.
- **Token Tracking**: Prompt vs. completion tokens parsed directly from Gemini `usageMetadata`.
- **Cost Modeling**: Dynamic pricing tiers ($0.075 / 1M input, $0.30 / 1M output on Gemini 2.5 Flash).
- **Security Observability**: Live counters of quarantined attacks, sanitized PII tickets, and clean traffic.
- **Live Observability Modal**: Interactive dashboard modal in the UI displaying live latency percentiles, uptime, token usage, and guardrail statistics directly in the browser.

### 5. 1-Click Incident Dispatch & Resolution Hub
Accelerates mean-time-to-resolution (MTTR) by allowing operators to export pre-formatted incident briefs directly from the triage results view:
- **Copy Customer Reply**: Single-click copy of the guardrail-sanitized customer reply with clipboard feedback.
- **Copy Slack Brief**: Generates structured incident notifications formatted specifically for Slack `#incidents` channels.
- **Copy Jira Issue**: Exports Markdown-formatted issue descriptions with acceptance criteria checklists ready for backlog ingestion.

---

## Repository Structure

```
sagent/
├── .github/
│   └── workflows/
│       ├── backend-ci.yml         # Ruff linting & 28-test Pytest suite
│       ├── frontend-ci.yml        # Vite production build & JSX validation
│       ├── evals.yml              # Automated AI quality gate on PRs
│       └── deploy.yml             # Render production deployment trigger
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── endpoints/
│   │   │       │   ├── config.py  # Dynamic model metadata
│   │   │       │   ├── tickets.py # Triage ingestion & history
│   │   │       │   ├── kb.py      # Hybrid RAG search & runbooks
│   │   │       │   └── metrics.py # Real-time latency, token & cost metrics
│   │   │       └── router.py
│   │   ├── core/
│   │   │   ├── config.py          # Dynamic model, Neon URL sanitizer & env loader
│   │   │   ├── database.py        # Async engine & sessionmaker (pgvector)
│   │   │   └── errors.py          # Centralized error handlers & envelopes
│   │   ├── models/                # SQLAlchemy models (Ticket, ContextChunk, Audit)
│   │   ├── schemas/               # Pydantic v2 schemas & security envelopes
│   │   ├── services/
│   │   │   ├── ai/                # Gemini client (3x backoff) & TokenTracker
│   │   │   ├── agents/            # Orchestrator, Triage, Researcher, Resolution
│   │   │   ├── evals/             # Systematic AI Evaluator benchmark engine
│   │   │   ├── security/          # PIIScrubber, InjectionGuard, OutputGuard
│   │   │   └── rag/               # Hybrid search with pgvector + tsvector RRF
│   │   └── main.py
│   ├── scripts/
│   │   └── run_evals.py           # CLI benchmark runner (--ci, --threshold)
│   ├── tests/
│   │   ├── evals/
│   │   │   └── golden_dataset.json# 20 curated benchmark scenarios
│   │   ├── test_config.py
│   │   ├── test_evals.py
│   │   ├── test_gemini_client.py
│   │   ├── test_injection_guard.py
│   │   ├── test_output_guard.py
│   │   ├── test_pii_scrubber.py
│   │   └── test_triage_orchestrator.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── public/
│   │   └── favicon.svg            # Minimalist brand favicon
│   ├── src/
│   │   ├── components/            # Header, TicketForm, TriageResult, TelemetryModal, KB
│   │   ├── hooks/                 # Custom React hooks (useAgent, useConfig)
│   │   ├── services/              # API client with interceptors
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   ├── vite.config.js
│   └── vercel.json
├── docker-compose.yml             # Local Postgres + pgvector + Backend + Frontend
├── render.yaml                    # Render Blueprint IaC
├── PHASE_3_TESTING_GUIDE.md       # Complete step-by-step testing walkthrough
├── Phase_3_Testing_Guide.docx     # Downloadable testing guide for Google Docs
└── README.md
```

---

## Local Development Setup

### Option 1: Native Virtual Environment (Fastest)

#### 1. Backend Setup
```bash
cd backend

# Create and activate python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Configure your GEMINI_API_KEY in .env:
# GEMINI_API_KEY=your_key_here
# GEMINI_MODEL=gemini-2.5-flash

# Run the FastAPI server
uvicorn app.main:app --reload --port 8000
```
API Documentation will be available at: `http://localhost:8000/docs`

#### 2. Frontend Setup
```bash
cd frontend

# Install node dependencies
npm install

# Start Vite development server
npm run dev
```
Frontend will be available at: `http://localhost:5173`

---

### Option 2: Docker Compose (PostgreSQL with pgvector)

```bash
# Set your Gemini API key
export GEMINI_API_KEY=your_gemini_api_key_here
export GEMINI_MODEL=gemini-2.5-flash

# Start PostgreSQL with pgvector and Backend
docker compose up --build
```
This starts:
- PostgreSQL 16 with `pgvector` on port `5432`
- Sagent FastAPI Backend on port `8000`

---

## Running Automated Tests

Run backend unit tests (covers dynamic config, exponential backoff, rate-limit exception envelope, and multi-agent triage):

```bash
cd backend
source venv/bin/activate
pytest -v
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/v1/config` | Returns dynamic active model metadata for header badge |
| `POST` | `/api/v1/tickets/triage` | Ingests ticket, runs multi-agent pipeline, returns classification & grounded reply |
| `GET` | `/api/v1/tickets` | Lists historical triaged tickets |
| `GET` | `/api/v1/tickets/{id}` | Retrieves specific ticket by ID |
| `GET` | `/api/v1/metrics` | Returns real-time latency p50/p95, cumulative tokens, cost, and security metrics |
| `POST` | `/api/v1/kb/search` | Direct testing of Hybrid RAG (dense + BM25 RRF) |
| `POST` | `/api/v1/kb/seed` | Seeds default enterprise runbooks into vector store |
