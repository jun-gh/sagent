import re
import logging
from typing import List, Tuple, Dict, Any, Optional

from .security_types import PIITokenMap

logger = logging.getLogger("sagent.security.output")


class OutputGuard:
    """
    Validates model-synthesized responses before returning them to clients or persisting.
    Prevents prompt leaking, internal connection string exposure, and out-of-policy promises.
    """

    # Default fallback threshold ($250 USD)
    MAX_AUTOMATED_REFUND_USD = 250.0

    LEAKAGE_PATTERNS: List[Tuple[str, re.Pattern]] = [
        # Internal connection strings
        (
            "DB_CONNECTION_STRING",
            re.compile(r"postgres(?:ql)?://[^\s]+:[^\s]+@[^\s]+", re.IGNORECASE),
        ),
        # Internal instructions leaking
        (
            "SYSTEM_PROMPT_LEAK",
            re.compile(
                r"(?i)\b(?:as\s+stated\s+in\s+my\s+system\s+prompt|my\s+instructions\s+are\s+to\s+classify|under\s+my\s+system\s+directives)\b"
            ),
        ),
        # API Keys leaking in reply
        (
            "RAW_KEY_LEAK",
            re.compile(r"\b(?:AKIA[0-9A-Z]{16}|(?:sk|rk)_(?:live|test)_[0-9a-zA-Z]{24,})\b"),
        ),
    ]

    REFUND_PATTERNS: List[re.Pattern] = [
        # Phrase starting with refund/credit action followed by dollar amount (e.g. "refund for the duplicate transaction of $12,400")
        re.compile(
            r"(?i)\b(?:refund|credit|compensate|reimburse|charge\s*back)(?:ed|ing|s|ment)?\b[^.\n]{0,80}?(?:\$|USD\s*)(\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d+(?:\.\d{2})?)"
        ),
        # Dollar amount followed by refund/credit action (e.g. "$2,400 refund")
        re.compile(
            r"(?i)(?:\$|USD\s*)(\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d+(?:\.\d{2})?)[^.\n]{0,80}?\b(?:refund|credit|compensate|reimburse|charge\s*back)(?:ed|ing|s|ment)?\b"
        ),
        # Direct fallback for simple phrases like "refunded you 850.00" without dollar sign
        re.compile(
            r"(?i)\b(?:refund|credit|compensate|reimburse)(?:ed|ing)?\s+(?:(?:you|of|for|an?\s+amount\s+of)\s+)?(?:\$|USD\s*)?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d+(?:\.\d{2})?)\b"
        ),
    ]
    # Backward compatibility alias
    REFUND_PATTERN = REFUND_PATTERNS[0]

    def __init__(self, max_refund_usd: Optional[float] = None):
        if max_refund_usd is not None:
            self.max_refund_usd = float(max_refund_usd)
        else:
            try:
                from app.core.config import get_settings
                self.max_refund_usd = float(get_settings().MAX_AUTOMATED_REFUND_USD)
            except Exception:
                self.max_refund_usd = self.MAX_AUTOMATED_REFUND_USD

    def sanitize_output(
        self,
        customer_reply: str,
        internal_action_plan: List[str],
        token_map: Optional[PIITokenMap] = None,
    ) -> Tuple[str, List[str], bool, List[str]]:
        """
        Validates customer reply and action plan.
        Returns:
            sanitized_reply, sanitized_action_plan, policy_violation_found, reasons
        """
        reasons: List[str] = []
        violation = False
        safe_reply = customer_reply

        # Check 1: Sensitive Data & Secret Leakage
        for leak_name, pattern in self.LEAKAGE_PATTERNS:
            if pattern.search(safe_reply):
                logger.warning("Output leakage detected: %s. Sanitizing reply.", leak_name)
                safe_reply = pattern.sub("[REDACTED_INTERNAL_INFORMATION]", safe_reply)
                reasons.append(f"LEAKAGE_{leak_name}")
                violation = True

        # Check 2: Financial Policy Bounds (Refund Caps)
        for pat in self.REFUND_PATTERNS:
            for match in pat.finditer(safe_reply):
                try:
                    amount = float(match.group(1).replace(",", ""))
                    if amount > self.max_refund_usd:
                        logger.warning(
                            "Refund of $%.2f exceeds automated policy threshold of $%.2f. Intercepting.",
                            amount,
                            self.max_refund_usd,
                        )
                        note = (
                            f"\n\n*Note: Credit adjustments exceeding ${self.max_refund_usd:.2f} "
                            "require manual verification by our billing operations supervisor.*"
                        )
                        if note not in safe_reply:
                            safe_reply += note
                        if "REFUND_CAP_EXCEEDED" not in reasons:
                            reasons.append("REFUND_CAP_EXCEEDED")
                        violation = True
                except (ValueError, IndexError):
                    pass

        # Check 3: Clean internal action plan
        safe_plan: List[str] = []
        for step in internal_action_plan:
            cleaned_step = step
            for leak_name, pattern in self.LEAKAGE_PATTERNS:
                if pattern.search(cleaned_step):
                    cleaned_step = pattern.sub("[REDACTED_INTERNAL_CONFIG]", cleaned_step)
            safe_plan.append(cleaned_step)

        # Check 4: Safe entity restoration (e.g. customer name/email if desired, keeping secrets masked)
        if token_map:
            safe_reply = token_map.restore(safe_reply)

        return safe_reply, safe_plan, violation, reasons
