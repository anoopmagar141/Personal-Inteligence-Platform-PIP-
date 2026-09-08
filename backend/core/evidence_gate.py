# PIP - Evidence Gate
#
# Sits between the Observer's extraction (Stage 11) and the Constitution's
# validation (Stage 12), in the trusted layer, and answers the one question
# neither of those two was ever asked:
#
#     Does the cited evidence actually support the proposed memory?
#
# WHAT WAS ALREADY THERE, AND WHY IT WAS NOT ENOUGH
#
# Stage 11 already grounds a candidate: _quote_is_grounded() checks that
# evidence_text appears somewhere in the transcript, which establishes "this
# text exists". Stage 12 + ConstitutionEnforcer then check policy: is the table
# writable, is the field immutable, is there enough evidence for the profile's
# age, is the field gated, does it conflict with something already stored.
#
# Neither step ever compares the evidence to the claim. So this passed end to
# end, on a real transcript, with no rule broken:
#
#     user says      "I've been comparing FastAPI and Flask."
#     candidate      preference_memory.preferred_tools = "Flask", label=explicit
#     grounding      PASS - the user really did say that
#     constitution   PASS - week 1-2 needs evidence >= 1 and an explicit label
#     result         WRITTEN
#
# The user never expressed a preference. The quote is genuine, the label is
# defensible ("explicit" only means the model claims the user said it), the
# table is writable, the threshold is met - and PIP now believes something
# about its user that its user never said. That is the failure this module
# exists to make impossible, and it is not reachable by making the Observer's
# prompt sterner: the Observer is the untrusted party, and asking it to
# self-police the exact judgement it is bad at is the mistake ADR-005 already
# records about confidence scoring.
#
# TWO SEPARATE QUESTIONS, DELIBERATELY NOT COLLAPSED
#
#   A. AUTHENTICITY - did the user actually provide this evidence?
#      Fabricated quotes, quotes that exist only in an Assistant turn, quotes
#      from a different conversation or a different profile, spliced or
#      truncated quotes, empty or malformed evidence.
#
#   B. ENTAILMENT - does that evidence support this particular claim?
#      A candidate can pass A completely and still fail B, which is the whole
#      point. Authenticity says the words are real; entailment says the words
#      mean what the candidate says they mean.
#
# The states below name both failures separately so a rejection is legible
# afterwards, in logs and in the evaluation harness, rather than collapsing
# into one undifferentiated "rejected".
#
# WHY THIS IS AN ALLOWLIST, AND WHY THAT IS THE RIGHT DIRECTION
#
# Entailment is decided by requiring the user's own words to carry a
# recognised support construction for the KIND of claim being made - a
# preference claim needs preference language, a skill claim needs
# demonstrated-ability language, a goal claim needs commitment language. That
# is not invented here: constitutional.json's memory_types block already says
# skill_memory is validated by "demonstrated_performance", preference_memory by
# "explicit_or_behavioral" and goal_memory by "commitment". This module is the
# first thing in the codebase that actually enforces those three words.
#
# Matching is an ALLOWLIST of support constructions, not a denylist of bad
# ones. That is a deliberate asymmetry. An unrecognised phrasing produces a
# false REJECT - the memory is not learned this session, and is learned the
# next time the user says it more plainly, or through the pending-candidate
# queue where the user is asked directly. An unrecognised phrasing under a
# denylist would produce a false ACCEPT - an unjustified belief written into
# the profile, silently, permanently, and reaching every prompt PIP assembles
# from then on. The brief is explicit that the second is the critical failure,
# so every ambiguous case in this file resolves toward rejection.
#
# The denylists that do exist here (negation, meaning-changing omissions,
# injection markers) only ever make the gate STRICTER on evidence that already
# matched the allowlist. They can cause a false reject; they cannot cause a
# false accept.
#
# WHY THIS RUNS BEFORE STAGE 12 AND NOT INSIDE IT
#
# stage_12.reinforce_evidence() writes to memory_observation_log, and that log
# is what lets a signal accumulate evidence_count across sessions until it
# clears the constitution's thresholds. A candidate whose evidence does not
# support it must therefore be stopped BEFORE reinforcement, not after
# validation - otherwise the same unsupported inference, repeated over three
# sessions, accumulates three observations and clears month_2_plus on its own.
# The gate would be watching the front door while the back door counted votes.
# That ordering constraint, not convenience, is why this is its own step in
# run_session_end() rather than a branch inside the enforcer.
#
# WHAT THIS IS NOT
#
# Not a second validation pipeline. A candidate must pass this gate AND the
# constitution; neither can approve anything on its own, and the write path is
# still exactly stage_13.run(). Not a model call either - nothing here asks an
# LLM whether an inference is justified, because that would put the untrusted
# party back in charge of the decision it is being checked on.

import re
from typing import Any, Literal, Optional, TypedDict

from backend.core.types import MemoryCandidate, ValidationResult


