from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from app.core.config import get_settings
from app.core.database import get_db_session
from app.core.errors import SessionLimitReachedException
from app.core.security import verify_rate_limit, verify_api_key
from app.models.ticket import Ticket
from app.models.audit import AuditLog
from app.schemas.ticket import (
    TicketTriageRequest,
    TicketTriageResponse,
    TicketRead,
)
from app.services.agents.orchestrator import TriageOrchestrator

router = APIRouter()


async def cleanup_expired_tickets(session: AsyncSession, expiry_days: int) -> None:
    """Safely purge expired tickets and associated audit logs past the retention window."""
    try:
        cutoff = datetime.utcnow() - timedelta(days=expiry_days)
        subq = select(Ticket.id).where(Ticket.created_at < cutoff)
        await session.execute(delete(AuditLog).where(AuditLog.ticket_id.in_(subq)))
        await session.execute(delete(Ticket).where(Ticket.created_at < cutoff))
        await session.flush()
    except Exception:
        # Ignore cleanup errors if tables are not initialized or in fallback mode
        pass


@router.post(
    "/tickets/triage",
    response_model=TicketTriageResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest and autonomous triage of a support ticket",
    dependencies=[Depends(verify_rate_limit), Depends(verify_api_key)],
)
async def triage_ticket(
    request: TicketTriageRequest,
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Ingests an incoming support ticket, checks session quota, cleans expired tickets,
    runs classification via TriageAgent, retrieves grounding knowledge via Hybrid RAG,
    and synthesizes a solution.
    """
    settings = get_settings()

    # Automatically purge expired tickets
    await cleanup_expired_tickets(session, settings.SESSION_EXPIRY_DAYS)

    # Resolve session ID from request body or header
    active_session_id = request.session_id or x_session_id
    if active_session_id:
        request.session_id = active_session_id

        # Enforce MAX_TICKET_PER_SESSION quota
        try:
            count_stmt = select(func.count(Ticket.id)).where(Ticket.session_id == active_session_id)
            count_res = await session.execute(count_stmt)
            session_ticket_count = count_res.scalar() or 0
            if session_ticket_count >= settings.MAX_TICKET_PER_SESSION:
                raise SessionLimitReachedException(
                    max_tickets=settings.MAX_TICKET_PER_SESSION,
                    message=f"Session ticket limit reached ({settings.MAX_TICKET_PER_SESSION} tickets). Please start a new session.",
                )
        except SessionLimitReachedException:
            raise
        except Exception:
            # If DB count fails (e.g. initial connection), proceed gracefully
            pass

    orchestrator = TriageOrchestrator()
    response = await orchestrator.execute_triage(request, session=session)
    return response


@router.get(
    "/tickets",
    response_model=List[TicketRead],
    summary="List all triaged tickets for the current session",
)
async def list_tickets(
    limit: int = 50,
    offset: int = 0,
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    session: AsyncSession = Depends(get_db_session),
):
    """Retrieves session-isolated historical tickets sorted by recent creation."""
    settings = get_settings()
    # Cleanup expired tickets first
    await cleanup_expired_tickets(session, settings.SESSION_EXPIRY_DAYS)

    if not x_session_id:
        return []

    try:
        effective_limit = min(limit, settings.MAX_TICKET_PER_SESSION)
        stmt = (
            select(Ticket)
            .where(Ticket.session_id == x_session_id)
            .order_by(Ticket.created_at.desc())
            .limit(effective_limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        tickets = result.scalars().all()
        return tickets
    except Exception:
        # If DB is not connected yet, return empty list gracefully
        return []


@router.get(
    "/tickets/{ticket_id}",
    response_model=TicketRead,
    summary="Retrieve ticket by ID",
)
async def get_ticket(
    ticket_id: str,
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    session: AsyncSession = Depends(get_db_session),
):
    stmt = select(Ticket).where(Ticket.id == ticket_id)
    result = await session.execute(stmt)
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )
    if x_session_id and ticket.session_id and ticket.session_id != x_session_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found in this session",
        )
    return ticket
