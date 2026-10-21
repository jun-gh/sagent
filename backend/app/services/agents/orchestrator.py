import time
import uuid
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import RateLimitExceededException
from app.models.ticket import Ticket, TicketStatus, TicketUrgency, TicketCategory
from app.models.audit import AuditLog
from app.schemas.ticket import (
    TicketTriageRequest,
    TicketTriageResponse,
    AgentStep,
)
from app.services.ai.gemini_client import GeminiClient
from app.services.rag.hybrid_search import HybridSearchService
from app.services.agents.triage_agent import TriageAgent
from app.services.agents.researcher_agent import ResearcherAgent
from app.services.agents.resolution_agent import ResolutionAgent
from app.services.security import (
    PIIScrubber,
    InjectionGuard,
    OutputGuard,
    SecurityVerdict,
)

logger = logging.getLogger("sagent.orchestrator")


class TriageOrchestrator:
    """
    Primary Multi-Agent Orchestrator with integrated Phase 2 Security Guardrails.
    Directs the triage lifecycle across Security, Triage, Researcher, and Resolution agents.
    """

    def __init__(
        self,
        gemini_client: Optional[GeminiClient] = None,
        hybrid_search: Optional[HybridSearchService] = None,
        pii_scrubber: Optional[PIIScrubber] = None,
        injection_guard: Optional[InjectionGuard] = None,
        output_guard: Optional[OutputGuard] = None,
    ):
        self.settings = get_settings()
        self.gemini_client = gemini_client or GeminiClient()
        self.hybrid_search = hybrid_search or HybridSearchService(self.gemini_client)
        
        self.triage_agent = TriageAgent(self.gemini_client)
        self.researcher_agent = ResearcherAgent(self.hybrid_search)
        self.resolution_agent = ResolutionAgent(self.gemini_client)

        # Security Guardrails
        self.pii_scrubber = pii_scrubber or PIIScrubber()
        self.injection_guard = injection_guard or InjectionGuard()
        self.output_guard = output_guard or OutputGuard()

    async def execute_triage(
        self,
        request: TicketTriageRequest,
        session: Optional[AsyncSession] = None,
    ) -> TicketTriageResponse:
        """
        Executes end-to-end multi-agent triage pipeline with Phase 2 Security Guardrails.
        """
        # Testing hook for rate limit simulation
        if request.simulate_rate_limit:
            logger.warning("Simulated rate limit requested by caller.")
            raise RateLimitExceededException(
                message="Gemini API quota exhausted. Please try again in 30 seconds.",
                retries_attempted=3,
                details={"reason": "Simulated rate limit triggered for verification."},
            )

        start_total = time.perf_counter()
        agent_steps: List[AgentStep] = []
        ticket_id = str(uuid.uuid4())

        # =========================================================================
        # Security Guardrail 1: PII & Secret Scrubbing
        # =========================================================================
        scrub_title = self.pii_scrubber.scrub(request.title)
        scrub_desc = self.pii_scrubber.scrub(request.description)
        pii_count = scrub_title.redactions_count + scrub_desc.redactions_count
        entities_found = sorted(list(set(scrub_title.entities_found + scrub_desc.entities_found)))

        if pii_count > 0:
            agent_steps.append(
                AgentStep(
                    agent_name="PIIScrubber",
                    action="Redact Sensitive Data & Credentials",
                    thought=f"Detected and redacted {pii_count} sensitive item(s) ({', '.join(entities_found)}) before model inference or storage.",
                    duration_ms=0.5,
                    details={"redacted_count": pii_count, "entities": entities_found},
                )
            )

        # =========================================================================
        # Security Guardrail 2: Prompt Injection & Adversarial Pattern Defense
        # =========================================================================
        combined_text = f"{scrub_title.sanitized_text}\n{scrub_desc.sanitized_text}"
        injection_eval = self.injection_guard.evaluate(combined_text)

        if injection_eval.injection_detected:
            logger.warning(
                "Prompt injection intercepted for ticket '%s' (risk: %.2f, reasons: %s)",
                request.title,
                injection_eval.risk_score,
                injection_eval.injection_reasons,
            )
            agent_steps.append(
                AgentStep(
                    agent_name="InjectionGuard",
                    action="Intercept Prompt Injection Attack",
                    thought=f"Adversarial prompt injection pattern detected ({', '.join(injection_eval.injection_reasons)}). Input safely quarantined.",
                    duration_ms=0.5,
                    details={
                        "risk_score": injection_eval.risk_score,
                        "reasons": injection_eval.injection_reasons,
                    },
                )
            )

            safe_reply = (
                "Our automated security guardrails detected potentially restricted or adversarial instructions "
                "in this ticket submission. For compliance and platform security, this ticket has been quarantined "
                "and routed to our Security Operations team for manual review."
            )
            safe_action_plan = [
                "Step 1: Security Operations review of quarantined adversarial prompt payload.",
                "Step 2: Inspect client IP and account activity for malicious activity or credential stuffing.",
                "Step 3: Manually review ticket intent and communicate securely with client if legitimate.",
            ]
            total_latency_ms = round((time.perf_counter() - start_total) * 1000, 2)

            # Persist quarantined ticket to database
            if session:
                try:
                    async with session.begin_nested():
                        ticket_record = Ticket(
                            id=ticket_id,
                            title=scrub_title.sanitized_text,
                            description=scrub_desc.sanitized_text,
                            customer_email=request.customer_email,
                            customer_tier=request.customer_tier,
                            session_id=request.session_id,
                            status=TicketStatus.ESCALATED,
                            urgency=TicketUrgency.HIGH,
                            category=TicketCategory.SECURITY,
                            sentiment="Adversarial / Flagged",
                            confidence_score="0.0",
                            suggested_reply=safe_reply,
                            internal_action_plan=safe_action_plan,
                            tags=["security", "prompt-injection", "quarantined"],
                            triage_notes=f"Quarantined by InjectionGuard (risk: {injection_eval.risk_score:.2f}, patterns: {injection_eval.injection_reasons})",
                            grounding_citations=[],
                            agent_steps=[s.model_dump() for s in agent_steps],
                        )
                        session.add(ticket_record)
                        await session.flush()

                        audit_record = AuditLog(
                            ticket_id=ticket_record.id,
                            action="SECURITY_QUARANTINE",
                            agent_name="InjectionGuard",
                            model_used="rule-engine",
                            latency_ms=0.5,
                            details_json={
                                "risk_score": injection_eval.risk_score,
                                "reasons": injection_eval.injection_reasons,
                            },
                        )
                        session.add(audit_record)
                        await session.flush()
                except Exception as db_err:
                    logger.warning("Could not persist quarantined ticket: %s", db_err)

            return TicketTriageResponse(
                ticket_id=ticket_id,
                session_id=request.session_id,
                title=scrub_title.sanitized_text,
                description=scrub_desc.sanitized_text,
                customer_tier=request.customer_tier,
                status=TicketStatus.ESCALATED.value,
                urgency=TicketUrgency.HIGH.value,
                category=TicketCategory.SECURITY.value,
                sentiment="Adversarial / Flagged",
                confidence_score=0.0,
                suggested_reply=safe_reply,
                internal_action_plan=safe_action_plan,
                tags=["security", "prompt-injection", "quarantined"],
                triage_notes=f"Quarantined by InjectionGuard (risk: {injection_eval.risk_score:.2f})",
                grounding_citations=[],
                agent_steps=agent_steps,
                model_used=self.gemini_client.model,
                total_latency_ms=total_latency_ms,
                security_verdict=SecurityVerdict.QUARANTINED.value,
                pii_redacted_count=pii_count,
                injection_risk_score=injection_eval.risk_score,
                security_details={"quarantined": True, "reasons": injection_eval.injection_reasons},
            )

        # =========================================================================
        # Step 1: Triage Classification Agent (Runs on Sanitized Input)
        # =========================================================================
        logger.info("Executing TriageAgent for ticket '%s'...", scrub_title.sanitized_text)
        classification = await self.triage_agent.classify(
            title=scrub_title.sanitized_text,
            description=scrub_desc.sanitized_text,
            customer_tier=request.customer_tier,
        )
        agent_steps.append(
            AgentStep(
                agent_name="TriageAgent",
                action="Classify Intent & Urgency",
                thought=f"Assessed category as {classification['category']} with {classification['urgency']} urgency. Sentiment: {classification['sentiment']}. Formulated search terms: {classification['search_queries']}.",
                duration_ms=classification["duration_ms"],
                details=classification,
            )
        )

        # =========================================================================
        # Step 2: Knowledge Researcher Agent (Hybrid RAG on Sanitized Queries)
        # =========================================================================
        logger.info("Executing ResearcherAgent with queries: %s...", classification["search_queries"])
        research = await self.researcher_agent.retrieve_grounding(
            session=session,
            search_queries=classification["search_queries"],
            category=classification["category"],
            top_k=4,
        )
        agent_steps.append(
            AgentStep(
                agent_name="ResearcherAgent",
                action="Hybrid RAG Grounding Search",
                thought=research["thought"],
                duration_ms=research["duration_ms"],
                details={"citations_found": len(research["citations"])},
            )
        )

        # =========================================================================
        # Step 3: Resolution & Synthesis Agent
        # =========================================================================
        logger.info("Executing ResolutionAgent...")
        resolution = await self.resolution_agent.synthesize(
            title=scrub_title.sanitized_text,
            description=scrub_desc.sanitized_text,
            customer_tier=request.customer_tier,
            category=classification["category"],
            urgency=classification["urgency"],
            grounding_chunks=research["raw_chunks"],
        )
        agent_steps.append(
            AgentStep(
                agent_name="ResolutionAgent",
                action="Synthesize Customer Response & Internal Checklist",
                thought=resolution["thought"],
                duration_ms=resolution["duration_ms"],
                details={"confidence": resolution["confidence_score"]},
            )
        )

        # =========================================================================
        # Security Guardrail 3: Output Policy Shield & Leakage Guard
        # =========================================================================
        safe_reply, safe_plan, policy_violation, violation_reasons = self.output_guard.sanitize_output(
            customer_reply=resolution["suggested_reply"],
            internal_action_plan=resolution["internal_action_plan"],
            token_map=scrub_desc.token_map,
        )
        if policy_violation:
            agent_steps.append(
                AgentStep(
                    agent_name="OutputGuard",
                    action="Enforce Output Safety & Policy Bounds",
                    thought=f"Sanitized output for policy compliance: {', '.join(violation_reasons)}.",
                    duration_ms=0.3,
                    details={"reasons": violation_reasons},
                )
            )

        total_latency_ms = round((time.perf_counter() - start_total) * 1000, 2)

        # Determine overall security verdict
        security_verdict = SecurityVerdict.PASSED.value
        if pii_count > 0:
            security_verdict = SecurityVerdict.REDACTED.value

        # Map string urgency/category safely to Enums
        try:
            urgency_enum = TicketUrgency(classification["urgency"].upper())
        except ValueError:
            urgency_enum = TicketUrgency.MEDIUM

        try:
            category_enum = TicketCategory(classification["category"].upper())
        except ValueError:
            category_enum = TicketCategory.TECHNICAL

        # Persist to database if session is available
        if session:
            try:
                async with session.begin_nested():
                    ticket_record = Ticket(
                        id=ticket_id,
                        title=scrub_title.sanitized_text,
                        description=scrub_desc.sanitized_text,
                        customer_email=request.customer_email,
                        customer_tier=request.customer_tier,
                        session_id=request.session_id,
                        status=TicketStatus.TRIAGED,
                        urgency=urgency_enum,
                        category=category_enum,
                        sentiment=classification["sentiment"],
                        confidence_score=str(resolution["confidence_score"]),
                        suggested_reply=safe_reply,
                        internal_action_plan=safe_plan,
                        tags=resolution["tags"],
                        triage_notes=resolution["triage_notes"],
                        grounding_citations=[c.model_dump() for c in research["citations"]],
                        agent_steps=[s.model_dump() for s in agent_steps],
                    )
                    session.add(ticket_record)
                    await session.flush()

                    # Add Audit Log referencing the persisted ticket
                    audit_record = AuditLog(
                        ticket_id=ticket_record.id,
                        action="TRIAGE_COMPLETED",
                        agent_name="TriageOrchestrator",
                        model_used=self.gemini_client.model,
                        latency_ms=total_latency_ms,
                        details_json={
                            "urgency": urgency_enum.value,
                            "category": category_enum.value,
                            "citations_count": len(research["citations"]),
                            "security_verdict": security_verdict,
                            "pii_redacted_count": pii_count,
                            "entities_found": entities_found,
                        },
                    )
                    session.add(audit_record)
                    await session.flush()
                logger.info("Persisted sanitized ticket %s and audit record to database.", ticket_id)
            except Exception as db_err:
                logger.warning("Database persistence skipped or failed: %s", db_err)

        return TicketTriageResponse(
            ticket_id=ticket_id,
            session_id=request.session_id,
            title=scrub_title.sanitized_text,
            description=scrub_desc.sanitized_text,
            customer_tier=request.customer_tier,
            status=TicketStatus.TRIAGED.value,
            urgency=urgency_enum.value,
            category=category_enum.value,
            sentiment=classification["sentiment"],
            confidence_score=resolution["confidence_score"],
            suggested_reply=safe_reply,
            internal_action_plan=safe_plan,
            tags=resolution["tags"],
            triage_notes=resolution["triage_notes"],
            grounding_citations=research["citations"],
            agent_steps=agent_steps,
            model_used=self.gemini_client.model,
            total_latency_ms=total_latency_ms,
            security_verdict=security_verdict,
            pii_redacted_count=pii_count,
            injection_risk_score=injection_eval.risk_score,
            security_details={
                "pii_redacted": pii_count > 0,
                "entities_found": entities_found,
                "quarantined": False,
            },
        )
