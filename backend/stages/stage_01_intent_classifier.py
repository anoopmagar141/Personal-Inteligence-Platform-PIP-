# PIP Message Pipeline - Stage 1: Intent Classifier
#
# ADR-019 / Intent Classifier design:
# Mechanism 1 (skip_rag flag): Keyword/token match vs active_projects names + decision-log keyword cache to produce skip_rag bool.
# Mechanism 2 (ADR-002 safety net): Lightweight title-only embedding pre-check running regardless of skip_rag result.
# These are NOT the same check. Mechanism 1 saves ~35ms, whereas Mechanism 2 acts as a safety fallback.
