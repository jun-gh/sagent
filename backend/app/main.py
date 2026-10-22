import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import init_db
from app.core.errors import (
    ErrorDetail,
    ErrorEnvelope,
    SagentException,
    generic_exception_handler,
    sagent_exception_handler,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sagent")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle management."""
    logger.info("Starting up %s (env: %s)...", settings.APP_NAME, settings.APP_ENV)
    logger.info("Active Gemini Model: %s", settings.GEMINI_MODEL)
    logger.info("Active Embedding Model: %s", settings.EMBEDDING_MODEL)
    
    # Initialize DB tables and pgvector extension
    db_connected = await init_db()
    if db_connected:
        logger.info("Database connection verified and initialized.")
        try:
            from sqlalchemy import func, select, text

            from app.core.database import AsyncSessionLocal
            from app.models.knowledge import ContextChunk
            async with AsyncSessionLocal() as session:
                # Update any existing records containing placeholder internal domains
                updates = [
                    "UPDATE context_chunks SET source_url = 'https://support.okta.com/help/s/article/How-to-configure-SAML-2-0-for-an-application' WHERE source_url LIKE '%internal%' AND category = 'AUTH'",
                    "UPDATE context_chunks SET source_url = 'https://docs.stripe.com/refunds' WHERE category = 'BILLING'",
                    "UPDATE context_chunks SET source_url = 'https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-DEADLOCKS' WHERE source_url LIKE '%internal%' AND (document_title LIKE '%PostgreSQL%' OR category = 'TECHNICAL')",
                    "UPDATE context_chunks SET source_url = 'https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/429' WHERE source_url LIKE '%internal%' AND document_title LIKE '%Rate Limiting%'",
                    "UPDATE context_chunks SET source_url = 'https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories' WHERE source_url LIKE '%internal%' AND document_title LIKE '%RBAC%'",
                ]
                for stmt in updates:
                    try:
                        await session.execute(text(stmt))
                    except Exception:
                        pass
                await session.commit()

                count_res = await session.execute(select(func.count(ContextChunk.id)))
                count = count_res.scalar() or 0
                if count == 0:
                    from app.services.rag.hybrid_search import HybridSearchService
                    service = HybridSearchService()
                    static_chunks = service._default_static_chunks("", None, 10)
                    for sc in static_chunks:
                        chunk = ContextChunk(
                            id=sc.id,
                            document_title=sc.document_title,
                            category=sc.category,
                            content=sc.content,
                            source_url=sc.source_url,
                        )
                        session.add(chunk)
                    await session.commit()
                    logger.info("Auto-seeded %d enterprise runbooks into context_chunks.", len(static_chunks))
        except Exception as seed_err:
            logger.warning("Auto-seeding context chunks skipped: %s", seed_err)
    else:
        logger.warning("Database unavailable on startup; local fallback provider active.")

    yield
    logger.info("Shutting down %s...", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    description="Autonomous Ticket Triage AI Agent with Hybrid RAG & Multi-Agent Orchestration",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handlers
app.add_exception_handler(SagentException, sagent_exception_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Enforces consistent typed error envelope on validation errors."""
    errors = exc.errors()
    error_msg = "; ".join([f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}" for e in errors])
    envelope = ErrorEnvelope(
        error=ErrorDetail(
            code="VALIDATION_ERROR",
            message=error_msg,
            retries_attempted=0,
            details=errors,
        )
    )
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=envelope.model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return await generic_exception_handler(request, exc)


# Include API v1 Router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "model": settings.GEMINI_MODEL,
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME} Ticket Triage API",
        "docs": "/docs",
        "config": f"{settings.API_V1_PREFIX}/config",
        "triage": f"{settings.API_V1_PREFIX}/tickets/triage",
    }
