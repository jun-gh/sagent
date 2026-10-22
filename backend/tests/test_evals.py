import json
import os
import pytest
from app.services.ai.token_tracker import (
    TokenUsage,
    LatencyBreakdown,
    TelemetryData,
    calculate_cost,
    estimate_tokens,
    MetricsCollector,
)
from app.services.evals.evaluator import (
    SagentEvaluator,
    TestCaseResult,
    EvalSummaryReport,
)


def test_calculate_cost():
    # 100k prompt tokens, 50k completion tokens on gemini-2.5-flash
    # input: 0.1 * 0.075 = 0.0075
    # output: 0.05 * 0.30 = 0.015
    # total = 0.0225
    cost = calculate_cost(100_000, 50_000, "gemini-2.5-flash")
    assert cost == pytest.approx(0.0225, rel=1e-4)

    # Empty usage should yield 0.0
    assert calculate_cost(0, 0, "gemini-2.5-flash") == 0.0


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello") >= 1
    text = "A" * 400
    assert estimate_tokens(text) == 100


def test_metrics_collector():
    collector = MetricsCollector()
    assert collector.total_requests == 0

    # Record 3 sample requests
    collector.record_request(
        latency_ms=120.0,
        tokens=TokenUsage(prompt_tokens=100, completion_tokens=50, estimated_cost_usd=0.0001),
        security_verdict="PASSED",
        category="TECHNICAL",
        urgency="HIGH",
    )
    collector.record_request(
        latency_ms=250.0,
        tokens=TokenUsage(prompt_tokens=200, completion_tokens=80, estimated_cost_usd=0.0002),
        security_verdict="PASSED",
        category="BILLING",
        urgency="MEDIUM",
    )
    collector.record_request(
        latency_ms=50.0,
        tokens=TokenUsage(prompt_tokens=50, completion_tokens=10, estimated_cost_usd=0.00005),
        security_verdict="QUARANTINED",
        category="SECURITY",
        urgency="CRITICAL",
    )

    summary = collector.get_summary()
    assert summary["total_requests"] == 3
    assert summary["tokens"]["total_tokens"] == 490
    assert summary["tokens"]["cumulative_cost_usd"] == pytest.approx(0.00035, abs=1e-4)
    assert summary["security"]["quarantined_attacks"] == 1
    assert summary["latency"]["avg_ms"] == pytest.approx(140.0, rel=1e-2)
    assert summary["distribution"]["categories"]["TECHNICAL"] == 1


def test_golden_dataset_structure():
    dataset_path = os.path.join(
        os.path.dirname(__file__), "evals", "golden_dataset.json"
    )
    assert os.path.exists(dataset_path), f"Golden dataset not found at {dataset_path}"

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list)
    assert len(data) >= 15, "Golden dataset should have at least 15 test cases"

    for case in data:
        assert "id" in case
        assert "name" in case
        assert "title" in case
        assert "description" in case
        assert "expected_category" in case
        assert "expected_urgency" in case
        assert "expected_security_verdict" in case


def test_eval_summary_report_markdown():
    res = TestCaseResult(
        id="TC-001",
        name="Test Case 1",
        passed=True,
        category_match=True,
        urgency_match=True,
        security_match=True,
        grounding_match=True,
        policy_match=True,
        latency_ms=145.2,
        actual_category="BILLING",
        expected_category="BILLING",
        actual_urgency="HIGH",
        expected_urgency="HIGH",
        actual_security="PASSED",
        expected_security="PASSED",
        confidence_score=0.95,
        citations_count=2,
    )
    report = EvalSummaryReport(
        total_cases=1,
        passed_cases=1,
        overall_accuracy_pct=100.0,
        category_accuracy_pct=100.0,
        urgency_accuracy_pct=100.0,
        grounding_precision_pct=100.0,
        security_quarantine_pct=100.0,
        pii_redaction_pct=100.0,
        financial_policy_pct=100.0,
        avg_latency_ms=145.2,
        total_tokens=250,
        total_cost_usd=0.00012,
        is_ci_passed=True,
        results=[res],
    )

    evaluator = SagentEvaluator()
    markdown = evaluator.generate_markdown_report(report)
    assert "# Sagent AI Evaluation Report" in markdown
    assert "PASSED" in markdown
    assert "TC-001" in markdown
    assert "100.0%" in markdown
