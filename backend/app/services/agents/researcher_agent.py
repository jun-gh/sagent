import time
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.ticket import Citation
from app.services.rag.hybrid_search import HybridSearchService


class ResearcherAgent:
    """
    Agent responsible for querying the Hybrid RAG engine using search terms,
    filtering relevant context chunks, and compiling grounding citations.
    """

    def __init__(self, hybrid_search: HybridSearchService):
        self.hybrid_search = hybrid_search

    async def retrieve_grounding(
        self,
        session: AsyncSession,
        search_queries: List[str],
        category: Optional[str] = None,
        top_k: int = 4,
    ) -> Dict[str, Any]:
        """
        Executes hybrid searches across all suggested queries and compiles unique citations.
        """
        start = time.perf_counter()
        seen_ids = set()
        citations: List[Citation] = []
        raw_chunks: List[Dict[str, Any]] = []

        # Search with the primary queries
        for query in search_queries[:3]:
            results = await self.hybrid_search.search(
                session=session,
                query_text=query,
                category=category,
                top_k=top_k,
            )

            for r in results:
                if r.id not in seen_ids:
                    seen_ids.add(r.id)
                    citations.append(
                        Citation(
                            document_title=r.document_title,
                            category=r.category,
                            content_snippet=r.content[:240] + ("..." if len(r.content) > 240 else ""),
                            score=round(r.combined_score, 3),
                            source_url=r.source_url,
                        )
                    )
                    raw_chunks.append({
                        "title": r.document_title,
                        "content": r.content,
                        "source": r.source_url,
                    })

        # Sort citations by relevance score descending
        citations.sort(key=lambda c: c.score, reverse=True)
        top_citations = citations[:top_k]
        duration_ms = (time.perf_counter() - start) * 1000

        return {
            "citations": top_citations,
            "raw_chunks": raw_chunks[:top_k],
            "duration_ms": round(duration_ms, 2),
            "thought": f"Retrieved {len(top_citations)} grounded runbook articles matching queries: {', '.join(search_queries[:2])}.",
        }
