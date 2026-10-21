"""
Angle "clause-position": a candidate replacement for evidence_gate._topic_raising_text (D-41, D-46).

Same contract as the gate's function: given the normalised quote and the user turns it was found in, return the
part of the quote that raises a topic as the USER's ("" for none). Written to be pasted into evidence_gate.py in
place of _topic_raising_text; it only uses names that module already defines.
"""
import re

from backend.core.evidence_gate import (
    _ABBREVIATION_RE,
    _HYPOTHETICAL_MARKERS,
    _SENTENCE_END_RE,
    _TOKEN_RE,
    _only_ever_asked,
    _sentence_pieces,
)

# Where one clause of a sentence stops and the next starts, for the purpose of
# asking whose clause it is. Punctuation only, no words: a comma is what makes
# "Honestly, I keep thinking about WebAssembly" and "Right, I keep coming back
# to this because our sync is broken" (M-1(a) items 13, 55, 103, all graded S)
# open with "I", and a colon is what makes "One more thing about me: I want to
# pass the AWS Solutions Architect Associate exam by March" (items 6 and 90,
# graded S) open with it. Without the comma those three S items are lost; without
# the colon those two are. "and" / "but" are NOT boundaries, because reading them
# would be a list of words - see the cost written up under _raised_in_first_person.
_CLAUSE_BREAK_RE = re.compile(r"[,;:]")

# Opening quotation marks (straight, curly double, curly single-open; a curly
# single CLOSE is folded into the apostrophe by normalize() and cannot be told
# from one). A clause whose "I" sits after one of these is someone's quoted
# words: `My friend said, "I think you'd love Elixir."` has a clause that opens
# with "I" after its comma, and that "I" is the friend.
_QUOTATION_MARKS = "\"“”‘"

# How many words may stand in a clause before its "I". One, and the number is
# the whole of the rule: putting words in the user's mouth takes a speaker and
# a verb of saying or thinking before the "I" - "My friend says I should do a
# full marathon" (D-41), "Priya keeps telling me I need to try Svelte", "She
# said I'd love Elm" - so at least two words. A single word before "I" is the
# ordinary way people start a sentence about themselves: "Lately I've been
# reading about consensus protocols", "So I started reading the Rust book",
# "Recently I", "Honestly I", "Also I". Zero (the clause must OPEN with "I")
# was measured too and costs exactly those: the dev probes go from 10/10 to 8/10
# ("Lately I've been ...", "..., so I started ...") and six one-word-lead
# sentences of a second, self-written probe set become false rejects ("Recently
# I", "So I", "Honestly I", "Actually I", "Also I", "When I get home I'm going
# to try Deno"), for two more right refusals ("Apparently I should be learning
# Kubernetes"; "If I had more time I'd learn Haskell") that one word cannot
# tell from "Lately I". Two words before "I" ("These days I", "At work I",
# "Ok so I") are refused either way: "My friend says I" is two words too.
_WORDS_BEFORE_I = 1


def _sentence_lead(text: str, at: int) -> str:
    """What the user said in the same sentence before `text[at]`."""
    prefix = text[:at]
    start = 0
    for end in _SENTENCE_END_RE.finditer(prefix):
        if end.group() == "." and _ABBREVIATION_RE.search(prefix[: end.start()]):
            continue
        start = end.end()
    return prefix[start:]


def _source_leads(quote: str, user_sources: list) -> list[str]:
    """
    For every place the user said the quote, the part of its sentence the quote
    left out in front.

    A quote is often cut out of a sentence, and where a clause starts is a fact
    about the sentence, not about the cut: "I should do a full marathon", cut
    from "My friend says I should do a full marathon", opens with "I" only
    because the Observer dropped the friend. So the first clause of a quote is
    judged with what precedes it in the turn. Every occurrence is tried, for the
    reason _only_ever_asked() gives: if the user once said it plainly, the plain
    statement stands.
    """
    leads = []
    for turn in user_sources:
        text = turn["normalized"]
        at = text.find(quote)
        while at != -1:
            leads.append(_sentence_lead(text, at))
            at = text.find(quote, at + 1)
    return leads or [""]


