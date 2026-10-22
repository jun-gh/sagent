import asyncio
import json
import logging
import random
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import GeminiAPIException, RateLimitExceededException

logger = logging.getLogger("sagent.gemini")


class GeminiClient:
    """
    Resilient Google Gemini client wrapper.
    Executes outbound LLM calls with exponential backoff and jitter (up to 3 retries),
    strictly catching HTTP 429 rate limits, resource exhaustion, and temporary outages.
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self.embedding_model = settings.EMBEDDING_MODEL
        self.max_retries = settings.MAX_GEMINI_RETRIES
        self.base_delay = settings.RETRY_BASE_DELAY
        self.max_delay = settings.RETRY_MAX_DELAY
        self.last_usage_metadata: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    def is_configured(self) -> bool:
        """Checks if a valid API key has been configured."""
        return bool(self.api_key and not self.api_key.startswith("your_"))

    async def _execute_with_retry(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any],
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Executes an HTTP request to Gemini API with exponential backoff + jitter.
        Retries on 429, 500, 502, 503, 504 and network errors.
        """
        params = params or {}
        params["key"] = self.api_key
        url = f"{self.BASE_URL}/{endpoint}"
        retries_attempted = 0

        for attempt in range(self.max_retries + 1):
            async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=10.0)) as client:
                try:
                    logger.debug("Gemini request attempt %d to %s", attempt + 1, endpoint)
                    response = await client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )

                    # Check for rate limit
                    if response.status_code == 429:
                        error_data = response.json().get("error", {}) if response.content else {}
                        err_msg = error_data.get("message", "Rate limit exceeded (HTTP 429).")
                        logger.warning(
                            "Gemini 429 Quota Exceeded on attempt %d/%d: %s",
                            attempt + 1,
                            self.max_retries,
                            err_msg,
                        )

                        if attempt < self.max_retries:
                            retries_attempted += 1
                            # Exponential backoff with jitter: delay = min(max_delay, base * 2^attempt + jitter)
                            jitter = random.uniform(0.1, 0.5)
                            backoff = min(self.max_delay, (self.base_delay * (2 ** attempt)) + jitter)
                            logger.info("Backing off for %.2f seconds before retry...", backoff)
                            await asyncio.sleep(backoff)
                            continue
                        else:
                            raise RateLimitExceededException(
                                message=f"Gemini API quota exhausted. {err_msg} Please try again in 30 seconds.",
                                retries_attempted=retries_attempted,
                                details=error_data,
                            )

                    # Check for transient server errors (5xx)
                    if response.status_code in (500, 502, 503, 504):
                        retries_attempted += 1
                        if attempt < self.max_retries:
                            jitter = random.uniform(0.1, 0.5)
                            backoff = min(self.max_delay, (self.base_delay * (2 ** attempt)) + jitter)
                            logger.warning(
                                "Gemini server error %d on attempt %d. Retrying in %.2fs...",
                                response.status_code,
                                retries_attempted,
                                backoff,
                            )
                            await asyncio.sleep(backoff)
                            continue
                        else:
                            raise GeminiAPIException(
                                message=f"Gemini API temporary server error ({response.status_code}).",
                                retries_attempted=retries_attempted,
                                details=response.text,
                            )

                    # Normal success
                    if 200 <= response.status_code < 300:
                        return response.json()

                    # Other 4xx client errors
                    error_json = response.json() if response.content else {"message": response.text}
                    raise GeminiAPIException(
                        message=f"Gemini API client error ({response.status_code}): {error_json.get('error', {}).get('message', response.text)}",
                        retries_attempted=retries_attempted,
                        details=error_json,
                    )

                except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as net_err:
                    retries_attempted += 1
                    logger.warning("Network issue during Gemini call (attempt %d): %s", retries_attempted, net_err)
                    if attempt < self.max_retries:
                        backoff = min(self.max_delay, (self.base_delay * (2 ** attempt)) + random.uniform(0.1, 0.4))
                        await asyncio.sleep(backoff)
                        continue
                    raise GeminiAPIException(
                        message="Network connectivity error while reaching Gemini API.",
                        retries_attempted=retries_attempted,
                        details=str(net_err),
                    )

        raise GeminiAPIException(
            message="Exceeded max retries calling Gemini API.",
            retries_attempted=retries_attempted,
        )

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.2,
        model: str | None = None,
    ) -> str:
        """Generates plain text response using Gemini."""
        if not self.is_configured():
            logger.info("GEMINI_API_KEY is not set. Generating synthetic response.")
            return self._synthetic_text_response(prompt)

        target_model = model or self.model
        payload: dict[str, Any] = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        endpoint = f"models/{target_model}:generateContent"
        data = await self._execute_with_retry("POST", endpoint, payload)
        self._record_usage(data, prompt)
        
        try:
            candidates = data.get("candidates", [])
            if candidates and "content" in candidates[0]:
                parts = candidates[0]["content"].get("parts", [])
                if parts and "text" in parts[0]:
                    return parts[0]["text"]
            return ""
        except Exception as e:
            raise GeminiAPIException(f"Failed to parse Gemini response: {e!s}", details=data)

    async def generate_json(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature: float = 0.1,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Generates structured JSON response using Gemini JSON Mode."""
        if not self.is_configured():
            logger.info("GEMINI_API_KEY is not set. Generating synthetic JSON.")
            return self._synthetic_json_response(prompt)

        target_model = model or self.model
        payload: dict[str, Any] = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        endpoint = f"models/{target_model}:generateContent"
        data = await self._execute_with_retry("POST", endpoint, payload)
        self._record_usage(data, prompt)

        try:
            candidates = data.get("candidates", [])
            if candidates and "content" in candidates[0]:
                parts = candidates[0]["content"].get("parts", [])
                if parts and "text" in parts[0]:
                    raw_text = parts[0]["text"].strip()
                    # Strip markdown code blocks if present
                    raw_text = raw_text.removeprefix("```json")
                    raw_text = raw_text.removeprefix("```")
                    raw_text = raw_text.removesuffix("```")
                    return json.loads(raw_text.strip())
            raise GeminiAPIException("No valid candidate returned from Gemini.", details=data)
        except json.JSONDecodeError as jde:
            raise GeminiAPIException(f"Failed to decode JSON from Gemini output: {jde!s}", details=data)

    def _record_usage(self, data: dict[str, Any], prompt: str = "") -> None:
        """Extracts usageMetadata from response or estimates tokens."""
        usage = data.get("usageMetadata", {})
        if usage:
            self.last_usage_metadata = {
                "prompt_tokens": usage.get("promptTokenCount", 0),
                "completion_tokens": usage.get("candidatesTokenCount", 0),
                "total_tokens": usage.get("totalTokenCount", 0),
            }
        else:
            p_tok = max(1, len(prompt) // 4)
            c_tok = 50
            self.last_usage_metadata = {
                "prompt_tokens": p_tok,
                "completion_tokens": c_tok,
                "total_tokens": p_tok + c_tok,
            }

    def get_last_usage(self) -> dict[str, int]:
        """Returns the token usage metrics from the most recent Gemini call."""
        return dict(self.last_usage_metadata)

    async def get_embedding(self, text: str) -> list[float]:
        """
        Generates 768-dimensional dense vector embeddings using gemini-embedding-001.
        """
        if not self.is_configured():
            # Deterministic pseudo-embedding for local dev when no key is provided
            return self._synthetic_embedding(text)

        model_name = self.embedding_model if self.embedding_model and self.embedding_model != "text-embedding-004" else "gemini-embedding-001"

        payload = {
            "model": f"models/{model_name}",
            "content": {
                "parts": [{"text": text[:2048]}]
            },
            "outputDimensionality": 768,
        }

        endpoint = f"models/{model_name}:embedContent"
        data = await self._execute_with_retry("POST", endpoint, payload)

        embedding_values = data.get("embedding", {}).get("values", [])
        if not embedding_values:
            raise GeminiAPIException("Empty embedding returned by Gemini.", details=data)
        return embedding_values[:768]

    def _synthetic_embedding(self, text: str) -> list[float]:
        """Creates a normalized 768-dimension pseudo-embedding based on text hash."""
        import hashlib
        import math
        seed = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16)
        random.seed(seed)
        vec = [random.gauss(0, 1) for _ in range(768)]
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [round(x / norm, 6) for x in vec]

    def _synthetic_text_response(self, prompt: str) -> str:
        return (
            "Thank you for contacting support. We have analyzed your issue and identified the root cause. "
            "Please follow the recommended steps provided below."
        )

    def _synthetic_json_response(self, prompt: str) -> dict[str, Any]:
        """Realistic fallback when running locally without an active Gemini API key."""
        prompt_lower = prompt.lower()
        if "sso" in prompt_lower or "saml" in prompt_lower or "auth" in prompt_lower or "login" in prompt_lower:
            return {
                "category": "AUTH",
                "urgency": "HIGH",
                "sentiment": "Urgent / Blocked",
                "confidence_score": 0.94,
                "search_queries": [
                    "SAML SSO certificate expiration",
                    "IdP metadata renewal Okta Azure AD",
                    "Single sign-on certificate rollover"
                ],
                "suggested_reply": (
                    "Hello,\n\nWe have identified that this issue is typically caused by an expired SAML signing certificate "
                    "or mismatched Identity Provider (IdP) metadata. To restore access:\n\n"
                    "1. Have your IT administrator navigate to Organization Settings -> Single Sign-On.\n"
                    "2. Download your current IdP certificate (X.509 PEM format) and upload it into the SAML configuration.\n"
                    "3. Ensure the Entity ID and Assertion Consumer Service (ACS) URL match your IdP app configuration.\n\n"
                    "Our security team is monitoring this ticket to assist if further verification is required."
                ),
                "internal_action_plan": [
                    "Check customer Okta / Azure AD metadata fingerprint against production audit logs",
                    "Verify if IdP rollover grace period is enabled for this tenant",
                    "Inspect recent tenant SSO certificate expiry alerts in Datadog"
                ],
                "tags": ["sso", "saml", "authentication", "idp-rollover"],
                "triage_notes": "Identified as SAML SSO certificate or metadata mismatch affecting user authentication."
            }
        elif "refund" in prompt_lower or "invoice" in prompt_lower or "charge" in prompt_lower or "billing" in prompt_lower:
            return {
                "category": "BILLING",
                "urgency": "MEDIUM",
                "sentiment": "Frustrated",
                "confidence_score": 0.92,
                "search_queries": [
                    "Stripe duplicate invoice webhook failure",
                    "Billing dispute refund policy",
                    "Subscription prorated upgrade charge"
                ],
                "suggested_reply": (
                    "Hello,\n\nThank you for reaching out. We apologize for the discrepancy on your latest billing statement. "
                    "Our finance engine has flagged the duplicate transaction for automated reconciliation.\n\n"
                    "A refund of the duplicate charge has been queued to your original payment method. Depending on your bank, "
                    "funds will appear within 3-5 business days. Your subscription remains active without disruption."
                ),
                "internal_action_plan": [
                    "Lookup customer transaction ID in Stripe Dashboard",
                    "Validate webhook replay logs for duplicate charge events",
                    "Confirm credit note issuance in billing ledger"
                ],
                "tags": ["billing", "duplicate-charge", "stripe", "refund"],
                "triage_notes": "Customer incurred duplicate transaction due to retry webhook; queued refund."
            }
        elif "deadlock" in prompt_lower or "database" in prompt_lower or "postgres" in prompt_lower or "slow" in prompt_lower:
            return {
                "category": "TECHNICAL",
                "urgency": "CRITICAL",
                "sentiment": "Critical Escalation",
                "confidence_score": 0.96,
                "search_queries": [
                    "PostgreSQL transaction deadlock resolution pg_stat_activity",
                    "Database connection pool exhaustion pgbouncer",
                    "Slow query locking tenant isolation"
                ],
                "suggested_reply": (
                    "Hello,\n\nOur site reliability team has picked up this incident immediately. The symptoms described point to "
                    "transient lock contention or database connection pooling saturation.\n\n"
                    "We have initiated diagnostic isolation on your dedicated read-replica and verified connection pools. "
                    "An incident commander has been assigned and will provide another update within 15 minutes."
                ),
                "internal_action_plan": [
                    "Run pg_stat_activity query to identify blocking PID and terminate long-held locks",
                    "Check PgBouncer active client vs server connection ratios",
                    "Review recent migration logs for unindexed foreign keys causing table locks"
                ],
                "tags": ["database", "deadlock", "postgres", "p0-outage"],
                "triage_notes": "High concurrency deadlock or connection exhaustion impacting tenant queries."
            }
        else:
            return {
                "category": "TECHNICAL",
                "urgency": "MEDIUM",
                "sentiment": "Neutral",
                "confidence_score": 0.88,
                "search_queries": [
                    "General API troubleshooting",
                    "Standard resolution runbook",
                    "Customer service SLA guidelines"
                ],
                "suggested_reply": (
                    "Hello,\n\nThank you for contacting Sagent Support. We have received your ticket and our engineering "
                    "team is reviewing the logs and service metrics related to your account.\n\n"
                    "We will follow up shortly with concrete resolution steps."
                ),
                "internal_action_plan": [
                    "Inspect account event logs for recent anomalies",
                    "Verify user permissions and quota boundaries"
                ],
                "tags": ["support", "general-inquiry", "investigating"],
                "triage_notes": "Ticket ingested and classified for Tier-1 investigation."
            }
