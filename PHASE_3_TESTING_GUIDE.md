# Sagent AI — Phase 3 Testing Guide
### Operational Telemetry, Sub-Cent Cost Accounting & Systematic AI Evaluations

---

## 1. Phase 3 Feature Summary

| Feature | Component | Purpose & Capabilities |
| :--- | :--- | :--- |
| **1. Token & Cost Accounting Engine** | `backend/app/services/ai/token_tracker.py` | Profiles prompt vs. completion tokens and computes exact sub-cent inference cost (USD) per ticket using Gemini pricing tiers. |
| **2. Real-Time Metrics API** | `GET /api/v1/metrics` | Exposes operational metrics: p50/p95/avg latencies, total tokens, cumulative USD cost, and security quarantine/redaction counters. |
| **3. UI Telemetry Badges** | `frontend/src/components/TriageResult.jsx` | Renders token count (e.g., `185 toks`) and cost pill (e.g., `$0.0001`) beside Latency/Confidence with breakdown tooltip. |
| **4. Golden Evals Benchmark (20 Cases)** | `backend/tests/evals/golden_dataset.json` | 20 real-world benchmark tickets evaluating Category/Urgency F1, Hybrid RAG precision, injection quarantines, PII scrubbing, and refund caps. |
| **5. Evals CLI Benchmark Runner** | `backend/scripts/run_evals.py` | CLI utility to execute evaluations, display a terminal scorecard, and export a Markdown report (`eval_report.md`). |
| **6. CI/CD Eval Quality Gate** | `.github/workflows/evals.yml` | Automated GitHub Actions workflow running evals on PRs and publishing summary scorecards. |

---

## 2. Step-by-Step Testing Guide

### Test 1: Real-Time Operational Metrics API (`GET /api/v1/metrics`)
*Purpose: Verify that the backend actively tracks throughput, p50/p95 latency, token counts, and cumulative USD inference expenditure.*

**Step 1.1: Query the live metrics endpoint:**
```bash
curl -s http://localhost:8000/api/v1/metrics | python3 -m json.tool
```

**Expected Output Structure:**
```json
{
    "status": "healthy",
    "uptime_seconds": 1245.0,
    "total_requests": 0,
    "latency": {
        "avg_ms": 0.0,
        "p50_ms": 0.0,
        "p95_ms": 0.0,
        "p99_ms": 0.0
    },
    "tokens": {
        "total_tokens": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cumulative_cost_usd": 0.0
    },
    "security": {
        "quarantined_attacks": 0,
        "sanitized_pii_tickets": 0,
        "clean_tickets": 0
    },
    "distribution": {
        "categories": {},
        "urgencies": {}
    }
}
```

**Step 1.2: Trigger a ticket triage request to increment live counters:**
```bash
curl -X POST http://localhost:8000/api/v1/tickets/triage \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Cannot login with SAML SSO",
    "description": "Our Okta certificate expired this morning and all users are blocked.",
    "customer_tier": "enterprise",
    "customer_email": "admin@megacorp.com"
  }'
```

**Step 1.3: Re-query the metrics endpoint to verify counter updates:**
```bash
curl -s http://localhost:8000/api/v1/metrics | python3 -m json.tool
```
**Verification Check:**
- `total_requests` has incremented to `1`.
- `total_tokens` reflects actual usage (e.g. `~160–220 tokens`).
- `cumulative_cost_usd` updates with actual inference cost (e.g. `$0.0001`).

---

### Test 2: Frontend Telemetry Pill & Cost Breakdown
*Purpose: Verify that the web UI displays live token consumption and sub-cent financial cost alongside latency and confidence.*

**Step 2.1: Open the Dashboard in your browser:**
```text
http://localhost:5173
```

**Step 2.2: Submit a test support ticket with the following details:**
- **Title**: `PostgreSQL connection pool exhausted`
- **Description**: `Error 53300: too many connections to database server. Applications failing with 500.`
- **Customer Tier**: `Enterprise`

**Step 2.3: Verify the Triage Result Header Badge:**
- Beside **Confidence** and **Latency**, observe the new telemetry badge:  
  `⚡ 165 toks · $0.0001`
- Hover over the badge to reveal the breakdown tooltip:  
  `Prompt Tokens: 125 | Completion Tokens: 40`