def _raised_in_first_person(sentence: str, clause_start: int, clause_end: int, quote_start: int) -> bool:
    """
    Whether sentence[clause_start:clause_end] is a clause the user says about
    themselves: its "I" is its first or second word (see _WORDS_BEFORE_I), that
    "I" is inside the quote, it is not inside quotation marks, and no
    hypothetical frame was opened before it.

    The "I" has to be the quote's own (token.start() >= quote_start): what the
    turn said in front of a quote may only ever take a clause away, never add
    one. "our sync is broken", cut from "Right, I keep coming back to this
    because our sync is broken", stays refused as it is today - a clause the
    Observer cut the speaker off is not read as said by them.

    D-46 (FREEZE_LIST §7.67): "If I ever had a free summer I might look at
    Elixir, but honestly that is not going to happen" is refused by the word
    count alone ("if" stands before "I"), but "Maybe I'll try Kotlin" and "If I
    ever get a quiet month, I'd like to look at OCaml" are not: one word, and a
    comma. Every other table refuses a quote carrying _HYPOTHETICAL_MARKERS; here
    a marker counts only when it starts BEFORE the clause's "I", anywhere earlier
    in the sentence - "maybe I'll", "someday I", "if I ever ..., I'd". A marker
    after the "I" is the user's own hedge about something that is theirs, and is
    left alone: "I might learn Swift someday, not sure yet" was graded S for the
    topic Swift in M-1(a) (item 102, §7.63), and "I think the bug might be in my
    Redis config" is about Redis. That is a choice with a cost, written down
    rather than hidden: "I might try Kotlin one day" still raises Kotlin.
    Reading the marker anywhere up to the clause's end instead (one comparison)
    was measured: it refuses that sentence, and also flips item 102 (graded S)
    and the Redis sentence, for the same dev-probe score.

    What this cannot see, because seeing it would take words: a reported frame
    joined by "and"/"but" inside one clause ("I love hiking and my friend says I
    should do a marathon"), a frame that itself opens with "I" ("I heard from my
    friend that I should do a triathlon"), hearsay in one word ("Apparently I
    should be learning Kubernetes"), a reporting clause set off by a comma
    ("According to my boss, I need to learn Terraform"), and a conditional
    without one of the gate's markers ("If I had more time I'd learn Haskell").
    Each of those is accepted, as every one of them is by the rule this replaces.
    """
    tokens = list(_TOKEN_RE.finditer(sentence, clause_start, clause_end))
    for token in tokens[: _WORDS_BEFORE_I + 1]:
        if token.group() != "i":
            continue
        if token.start() < quote_start:
            return False
        if any(mark in sentence[clause_start:token.start()] for mark in _QUOTATION_MARKS):
            return False
        if any(marker.start() < token.start() for marker in _HYPOTHETICAL_MARKERS.finditer(sentence)):
            return False
        return True
    return False


def _first_person_clauses(piece: str, lead: str) -> list[bool]:
    """
    For each clause of a statement `piece` (split at _CLAUSE_BREAK_RE), whether
    it is raised in the first person, the piece being preceded in its sentence by
    `lead` (empty unless the quote was cut from mid-sentence).
    """
    sentence = lead + piece
    quote_start = len(lead)
    breaks = [m.end() for m in _CLAUSE_BREAK_RE.finditer(piece)]
    starts = [0] + breaks
    ends = breaks + [len(piece)]
    lead_clause_start = 0
    for m in _CLAUSE_BREAK_RE.finditer(lead):
        lead_clause_start = m.end()
    flags = []
    for index, (start, end) in enumerate(zip(starts, ends)):
        clause_start = lead_clause_start if index == 0 else quote_start + start
        flags.append(_raised_in_first_person(sentence, clause_start, quote_start + end, quote_start))
    return flags


def topic_raising_text(quote: str, user_sources: list) -> str:
    """
    What in a quote raises a topic as the USER's (D-33, D-41, D-46): the
    questions they asked, and the clauses they said about themselves.

    D-33 (FREEZE_LIST §7.61) read a sentence as the user's when it contained the
    pronoun "I" anywhere. Reported speech has one too: "My friend says I should
    do a full marathon but that's crazy" was accepted as the user's topic
    "marathon" and graded D twice by M-1(a) (items 56 and 81, §7.63; D-41). The
    pronoun still decides, and it is still the only word read - what changes is
    WHERE it has to be: at the head of its clause, with at most one word before
    it (see _WORDS_BEFORE_I), because a frame that hands the "I" to someone else
    ("my friend says", "my manager thinks") needs a speaker and a verb in front.

    Kept per clause, not per sentence. "My friend says I should do a full
    marathon, but I think that's crazy" has a clause of the user's ("but I think
    that's crazy"), and keeping its whole sentence for that would hand the
    friend's marathon back to the user. The cost is a topic named only outside
    the user's clause: "My team uses Kafka; I'm trying to get my head around it"
    no longer raises Kafka (the D-33 rule accepted it).

    A question is kept whole, whoever it mentions: asking about a topic is
    raising it (the owner's rule, and the D-33 contract). A quote cut short of
    its sentence's question mark is still that question (see _only_ever_asked).
    """
    pieces = _sentence_pieces(quote)
    if pieces and not pieces[-1][1] and _only_ever_asked(quote, user_sources):
        pieces[-1] = (pieces[-1][0], True)
    leads = _source_leads(quote, user_sources)
    kept = []
    for index, (text, is_question) in enumerate(pieces):
        if is_question:
            kept.append(text.strip())
            continue
        # Only the quote's first piece can have been cut from mid-sentence; every
        # later piece starts where a sentence of the quote ended.
        flags = [False] * len(_CLAUSE_BREAK_RE.split(text))
        for lead in (leads if index == 0 else [""]):
            flags = [a or b for a, b in zip(flags, _first_person_clauses(text, lead))]
        kept.extend(
            clause.strip() for clause, keep in zip(_CLAUSE_BREAK_RE.split(text), flags) if keep and clause.strip()
        )
    return " ".join(kept)