class EvidenceState:
    """
    Every terminal answer the gate can give, named separately so the reason a
    candidate died survives into the logs and the evaluation report.

    Plain string constants rather than an Enum: the value goes straight into
    ValidationResult.reason (a str) and into log lines, and every other status
    vocabulary in this codebase (ValidationResult.status, candidate state,
    Stage 13 outcome) is bare strings too.
    """

    # --- A. authenticity failures -----------------------------------------
    NO_EVIDENCE = "NO_EVIDENCE"
    EVIDENCE_INVALID = "EVIDENCE_INVALID"
    EVIDENCE_NOT_FOUND = "EVIDENCE_NOT_FOUND"
    EVIDENCE_NOT_USER_SOURCE = "EVIDENCE_NOT_USER_SOURCE"

    # --- B. entailment failures -------------------------------------------
    EVIDENCE_CONTRADICTORY = "EVIDENCE_CONTRADICTORY"
    EVIDENCE_NOT_ENTAILING = "EVIDENCE_NOT_ENTAILING"

    # --- pass --------------------------------------------------------------
    EVIDENCE_SUFFICIENT = "EVIDENCE_SUFFICIENT"


# Which of the two questions each failure answers. Kept as sets rather than
# inferred from the name so the evaluation harness can report authenticity
# accuracy and inference-support accuracy separately without re-deriving the
# taxonomy from string prefixes.
AUTHENTICITY_STATES = frozenset({
    EvidenceState.NO_EVIDENCE,
    EvidenceState.EVIDENCE_INVALID,
    EvidenceState.EVIDENCE_NOT_FOUND,
    EvidenceState.EVIDENCE_NOT_USER_SOURCE,
})

SUPPORT_STATES = frozenset({
    EvidenceState.EVIDENCE_CONTRADICTORY,
    EvidenceState.EVIDENCE_NOT_ENTAILING,
})

REJECTION_STATES = AUTHENTICITY_STATES | SUPPORT_STATES


# An authenticity failure is an integrity violation - the evidence is not what
# it claims to be - and maps to HARD_REJECT, the status the enforcer already
# uses for "this candidate is not admissible at all".
#
# An entailment failure maps to DISCARD: the evidence is genuine, it simply
# does not establish this claim, which is the same shape as a threshold
# violation. Both route to "rejected" in Stage 13 and neither writes anything;
# the distinction is for whoever reads the log, and for stage_13's
# contradiction logging, which must not count a gate rejection as behavioural
# evidence toward overriding a stated preference (see
# _maybe_log_behavioral_contradiction).
_STATUS_FOR_STATE = {
    EvidenceState.NO_EVIDENCE: "HARD_REJECT",
    EvidenceState.EVIDENCE_INVALID: "HARD_REJECT",
    EvidenceState.EVIDENCE_NOT_FOUND: "HARD_REJECT",
    EvidenceState.EVIDENCE_NOT_USER_SOURCE: "HARD_REJECT",
    EvidenceState.EVIDENCE_CONTRADICTORY: "DISCARD",
    EvidenceState.EVIDENCE_NOT_ENTAILING: "DISCARD",
}


# ---------------------------------------------------------------------------
# The ledger: the trusted record of who said what.
# ---------------------------------------------------------------------------

# Anchored at the start of a line, and deliberately NOT applied to a stripped
# line. session_lifecycle.format_transcript() indents any content line that
# would otherwise look like a role header, precisely so that an assistant turn
# containing the text "User: I prefer Flask" cannot manufacture a user turn
# here. Stripping first would undo that escaping and hand the forgery back.
_ROLE_LINE_RE = re.compile(r"^(User|Assistant):", re.IGNORECASE)

_APOSTROPHES = str.maketrans({"’": "'", "ʼ": "'", "´": "'"})


def normalize(text: Any) -> str:
    """
    The one normalisation used for every comparison in this module: lowercase,
    curly apostrophes folded to straight ones, all whitespace runs collapsed to
    single spaces.

    Whitespace collapsing matters more than it looks. Stage 11's
    _quote_is_grounded() normalises the QUOTE but searches the RAW transcript,
    so a quote spanning two lines of one message can never match there - an
    accident that happened to be safe. Here both sides are normalised, so a
    quote is matched against the turn it actually came from, which is what
    makes per-turn role attribution possible at all.
    """
    if not isinstance(text, str):
        return ""
    return " ".join(text.translate(_APOSTROPHES).lower().split())


class EvidenceTurn(TypedDict):
    index: int
    role: Literal["user", "assistant", "unknown"]
    text: str
    normalized: str


