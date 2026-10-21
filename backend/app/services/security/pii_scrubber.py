import re
import logging
from typing import List, Tuple, Dict, Any, Optional

from .security_types import PIIItem, PIITokenMap, SanitizedPayload

logger = logging.getLogger("sagent.security.pii")


def luhn_checksum_valid(number_str: str) -> bool:
    """Validates credit card number candidates using the Luhn algorithm."""
    digits = [int(c) for c in number_str if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, digit in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = digit * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += digit
    return checksum % 10 == 0


class PIIScrubber:
    """
    High-performance, rule-based PII and secret redaction engine.
    Scrubs credentials, tokens, credit cards, SSNs, and contact info
    before LLM inference and telemetry logging.
    """

    # Pre-compiled high-performance regex patterns
    PATTERNS: List[Tuple[str, re.Pattern, Optional[Any]]] = [
        # 1. Private Keys
        (
            "PRIVATE_KEY",
            re.compile(
                r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----",
                re.MULTILINE,
            ),
            None,
        ),
        # 2. AWS Access Key IDs
        (
            "AWS_ACCESS_KEY",
            re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
            None,
        ),
        # 3. Stripe Secret & Restricted Keys
        (
            "STRIPE_KEY",
            re.compile(r"\b((?:sk|rk)_(?:live|test)_[0-9a-zA-Z]{24,})\b"),
            None,
        ),
        # 4. GitHub Tokens
        (
            "GITHUB_TOKEN",
            re.compile(r"\b(gh[pousr]_[0-9a-zA-Z]{36,})\b"),
            None,
        ),
        # 5. JWT Tokens
        (
            "JWT_TOKEN",
            re.compile(r"\b(ey[A-Za-z0-9_-]{10,}\.ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9._-]*)\b"),
            None,
        ),
        # 6. Bearer Tokens
        (
            "BEARER_TOKEN",
            re.compile(r"\bBearer\s+([A-Za-z0-9_\-\.]{20,})\b", re.IGNORECASE),
            None,
        ),
        # 7. Generic API Key Assignments (e.g. api_key: "abc123xyz...")
        (
            "API_KEY",
            re.compile(
                r"(?i)\b(?:api[_-]?key|secret[_-]?token|auth[_-]?token)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-]{16,})['\"]?",
            ),
            None,
        ),
        # 8. Password in plaintext assignments
        (
            "CREDENTIAL",
            re.compile(
                r"(?i)\b(?:password|passwd|pwd|db_pass)\s*[:=]\s*['\"]?([^\s,;'\"\n]{4,})['\"]?",
            ),
            None,
        ),
        # 9. Social Security Numbers (US SSN)
        (
            "SSN",
            re.compile(r"\b(?!000|666|9\d{2})(\d{3})[- ](?!00)(\d{2})[- ](?!0000)(\d{4})\b"),
            None,
        ),
        # 10. Credit Cards (Luhn verified)
        (
            "CREDIT_CARD",
            re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
            luhn_checksum_valid,
        ),
        # 11. Email addresses
        (
            "EMAIL",
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
            None,
        ),
        # 12. Phone numbers (standard North American & international formats)
        (
            "PHONE",
            re.compile(
                r"\b(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?[2-9]\d{2}[-.\s]?\d{4}\b"
            ),
            None,
        ),
    ]

    def scrub(self, text: str) -> SanitizedPayload:
        """
        Scrubs all detected PII entities from the input text, replacing them
        with type-specific anonymous placeholders.
        """
        if not text:
            return SanitizedPayload(
                sanitized_text="",
                original_length=0,
                redactions_count=0,
                entities_found=[],
                token_map=PIITokenMap(),
            )

        sanitized = text
        token_items: List[PIIItem] = []
        entities_found_set = set()
        entity_counters: Dict[str, int] = {}

        for entity_type, regex, validator in self.PATTERNS:
            # Find all matches
            matches = list(regex.finditer(sanitized))
            # Process in reverse order so replacements do not alter earlier character offsets
            for match in reversed(matches):
                # If regex has capture groups, use the first group, else whole match
                matched_str = match.group(1) if match.lastindex and match.lastindex >= 1 else match.group(0)
                
                # Run validator if present (e.g. Luhn for credit cards)
                if validator and not validator(matched_str):
                    continue

                entity_counters[entity_type] = entity_counters.get(entity_type, 0) + 1
                idx = entity_counters[entity_type]
                placeholder = f"[REDACTED_{entity_type}_{idx}]"

                # Replace in text
                start, end = match.start(), match.end()
                sanitized = sanitized[:start] + placeholder + sanitized[end:]

                token_items.append(
                    PIIItem(
                        entity_type=entity_type,
                        placeholder=placeholder,
                        original_value=matched_str,
                        start_pos=start,
                        end_pos=end,
                    )
                )
                entities_found_set.add(entity_type)

        token_map = PIITokenMap(items=token_items)
        if token_items:
            logger.info(
                "PII Scrubber redacted %d items (entities: %s)",
                len(token_items),
                sorted(list(entities_found_set)),
            )

        return SanitizedPayload(
            sanitized_text=sanitized,
            original_length=len(text),
            redactions_count=len(token_items),
            entities_found=sorted(list(entities_found_set)),
            token_map=token_map,
        )
