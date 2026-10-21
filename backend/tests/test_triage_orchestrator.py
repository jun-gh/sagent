import pytest
from app.schemas.ticket import TicketTriageRequest
from app.services.agents.orchestrator import TriageOrchestrator
from app.core.errors import RateLimitExceededException


@pytest.mark.asyncio
async def test_triage_orchestration_flow():
    orchestrator = TriageOrchestrator()
    request = TicketTriageRequest(
        title="SAML SSO login failing with invalid signature",
        description="Our entire enterprise team is unable to sign in via Okta. Error code: Invalid Signature.",
        customer_tier="enterprise",
        customer_email="admin@acme.corp",
    )

    response = await orchestrator.execute_triage(request, session=None)
    assert response.ticket_id is not None
    assert response.urgency in ["HIGH", "CRITICAL", "MEDIUM", "LOW"]
    assert response.category in ["AUTH", "TECHNICAL", "BILLING", "FEATURE_REQUEST", "SECURITY", "GENERAL"]
    assert len(response.grounding_citations) > 0
    assert len(response.internal_action_plan) > 0
    assert len(response.suggested_reply) > 20
    assert len(response.agent_steps) == 3
    assert response.confidence_score > 0.0


@pytest.mark.asyncio
async def test_simulate_rate_limit_flag():
    orchestrator = TriageOrchestrator()
    request = TicketTriageRequest(
        title="Simulated error test",
        description="Trigger quota exceeded check.",
        simulate_rate_limit=True,
    )

    with pytest.raises(RateLimitExceededException) as exc_info:
        await orchestrator.execute_triage(request, session=None)

    assert exc_info.value.code == "RATE_LIMIT_EXCEEDED"
    assert exc_info.value.retries_attempted == 3
