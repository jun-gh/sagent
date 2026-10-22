#!/usr/bin/env python3
"""
Generates a professionally styled Microsoft Word (.docx) document
for Sagent Phase 3 Testing Guide that imports seamlessly into Google Docs.
"""

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn


def set_cell_background(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    tcPr.append(shd)


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)


def add_code_block(doc, code_text):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    
    cell = table.cell(0, 0)
    cell.width = Inches(6.5)
    set_cell_background(cell, "F1F5F9")  # Slate 100
    set_cell_margins(cell, top=120, bottom=120, left=180, right=180)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.15
    run = p.add_run(code_text)
    run.font.name = "Consolas"
    run.font.size = Pt(9.5)
    run.font.color.rgb = RGBColor(30, 41, 59)  # Slate 800
    
    # Empty space after table
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def create_document(output_path):
    doc = Document()

    # Page Margins
    for section in doc.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # Document Title
    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(0)
    p_title.paragraph_format.space_after = Pt(4)
    run_title = p_title.add_run("Sagent AI — Phase 3 Testing Guide")
    run_title.font.name = "Arial"
    run_title.font.size = Pt(22)
    run_title.font.bold = True
    run_title.font.color.rgb = RGBColor(15, 23, 42)  # Slate 900

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_after = Pt(16)
    run_sub = p_sub.add_run("Operational Telemetry, Sub-Cent Cost Accounting & Systematic AI Evaluations")
    run_sub.font.name = "Arial"
    run_sub.font.size = Pt(12)
    run_sub.font.color.rgb = RGBColor(71, 85, 105)  # Slate 600

    # Section 1: Feature Summary Table
    h1 = doc.add_heading("1. Phase 3 Feature Summary", level=1)
    h1.paragraph_format.space_before = Pt(12)
    h1.paragraph_format.space_after = Pt(8)

    features = [
        ("1. Token & Cost Accounting Engine", "backend/app/services/ai/token_tracker.py", "Profiles prompt vs. completion tokens and computes exact sub-cent inference cost (USD) per ticket using Gemini pricing tiers."),
        ("2. Real-Time Metrics API", "GET /api/v1/metrics", "Exposes operational metrics: p50/p95/avg latencies, total tokens, cumulative USD cost, and security quarantine/redaction counters."),
        ("3. UI Telemetry Badges", "frontend/src/components/TriageResult.jsx", "Renders token count (e.g., 185 toks) and cost pill (e.g., $0.0001) beside Latency/Confidence with breakdown tooltip."),
        ("4. Golden Evals Benchmark (20 Cases)", "backend/tests/evals/golden_dataset.json", "20 real-world benchmark tickets evaluating Category/Urgency F1, Hybrid RAG precision, injection quarantines, PII scrubbing, and refund caps."),
        ("5. Evals CLI Benchmark Runner", "backend/scripts/run_evals.py", "CLI utility to execute evaluations, display a terminal scorecard, and export a Markdown report (eval_report.md)."),
        ("6. CI/CD Eval Quality Gate", ".github/workflows/evals.yml", "Automated GitHub Actions workflow running evals on PRs and publishing summary scorecards."),
    ]

    table = doc.add_table(rows=1, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    col_widths = [Inches(1.8), Inches(2.2), Inches(2.5)]

    # Header Row
    hdr_cells = table.rows[0].cells
    hdr_titles = ["Feature", "Component", "Purpose & Capabilities"]
    for i, title in enumerate(hdr_titles):
        hdr_cells[i].width = col_widths[i]
        set_cell_background(hdr_cells[i], "1E293B")  # Slate 800
        set_cell_margins(hdr_cells[i], top=100, bottom=100, left=120, right=120)
        p = hdr_cells[i].paragraphs[0]
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        run = p.add_run(title)
        run.font.name = "Arial"
        run.font.size = Pt(10)
        run.font.bold = True
        run.font.color.rgb = RGBColor(255, 255, 255)

    # Data Rows
    for row_idx, (f_name, comp, purp) in enumerate(features):
        row = table.add_row()
        bg_color = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for i, val in enumerate([f_name, comp, purp]):
            cell = row.cells[i]
            cell.width = col_widths[i]
            set_cell_background(cell, bg_color)
            set_cell_margins(cell, top=80, bottom=80, left=120, right=120)
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            run = p.add_run(val)
            run.font.name = "Arial"
            run.font.size = Pt(9.5)
            if i == 0:
                run.font.bold = True
            elif i == 1:
                run.font.name = "Consolas"
                run.font.size = Pt(9)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # Section 2: Step-by-Step Testing Guide
    h2 = doc.add_heading("2. Step-by-Step Testing Guide", level=1)
    h2.paragraph_format.space_before = Pt(16)
    h2.paragraph_format.space_after = Pt(8)

    # Test 1
    t1 = doc.add_heading("Test 1: Real-Time Operational Metrics API (GET /api/v1/metrics)", level=2)
    t1.paragraph_format.space_before = Pt(10)
    t1.paragraph_format.space_after = Pt(4)

    p = doc.add_paragraph("Purpose: Verify that the backend actively tracks throughput, p50/p95 latency, token counts, and cumulative USD inference expenditure.")
    p.runs[0].font.italic = True
    p.paragraph_format.space_after = Pt(4)

    doc.add_paragraph("Step 1.1: Query the live metrics endpoint:").runs[0].font.bold = True
    add_code_block(doc, "curl -s http://localhost:8000/api/v1/metrics | python3 -m json.tool")

    doc.add_paragraph("Expected Output Structure:").runs[0].font.bold = True
    add_code_block(doc, """{
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
}""")

    doc.add_paragraph("Step 1.2: Trigger a ticket triage request to increment live counters:").runs[0].font.bold = True
    add_code_block(doc, """curl -X POST http://localhost:8000/api/v1/tickets/triage \\
  -H "Content-Type: application/json" \\
  -d '{
    "title": "Cannot login with SAML SSO",
    "description": "Our Okta certificate expired this morning and all users are blocked.",
    "customer_tier": "enterprise",
    "customer_email": "admin@megacorp.com"
  }'""")

    doc.add_paragraph("Step 1.3: Re-query the metrics endpoint to verify counter updates:").runs[0].font.bold = True
    add_code_block(doc, "curl -s http://localhost:8000/api/v1/metrics | python3 -m json.tool")
    
    p = doc.add_paragraph("Verification Check:")
    p.runs[0].font.bold = True
    doc.add_paragraph("• total_requests has incremented to 1.")
    doc.add_paragraph("• total_tokens reflects actual usage (e.g. ~160–220 tokens).")
    doc.add_paragraph("• cumulative_cost_usd updates with actual inference cost (e.g. $0.0001).")

    # Test 2
    t2 = doc.add_heading("Test 2: Frontend Telemetry Pill & Cost Breakdown", level=2)
    t2.paragraph_format.space_before = Pt(14)
    t2.paragraph_format.space_after = Pt(4)

    p = doc.add_paragraph("Purpose: Verify that the web UI displays live token consumption and sub-cent financial cost alongside latency and confidence.")
    p.runs[0].font.italic = True
    p.paragraph_format.space_after = Pt(4)

    doc.add_paragraph("Step 2.1: Open the Dashboard in your browser:").runs[0].font.bold = True
    add_code_block(doc, "http://localhost:5173")

    doc.add_paragraph("Step 2.2: Submit a test support ticket with the following details:").runs[0].font.bold = True
    doc.add_paragraph("• Title: PostgreSQL connection pool exhausted")
    doc.add_paragraph("• Description: Error 53300: too many connections to database server. Applications failing with 500.")
    doc.add_paragraph("• Customer Tier: Enterprise")

    doc.add_paragraph("Step 2.3: Verify the Triage Result Header Badge:").runs[0].font.bold = True
    doc.add_paragraph("• Beside Confidence and Latency, observe the new telemetry badge: ⚡ 165 toks · $0.0001")
    doc.add_paragraph("• Hover over the badge to reveal the breakdown tooltip: Prompt Tokens: 125 | Completion Tokens: 40")

    # Test 3
    t3 = doc.add_heading("Test 3: Systematic AI Evaluations (Evals) Benchmark CLI", level=2)
    t3.paragraph_format.space_before = Pt(14)
    t3.paragraph_format.space_after = Pt(4)

    p = doc.add_paragraph("Purpose: Run the 20-ticket golden dataset through the multi-agent pipeline and generate an evaluation scorecard and report.")
    p.runs[0].font.italic = True
    p.paragraph_format.space_after = Pt(4)

    doc.add_paragraph("Step 3.1: Execute the evaluation runner command:").runs[0].font.bold = True
    add_code_block(doc, "docker compose exec backend python scripts/run_evals.py --threshold 75.0 --output /app/eval_report.md")

    doc.add_paragraph("Expected Terminal Scorecard:").runs[0].font.bold = True
    add_code_block(doc, """Loading golden benchmark dataset from: /app/tests/evals/golden_dataset.json
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
======================================================================""")

    doc.add_paragraph("Step 3.2: Inspect the generated Markdown evaluation report:").runs[0].font.bold = True
    add_code_block(doc, "docker compose exec backend cat /app/eval_report.md")

    # Test 4
    t4 = doc.add_heading("Test 4: Run the Backend Pytest Suite", level=2)
    t4.paragraph_format.space_before = Pt(14)
    t4.paragraph_format.space_after = Pt(4)

    p = doc.add_paragraph("Purpose: Run the entire automated Python unit test suite covering dynamic config, Gemini backoff, security guards, token tracker, and evals.")
    p.runs[0].font.italic = True
    p.paragraph_format.space_after = Pt(4)

    doc.add_paragraph("Step 4.1: Execute pytest inside the Docker container:").runs[0].font.bold = True
    add_code_block(doc, "docker compose exec backend pytest tests/")

    doc.add_paragraph("Expected Pytest Output:").runs[0].font.bold = True
    add_code_block(doc, """tests/test_config.py .                                                   [  3%]
tests/test_evals.py .....                                                [ 22%]
tests/test_gemini_client.py ..                                           [ 29%]
tests/test_injection_guard.py .....                                      [ 48%]
tests/test_output_guard.py ....                                          [ 62%]
tests/test_pii_scrubber.py ........                                      [ 92%]
tests/test_triage_orchestrator.py ..                                     [100%]

======================= 27 passed, 2 warnings in 18.56s ========================""")
    doc.add_paragraph("Verification Check: All 27 tests pass with a 100% success rate.").runs[0].font.bold = True

    # Test 5
    t5 = doc.add_heading("Test 5: Verify Frontend Production Build", level=2)
    t5.paragraph_format.space_before = Pt(14)
    t5.paragraph_format.space_after = Pt(4)

    p = doc.add_paragraph("Purpose: Verify that the React 18 frontend dashboard bundles cleanly without JSX, Tailwind, or Lucide icon errors.")
    p.runs[0].font.italic = True
    p.paragraph_format.space_after = Pt(4)

    doc.add_paragraph("Step 5.1: Execute the Vite production build command:").runs[0].font.bold = True
    add_code_block(doc, "docker compose exec frontend npm run build")

    doc.add_paragraph("Expected Build Output:").runs[0].font.bold = True
    add_code_block(doc, """vite v5.4.21 building for production...
✓ 1635 modules transformed.
dist/index.html                   0.96 kB │ gzip:  0.52 kB
dist/assets/index-Chc1VoZG.css   37.32 kB │ gzip:  6.46 kB
dist/assets/index-3eHB-PAn.js   275.50 kB │ gzip: 85.43 kB
✓ built in 6.29s""")

    # Section 3: Verification Checklist
    h3 = doc.add_heading("3. Summary Verification Checklist", level=1)
    h3.paragraph_format.space_before = Pt(16)
    h3.paragraph_format.space_after = Pt(6)

    checklist = [
        "Latency & Token Telemetry: Pipeline accurately profiles stage durations and prompt/completion token usage.",
        "Sub-Cent Accounting: Pricing models calculate accurate USD expenditure based on model token tiers.",
        "Operational API: GET /api/v1/metrics exposes system health, throughput, and latency percentiles.",
        "Frontend Dashboard: UI displays token and cost badges alongside confidence and latency metrics.",
        "Golden Benchmark: 20 scenarios validate intent accuracy, RAG grounding, and security guardrail containment.",
        "CI/CD Quality Gate: Automated GitHub Actions workflow (.github/workflows/evals.yml) enforces thresholds on PRs.",
    ]

    for item in checklist:
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(3)
        run = p.add_run(item)
        run.font.name = "Arial"
        run.font.size = Pt(10)

    # Save document
    doc.save(output_path)
    print(f"Document successfully created at: {output_path}")


if __name__ == "__main__":
    create_document("/app/Phase_3_Testing_Guide.docx")
