import time
import logging
from typing import Dict, List, Optional
from collections import defaultdict
from fastapi import Request, Header, HTTPException, status, Depends

from app.core.config import get_settings
from app.core.errors import RateLimitExceededException, UnauthorizedAPIException

logger = logging.getLogger("sagent.security.middleware")
settings = get_settings()


class SlidingWindowRateLimiter:
    """
    In-memory sliding window rate limiter per client IP address.
    """
    def __init__(self, requests_per_minute: int = 120):
        self.rpm = requests_per_minute
        self.window_seconds = 60.0
        self._history: Dict[str, List[float]] = defaultdict(list)

    def check(self, client_ip: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        
        # Clean expired timestamps
        history = [ts for ts in self._history[client_ip] if ts > cutoff]
        self._history[client_ip] = history

        if len(history) >= self.rpm:
            return False

        self._history[client_ip].append(now)
        return True


rate_limiter = SlidingWindowRateLimiter(requests_per_minute=settings.RATE_LIMIT_RPM)


async def verify_rate_limit(request: Request):
    """Dependency verifying client does not exceed configured RPM."""
    client_ip = request.client.host if request.client else "unknown"
    if not rate_limiter.check(client_ip):
        logger.warning("Rate limit exceeded for IP: %s (limit: %d RPM)", client_ip, settings.RATE_LIMIT_RPM)
        raise RateLimitExceededException(
            message=f"Rate limit of {settings.RATE_LIMIT_RPM} requests per minute exceeded. Please try again shortly.",
            retries_attempted=0,
        )


async def verify_api_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Dependency verifying API Key if REQUIRE_API_KEY is enabled.
    Accepts X-API-Key header or Authorization: Bearer <key>.
    """
    if not settings.REQUIRE_API_KEY:
        return True

    provided_key = x_api_key
    if not provided_key and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            provided_key = parts[1]

    if not provided_key or provided_key != settings.SAGENT_API_KEY:
        logger.warning("Unauthorized API access attempt from %s", request.client.host if request.client else "unknown")
        raise UnauthorizedAPIException(
            message="Valid API Key required in 'X-API-Key' or 'Authorization: Bearer <token>' header."
        )

    return True