class EvidenceLedger:
    """
    The turns of ONE session, with roles attached - the only body of text a
    candidate from that session is allowed to cite.

    Scope is the mechanism behind two of the required rejections, and it is
    worth being explicit that they need no code of their own:

      - evidence from another CONVERSATION is not in this ledger, because the
        ledger is built from this session's transcript, so it fails
        EVIDENCE_NOT_FOUND like any other quote that is not there.
      - evidence from another PROFILE is not in this ledger for the same
        reason, and could not be even if the gate were absent: profiles are
        separate encrypted databases and a session's transcript is read
        through the connection of the profile it belongs to.

    A ledger is data, never a source of instructions. Turn text is whatever the
    user or the model produced; nothing in this module ever executes, follows
    or trusts it - it is only ever searched.
    """

    def __init__(self, turns: list[EvidenceTurn]):
        self.turns = turns

    @classmethod
    def from_transcript(cls, transcript: str) -> "EvidenceLedger":
        """
        Parses format_transcript()'s "User: ..." / "Assistant: ..." shape back
        into turns, with continuation lines belonging to the turn above them.

        A line appearing before any role header at all is recorded with role
        "unknown" rather than dropped or guessed at. Dropping it would let a
        quote grounded there read as EVIDENCE_NOT_FOUND - true, but for the
        wrong reason, and it would hide a malformed transcript. Guessing "user"
        would be exactly the unearned attribution this module exists to
        prevent. "unknown" is never a user source, so it fails closed.
        """
        turns: list[EvidenceTurn] = []
        buffer: list[str] = []
        role: Literal["user", "assistant", "unknown"] = "unknown"

        def flush() -> None:
            if not buffer:
                return
            text = "\n".join(buffer)
            turns.append({
                "index": len(turns),
                "role": role,
                "text": text,
                "normalized": normalize(text),
            })

        for line in (transcript or "").splitlines():
            match = _ROLE_LINE_RE.match(line)
            if match:
                flush()
                buffer = [line[match.end():].strip()]
                role = "user" if match.group(1).lower() == "user" else "assistant"
            else:
                buffer.append(line)
        flush()

        return cls([t for t in turns if t["normalized"]])

    def locate(self, quote: str) -> list[EvidenceTurn]:
        """Every turn whose own text contains this (already normalised) quote."""
        if not quote:
            return []
        return [t for t in self.turns if quote in t["normalized"]]

    def user_turns(self) -> list[EvidenceTurn]:
        return [t for t in self.turns if t["role"] == "user"]


# ---------------------------------------------------------------------------
# Marker vocabularies.
#
# Every list below is matched on WORD BOUNDARIES, never as a bare substring.
# That is load-bearing rather than tidiness: "i use" as a substring matches "I
# used Flask once for a university assignment", which is the exact sentence the
# brief names as something that must be rejected. With boundaries, "i used"
# does not match "i use", and that candidate dies where it should.
# ---------------------------------------------------------------------------

# Apostrophe-less spellings that would become a different, common English word
# and start matching sentences that mean nothing like the marker. "i'll" ->
# "ill" is the whole list so far, and it is enough of a reason to have one:
# "I feel ill about the deadline" is not a commitment.
_AMBIGUOUS_WITHOUT_APOSTROPHE = frozenset({"ill"})


