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
#
# goal_memory is in personal_question for the same reason, found the same way:
# "what goals do I have?" classifies as personal_question (it is one - "my
# goals" is as personal as "my skills"), and without this it retrieved
# identity, preferences and projects but not the goals it literally names,
# so the model correctly answered "I don't have that recorded" against eight
# recorded goals. The bug was invisible while goal_memory was empty, because
# "not looked up" and "the user has none" render identically - which is the
# distinction tables_for_category() exists to preserve.
_CATEGORY_TABLES = {
    "personal_question": {"identity", "preference_memory", "interaction_style", "skill_memory", "active_projects", "goal_memory", "topic_interests"},
    "project_question": {"active_projects", "goal_memory", "interaction_style"},
    "project_continuation": {"active_projects", "goal_memory", "interaction_style"},
    "coding_question": {"skill_memory", "preferred_tools", "interaction_style", "document_access_patterns"},
    # topic_interests and document_access_patterns are observational rather than
    # stated, so they are looked up where knowing what the user keeps coming
    # back to actually changes an answer - explaining something, or researching
    # it - rather than being added to _DEFAULT_TABLES and charged to every
    # prompt including one-off general knowledge.
    "technical_explanation": {"interaction_style", "topic_interests"},
    "research_request": {"interaction_style", "topic_interests", "document_access_patterns"},
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
