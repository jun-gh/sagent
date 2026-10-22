import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_get_config():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/config")
    
    assert response.status_code == 200
    data = response.json()
    assert "gemini_model" in data
    assert "embedding_model" in data
    assert data["provider"] == "Google Gemini"
    assert data["status"] == "operational"
    assert data["max_retries"] == 3


def test_database_url_sanitization():
    from app.core.config import Settings
    neon_url = "postgresql+asyncpg://neondb_owner:pass@ep-test-pooler.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    s = Settings(DATABASE_URL=neon_url, GEMINI_API_KEY="dummy")
    assert "sslmode" not in s.DATABASE_URL
    assert "channel_binding" not in s.DATABASE_URL
    assert "ssl=require" in s.DATABASE_URL