def _phrases(*phrases: str) -> re.Pattern:
    """
    One word-boundary-anchored alternation over every listed phrase, plus the
    apostrophe-less spelling of each ("i'm building" also matches "im
    building").

    People type "im" and "ive" constantly, and a support marker that only
    matched the typographically correct form would produce false REJECTS on
    ordinary chat - the safe direction, but a needless amount of it. Generated
    rather than hand-listed because a hand-listed pair drifts the moment
    someone adds a phrase and remembers only one form.
    """
    expanded = set(phrases)
    for phrase in phrases:
        if "'" in phrase:
            bare = phrase.replace("'", "")
            if bare not in _AMBIGUOUS_WITHOUT_APOSTROPHE:
                expanded.add(bare)
    alternatives = "|".join(re.escape(p) for p in sorted(expanded, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)")


# A statement of preference or settled habit, in the user's own voice. Mention
# of a tool is not preference for it; comparing two is not choosing one.
_PREFERENCE_MARKERS = _phrases(
    "i prefer", "i preferred", "i like", "i love", "i enjoy", "i favour", "i favor",
    "i always use", "i always reach for", "i always", "i usually use", "i usually",
    "i normally", "i mostly use", "i mostly", "i tend to use", "i stick to",
    "i stick with", "i default to", "i settled on", "i've settled on",
    "my go-to", "my favourite", "my favorite", "i'd rather", "i would rather",
    "i switched to", "i've switched to", "i moved to", "i've moved to",
    "i use", "i'm using", "i am using", "i keep using", "i want", "i'd like",
    "i work in", "i live in",
    # Elliptical habit statements - real speech drops the subject constantly,
    # and "still using Neovim" or "Neovim is my editor of choice" is exactly the
    # settled behaviour constitutional.json means by preference_memory's
    # "explicit_or_behavioral" validation. Left out of the first draft of this
    # list, which then rejected two of the codebase's own realistic transcript
    # fixtures - a false reject is the safe direction to fail in, but it is
    # still a failure, and these are not ambiguous.
    "still using", "still on", "sticking with", "i'm sticking with",
    "of choice", "my daily driver", "my main", "i went with", "i'm going with",
    "i am going with", "i've gone with", "went with", "i settle on",
)

# Directives about how PIP should answer, split by which direction they point.
#
# A style claim is the one place where the stored value is a LABEL the user
# will never have said ("concise", "brief_summary_first", "full_detail" - the
# vocabulary onboarding's dropdown writes), so the usual anchor check, "does
# the claimed value appear in the user's words", cannot work here.
#
# Dropping the anchor entirely would leave a real hole: any directive about
# answering would then support any style label, so "give me more detail" could
# establish "concise". Splitting the markers by direction closes it without
# needing the user to have used the label - the evidence must point the same
# way the claim does. _style_family() below maps a proposed value onto one of
# these two sets, and a value that maps to neither is not supported by
# anything, which is the fail-closed answer for a label PIP would not know what
# to do with anyway.
_BRIEF_STYLE_MARKERS = _phrases(
    "keep it short", "keep it brief", "keep answers short", "keep answers brief",
    "be concise", "be brief", "be direct", "shorter", "briefer", "less detail",
    "don't explain", "dont explain", "no preamble", "just give me",
    "just tell me", "stop explaining", "answer briefly", "to the point",
    "tldr", "short answers", "brief summary", "summary first", "get to the point",
    "cut the", "skip the explanation",
)

_DETAILED_STYLE_MARKERS = _phrases(
    "more detail", "in more depth", "in depth", "spell it out", "explain more",
    "step by step", "walk me through", "longer", "thorough", "comprehensive",
    "full detail", "full explanation", "elaborate", "don't summarise",
    "don't summarize", "dont summarise", "dont summarize", "show your working",
    "show your work", "all the detail",
)

# Tokens in a proposed style value that decide which direction it points. Read
# from the value, never from the evidence, so the two halves stay independent.
_BRIEF_STYLE_TOKENS = ("brief", "concise", "short", "terse", "summary", "minimal", "direct", "tldr")
_DETAILED_STYLE_TOKENS = ("detail", "full", "verbose", "thorough", "depth", "long", "comprehensive", "elaborate")

# Ability actually demonstrated or asserted, per constitutional.json's
# skill_memory validation = "demonstrated_performance".
_SKILL_MARKERS = _phrases(
    "i've been using", "i have been using", "i've used", "i have used",
    "i've written", "i have written", "i wrote", "i write", "i've built",
    "i have built", "i built", "i build", "i've worked with", "i work with",
    "i worked with", "i maintain", "i've maintained", "i develop", "i program in",
    "i code in", "i'm experienced", "i am experienced", "i'm an expert",
    "i am an expert", "i'm advanced", "i'm proficient", "i'm comfortable with",
    "i am comfortable with", "i know", "i've shipped", "i ship",
    "years of", "years with", "years in", "professionally",
)

# Phrasings that CAP how much ability a quote can support, however confident
# the candidate is. Checked against the whole cited turn.
_NOVICE_MARKERS = _phrases(
    "learning", "learn", "new to", "just started", "beginner", "never used",
    "haven't used", "have not used", "trying to learn", "picking up",
    "getting started", "no experience", "first time", "tutorial", "comparing",
    "which one should", "should i use",
)

# What a level at or above _EXPERTISE_FLOOR needs the user's own words to say.
_EXPERTISE_MARKERS = _phrases(
    "expert", "advanced", "senior", "proficient", "years", "professionally",
    "daily", "every day", "for a living", "i maintain", "i've built",
    "i have built", "i build", "i've shipped", "fluent", "deeply",
)

# constitutional.json: goal_memory validation = "commitment". Wanting to know
# about something is not committing to it.
_GOAL_MARKERS = _phrases(
    "i'm going to", "i am going to", "i will", "i'll", "i plan to", "i'm planning",
    "i am planning", "i intend to", "i've decided", "i have decided", "i decided",
    "my goal", "my plan", "i need to", "i have to", "i must", "i want to",
    "i'm aiming", "i am aiming", "i'm building", "i am building",
    "i'm working on", "i am working on", "by the end of",
)

# Ownership of a thing being built, for active_projects.
_PROJECT_MARKERS = _phrases(
    "i'm building", "i am building", "i built", "i'm working on",
    "i am working on", "i started", "i've started", "i'm writing",
    "i am writing", "i'm developing", "i am developing", "my project",
    "my app", "my side project", "i call it", "working on",
)

# A stance AGAINST the value being claimed. Only ever consulted alongside the
# claimed value, so "I don't like Django" cannot reject a claim about Flask.
_NEGATIVE_STANCE_MARKERS = _phrases(
    "don't like", "dont like", "do not like", "didn't like", "didnt like",
    "don't use", "dont use", "do not use", "don't prefer", "dont prefer",
    "never use", "never used", "hate", "hated", "dislike", "disliked",
    "not a fan", "stopped using", "moved off", "moved away from",
    "switched away from", "switched off", "avoid", "avoiding", "gave up on",
    "can't stand", "cant stand", "no longer use", "no longer using",
    "wouldn't use", "wouldnt use",
)

# Words that, left OUT of a quote but present in the turn it was cut from,
# change what that turn actually said. A quote that drops one of these is a
# truthful string that is no longer a truthful summary.
#
# Scope-limiting phrases only. A bare "don't" / "never" / "hate" was in the
# first version of this list and had to come out: "keep it short when you
# answer, I don't need the preamble" had its qualifying clause REINFORCING the
# claim, and a bare negation anywhere in the remainder rejected it. Negation
# that actually bears on the claim is already handled, and handled better, by
# _negated_about() - which requires the negation and the claimed value to be in
# the same turn, so it can tell "I don't like Flask" from "I don't need the
# preamble". This list is for the other failure: a remainder that narrows or
# dates the claim without contradicting anything.
#
# "only" is listed bare, and the reason is the one false ACCEPT the held-out
# set produced: "I use Java only when a client insists on it" was cut down to
# "I use Java" and accepted, because the list held "only for" and the turn said
# "only when". Enumerating the prepositions that can follow "only" is the
# whack-a-mole this codebase has lost before; the restrictive word itself is
# the signal, and whatever follows it is decoration. Same for "unless",
# "except" and the "but i" / "if i" clause openers.
_MEANING_CHANGING_OMISSIONS = _phrases(
    "once", "twice", "used to", "no longer", "stopped", "not really", "but not",
    "but i", "if i", "only", "solely", "exclusively", "just for", "not for",
    "never for", "never actually", "apart from", "other than", "for a class",
    "for a university assignment", "for an assignment", "for one project",
    "when i have to", "when a client", "temporarily", "years ago", "back then",
    "back in", "thinking about", "considering", "might", "maybe", "trying out",
    "experimenting", "not sure", "unless", "except",
)

# Text addressed to the SYSTEM rather than said by a person. A genuine
# self-report never contains any of these, and their presence in something
# offered as the user's own words is the signature of an injection attempt
# reaching for the profile - whether it arrived in a pasted document, a
# relayed search result, or the Observer's own output.
#
# "remember that" is deliberately absent: a user really does say "remember
# that I use Neovim", and rejecting it would refuse the plainest and most
# consenting evidence there is.
_INJECTION_MARKERS = _phrases(
    "ignore previous", "ignore all previous", "ignore the above",
    "disregard previous", "disregard the above", "system:", "system prompt",
    "you must remember", "add to your memory", "store this in memory",
    "store in memory", "update your profile", "write to memory",
    "new instruction", "new instructions", "override your", "as an ai",
    "the user prefers", "the user is", "the user's", "user profile:",
)

_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "for", "with", "that", "this", "then",
    "his", "her", "its", "our", "their", "into", "onto", "from", "over",
    "use", "using", "used", "one", "all", "any", "some", "not", "but",
})

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#._-]*")

