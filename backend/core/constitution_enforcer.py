import json
from datetime import datetime, timezone
from fnmatch import fnmatch
from typing import Any
from backend.core.types import MemoryCandidate, ValidationResult

OBSERVER_WRITABLE_TABLES = {
    "topic_interests",
    "preferred_tools",
    "document_access_patterns",
    "skill_memory",
    "preference_memory",
    "goal_memory",
    "interaction_style",
    "active_projects",
}

class ConstitutionEnforcer:
    def __init__(self, constitution_path: str):
        with open(constitution_path, "r", encoding="utf-8") as f:
            self.rules = json.load(f)

    def validate(
        self,
        candidate: MemoryCandidate,
        existing_field: Any,
        profile_age_weeks: int
    ) -> ValidationResult:
        field = candidate.get("field_name")
        target_table = candidate.get("target_table")

        # 1. Immutable field violation
        if field in self.rules["immutable_fields"]["fields"]:
            if self._field_value(existing_field, "current_value") is not None:
                return ValidationResult.HARD_REJECT("immutable_field")

        # 2. Observer write allowlist is table-level, not field-level
        if target_table not in OBSERVER_WRITABLE_TABLES:
            return ValidationResult.HARD_REJECT("schema_violation")

        # 3. Behavioral override trigger (stated preference vs behavioral contradiction)
        if self._triggers_behavioral_override(candidate, existing_field):
            return ValidationResult.PROMPT_RECONCILIATION("behavioral_override")

        # 4. Validation thresholds by profile age
        thresholds = self.rules["validation_thresholds"]
        evidence_count = candidate.get("evidence_count", 1)
        label = candidate.get("label", "inferred")
        confidence = None if target_table == "goal_memory" else self._compute_confidence(candidate)

        if profile_age_weeks <= 2:
            # Week 1-2: evidence >= 1, explicit label required
            rule = thresholds["week_1_2"]
            if evidence_count < rule["evidence"] or label not in ("explicit", "user_verified", "user_correction"):
                return ValidationResult.DISCARD("threshold_violation_week_1_2")
        elif profile_age_weeks <= 4:
            # Week 3-4: evidence >= 2
            rule = thresholds["week_3_4"]
            if evidence_count < rule["evidence"]:
                return ValidationResult.DISCARD("threshold_violation_week_3_4")
        else:
            # Month 2+: evidence >= 3, confidence >= 0.7
            rule = thresholds["month_2_plus"]
            if evidence_count < rule["evidence"]:
                return ValidationResult.DISCARD("threshold_violation_month_2_plus")
            if target_table != "goal_memory" and confidence < rule["confidence"]:
                return ValidationResult.DISCARD("threshold_violation_month_2_plus")

        # 5. Gated fields check
        if self._matches_gated_field(candidate):
            return ValidationResult.REQUIRES_CONFIRMATION("gated_field")

        # 6. Conflict with existing high-confidence field
        existing_val = self._field_value(existing_field, "current_value")
        if existing_val is not None:
            proposed_val = candidate.get("proposed_value")
            if existing_val != proposed_val:
                existing_conf = self._field_value(existing_field, "confidence", 1.0)
                if existing_conf > 0.7:
                    return ValidationResult.TIER_2_REQUIRED("high_confidence_conflict")

        return ValidationResult.APPROVED()

    def _compute_confidence(self, candidate: MemoryCandidate) -> float:
        label = candidate.get("label", "inferred")
        evidence_count = candidate.get("evidence_count", 1)
        base = 0.9 if label in ("explicit", "user_verified", "user_correction") else 0.4
        return base * min(evidence_count, 5) / 5.0

    def _triggers_behavioral_override(
        self,
        candidate: MemoryCandidate,
        existing_field: Any
    ) -> bool:
        current_value = self._field_value(existing_field, "current_value")
        if current_value is None:
            return False

        if current_value == candidate.get("proposed_value"):
            return False

        if candidate.get("label", "inferred") != "inferred":
            return False

        if self._field_value(existing_field, "source_label") not in (
            "explicit",
            "user_verified",
            "user_correction",
        ):
            return False

        override_rule = self.rules["behavioral_override"]
        behavioral_signal_count = self._field_value(existing_field, "behavioral_signal_count", 0)
        if behavioral_signal_count < override_rule["trigger_sessions"]:
            return False

        first_contradiction_date = self._field_value(existing_field, "first_contradiction_date")
        if first_contradiction_date is None:
            return False

        days = (datetime.now(timezone.utc) - self._parse_datetime(first_contradiction_date)).days
        return (
            days >= override_rule["trigger_days"]
        )

    def _matches_gated_field(self, candidate: MemoryCandidate) -> bool:
        field_path = f"{candidate.get('target_table')}.{candidate.get('field_name')}"
        return any(
            fnmatch(field_path, pattern) or fnmatch(candidate.get("field_name", ""), pattern)
            for pattern in self.rules["gated_fields"]["fields"]
        )

    def _field_value(self, existing_field: Any, name: str, default: Any = None) -> Any:
        if existing_field is None:
            return default
        if isinstance(existing_field, dict):
            return existing_field.get(name, default)
        return getattr(existing_field, name, default)

    def _parse_datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
