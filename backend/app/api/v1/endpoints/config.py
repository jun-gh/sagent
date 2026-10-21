from fastapi import APIRouter
from app.core.config import get_settings
from app.schemas.config import ModelConfigResponse

router = APIRouter()


@router.get("/config", response_model=ModelConfigResponse, summary="Get dynamic system and model configuration")
async def get_system_config():
    """
    Exposes active LLM model metadata, embedding model, and retry configuration.
    The frontend calls this to populate the live model status badge.
    """
    settings = get_settings()
    return ModelConfigResponse(
        app_name=settings.APP_NAME,
        environment=settings.APP_ENV,
        gemini_model=settings.GEMINI_MODEL,
        embedding_model=settings.EMBEDDING_MODEL,
        provider="Google Gemini",
        max_retries=settings.MAX_GEMINI_RETRIES,
        max_tickets_per_session=settings.MAX_TICKET_PER_SESSION,
        session_expiry_days=settings.SESSION_EXPIRY_DAYS,
        max_automated_refund_usd=settings.MAX_AUTOMATED_REFUND_USD,
        status="operational",
        api_version="v1",
    )