# Below this, a level claim needs the user to have said something about
# expertise; at or above it and paired with novice language, the claim is not
# supported at all. 0.4 is the constitution's own `inferred` confidence and the
# lower half of the 0.0-1.0 level scale, so a beginner still records as a
# beginner rather than as nothing.
_EXPERTISE_FLOOR = 0.7
_NOVICE_CEILING = 0.4

# A quote shorter than this is not a statement, it is a token. Three words is
# the shortest genuine self-report the marker lists can match ("I prefer
# Flask"), so it is the floor rather than a round number.
_MIN_EVIDENCE_WORDS = 3


def _content_tokens(text: Any) -> list[str]:
    """
    The words of `text` worth matching on, with a fallback that is not
    cosmetic.

    The length >= 3 filter keeps a multi-word anchor from being satisfied by
    some incidental "of" or "in". Applied without a fallback it also made every
    short-named technology unanchorable, and therefore unlearnable: Go, C, R,
    C#, F#. Found by the held-out set - "I would rather write Go than Java for
    anything with concurrency in it" was rejected as evidence for a Go
    preference on the grounds that it "never mentions 'Go'", which it plainly
    does.

    Falling back to every token when the filter empties the list fixes that
    without loosening the ordinary case: a short anchor is still matched on
    word boundaries, so "Go" matches "write Go than Java" and not "going".
    """
    tokens = [t for t in _TOKEN_RE.findall(normalize(text)) if t not in _STOPWORDS]
    substantial = [t for t in tokens if len(t) >= 3]
    return substantial or tokens


def _anchored(anchor: Any, quote: str) -> bool:
    """
    Whether the quote is actually ABOUT the thing the candidate claims.

    A quote can carry perfect preference language and still say nothing about
    the value being stored - "I always use Neovim" does not support
    preferred_tools = "Flask". Requiring the claimed value to appear in the
    user's own words is what stops a real quote being reused as evidence for an
    unrelated claim, and it is the check that rejects "the user is an advanced
    Python developer" from a sentence that never mentions Python.

    Multi-word anchors (a goal sentence, a project description) are matched
    token-wise rather than verbatim, because the candidate's wording is the
    model's and not the user's. One shared content token is enough - the
    support marker carries the weight, and demanding more would reject a
    correctly paraphrased goal.
    """
    tokens = _content_tokens(anchor)
    if not tokens:
        return False
    return any(re.search(rf"(?<!\w){re.escape(t)}(?!\w)", quote) for t in tokens)


