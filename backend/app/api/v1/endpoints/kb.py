import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.core.database import get_db_session
from app.models.knowledge import ContextChunk
from app.schemas.knowledge import (
    HybridSearchQuery,
    HybridSearchResult,
    KnowledgeChunkCreate,
    KnowledgeChunkRead,
)
from app.services.rag.hybrid_search import HybridSearchService
from app.services.ai.gemini_client import GeminiClient

logger = logging.getLogger("sagent.kb")
router = APIRouter()


@router.get(
    "/kb",
    response_model=List[KnowledgeChunkRead],
    summary="List all knowledge runbooks in the database",
)
async def list_knowledge_chunks(
    category: Optional[str] = None,
    session: AsyncSession = Depends(get_db_session),
):
    """Retrieves all indexed runbooks currently stored in the knowledge base."""
    try:
        stmt = select(ContextChunk).order_by(ContextChunk.created_at.desc())
        if category:
            stmt = stmt.where(ContextChunk.category == category.upper())
        result = await session.execute(stmt)
        chunks = result.scalars().all()
        return chunks
    except Exception as e:
        logger.warning("Failed to fetch knowledge chunks: %s", e)
        return []


@router.post(
    "/kb",
    response_model=KnowledgeChunkRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a new custom knowledge runbook with embeddings",
)
async def create_knowledge_chunk(
    chunk_in: KnowledgeChunkCreate,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Creates a new knowledge runbook, computes its 768-dim dense embedding
    via Gemini text-embedding-004, and persists it for instant Hybrid RAG search.
    """
    gemini_client = GeminiClient()
    embedding = None
    try:
        embedding = await gemini_client.get_embedding(chunk_in.content)
    except Exception as err:
        logger.warning("Could not compute embedding for custom runbook: %s", err)

    chunk = ContextChunk(
        document_title=chunk_in.document_title.strip(),
        category=chunk_in.category.strip().upper(),
        content=chunk_in.content.strip(),
        source_url=chunk_in.source_url.strip() if chunk_in.source_url else None,
        chunk_index=chunk_in.chunk_index or "0",
        metadata_json=chunk_in.metadata_json,
        embedding=embedding,
    )
    session.add(chunk)
    await session.commit()
    await session.refresh(chunk)
    logger.info("Successfully added runbook '%s' to knowledge base.", chunk.document_title)
    return chunk


@router.delete(
    "/kb/{chunk_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a knowledge runbook by ID",
)
async def delete_knowledge_chunk(
    chunk_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Deletes an indexed runbook from the database."""
    stmt = select(ContextChunk).where(ContextChunk.id == chunk_id)
    result = await session.execute(stmt)
    chunk = result.scalar_one_or_none()
    if not chunk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Runbook {chunk_id} not found",
        )
    title = chunk.document_title
    await session.delete(chunk)
    await session.commit()
    logger.info("Deleted runbook '%s' (ID: %s).", title, chunk_id)
    return {"status": "success", "deleted_id": chunk_id, "document_title": title}


@router.post(
    "/kb/search",
    response_model=List[HybridSearchResult],
    summary="Direct test endpoint for Hybrid RAG search",
)
async def search_kb(
    query: HybridSearchQuery,
    session: AsyncSession = Depends(get_db_session),
):
    """
    Directly tests the hybrid search algorithm (pgvector + tsvector BM25 with RRF).
    """
    service = HybridSearchService()
    results = await service.search(
        session=session,
        query_text=query.query,
        category=query.category,
        top_k=query.top_k,
        dense_weight=query.dense_weight,
        keyword_weight=query.keyword_weight,
    )
    return results


@router.post(
    "/kb/seed",
    status_code=status.HTTP_201_CREATED,
    summary="Seed default enterprise knowledge runbooks into database",
)
async def seed_knowledge_base(
    session: AsyncSession = Depends(get_db_session),
):
    """
    Seeds initial enterprise IT and technical support runbooks with dense embeddings
    and tsvector search tokens.
    """
    gemini_client = GeminiClient()

    seed_articles = [
        {
            "title": "Enterprise SAML SSO & Identity Provider Rollover",
            "category": "AUTH",
            "source_url": "https://support.okta.com/help/s/article/How-to-configure-SAML-2-0-for-an-application",
            "content": (
                "When SAML 2.0 logins fail with 'Invalid SAML Response' or 'Signature Verification Failed', "
                "the issue is almost always an expired X.509 signing certificate from the IdP (Okta, Azure AD, Ping). "
                "Steps to resolve: 1) Admin downloads new X.509 cert from IdP. 2) Upload PEM into Sagent SSO Settings. "
                "3) Verify ACS URL matches https://app.sagent.io/saml/acs. 4) Ensure SHA-256 signing is enforced."
            ),
        },
        {
            "title": "Stripe Webhook Duplication & Duplicate Invoice Reconciliation",
            "category": "BILLING",
            "source_url": "https://docs.stripe.com/refunds",
            "content": (
                "Duplicate charges typically stem from Stripe retry webhooks when the primary endpoint responds > 5000ms. "
                "Policy: All duplicate transactions within 24 hours on identical idempotency keys are eligible for immediate "
                "one-click automated refund. Sagent will emit an internal credit memo and trigger Stripe API refund within 60s."
            ),
        },
        {
            "title": "PostgreSQL Concurrency Deadlock & Lock Contention Runbook",
            "category": "TECHNICAL",
            "source_url": "https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-DEADLOCKS",
            "content": (
                "PostgreSQL Error 40P01 indicates deadlock detected between concurrent transactions. "
                "Immediate Triage: 1) Query pg_stat_activity for queries in 'active' state with wait_event_type = 'Lock'. "
                "2) Issue pg_cancel_backend(pid) or pg_terminate_backend(pid) on blocking session. "
                "3) Check recent schema migrations for unindexed foreign keys causing share-row locks."
            ),
        },
        {
            "title": "API Rate Limiting, HTTP 429 & Quota Expansion Protocol",
            "category": "TECHNICAL",
            "source_url": "https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/429",
            "content": (
                "When clients receive HTTP 429 Too Many Requests, evaluate current tier caps. "
                "Standard tier: 60 RPM. Enterprise tier: 1000 RPM. If an Enterprise customer breaches rate limits "
                "during a production migration, the On-Call Engineer can issue a 48-hour temporary quota override "
                "via the Admin Console."
            ),
        },
        {
            "title": "Organization RBAC Privileges & Member Invitation Failures",
            "category": "AUTH",
            "source_url": "https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories",
            "content": (
                "If an invited team member receives 'Unauthorized 403' upon accepting an email invite, "
                "verify if domain restriction is enabled for the workspace. Workspaces configured with strict "
                "domain whitelist (e.g. @company.com) will reject invitations sent to personal email providers."
            ),
        },
    ]

    inserted_count = 0
    try:
        for item in seed_articles:
            # Check if exists
            stmt = select(ContextChunk).where(ContextChunk.document_title == item["title"])
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing:
                continue

            embedding = await gemini_client.get_embedding(item["content"])

            chunk = ContextChunk(
                document_title=item["title"],
                category=item["category"],
                content=item["content"],
                source_url=item["source_url"],
                embedding=embedding,
            )
            session.add(chunk)
            inserted_count += 1

        await session.commit()
        return {"status": "success", "seeded_chunks": inserted_count, "total_runbooks": len(seed_articles)}
    except Exception as e:
        return {"status": "fallback_ready", "error": str(e), "message": "Pre-packaged runbooks will be served via in-memory provider."}
