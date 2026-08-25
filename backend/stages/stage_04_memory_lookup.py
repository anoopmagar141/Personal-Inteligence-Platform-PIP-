# PIP Message Pipeline - Stage 4: Memory Lookup
#
# Part 7.3: "relevant profile fields only (NEVER full profile dump)". profile_store
# has no per-category selective query, only get_profile() (everything) and
# get_profile_field() (one named field) - neither fits this stage's contract on its
# own. This stage fetches the full profile via profile_store.py (the only allowed
# access path, per spec) and filters it down to the tables relevant to the given
# category before returning anything, so a full dump never leaves this function.

import logging

from backend.memory import profile_store

logger = logging.getLogger(__name__)

# Tables relevant to each category. Categories not listed fall back to
# _DEFAULT_TABLES - interaction_style alone, since "how to respond" is broadly
# useful regardless of topic, without approaching a full profile dump.
#
# personal_question includes active_projects too (found live: "summarize my
# project" hits _PERSONAL_PATTERNS' bare "my" match before some phrasings of
# Stage 1's project-status check, landing here rather than project_question -
# without this, that phrasing still got zero real project data despite
# clearly asking about one).
_CATEGORY_TABLES = {
    "personal_question": {"identity", "preference_memory", "interaction_style", "skill_memory", "active_projects"},
    "project_question": {"active_projects", "goal_memory", "interaction_style"},
    "project_continuation": {"active_projects", "goal_memory", "interaction_style"},
    "coding_question": {"skill_memory", "preferred_tools", "interaction_style"},
}
_DEFAULT_TABLES = {"interaction_style"}


def tables_for_category(category: str) -> set[str]:
    """
    The tables this stage WOULD fetch for a category, independent of whether
    any rows actually exist.

    Stage 7 needs this to tell two very different situations apart: "projects
    weren't looked up for this question" and "projects were looked up and the
    user genuinely has none". Rendering both as an absent section is what let
    the model treat missing data as data it simply hadn't been shown yet, and
    invent a plausible list to fill the gap. Exposed here rather than
    duplicated there so the mapping keeps exactly one definition.
    """
    return _CATEGORY_TABLES.get(category, _DEFAULT_TABLES)


def run(conn, category: str, retrieval_hint: str = "") -> list[dict]:
    """
    Returns only the profile fields relevant to category, never the full profile.
    Failure mode: return empty, continue (Part 7.3 spec).
    """
    try:
        relevant_tables = tables_for_category(category)
        full_profile = profile_store.get_profile(conn)
        return [row for row in full_profile if row["table"] in relevant_tables]
    except Exception as e:
        logger.error(f"Stage 4 memory lookup failed, returning empty: {e}")
        return []