def _negated_about(value: Any, text: str) -> bool:
    """
    Whether `text` takes a stance against `value`: it names the value (or part
    of it) and carries a negative-stance marker. Both halves are required, so a
    turn disliking something else entirely is not read as contradicting this
    claim.
    """
    return bool(_NEGATIVE_STANCE_MARKERS.search(text)) and _anchored(value, text)


# ---------------------------------------------------------------------------
# Support contracts, one per writable target_table.
#
# Each contract answers: what must the user's own words contain before this
# KIND of claim is established? The three that matter most are lifted straight
# from constitutional.json's memory_types block, which named the validation
# model for each table ("demonstrated_performance", "explicit_or_behavioral",
# "commitment") and until now was read by nothing at all.
# ---------------------------------------------------------------------------

class _Contract(TypedDict):
    # None means "this claim needs no support construction" - see
    # topic_interests below, the only table that is not a belief about the user.
    markers: Optional[re.Pattern]
    # Which part of the candidate must appear in the quote: the value being
    # stored, the field it is stored under, or nothing (see the style contract).
    anchor: Literal["proposed_value", "field_name", "none"]
    # An extra, claim-specific check run after the markers matched. Takes
    # (proposed_value, quote, user_sources) and returns a verdict to stop on or
    # None to continue.
    calibrate: Optional[str]


# Style claims: the markers are chosen per candidate by _adjudicate_style, so
# this entry's own marker set is None and the whole contract rests on the
# calibrator. anchor="none" for the reason spelled out above
# _BRIEF_STYLE_MARKERS - the stored value is a label, not the user's word.
_STYLE_CONTRACT: _Contract = {"markers": None, "anchor": "none", "calibrate": "style"}

# Keyed by (target_table, field_name) first and target_table second, because
# one table can hold two different KINDS of claim. preference_memory is the
# case: preferred_tools names a thing the user said out loud, while
# answer_style holds the same normalised label interaction_style does and is
# established by the same directives. Treating them alike meant the anchor
# check looked for the word "concise" in "keep it short when you answer" and
# rejected a perfectly good candidate.
_FIELD_CONTRACTS: dict[tuple[str, str], _Contract] = {
    ("preference_memory", "answer_style"): _STYLE_CONTRACT,
}

_CONTRACTS: dict[str, _Contract] = {
    "preference_memory": {
        "markers": _PREFERENCE_MARKERS, "anchor": "proposed_value", "calibrate": None,
    },
    "skill_memory": {
        "markers": _SKILL_MARKERS, "anchor": "field_name", "calibrate": "skill_level",
    },
    "goal_memory": {
        "markers": _GOAL_MARKERS, "anchor": "proposed_value", "calibrate": None,
    },
    "active_projects": {
        "markers": _PROJECT_MARKERS, "anchor": "field_name", "calibrate": None,
    },
    "interaction_style": _STYLE_CONTRACT,
    # topic_interests records what was discussed, not a belief about who the
    # user is, so it takes no support markers - a question is as good as an
    # assertion for "this came up". It still has to be the user who raised it,
    # and the topic still has to appear in their own words.
    "topic_interests": {"markers": None, "anchor": "field_name", "calibrate": None},
}


class EvidenceVerdict:
    """
    One state, plus the sentence explaining it - the same shape the memory
    layer already uses for a refusal (a ValueError carrying the reason), so the
    detail is readable by whoever has to understand why a memory was not kept.
    """

    def __init__(self, state: str, detail: str = ""):
        self.state = state
        self.detail = detail

    @property
    def sufficient(self) -> bool:
        return self.state == EvidenceState.EVIDENCE_SUFFICIENT

    def to_validation_result(self) -> ValidationResult:
        """
        The gate's answer expressed in the vocabulary Stage 13 already routes
        on, so no new write path and no new outcome value is introduced. reason
        is the state name itself, which is what lets stage_13 recognise a gate
        rejection and what the evaluation harness reads back.
        """
        if self.sufficient:
            raise ValueError("a sufficient verdict has no rejection to express")
        return ValidationResult(_STATUS_FOR_STATE[self.state], reason=self.state)

    def __repr__(self) -> str:
        return f"EvidenceVerdict(state={self.state}, detail={self.detail!r})"


_SUFFICIENT = EvidenceVerdict(EvidenceState.EVIDENCE_SUFFICIENT)


