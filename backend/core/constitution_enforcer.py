import json
from typing import Dict, Any
from backend.core.types import MemoryCandidate, ValidationResult

APPROVED_SCHEMA = {
    "name", "language_preference", "timezone",
    "interaction_style", "goals", "active_projects", "skill_level",
    "session_continuity", "topic_interests", "preferred_tools", "document_access_patterns"
}

class ConstitutionEnforcer:
    def __init__(self, constitution_path: str):
        with open(constitution_path, "r", encoding="utf-8") as f:
            self.rules = json.load(f)

    def validate(
        self,
        candidate: MemoryCandidate,
        existing_profile: Dict[str, Any],
        profile_age_weeks: int,
        onboarding_active: bool = False
    ) -> ValidationResult:
        field = candidate.get("field_name")

        # 1. Immutable field violation
        if field in self.rules["immutable_fields"]["fields"]:
            # If it already exists in the profile, we cannot overwrite it
            if field in existing_profile and existing_profile[field] is not None:
                return ValidationResult.HARD_REJECT("immutable_field")

        # 2. Forbidden schema key (not approved)
        if field not in APPROVED_SCHEMA and not onboarding_active:
            return ValidationResult.HARD_REJECT("schema_violation")

        # If onboarding bootstrap is active, bypass observer/validation
        if onboarding_active:
            return ValidationResult.APPROVED()

        # 3. Behavioral override trigger (stated preference vs behavioral contradiction)
        if self._triggers_behavioral_override(candidate, existing_profile):
            return ValidationResult.PROMPT_RECONCILIATION("behavioral_override")

        # 4. Validation thresholds by profile age
        thresholds = self.rules["validation_thresholds"]
        evidence_count = candidate.get("evidence_count", 1)
        label = candidate.get("label", "inferred")
        confidence = self._compute_confidence(candidate)

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
            if evidence_count < rule["evidence"] or confidence < rule["confidence"]:
                return ValidationResult.DISCARD("threshold_violation_month_2_plus")

        # 5. Gated fields check
        if field in self.rules["gated_fields"]["fields"]:
            return ValidationResult.REQUIRES_CONFIRMATION("gated_field")

        # 6. Conflict with existing high-confidence field
        if field in existing_profile and existing_profile[field] is not None:
            existing_val = existing_profile[field]
            proposed_val = candidate.get("proposed_value")
            if existing_val != proposed_val:
                # If we are here, we are not rejecting or overriding, so check conflict
                # Typically, check if existing field has high confidence
                # For this check we assume if it exists and confidence is high, TIER_2 is required
                existing_conf = existing_profile.get(f"{field}_confidence", 1.0)
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
        existing_profile: Dict[str, Any]
    ) -> bool:
        field = candidate.get("field_name")
        if field not in existing_profile or existing_profile[field] is None:
            return False

        if existing_profile[field] == candidate.get("proposed_value"):
            return False

        if candidate.get("label", "inferred") != "inferred":
            return False

        override_rule = self.rules["behavioral_override"]
        sessions = candidate.get("evidence_count", 1)
        days = candidate.get("behavioral_days_observed", 0)
        return (
            sessions >= override_rule["trigger_sessions"]
            and days >= override_rule["trigger_days"]
        )
