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
