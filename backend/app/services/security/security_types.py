from enum import Enum

from pydantic import BaseModel, Field


class SecurityVerdict(str, Enum):
    PASSED = "PASSED"
    REDACTED = "REDACTED"
    FLAGGED = "FLAGGED"
    QUARANTINED = "QUARANTINED"


class PIIItem(BaseModel):
    entity_type: str
    placeholder: str
    original_value: str
    start_pos: int
    end_pos: int


class PIITokenMap(BaseModel):
    items: list[PIIItem] = Field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.items)

    def restore(self, text: str) -> str:
        """
        Re-inserts original safe values into text (e.g. customer name/reference),
        while maintaining redaction of secrets/credentials.
        """
        result = text
        for item in self.items:
            # We only restore safe identifiers like emails if needed; secrets stay redacted
            if item.entity_type in {"EMAIL", "PHONE"}:
                result = result.replace(item.placeholder, item.original_value)
        return result


class SanitizedPayload(BaseModel):
    sanitized_text: str
    original_length: int
    redactions_count: int
    entities_found: list[str] = Field(default_factory=list)
    token_map: PIITokenMap = Field(default_factory=PIITokenMap)


class SecurityEvaluation(BaseModel):
    verdict: SecurityVerdict
    risk_score: float = 0.0
    pii_detected: bool = False
    pii_count: int = 0
    entities_found: list[str] = Field(default_factory=list)
    injection_detected: bool = False
    injection_reasons: list[str] = Field(default_factory=list)
    sanitized_text: str
    action_taken: str = "PROCEED"
