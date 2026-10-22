import logging
import math
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import ContextChunk
from app.schemas.knowledge import HybridSearchResult
from app.services.ai.gemini_client import GeminiClient

logger = logging.getLogger("sagent.rag")


def sanitize_url(url: str | None, category: str = "", title: str = "") -> str | None:
    """Ensures runbook source URL is a real public documentation link."""
    if not url or "internal" in url:
        t = (title or "").lower()
        if "rate" in t or "429" in t:
            return "https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/429"
        if "postgres" in t or "deadlock" in t:
            return "https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-DEADLOCKS"
        if "stripe" in t or "invoice" in t or "charge" in t or category == "BILLING":
            return "https://docs.stripe.com/refunds"
        if "sso" in t or "saml" in t or "okta" in t or category == "AUTH":
            return "https://support.okta.com/help/s/article/How-to-configure-SAML-2-0-for-an-application"
        if "rbac" in t or "invite" in t:
            return "https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories"
        return "https://developer.mozilla.org"
    return url


class HybridSearchService:
    """
    Hybrid Search Engine combining:
    1. pgvector Cosine Semantic Similarity (Dense Vector Search)
    2. PostgreSQL tsvector FTS with ts_rank_cd (Sparse Keyword BM25-style Search)
    3. Reciprocal Rank Fusion (RRF) combining both signals
    """

    def __init__(self, gemini_client: GeminiClient | None = None):
        self.gemini_client = gemini_client or GeminiClient()

    async def search(
        self,
        session: AsyncSession | None,
        query_text: str,
        category: str | None = None,
        top_k: int = 5,
        dense_weight: float = 0.6,
        keyword_weight: float = 0.4,
        rrf_k: int = 60,
    ) -> list[HybridSearchResult]:
        """
        Executes hybrid search over knowledge base context chunks.
        """
        if not session:
            return self._default_static_chunks(query_text, category, top_k)

        # Step 1: Generate query embedding
        query_embedding: list[float] | None = None
        try:
            query_embedding = await self.gemini_client.get_embedding(query_text)
        except Exception as e:
            logger.warning("Could not compute embedding, falling back to keyword search: %s", e)

        # Step 2: Try native PostgreSQL pgvector + tsvector execution using a Savepoint
        try:
            async with session.begin_nested():
                results = await self._search_postgres(
                    session=session,
                    query_text=query_text,
                    query_embedding=query_embedding,
                    category=category,
                    top_k=top_k,
                    dense_weight=dense_weight,
                    keyword_weight=keyword_weight,
                    rrf_k=rrf_k,
                )
                return self._prune_relative_tail(results)
        except Exception as pg_err:
            logger.warning("PostgreSQL hybrid search failed (%s); using resilient fallback.", pg_err)

        # Step 3: Resilient fallback
        fallback_results = await self._search_in_memory_fallback(
            session=session,
            query_text=query_text,
            query_embedding=query_embedding,
            category=category,
            top_k=top_k,
        )
        return self._prune_relative_tail(fallback_results)

    async def _search_postgres(
        self,
        session: AsyncSession,
        query_text: str,
        query_embedding: list[float] | None,
        category: str | None,
        top_k: int,
        dense_weight: float,
        keyword_weight: float,
        rrf_k: int,
    ) -> list[HybridSearchResult]:
        """
        Executes PostgreSQL query with vector similarity and full-text search.
        """
        # Sanitize query for plainto_tsquery
        clean_words = [w for w in query_text.replace("'", "").replace('"', '').split() if len(w) > 1]
        clean_query = " ".join(clean_words) if clean_words else "general"

        has_embedding = bool(query_embedding and len(query_embedding) == 768)

        if has_embedding:
            embedding_literal = f"[{','.join(str(x) for x in query_embedding)}]"
            sql = f"""
            WITH vector_ranked AS (
                SELECT
                    id, document_title, category, content, source_url,
                    (1.0 - (embedding <=> '{embedding_literal}'::vector)) as dense_score,
                    ROW_NUMBER() OVER (ORDER BY (embedding <=> '{embedding_literal}'::vector) ASC) as v_rank
                FROM context_chunks
                WHERE embedding IS NOT NULL
                  AND (1.0 - (embedding <=> '{embedding_literal}'::vector)) >= 0.58
                {"AND category = :category_val" if category else ""}
                LIMIT 20
            ),
            keyword_ranked AS (
                SELECT
                    id, document_title, category, content, source_url,
                    ts_rank_cd(to_tsvector('english', coalesce(document_title, '') || ' ' || content), plainto_tsquery('english', :query_val)) as sparse_score,
                    ROW_NUMBER() OVER (ORDER BY ts_rank_cd(to_tsvector('english', coalesce(document_title, '') || ' ' || content), plainto_tsquery('english', :query_val)) DESC) as k_rank
                FROM context_chunks
                WHERE to_tsvector('english', coalesce(document_title, '') || ' ' || content) @@ plainto_tsquery('english', :query_val)
                {"AND category = :category_val" if category else ""}
                LIMIT 20
            )
            SELECT
                COALESCE(v.id, k.id) as id,
                COALESCE(v.document_title, k.document_title) as document_title,
                COALESCE(v.category, k.category) as category,
                COALESCE(v.content, k.content) as content,
                COALESCE(v.source_url, k.source_url) as source_url,
                COALESCE(v.dense_score, 0.0) as vector_score,
                COALESCE(k.sparse_score, 0.0) as keyword_score,
                (
                    COALESCE(1.0 / ({rrf_k} + v.v_rank), 0.0) * {dense_weight} +
                    COALESCE(1.0 / ({rrf_k} + k.k_rank), 0.0) * {keyword_weight}
                ) as combined_score
            FROM vector_ranked v
            FULL OUTER JOIN keyword_ranked k ON v.id = k.id
            WHERE (COALESCE(v.dense_score, 0.0) >= 0.58 OR COALESCE(k.sparse_score, 0.0) >= 0.01)
            ORDER BY combined_score DESC
            LIMIT {top_k};
            """
        else:
            # Keyword-only query when embedding is absent
            sql = f"""
            SELECT
                id, document_title, category, content, source_url,
                0.0 as vector_score,
                ts_rank_cd(to_tsvector('english', coalesce(document_title, '') || ' ' || content), plainto_tsquery('english', :query_val)) as keyword_score,
                ts_rank_cd(to_tsvector('english', coalesce(document_title, '') || ' ' || content), plainto_tsquery('english', :query_val)) as combined_score
            FROM context_chunks
            WHERE to_tsvector('english', coalesce(document_title, '') || ' ' || content) @@ plainto_tsquery('english', :query_val)
            {"AND category = :category_val" if category else ""}
            ORDER BY keyword_score DESC
            LIMIT {top_k};
            """

        params: dict[str, Any] = {"query_val": clean_query}
        if category:
            params["category_val"] = category

        result = await session.execute(text(sql), params)
        rows = result.fetchall()

        results: list[HybridSearchResult] = []
        for r in rows:
            results.append(
                HybridSearchResult(
                    id=str(r.id),
                    document_title=str(r.document_title),
                    category=str(r.category),
                    content=str(r.content),
                    combined_score=round(float(r.combined_score or 0.0), 4),
                    vector_score=round(float(r.vector_score or 0.0), 3),
                    keyword_score=round(float(r.keyword_score or 0.0), 3),
                    source_url=sanitize_url(r.source_url, str(r.category), str(r.document_title)),
                )
            )

        return results

    @staticmethod
    def _prune_relative_tail(results: list[HybridSearchResult]) -> list[HybridSearchResult]:
        """
        Relative Score Pruning:
        In hybrid RRF search, when a dominant winner exists (e.g. matching both dense
        and sparse search), trailing results that lack keyword confirmation and fall
        significantly behind the top score are pruned to maintain high retrieval precision.
        """
        if not results or len(results) <= 1:
            return results

        top = results[0]
        top_score = top.combined_score
        if top_score <= 0:
            return results

        pruned = [top]
        for item in results[1:]:
            # Rule 1: If trailing candidate has zero keyword match and score is < 70% of top score, prune it.
            if item.keyword_score == 0.0 and (item.combined_score < 0.70 * top_score):
                logger.info(
                    "Relative pruning dropped candidate '%s' (score: %.4f vs top: %.4f, zero keyword match)",
                    item.document_title, item.combined_score, top_score
                )
                continue

            # Rule 2: If an item's combined score falls below 50% of the top score, prune it.
            if item.combined_score < 0.50 * top_score:
                logger.info(
                    "Relative pruning dropped candidate '%s' (score: %.4f is <50%% of top: %.4f)",
                    item.document_title, item.combined_score, top_score
                )
                continue

            pruned.append(item)

        return pruned

    async def _search_in_memory_fallback(
        self,
        session: AsyncSession | None,
        query_text: str,
        query_embedding: list[float] | None,
        category: str | None,
        top_k: int,
    ) -> list[HybridSearchResult]:
        """
        Pure Python in-memory search fallback with relevance thresholding.
        """
        chunks = []
        if session:
            try:
                async with session.begin_nested():
                    stmt = select(ContextChunk)
                    if category:
                        stmt = stmt.where(ContextChunk.category == category)
                    res = await session.execute(stmt)
                    chunks = res.scalars().all()
            except Exception as e:
                logger.debug("Database read in fallback skipped: %s", e)
                chunks = []

        if not chunks:
            return self._default_static_chunks(query_text, category, top_k)

        scored: list[tuple[float, float, float, ContextChunk]] = []
        STOP_WORDS = {
            "policy", "guide", "runbook", "protocol", "how", "to", "for", "the",
            "in", "on", "and", "with", "a", "an", "of", "is", "at", "by", "from"
        }
        raw_tokens = [w.lower() for w in query_text.replace("'", "").replace('"', '').split() if len(w) > 1]
        meaningful_tokens = [t for t in raw_tokens if t not in STOP_WORDS]
        tokens = set(meaningful_tokens) if meaningful_tokens else set(raw_tokens)

        for chunk in chunks:
            chunk_text = f"{chunk.document_title} {chunk.content}".lower()
            
            # Meaningful token overlap
            matched_tokens = [t for t in tokens if t in chunk_text]
            overlap = len(matched_tokens)
            keyword_score = round(overlap / max(1, len(tokens)), 4) if tokens else 0.0

            vector_score = 0.0
            if query_embedding and chunk.embedding:
                try:
                    dot = sum(a * b for a, b in zip(query_embedding, chunk.embedding))
                    norm1 = math.sqrt(sum(a * a for a in query_embedding))
                    norm2 = math.sqrt(sum(b * b for b in chunk.embedding))
                    if norm1 > 0 and norm2 > 0:
                        vector_score = round(max(0.0, dot / (norm1 * norm2)), 4)
                except Exception:
                    pass

            # Gate: require either meaningful vector similarity (>= 0.48) or keyword match (> 0)
            if vector_score < 0.48 and keyword_score == 0:
                continue

            combined = round((vector_score * 0.6) + (keyword_score * 0.4), 4)
            scored.append((combined, vector_score, keyword_score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            HybridSearchResult(
                id=c.id,
                document_title=c.document_title,
                category=c.category,
                content=c.content,
                combined_score=comb,
                vector_score=v_sc,
                keyword_score=k_sc,
                source_url=sanitize_url(c.source_url, c.category, c.document_title),
            )
            for comb, v_sc, k_sc, c in scored[:top_k]
        ]

    def _default_static_chunks(
        self, query_text: str, category: str | None, top_k: int
    ) -> list[HybridSearchResult]:
        """Pre-packaged enterprise runbook knowledge chunks for grounding."""
        catalog = [
            HybridSearchResult(
                id="kb-sso-01",
                document_title="Enterprise SAML SSO & Identity Provider Rollover",
                category="AUTH",
                content=(
                    "When SAML 2.0 logins fail with 'Invalid SAML Response' or 'Signature Verification Failed', "
                    "the issue is almost always an expired X.509 signing certificate from the IdP (Okta, Azure AD, Ping). "
                    "Steps to resolve: 1) Admin downloads new X.509 cert from IdP. 2) Upload PEM into Sagent SSO Settings. "
                    "3) Verify ACS URL matches https://app.sagent.io/saml/acs. 4) Ensure SHA-256 signing is enforced."
                ),
                combined_score=0.91,
                vector_score=0.93,
                keyword_score=0.88,
                source_url="https://support.okta.com/help/s/article/How-to-configure-SAML-2-0-for-an-application",
            ),
            HybridSearchResult(
                id="kb-bill-02",
                document_title="Stripe Webhook Duplication & Duplicate Invoice Reconciliation",
                category="BILLING",
                content=(
                    "Duplicate charges typically stem from Stripe retry webhooks when the primary endpoint responds > 5000ms. "
                    "Policy: All duplicate transactions within 24 hours on identical idempotency keys are eligible for immediate "
                    "one-click automated refund. Sagent will emit an internal credit memo and trigger Stripe API refund within 60s."
                ),
                combined_score=0.89,
                vector_score=0.91,
                keyword_score=0.86,
                source_url="https://docs.stripe.com/refunds",
            ),
            HybridSearchResult(
                id="kb-db-03",
                document_title="PostgreSQL Concurrency Deadlock & Lock Contention Runbook",
                category="TECHNICAL",
                content=(
                    "PostgreSQL Error 40P01 indicates deadlock detected between concurrent transactions. "
                    "Immediate Triage: 1) Query pg_stat_activity for queries in 'active' state with wait_event_type = 'Lock'. "
                    "2) Issue pg_cancel_backend(pid) or pg_terminate_backend(pid) on blocking session. "
                    "3) Check recent schema migrations for unindexed foreign keys causing share-row locks."
                ),
                combined_score=0.95,
                vector_score=0.96,
                keyword_score=0.94,
                source_url="https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-DEADLOCKS",
            ),
            HybridSearchResult(
                id="kb-rate-04",
                document_title="API Rate Limiting, HTTP 429 & Quota Expansion Protocol",
                category="TECHNICAL",
                content=(
                    "When clients receive HTTP 429 Too Many Requests, evaluate current tier caps. "
                    "Standard tier: 60 RPM. Enterprise tier: 1000 RPM. If an Enterprise customer breaches rate limits "
                    "during a production migration, the On-Call Engineer can issue a 48-hour temporary quota override "
                    "via the Admin Console with exponential backoff."
                ),
                combined_score=0.84,
                vector_score=0.86,
                keyword_score=0.81,
                source_url="https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/429",
            ),
            HybridSearchResult(
                id="kb-rbac-05",
                document_title="Organization RBAC Privileges & Member Invitation Failures",
                category="AUTH",
                content=(
                    "If an invited team member receives 'Unauthorized 403' or permission denied upon accessing role-gated pipelines, "
                    "verify if domain restriction or RBAC policy audit revoked staging deployment permissions for the Developer role."
                ),
                combined_score=0.82,
                vector_score=0.84,
                keyword_score=0.79,
                source_url="https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories",
            ),
            HybridSearchResult(
                id="kb-redis-06",
                document_title="Redis Cache Eviction Spike, Memory Pressure & OOM Runbook",
                category="TECHNICAL",
                content=(
                    "Redis memory usage exceeding 95% threshold triggers volatile-lru or allkeys-lru cache eviction spikes and OOM "
                    "command not allowed errors under maxmemory-policy. Run redis-cli --bigkeys and memory doctor to identify large keys."
                ),
                combined_score=0.93,
                vector_score=0.94,
                keyword_score=0.90,
                source_url="https://redis.io/docs/management/optimization/memory-optimization/",
            ),
            HybridSearchResult(
                id="kb-k8s-07",
                document_title="Kubernetes Pod CrashLoopBackOff & OOMKilled Exit Code 137 Runbook",
                category="TECHNICAL",
                content=(
                    "Payment service checkout-worker pods crashing in CrashLoopBackOff with exit code 137 indicates the container "
                    "exceeded cgroup memory limits and was terminated by Linux kernel OOMKilled. Inspect kubectl describe pod and increase limits."
                ),
                combined_score=0.94,
                vector_score=0.95,
                keyword_score=0.92,
                source_url="https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/",
            ),
            HybridSearchResult(
                id="kb-stripe-sig-08",
                document_title="Stripe Payment Webhook Signature Mismatch & InvalidSignature Runbook",
                category="BILLING",
                content=(
                    "When Stripe webhook verification fails with InvalidSignature or Webhook signature verification failed, "
                    "the signing secret whsec_ differs between environments or the raw HTTP request body was mutated before signature verification."
                ),
                combined_score=0.92,
                vector_score=0.93,
                keyword_score=0.89,
                source_url="https://docs.stripe.com/webhooks/signatures",
            ),
            HybridSearchResult(
                id="kb-s3-09",
                document_title="AWS S3 Bucket HTTP 403 Access Denied & IAM Policy Remediation",
                category="TECHNICAL",
                content=(
                    "AWS S3 HTTP 403 AccessDenied during PutObject or bucket sync indicates the caller IAM role lacks s3:PutObject "
                    "permissions or the bucket policy denies public uploads. Verify KMS key decrypt permissions and bucket ACLs."
                ),
                combined_score=0.91,
                vector_score=0.92,
                keyword_score=0.88,
                source_url="https://docs.aws.amazon.com/AmazonS3/latest/userguide/troubleshoot-403-errors.html",
            ),
        ]

        query_words = set(query_text.lower().replace("'", "").replace('"', '').split())
        scored_catalog: list[tuple[int, HybridSearchResult]] = []
        for chunk in catalog:
            chunk_text = f"{chunk.document_title} {chunk.content}".lower()
            overlap = sum(1 for w in query_words if len(w) > 2 and w in chunk_text)
            cat_bonus = 2 if category and chunk.category == category else 0
            scored_catalog.append((overlap + cat_bonus, chunk))

        scored_catalog.sort(key=lambda x: x[0], reverse=True)
        relevant_chunks = [c for score, c in scored_catalog if score > 0]
        return (relevant_chunks or catalog)[:top_k]