def adjudicate(candidate: MemoryCandidate, ledger: EvidenceLedger) -> EvidenceVerdict:
    """
    The whole gate, in the order the questions have to be asked.

    Authenticity first (1-4): there is no point asking whether words support a
    claim before establishing that the user said them. Contradiction next (5),
    ahead of entailment, so "I don't use Flask" is reported as contradicting
    the claim rather than merely failing to support it - both reject, but only
    one of them tells the reader what actually happened. Entailment (6), then
    the partial-quote check (7), which is the one failure that only exists for
    a quote that DOES support the claim: it is about what the quote left behind
    in the turn it was cut from.
    """
    quote = normalize(candidate.get("evidence_text"))
    target_table = candidate.get("target_table")
    proposed_value = candidate.get("proposed_value")
    field_name = candidate.get("field_name")

    # 1. Is there evidence at all?
    if not quote:
        return EvidenceVerdict(
            EvidenceState.NO_EVIDENCE,
            "the candidate cites no evidence text",
        )

    # 2. Is what is cited a statement, and is it a person's statement?
    if len(quote.split()) < _MIN_EVIDENCE_WORDS:
        return EvidenceVerdict(
            EvidenceState.EVIDENCE_INVALID,
            f"cited evidence is {len(quote.split())} word(s); too short to establish anything",
        )
    injected = _INJECTION_MARKERS.search(quote)
    if injected:
        return EvidenceVerdict(
            EvidenceState.EVIDENCE_INVALID,
            "cited evidence is addressed to the system rather than spoken by the user: "
            f"{injected.group(0)!r}",
        )

    # 3. Does it exist in this session at all?
    located = ledger.locate(quote)
    if not located:
        return EvidenceVerdict(
            EvidenceState.EVIDENCE_NOT_FOUND,
            "cited evidence does not appear in this session's transcript",
        )

    # 4. Did the USER say it? A quote that lives only in an Assistant turn is
    #    PIP quoting itself back as though the user had spoken - the most
    #    direct way there is for a model to author a belief about its own user.
    user_sources = [t for t in located if t["role"] == "user"]
    if not user_sources:
        roles = sorted({t["role"] for t in located})
        return EvidenceVerdict(
            EvidenceState.EVIDENCE_NOT_USER_SOURCE,
            f"cited evidence appears only in {', '.join(roles)} turn(s), "
            "not in anything the user said",
        )

    contract = _FIELD_CONTRACTS.get((target_table, field_name)) or _CONTRACTS.get(target_table)
    if contract is None:
        # Fails closed on an unrecognised table, matching the enforcer's own
        # posture. A table added to the write path without a support contract
        # gets no memories rather than ungoverned ones.
        return EvidenceVerdict(
            EvidenceState.EVIDENCE_NOT_ENTAILING,
            f"no support contract defined for target_table {target_table!r}",
        )

    anchor_value = {
        "proposed_value": proposed_value,
        "field_name": field_name,
        "none": None,
    }[contract["anchor"]]

    # 5. Do the user's own words argue AGAINST this claim - in the quote
    #    itself, or anywhere else they spoke this session? An unresolved
    #    contradiction inside one session means the claim is not established,
    #    whichever statement came last. Deliberately not "the newest wins":
    #    letting recency settle it is how a passing remark overwrites a
    #    considered one.
    if anchor_value is not None:
        if _negated_about(anchor_value, quote):
            return EvidenceVerdict(
                EvidenceState.EVIDENCE_CONTRADICTORY,
                "the cited evidence states the opposite of the claim",
            )
        for turn in ledger.user_turns():
            if _negated_about(anchor_value, turn["normalized"]):
                return EvidenceVerdict(
                    EvidenceState.EVIDENCE_CONTRADICTORY,
                    "the user contradicted this claim elsewhere in the session: "
                    f"{turn['text'][:120]!r}",
                )

    # 6. Does the evidence support THIS claim?
    if anchor_value is not None and not _anchored(anchor_value, quote):
        return EvidenceVerdict(
            EvidenceState.EVIDENCE_NOT_ENTAILING,
            f"the cited evidence never mentions {str(anchor_value)[:60]!r}",
        )

    markers = contract["markers"]
    if markers is not None and not markers.search(quote):
        return EvidenceVerdict(
            EvidenceState.EVIDENCE_NOT_ENTAILING,
            f"the cited evidence carries no {target_table} support language - "
            "mentioning something is not asserting it",
        )

    calibrator = _CALIBRATORS.get(contract["calibrate"])
    if calibrator is not None:
        verdict = calibrator(proposed_value, quote, user_sources)
        if verdict is not None:
            return verdict

    # 7. Did the quote survive being cut out of its turn? A quote that is a
    #    fragment of a longer sentence can be word-for-word accurate and still
    #    misrepresent it, which is why this runs even though grounding passed.
    verdict = _adjudicate_partial_quote(quote, user_sources)
    if verdict is not None:
        return verdict

    return _SUFFICIENT