---

### Test 3: Systematic AI Evaluations (Evals) Benchmark CLI
*Purpose: Run the 20-ticket golden dataset through the multi-agent pipeline and generate an evaluation scorecard and report.*

**Step 3.1: Execute the evaluation runner command:**
```bash
docker compose exec backend python scripts/run_evals.py --threshold 75.0 --output /app/eval_report.md
```
*(Or natively if your virtualenv is activated: `python backend/scripts/run_evals.py`)*

**Expected Terminal Scorecard:**
```text
Loading golden benchmark dataset from: /app/tests/evals/golden_dataset.json
Loaded 20 evaluation scenarios. Starting multi-agent pipeline evaluation...

[01/20] Evaluating eval-001: SAML SSO Okta Cert Expiry... -> ✅ PASS
[02/20] Evaluating eval-002: Stripe Duplicate Upgrade Charge... -> ✅ PASS
[03/20] Evaluating eval-003: PostgreSQL Production Deadlocks... -> ✅ PASS
[04/20] Evaluating eval-004: Prompt Injection Jailbreak Attack... -> ✅ PASS
...
======================================================================
           SAGENT AI EVALUATION BENCHMARK SCORECARD
======================================================================
 Total Test Cases       : 20
 Tests Passed           : 18/20 (90.0%)
 Intent Classification  : 95.0%
 Urgency Assessment     : 90.0%
 Hybrid RAG Grounding   : 100.0%
 Injection Quarantine   : 100.0%
 PII Sanitization Rate  : 100.0%
 Financial Policy Bound : 100.0%
----------------------------------------------------------------------
 Average Latency        : 22000.00 ms
 Total Tokens Consumed  : ~24,000
 Estimated USD Cost     : ~$0.0022
======================================================================
```

**Step 3.2: Inspect the generated Markdown evaluation report:**
```bash
docker compose exec backend cat /app/eval_report.md
```

---

### Test 4: Run the Backend Pytest Suite
*Purpose: Run the entire automated Python unit test suite covering dynamic config, Gemini backoff, security guards, token tracker, and evals.*

**Step 4.1: Execute pytest inside the Docker container:**
```bash
docker compose exec backend pytest tests/
```

**Expected Pytest Output:**
```text
tests/test_config.py .                                                   [  3%]
tests/test_evals.py .....                                                [ 22%]
tests/test_gemini_client.py ..                                           [ 29%]
tests/test_injection_guard.py .....                                      [ 48%]
tests/test_output_guard.py ....                                          [ 62%]
tests/test_pii_scrubber.py ........                                      [ 92%]
tests/test_triage_orchestrator.py ..                                     [100%]

======================= 27 passed, 2 warnings in 18.56s ========================
```
**Verification Check:** All **27 tests pass with a 100% success rate**.

---

### Test 5: Verify Frontend Production Build
*Purpose: Verify that the React 18 frontend dashboard bundles cleanly without JSX, Tailwind, or Lucide icon errors.*

**Step 5.1: Execute the Vite production build command:**
```bash
docker compose exec frontend npm run build
```

**Expected Build Output:**
```text
vite v5.4.21 building for production...
✓ 1635 modules transformed.
dist/index.html                   0.96 kB │ gzip:  0.52 kB
dist/assets/index-Chc1VoZG.css   37.32 kB │ gzip:  6.46 kB
dist/assets/index-3eHB-PAn.js   275.50 kB │ gzip: 85.43 kB
✓ built in 6.29s
```

---

## 3. Summary Verification Checklist

- [x] **Latency & Token Telemetry**: Pipeline accurately profiles stage durations and prompt/completion token usage.
- [x] **Sub-Cent Accounting**: Pricing models calculate accurate USD expenditure based on model token tiers.
- [x] **Operational API**: `GET /api/v1/metrics` exposes system health, throughput, and latency percentiles.
- [x] **Frontend Dashboard**: UI displays token and cost badges alongside confidence and latency metrics.
- [x] **Golden Benchmark**: 20 scenarios validate intent accuracy, RAG grounding, and security guardrail containment.
- [x] **CI/CD Quality Gate**: Automated GitHub Actions workflow (`.github/workflows/evals.yml`) enforces thresholds on PRs.
