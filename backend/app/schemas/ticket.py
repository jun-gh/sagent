from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class Citation(BaseModel):
    document_title: str
    category: str
    content_snippet: str
    score: float
    source_url: Optional[str] = None


class AgentStep(BaseModel):
    agent_name: str
    action: str
    thought: str
    duration_ms: float
    details: Optional[Any] = None


class TicketCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255, description="Short summary of the issue")
    description: str = Field(..., min_length=10, description="Full details of the customer issue")
    customer_email: Optional[str] = Field(default=None, description="Customer contact email")
    customer_tier: str = Field(default="standard", description="standard, premium, enterprise")


class TicketTriageRequest(TicketCreate):
    simulate_rate_limit: Optional[bool] = Field(
        default=False,
        description="Flag for end-to-end testing of 429 rate limit backoff and UI banner"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Anonymous session ID for history isolation"
    )


class TicketRead(BaseModel):
    id: str
    session_id: Optional[str] = None
    title: str
    description: str
    customer_email: Optional[str]
    customer_tier: str
    status: str
    urgency: str
    category: str
    sentiment: Optional[str]
    confidence_score: Optional[str]
    suggested_reply: Optional[str]
    internal_action_plan: Optional[List[str]]
    tags: Optional[List[str]]
    triage_notes: Optional[str]
    grounding_citations: Optional[List[Citation]] = None
    agent_steps: Optional[List[AgentStep]] = None
    security_verdict: Optional[str] = "PASSED"
    pii_redacted_count: Optional[int] = 0
    injection_risk_score: Optional[float] = 0.0
    security_details: Optional[Any] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TicketTriageResponse(BaseModel):
    ticket_id: str
    session_id: Optional[str] = None
    title: str
    description: str
    customer_tier: str
    status: str
    urgency: str
    category: str
    sentiment: str
    confidence_score: float
    suggested_reply: str
    internal_action_plan: List[str]
    tags: List[str]
    triage_notes: str
    grounding_citations: List[Citation]
    agent_steps: List[AgentStep]
    model_used: str
    total_latency_ms: float
    security_verdict: str = "PASSED"
    pii_redacted_count: int = 0
    injection_risk_score: float = 0.0
    security_details: Optional[Any] = None
    telemetry: Optional[Dict[str, Any]] = None

