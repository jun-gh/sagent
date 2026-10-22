from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    retries_attempted: int = 0
    details: Any | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class SagentException(Exception):
    """Base exception for Sagent domain errors."""
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        retries_attempted: int = 0,
        details: Any | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.retries_attempted = retries_attempted
        self.details = details


class RateLimitExceededException(SagentException):
    def __init__(
        self,
        message: str = "Gemini API quota exhausted. Please try again shortly.",
        retries_attempted: int = 3,
        details: Any | None = None,
    ):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            retries_attempted=retries_attempted,
            details=details,
        )


class GeminiAPIException(SagentException):
    def __init__(
        self,
        message: str,
        code: str = "GEMINI_API_ERROR",
        retries_attempted: int = 0,
        details: Any | None = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_502_BAD_GATEWAY,
            retries_attempted=retries_attempted,
            details=details,
        )


class ResourceNotFoundException(SagentException):
    def __init__(self, message: str = "Requested resource not found"):
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            retries_attempted=0,
        )


class InvalidTicketDataException(SagentException):
    def __init__(self, message: str, details: Any | None = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            retries_attempted=0,
            details=details,
        )


class SessionLimitReachedException(SagentException):
    def __init__(
        self,
        max_tickets: int = 10,
        message: str | None = None,
    ):
        msg = message or f"Maximum session limit reached ({max_tickets} tickets). Please start a new session to submit more tickets."
        super().__init__(
            message=msg,
            code="SESSION_LIMIT_REACHED",
            status_code=status.HTTP_400_BAD_REQUEST,
            retries_attempted=0,
            details={"max_tickets": max_tickets},
        )


class SecurityQuarantineException(SagentException):
    def __init__(
        self,
        message: str = "Input quarantined by security guardrails (prompt injection or adversarial pattern detected).",
        reasons: Any | None = None,
    ):
        super().__init__(
            message=message,
            code="SECURITY_QUARANTINED",
            status_code=status.HTTP_400_BAD_REQUEST,
            retries_attempted=0,
            details={"reasons": reasons or ["INJECTION_DETECTED"]},
        )


class UnauthorizedAPIException(SagentException):
    def __init__(
        self,
        message: str = "Unauthorized: Invalid or missing API key.",
    ):
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
            retries_attempted=0,
        )



async def sagent_exception_handler(request: Request, exc: SagentException) -> JSONResponse:
    """Format domain exceptions into structured typed error envelopes."""
    content = ErrorEnvelope(
        error=ErrorDetail(
            code=exc.code,
            message=exc.message,
            retries_attempted=exc.retries_attempted,
            details=exc.details,
        )
    ).model_dump()
    return JSONResponse(status_code=exc.status_code, content=content)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fallback handler for unhandled internal errors."""
    content = ErrorEnvelope(
        error=ErrorDetail(
            code="INTERNAL_SERVER_ERROR",
            message=f"An unexpected error occurred: {exc!s}",
            retries_attempted=0,
            details=None,
        )
    ).model_dump()
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=content)
