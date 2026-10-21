import pytest
from unittest.mock import patch, MagicMock
import httpx
from app.services.ai.gemini_client import GeminiClient
from app.core.errors import RateLimitExceededException


@pytest.mark.asyncio
async def test_synthetic_fallback_when_unconfigured():
    client = GeminiClient(api_key="")
    assert not client.is_configured()
    
    text_res = await client.generate_text("test prompt")
    assert len(text_res) > 0

    json_res = await client.generate_json("SAML SSO login error cert expired")
    assert json_res["category"] == "AUTH"
    assert "search_queries" in json_res

    emb = await client.get_embedding("test query text")
    assert len(emb) == 768


@pytest.mark.asyncio
async def test_exponential_backoff_and_rate_limit_exception():
    client = GeminiClient(api_key="mock_test_key")
    assert client.is_configured()
    client.base_delay = 0.01  # fast delay for unit test
    client.max_retries = 3

    # Mock httpx response with 429 status code
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.content = b'{"error":{"message":"Resource has been exhausted (e.g. check quota)."}}'
    mock_response.json.return_value = {"error": {"message": "Resource has been exhausted (e.g. check quota)."}}

    with patch("httpx.AsyncClient.request", return_value=mock_response) as mock_req:
        with pytest.raises(RateLimitExceededException) as exc_info:
            await client._execute_with_retry("POST", "models/gemini-2.5-flash:generateContent", {})
        
        assert exc_info.value.code == "RATE_LIMIT_EXCEEDED"
        assert exc_info.value.retries_attempted == 3
        assert mock_req.call_count == 4  # 1 initial + 3 retries
