from typing import Any, Dict
from fastapi import APIRouter
from app.services.ai.token_tracker import metrics_collector

router = APIRouter(prefix="/metrics", tags=["Operations & Observability"])


@router.get("", response_model=Dict[str, Any])
async def get_system_metrics() -> Dict[str, Any]:
    """
    Returns real-time operational and telemetry metrics:
    - Uptime & total request counters
    - Latency distribution (average, p50, p95, p99)
    - Cumulative token consumption & estimated USD cost
    - Security guardrail stats (quarantines, PII sanitization)
    - Category & Urgency distribution
    """
    return metrics_collector.get_summary()
