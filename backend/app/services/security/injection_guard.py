import logging
import re

from .security_types import SecurityEvaluation, SecurityVerdict

logger = logging.getLogger("sagent.security.injection")


class InjectionGuard:
    """
    High-speed heuristic and pattern-based prompt injection & jailbreak shield.
    Evaluates untrusted inputs for adversarial intent and provides strict context
    isolation delimiters before input is fed to AI models.
    """

    # Signatures for prompt injection, role hijacking, and instruction escapes
    ATTACK_SIGNATURES: list[tuple[str, re.Pattern, float]] = [
        # 1. Instruction Reset & Override
        (
            "INSTRUCTION_OVERRIDE",
            re.compile(
                r"(?i)\b(?:ignore|disregard|forget|bypass)\s+(?:all\s+)?(?:previous|prior|above|existing|system)\s+(?:instructions|prompts|rules|directives)\b"
            ),
            0.95,
        ),
        # 2. Jailbreak Persona Adoptions (DAN, roleplay games, unrestricted mode, developer mode)
        (
            "JAILBREAK_PERSONA",
            re.compile(
                r"(?i)\b(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be|roleplay\s+game|play\s+a\s+roleplay|you\s+are\s+\w+,\s+an?\s+omnipotent\s+ai|does\s+not\s+follow\s+safety)\s*(?:dan|unfiltered|jailbroken|an\s+ai\s+without\s+(?:limits|restrictions|rules)|developer\s+mode|omega)?\b"
            ),
            0.90,
        ),
        # 3. System Override & Command Injection
        (
            "SYSTEM_OVERRIDE",
            re.compile(
                r"(?i)\b(?:system\s+override|system_prompt_reset|sudo\s+mode|root\s+access|admin\s+mode\s+on)\b"
            ),
            0.85,
        ),
        # 4. Prompt Leaking & Exfiltration
        (
            "PROMPT_LEAK_ATTEMPT",
            re.compile(
                r"(?i)\b(?:reveal|print|show|repeat|display|output)\s+(?:(?:your|all|the)\s+)?(?:(?:secret|system|initial|previous|prior|hidden)\s+(?:instructions|prompts|rules|directives)|system\s+prompt|everything\s+written\s+above|developer\s+guidelines|internal\s+configuration)\b"
            ),
            0.90,
        ),
        # 5. Role Hijacking Delimiters (trying to simulate system/assistant chat turns)
        (
            "ROLE_SPOOFING",
            re.compile(
                r"(?i)(?:<\s*/?\s*(?:system|assistant|instructions)\s*>|\n\s*(?:System|Assistant|AI):\s*['\"]?(?:You are|Output|Acknowledge))"
            ),
            0.80,
        ),
        # 6. Malicious Delimiter Escape
        (
            "DELIMITER_ESCAPE",
            re.compile(
                r"(?i)</\s*user_ticket_content\s*>"
            ),
            0.90,
        ),
    ]

    def evaluate(self, text: str) -> SecurityEvaluation:
        """
        Evaluates input text for prompt injection and jailbreak signatures.
        Returns a structured SecurityEvaluation.
        """
        if not text:
            return SecurityEvaluation(
                verdict=SecurityVerdict.PASSED,
                risk_score=0.0,
                injection_detected=False,
                injection_reasons=[],
                sanitized_text="",
                action_taken="PROCEED",
            )

        detected_reasons: list[str] = []
        max_risk = 0.0

        for rule_name, regex, risk_weight in self.ATTACK_SIGNATURES:
            if regex.search(text):
                detected_reasons.append(rule_name)
                max_risk = max(max_risk, risk_weight)

        injection_found = max_risk >= 0.70

        if injection_found:
            logger.warning(
                "Prompt Injection Attempt Intercepted! Risk: %.2f, Reasons: %s",
                max_risk,
                detected_reasons,
            )
            return SecurityEvaluation(
                verdict=SecurityVerdict.QUARANTINED,
                risk_score=max_risk,
                injection_detected=True,
                injection_reasons=detected_reasons,
                sanitized_text=text,
                action_taken="QUARANTINE_ADVERSARIAL",
            )

        return SecurityEvaluation(
            verdict=SecurityVerdict.PASSED,
            risk_score=max_risk,
            injection_detected=False,
            injection_reasons=detected_reasons,
            sanitized_text=text,
            action_taken="PROCEED",
        )

    @staticmethod
    def frame_untrusted_input(text: str) -> str:
        """
        Wraps user ticket input inside strict cognitive XML boundaries
        and sanitizes any premature closing delimiters.
        """
        escaped_text = text.replace("</user_ticket_content>", "[ESCAPED_DELIMITER]")
        return (
            "<user_ticket_content>\n"
            f"{escaped_text}\n"
            "</user_ticket_content>"
        )