def _adjudicate_skill_level(
    proposed_value: Any, quote: str, user_sources: list[EvidenceTurn]
) -> Optional[EvidenceVerdict]:
    """
    skill_memory stores a number, and a number is a much sharper claim than the
    sentence it came from. "I've used Python" supports that the user has used
    Python; it does not support 0.9.

    Two calibration rules, both one-directional - they can only lower what a
    quote is allowed to support:

      - novice language anywhere in the cited turn caps the level at
        _NOVICE_CEILING. "I'm learning Rust" cannot establish an advanced Rust
        level however confidently the model asserts one.
      - a level at or above _EXPERTISE_FLOOR requires the user to have said
        something about expertise. This is the rule that rejects the brief's
        own example: "I've been comparing FastAPI and Flask" -> "the user is an
        advanced Python developer".
    """
    try:
        level = float(proposed_value)
    except (TypeError, ValueError):
        # Stage 11 already drops a non-numeric level, so reaching here means a
        # candidate arrived from somewhere else. Unreadable level, unsupportable
        # claim.
        return EvidenceVerdict(
            EvidenceState.EVIDENCE_INVALID,
            f"skill level {proposed_value!r} is not a number, so no evidence can support it",
        )

    turn_text = user_sources[0]["normalized"]
    if level > _NOVICE_CEILING and _NOVICE_MARKERS.search(turn_text):
        return EvidenceVerdict(
            EvidenceState.EVIDENCE_NOT_ENTAILING,
            f"the user described themselves as still learning; that cannot support level {level}",
        )
    if level >= _EXPERTISE_FLOOR and not _EXPERTISE_MARKERS.search(turn_text):
        return EvidenceVerdict(
            EvidenceState.EVIDENCE_NOT_ENTAILING,
            f"level {level} claims expertise the user never asserted",
        )
    return None


def _style_family(proposed_value: Any) -> Optional[str]:
    """
    Which direction a style label points, read from the label alone.

    Checked longest-token-first is unnecessary here because the two vocabularies
    do not overlap: "brief_summary_first" carries only brief-side tokens and
    "full_detail" only detailed-side ones. A value carrying both would be
    incoherent as a style anyway, and returning None for it is the right answer.
    """
    value = normalize(proposed_value)
    if not value:
        return None
    brief = any(t in value for t in _BRIEF_STYLE_TOKENS)
    detailed = any(t in value for t in _DETAILED_STYLE_TOKENS)
    if brief and not detailed:
        return "brief"
    if detailed and not brief:
        return "detailed"
    return None


def _adjudicate_style(
    proposed_value: Any, quote: str, user_sources: list[EvidenceTurn]
) -> Optional[EvidenceVerdict]:
    """
    A style claim is supported only by a directive pointing the same way the
    claim does.

    "adaptive" - profile_store.DEFAULT_INTERACTION_STYLE - deliberately maps to
    no family and is therefore never supportable. It is the value a profile
    already holds when the user has expressed no preference, so an Observer
    proposing it is proposing to learn nothing, and there is no sentence a user
    can say that establishes "I have no preference about answer length" as a
    positive fact.
    """
    family = _style_family(proposed_value)
    if family is None:
        return EvidenceVerdict(
            EvidenceState.EVIDENCE_NOT_ENTAILING,
            f"style value {str(proposed_value)[:40]!r} points in no direction "
            "the user's words could confirm",
        )
    markers = _BRIEF_STYLE_MARKERS if family == "brief" else _DETAILED_STYLE_MARKERS
    if not markers.search(quote):
        return EvidenceVerdict(
            EvidenceState.EVIDENCE_NOT_ENTAILING,
            f"the cited evidence asks for nothing {family}, so it cannot establish "
            f"{str(proposed_value)[:40]!r}",
        )
    return None


def _adjudicate_partial_quote(
    quote: str, user_sources: list[EvidenceTurn]
) -> Optional[EvidenceVerdict]:
    """
    Rejects a quote that is a strict fragment of the user turn it came from and
    left a meaning-changing qualifier behind.

    "I'd use Flask, but not for anything I have to maintain" contains the
    substring "I'd use Flask". Every check up to here passes on that substring:
    it is genuine, the user said it, it carries preference language, it names
    the value. Only the words the quote stopped short of reveal that it does
    not mean what it appears to.

    Judged against the MOST COMPLETE turn the quote appears in - if the user
    said it plainly once and hedged it elsewhere, the plain statement stands. A
    quote equal to its whole turn skips this entirely, which is the ordinary
    case for a well-behaved extraction.
    """
    for turn in user_sources:
        remainder = turn["normalized"].replace(quote, " ")
        if not remainder.strip():
            # Quote IS the turn: nothing was left out, nothing to misrepresent.
            return None
        if not _MEANING_CHANGING_OMISSIONS.search(remainder):
            return None

    hit = _MEANING_CHANGING_OMISSIONS.search(
        user_sources[0]["normalized"].replace(quote, " ")
    )
    return EvidenceVerdict(
        EvidenceState.EVIDENCE_INVALID,
        f"the quote is a fragment of a turn that qualifies it ({hit.group(0)!r} was left out)",
    )


# Named rather than referenced directly in _CONTRACTS so the contract table
# stays a plain data literal that can be read top to bottom without jumping
# forward to function definitions that do not exist yet at that point in the
# file.
_CALIBRATORS = {
    "skill_level": _adjudicate_skill_level,
    "style": _adjudicate_style,
    None: None,
}
