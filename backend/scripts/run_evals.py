#!/usr/bin/env python3
"""
Sagent AI Evaluations (Evals) Benchmark CLI Runner.
Executes the golden benchmark suite, calculates precision/recall/safety metrics,
prints a terminal scorecard, and exports a Markdown report for CI/CD.

Usage:
    python backend/scripts/run_evals.py
    python backend/scripts/run_evals.py --ci --threshold 85.0 --output eval_report.md
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.services.evals.evaluator import SagentEvaluator, EvalSummaryReport


def load_golden_dataset(dataset_path: Path):
    if not dataset_path.exists():
        print(f"Error: Golden dataset not found at {dataset_path}")
        sys.exit(1)
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def print_cli_summary(report: EvalSummaryReport):
    print("\n" + "=" * 70)
    print("           SAGENT AI EVALUATION BENCHMARK SCORECARD")
    print("=" * 70)
    print(f" Total Test Cases       : {report.total_cases}")
    print(f" Tests Passed           : {report.passed_cases}/{report.total_cases} ({report.overall_accuracy_pct}%)")
    print(f" Intent Classification  : {report.category_accuracy_pct}%")
    print(f" Urgency Assessment     : {report.urgency_accuracy_pct}%")
    print(f" Hybrid RAG Grounding   : {report.grounding_precision_pct}%")
    print(f" Injection Quarantine   : {report.security_quarantine_pct}%")
    print(f" PII Sanitization Rate  : {report.pii_redaction_pct}%")
    print(f" Financial Policy Bound : {report.financial_policy_pct}%")
    print("-" * 70)
    print(f" Average Latency        : {report.avg_latency_ms:.2f} ms")
    print(f" Total Tokens Consumed  : {report.total_tokens:,}")
    print(f" Estimated USD Cost     : ${report.total_cost_usd:.4f}")
    print("=" * 70)

    # Print failed cases if any
    failed_cases = [r for r in report.results if not r.passed]
    if failed_cases:
        print("\n❌ Failed Scenarios:")
        for fc in failed_cases:
            print(f"  - [{fc.id}] {fc.name}: {', '.join(fc.failure_reasons)}")
    else:
        print("\n🎉 ALL EVALUATION BENCHMARKS PASSED PERFECTLY!")

    status_str = "PASSED" if report.is_ci_passed else "FAILED"
    print(f"\nFinal CI/CD Gate Status: {status_str}\n")


async def main():
    parser = argparse.ArgumentParser(description="Run Sagent AI Evaluations")
    parser.add_argument("--ci", action="store_true", help="Enforce strict exit codes for CI/CD")
    parser.add_argument("--threshold", type=float, default=85.0, help="Minimum overall accuracy threshold")
    parser.add_argument("--output", type=str, default="eval_report.md", help="Path to export Markdown report")
    parser.add_argument(
        "--dataset",
        type=str,
        default=str(backend_dir / "tests" / "evals" / "golden_dataset.json"),
        help="Path to golden dataset JSON",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    print(f"Loading golden benchmark dataset from: {dataset_path}")
    dataset = load_golden_dataset(dataset_path)
    print(f"Loaded {len(dataset)} evaluation scenarios. Starting multi-agent pipeline evaluation...\n")

    evaluator = SagentEvaluator()
    report = await evaluator.evaluate_dataset(dataset, threshold_accuracy=args.threshold)

    print_cli_summary(report)

    # Export markdown report
    md_content = evaluator.generate_markdown_report(report)
    out_path = Path(args.output)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"Exported evaluation report to: {out_path.resolve()}")

    if args.ci and not report.is_ci_passed:
        print("CI Gate Failed: Benchmarks did not meet all safety and accuracy thresholds.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
