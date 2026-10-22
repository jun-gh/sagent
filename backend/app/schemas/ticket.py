from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Citation(BaseModel):
    document_title: str
    category: str
    content_snippet: str
    score: float
    source_url: str | None = None


class AgentStep(BaseModel):
    agent_name: str
    action: str
    thought: str
    duration_ms: float
    details: Any | None = None


class TicketCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255, description="Short summary of the issue")
    description: str = Field(..., min_length=10, description="Full details of the customer issue")
    customer_email: str | None = Field(default=None, description="Customer contact email")
    customer_tier: str = Field(default="standard", description="standard, premium, enterprise")


class TicketTriageRequest(TicketCreate):
    simulate_rate_limit: bool | None = Field(
        default=False,
        description="Flag for end-to-end testing of 429 rate limit backoff and UI banner"
    )
    session_id: str | None = Field(
        default=None,
        description="Anonymous session ID for history isolation"
    )


class TicketRead(BaseModel):
    id: str
    session_id: str | None = None
    title: str
    description: str
    customer_email: str | None
    customer_tier: str
    status: str
    urgency: str
    category: str
    sentiment: str | None
    confidence_score: str | None
    suggested_reply: str | None
    internal_action_plan: list[str] | None
    tags: list[str] | None
    triage_notes: str | None
    grounding_citations: list[Citation] | None = None
    agent_steps: list[AgentStep] | None = None
    security_verdict: str | None = "PASSED"
    pii_redacted_count: int | None = 0
    injection_risk_score: float | None = 0.0
    security_details: Any | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TicketTriageResponse(BaseModel):
    ticket_id: str
    session_id: str | None = None
    title: str
    description: str
    customer_tier: str
    status: str
    urgency: str
    category: str
    sentiment: str
    confidence_score: float
    suggested_reply: str
    internal_action_plan: list[str]
    tags: list[str]
    triage_notes: str
    grounding_citations: list[Citation]
    agent_steps: list[AgentStep]
    model_used: str
    total_latency_ms: float
    security_verdict: str = "PASSED"
    pii_redacted_count: int = 0
    injection_risk_score: float = 0.0
    security_details: Any | None = None
    telemetry: dict[str, Any] | None = None

