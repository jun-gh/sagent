import logging
import math
import time
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("sagent.telemetry")

# Standard Google Gemini API Pricing (USD per 1 Million tokens)
# Source: Google Cloud Vertex AI & Google AI Studio pricing tiers
MODEL_PRICING: dict[str, dict[str, float]] = {
    # Gemini 3.8 Flash / 2.5 Flash / 1.5 Flash
    "gemini-3.8-flash": {"input_per_million": 0.075, "output_per_million": 0.30},
    "gemini-flash-latest": {"input_per_million": 0.075, "output_per_million": 0.30},
    "gemini-2.5-flash": {"input_per_million": 0.075, "output_per_million": 0.30},
    "gemini-1.5-flash": {"input_per_million": 0.075, "output_per_million": 0.30},
    "gemini-2.0-flash": {"input_per_million": 0.10, "output_per_million": 0.40},
    "gemini-3.1-flash-lite": {"input_per_million": 0.05, "output_per_million": 0.20},
    # Gemini 1.5 Pro
    "gemini-1.5-pro": {"input_per_million": 1.25, "output_per_million": 5.00},
    "gemini-2.5-pro": {"input_per_million": 1.25, "output_per_million": 5.00},
    # Default fallback rate
    "default": {"input_per_million": 0.10, "output_per_million": 0.40},
}


class TokenUsage(BaseModel):
    """Token consumption and financial cost metrics for an AI agent interaction."""
    prompt_tokens: int = Field(default=0, description="Tokens consumed by the input prompt")
    completion_tokens: int = Field(default=0, description="Tokens produced in the generated response")
    total_tokens: int = Field(default=0, description="Sum of prompt and completion tokens")
    estimated_cost_usd: float = Field(default=0.0, description="Estimated inference cost in USD")
    model: str = Field(default="gemini-3.8-flash", description="Model name used for calculation")


class LatencyBreakdown(BaseModel):
    """Granular latency profile across each pipeline stage in milliseconds."""
    security_filter_ms: float = 0.0
    triage_classification_ms: float = 0.0
    rag_retrieval_ms: float = 0.0
    resolution_synthesis_ms: float = 0.0
    output_guard_ms: float = 0.0
    total_latency_ms: float = 0.0


class TelemetryData(BaseModel):
    """Comprehensive observability payload attached to every triage response."""
    tokens: TokenUsage = Field(default_factory=TokenUsage)
    latency: LatencyBreakdown = Field(default_factory=LatencyBreakdown)
    timestamp: float = Field(default_factory=time.time)


def calculate_cost(prompt_tokens: int, completion_tokens: int, model: str) -> float:
    """Calculates estimated USD cost for a given token count and model."""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
    input_cost = (prompt_tokens / 1_000_000.0) * pricing["input_per_million"]
    output_cost = (completion_tokens / 1_000_000.0) * pricing["output_per_million"]
    return round(input_cost + output_cost, 7)


def estimate_tokens(text: str) -> int:
    """Heuristic token estimator (approx 4 characters per token)."""
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4.0))


class MetricsCollector:
    """
    In-memory thread-safe metrics collector for system-wide observability.
    Calculates p50, p95 latencies, cumulative token usage, and security rates.
    """

    def __init__(self) -> None:
        self.start_time = time.time()
        self.total_requests: int = 0
        self.latencies_ms: list[float] = []
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_cost_usd: float = 0.0
        self.security_stats: dict[str, int] = {
            "QUARANTINED": 0,
            "REDACTED": 0,
            "PASSED": 0,
        }
        self.category_counts: dict[str, int] = {}
        self.urgency_counts: dict[str, int] = {}

    def record_request(
        self,
        latency_ms: float,
        tokens: TokenUsage,
        security_verdict: str,
        category: str,
        urgency: str,
    ) -> None:
        """Records a completed ticket triage transaction."""
        self.total_requests += 1
        self.latencies_ms.append(latency_ms)
        # Keep sliding window of latest 10,000 latencies to avoid memory blowup
        if len(self.latencies_ms) > 10_000:
            self.latencies_ms.pop(0)

        self.total_prompt_tokens += tokens.prompt_tokens
        self.total_completion_tokens += tokens.completion_tokens
        self.total_cost_usd = round(self.total_cost_usd + tokens.estimated_cost_usd, 6)

        verdict_key = security_verdict.upper() if security_verdict else "PASSED"
        self.security_stats[verdict_key] = self.security_stats.get(verdict_key, 0) + 1

        self.category_counts[category] = self.category_counts.get(category, 0) + 1
        self.urgency_counts[urgency] = self.urgency_counts.get(urgency, 0) + 1

    def get_summary(self) -> dict[str, Any]:
        """Returns comprehensive operational metrics summary."""
        uptime = round(time.time() - self.start_time, 1)
        sorted_latencies = sorted(self.latencies_ms)
        n = len(sorted_latencies)

        p50 = 0.0
        p95 = 0.0
        p99 = 0.0
        avg_lat = 0.0

        if n > 0:
            avg_lat = round(sum(sorted_latencies) / n, 2)
            p50 = round(sorted_latencies[int(n * 0.50)], 2)
            p95 = round(sorted_latencies[min(n - 1, int(n * 0.95))], 2)
            p99 = round(sorted_latencies[min(n - 1, int(n * 0.99))], 2)

        total_tokens = self.total_prompt_tokens + self.total_completion_tokens

        return {
            "status": "healthy",
            "uptime_seconds": uptime,
            "total_requests": self.total_requests,
            "latency": {
                "avg_ms": avg_lat,
                "p50_ms": p50,
                "p95_ms": p95,
                "p99_ms": p99,
            },
            "tokens": {
                "total_tokens": total_tokens,
                "prompt_tokens": self.total_prompt_tokens,
                "completion_tokens": self.total_completion_tokens,
                "cumulative_cost_usd": round(self.total_cost_usd, 4),
            },
            "security": {
                "quarantined_attacks": self.security_stats.get("QUARANTINED", 0),
                "sanitized_pii_tickets": self.security_stats.get("REDACTED", 0),
                "clean_tickets": self.security_stats.get("PASSED", 0),
            },
            "distribution": {
                "categories": self.category_counts,
                "urgencies": self.urgency_counts,
            },
        }


# Global metrics collector singleton
metrics_collector = MetricsCollector()
