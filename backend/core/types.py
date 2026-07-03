import datetime
from typing import TypedDict, List, Optional, Literal

TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

def now_utc() -> str:
    """Returns the current UTC time formatted as an ISO 8601 string."""
    return datetime.datetime.now(datetime.timezone.utc).strftime(TIMESTAMP_FORMAT)

class MemoryCandidate(TypedDict):
    field_name: str
    proposed_value: str
    label: Literal["explicit", "inferred", "user_verified", "user_correction"]
    evidence_count: int
    evidence_text: str

class ValidationResult:
    def __init__(self, status: Literal["APPROVED", "DISCARD", "REQUIRES_CONFIRMATION", "PROMPT_RECONCILIATION", "TIER_2_REQUIRED", "HARD_REJECT"], reason: Optional[str] = None):
        self.status = status
        self.reason = reason

    @classmethod
    def APPROVED(cls):
        return cls("APPROVED")

    @classmethod
    def DISCARD(cls, reason: str):
        return cls("DISCARD", reason)

    @classmethod
    def REQUIRES_CONFIRMATION(cls, reason: str):
        return cls("REQUIRES_CONFIRMATION", reason)

    @classmethod
    def PROMPT_RECONCILIATION(cls, reason: str):
        return cls("PROMPT_RECONCILIATION", reason)

    @classmethod
    def TIER_2_REQUIRED(cls, reason: str):
        return cls("TIER_2_REQUIRED", reason)

    @classmethod
    def HARD_REJECT(cls, reason: str):
        return cls("HARD_REJECT", reason)

    def __repr__(self) -> str:
        return f"ValidationResult(status={self.status}, reason={self.reason})"
