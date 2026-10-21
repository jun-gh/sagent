from pydantic import BaseModel, Field


class ModelConfigResponse(BaseModel):
    app_name: str = Field(..., description="Application name")
    environment: str = Field(..., description="Runtime environment")
    gemini_model: str = Field(..., description="Active Gemini LLM model for triage")
    embedding_model: str = Field(..., description="Active embedding model for RAG")
    provider: str = Field(default="Google Gemini", description="AI Provider")
    max_retries: int = Field(..., description="Max retries with exponential backoff")
    max_tickets_per_session: int = Field(default=10, description="Max tickets allowed per session")
    session_expiry_days: int = Field(default=7, description="Number of days before session tickets expire")
    max_automated_refund_usd: float = Field(default=250.0, description="Max automated refund amount in USD")
    status: str = Field(default="operational", description="Service status")
    api_version: str = Field(default="v1", description="API version")
