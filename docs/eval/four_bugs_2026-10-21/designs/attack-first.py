"""
Candidate replacement for evidence_gate._topic_raising_text (angle "attack-first"): D-41 and D-46.

    topic_raising_text(quote, user_sources) -> str

Same contract as the gate's function: `quote` is the normalised, label-stripped quote, `user_sources` the user turns
it was found in; the result is the part of the quote that raises a topic as the USER's, "" for none. It only ever
returns less than the D-33 rule returns (FREEZE_LIST §7.61), never more: every sentence it keeps, D-33 keeps.
"""
import re

from backend.core.evidence_gate import (
    _HYPOTHETICAL_MARKERS,
    _TOKEN_RE,
    _only_ever_asked,
    _sentence_pieces,
)

# ---------------------------------------------------------------------------
# The grammar words this rule reads, and nothing else.
#
# The owner's rule is no new list of PHRASINGS: D-33 got away with reading only
# the pronoun "I" (whose sentence it is, not what it means), and D-41 and D-46
# are both cases where "I" is present and the sentence is still not the user
# raising a topic. Telling them apart needs a little more grammar, so every word
# below is a closed-class word (an auxiliary verb, a pronoun or determiner, a
# conjunction), named here in full so it can be weighed. None of them is a verb
# of saying ("says", "thinks", "reckons", "keeps telling"): that list is
# open-ended, and the D-41 sentence would have come back next week as "my
# friend swears I should". The one list the gate already has for this,
# _HYPOTHETICAL_MARKERS, is reused rather than copied.
#
# _GOAL_MARKERS was tried for "someone else's plan for the user" and dropped:
# it holds the user's own ongoing activity too ("I'm building", "I'm working
# on", "I want to"), so "My boss knows I'm working on the Kafka migration" and
# "You know I'm building a compiler in Rust" were refused.
#
# Words read that no gate list holds today: shouldn't, ought, could(n't), may,
# won't, mustn't, needn't, he, she, they, everyone, everybody, someone,
# somebody, so (and the apostrophe-less spellings of the n't forms).
# Words read that gate lists already hold: i (D-33), should ("should i use"),
# would(n't) and i'd ("i would rather", "i'd rather", "wouldn't use"), might
# (_HYPOTHETICAL_MARKERS), will, i'll, must, need, have to, going to, am ("i
# will", "i'll", "i must", "i need to", "i have to", "i'm going to", "i am going
# to" in _GOAL_MARKERS), my, your, you, me, his, her, our, their, and, but, or,
# that, if ("if i", "if i ever"). Punctuation: , ; : and the dashes.
# ---------------------------------------------------------------------------

# Auxiliaries that put what follows them out of the indicative: "I should",
# "I'd", "I could" say what someone thinks the user ought to do, would like or
# could do, never what the user does. The apostrophe-less spellings are here
# for the reason _phrases() gives: people type "shouldnt".
_IRREALIS = frozenset({
    "should", "shouldn't", "shouldnt", "ought", "would", "wouldn't", "wouldnt",
    "could", "couldn't", "couldnt", "may", "might",
})

# The irrealis ones plus the future and obligation auxiliaries. Read only where
# someone else opens the clause or the user sets a condition: "she says I'll
# love it" and "my tutor reckons I need to revise calculus" are someone else's
# plan for the user, while "This year I will finally learn Rust" and "For my
# thesis I need to understand Bayesian statistics" are the user's own. "can"
# is not here: "My laptop is so slow I can't run Docker" is a problem the user
# has, and "can" is how people say so.
_AUXILIARIES = _IRREALIS | {
    "will", "won't", "wont", "must", "mustn't", "mustnt", "need", "needn't", "neednt",
}
# The same two meanings said in two words: "I have to" is "I must", "I'm going
# to" is "I will". Without them "my professor said I must read up on Markov
# chains" is caught and "my professor said I have to" is not, which is the
# different-words failure the owner's rule is about.
_PERIPHRASTIC = (("have", "to"), ("going", "to"))

# Words that open a clause about SOMEONE ELSE: the third-person and second-
# person subject pronouns, the indefinite ones, and the possessive determiners
# ("my friend", "our team lead"). "I", "we" and "it" are deliberately absent:
# "I" is the user, "we" includes the user (D-33's "We're moving everything to
# Kubernetes" is a separate, open question), and "it looks like I need Docker"
# is the user's own need.
_OTHER_PEOPLE = frozenset({
    "he", "she", "they", "you", "everyone", "everybody", "someone", "somebody",
    "my", "your", "his", "her", "our", "their",
})

# A clause ends at a comma, semicolon, colon or dash, or before one of these.
_COORDINATORS = frozenset({"and", "but", "so", "or"})
_CLAUSE_BREAK_RE = re.compile(r"[,;:–—]|\s-\s")

# A word, apostrophes kept so "i'd" and "can't" are one word each; never ending
# in the sentence's own full stop ("should." is "should").
_WORD_RE = re.compile(r"[a-z0-9](?:[a-z0-9+#._'-]*[a-z0-9+#])?")


def _words(text: str) -> list[tuple[str, int]]:
    return [(m.group(), m.start()) for m in _WORD_RE.finditer(text)]


def _is_i(word: str) -> bool:
    # "i", "i'm", "i've", "i'd", "i'll": the same pronoun D-33 reads.
    return word == "i" or word.startswith("i'")


def _i_takes(words: list[tuple[str, int]], k: int, auxiliaries: frozenset) -> bool:
    """Whether the I at words[k] is followed directly by one of `auxiliaries` ("I should", or its own "I'd"/"I'll")."""
    word = words[k][0]
    if (word == "i'd" and "would" in auxiliaries) or (word == "i'll" and "will" in auxiliaries):
        return True
    after = [w for w, _ in words[k + 1:k + 4]]
    if after[:1] and after[0] in auxiliaries:
        return True
    if auxiliaries is _AUXILIARIES:
        if word == "i" and after[:1] == ["am"]:
            after = after[1:]
        return tuple(after[:2]) in _PERIPHRASTIC
    return False


def _clauses(sentence: str) -> list[tuple[int, int]]:
    """Clause spans of one sentence: split at clause punctuation and before a coordinator."""
    words = _words(sentence)
    starts = [0]
    for k in range(1, len(words)):
        word, at = words[k]
        before = words[k - 1]
        if _CLAUSE_BREAK_RE.search(sentence[before[1] + len(before[0]):at]) or word in _COORDINATORS:
            starts.append(at)
    bounds = sorted(set(starts)) + [len(sentence)]
    return list(zip(bounds, bounds[1:]))


def _reported(clause: str) -> bool:
    """
    Whether this clause's "I" is someone else's word about the user rather than the user speaking (D-41).

    D-33 read a sentence as the user's when it had the pronoun "I", and "My
    friend says I should do a full marathon but that's crazy" has one: M-1(a)
    accepted it twice as the user's topic "marathon" (FREEZE_LIST §7.63). In
    reported speech the "I" is not where its clause starts - someone else is
    the subject, and the "I" sits inside what they say - and the verb after it
    is not the user's indicative: they say what the user SHOULD do, WOULD like,
    COULD be. That is what is read here, in three shapes:

      - "... me I ...": the user is the object of someone telling them about
        themselves ("Priya keeps telling me I need to try Svelte", "everybody
        tells me I'm a natural at Go"). A comma in between breaks it, so
        "trust me, I love Rust" stays the user's.
      - a clause that someone or something other than "I" opens, whose first
        "I" takes an irrealis auxiliary: "Sam thinks I'd love Elm", "the
        recruiter said I should brush up on Kubernetes", "apparently I should
        be using Docker". The opener is not identified (a name is invisible
        once the quote is lower-cased), which is why this is the general case.
      - a clause opened by another PERSON (a pronoun or a possessive: "my
        mum", "she", "our team lead") whose first "I" takes a future or
        obligation auxiliary: "my mum keeps saying I need to learn piano",
        "she says I'll love it". That is someone else's plan for the user.
        Without the person opener this is NOT read, because "This year I will
        finally learn Rust" and "For my thesis I need to understand Bayesian
        statistics" are the user's own plans and needs.

    The known cost is the second shape: "Honestly I'd love to get better at
    SQL", "Right now I should be studying for the CKA exam" and "These days I
    would rather write Go than Java" are the user's own words and are refused,
    because nothing in the grammar words separates "Honestly I'd love" from
    "Sam thinks I'd love"; the comma does ("Honestly, I'd love ..." is kept).
    Chat openers typed without a comma ("yeah I'd like to try Rust") go the
    same way. Refusing both is the safe direction (a false reject), which is
    the gate's posture everywhere else; exempting the gate's own preference
    phrases ("I'd rather", "I'd like") was considered and not done, because
    "Sam thinks I'd like Elm" would then be the user's topic again.
    """
    words = _words(clause)
    while words and words[0][0] in _COORDINATORS:
        words = words[1:]
    i_at = [k for k, (w, _) in enumerate(words) if _is_i(w)]
    for k in i_at:
        before = [w for w, _ in words[max(0, k - 2):k]]
        if before and (before[-1] == "me" or before == ["me", "that"]):
            return True
    first = i_at[0]
    if first == 0:
        return False
    if _i_takes(words, first, _IRREALIS):
        return True
    return words[0][0] in _OTHER_PEOPLE and _i_takes(words, first, _AUXILIARIES)


def _hypothetical(sentence: str) -> bool:
    """
    Whether a sentence is a hypothetical or a conditional about the user (D-46).

    Every table but topic_interests refuses a quote carrying the gate's
    _HYPOTHETICAL_MARKERS; topics skipped that check because a question is
    evidence for them, and D-33 then read "If I ever had a free summer I might
    look at Elixir, but honestly that is not going to happen" as the user's
    topic "Elixir" (a labelled trap in the long-chat set, FREEZE_LIST §7.67).
    The same list is reused here, per SENTENCE and never on a question: a
    hedge in one sentence does not sink a plain statement in the next, and
    "Could I use Elixir if I ever needed websockets?" is still a question the
    user asked.

    The list cannot see a counterfactual it has no phrase for ("If I had more
    time I would learn Haskell", "I'd learn Rust if I had the time"). Those are
    read from the same grammar as _reported: the user's own condition ("if I",
    a phrase the gate already lists among its meaning-changing omissions) and
    another "I" in the sentence taking an auxiliary ("I would", "I'll").
    "I wonder if I could use Elixir" keeps its topic: the only "I" with an
    auxiliary is the condition's own. "If I'm honest, I spend most evenings on
    chess puzzles" keeps it too: no "I" in it takes one.
    """
    if _HYPOTHETICAL_MARKERS.search(sentence):
        return True
    words = _words(sentence)
    for k in range(len(words) - 1):
        if words[k][0] == "if" and _is_i(words[k + 1][0]):
            condition = k + 1
            if any(_is_i(w) and j != condition and _i_takes(words, j, _AUXILIARIES)
                   for j, (w, _) in enumerate(words)):
                return True
    return False


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans, at = [], 0
    for piece, _ in _sentence_pieces(text):
        spans.append((at, at + len(piece)))
        at += len(piece)
    return spans


def _owned_text(text: str, lo: int, hi: int) -> str:
    """
    The part of text[lo:hi] (a statement the quote holds) that the user says as their own, or "".

    Judged on the WHOLE sentence it was cut from, not on the quote: the model
    cuts quotes (M-1(a) item 56 is "My friend says I should do a full
    marathon", the turn's sentence without "but that's crazy"), and a cut that
    starts at the "I" ("I should do a full marathon") would otherwise lose the
    very words that say whose it is. Only what is inside the quote is
    returned, so the topic still has to be named in the user's quoted words.

    Within a sentence, a clause with someone else's "I" is taken out; a clause
    with no "I" at all stays as D-33 left it, because "My coworker says Zig is
    overrated, but I find it fascinating" names the topic there and the user's
    "I" refers back to it. The sentence raises a topic only if a clause of the
    user's own has its "I" inside the quote.
    """
    keep, own = [], False
    for s0, s1 in _sentence_spans(text):
        if s1 <= lo or s0 >= hi:
            continue
        sentence = text[s0:s1]
        if _hypothetical(sentence):
            return ""
        for c0, c1 in _clauses(sentence):
            a, b = max(lo, s0 + c0), min(hi, s0 + c1)
            if a >= b:
                continue
            clause = sentence[c0:c1]
            has_i = any(_is_i(w) for w, _ in _words(clause))
            if has_i and _reported(clause):
                continue
            if has_i and any(_is_i(w) for w, _ in _words(text[a:b])):
                own = True
            keep.append(text[a:b].strip())
    return " ".join(k for k in keep if k) if own else ""


def topic_raising_text(quote: str, user_sources: list) -> str:
    """
    What in a quote raises a topic as the USER's (D-33, D-41, D-46): the
    questions they asked, and the statements they made in the first person -
    their own, as they are, not someone else's word about them (D-41) and not
    a hypothetical (D-46).

    Questions are untouched, including a quote cut short of its question mark
    (see _only_ever_asked): asking is raising. A statement still needs the
    pronoun "I" in the quote, exactly as D-33 required; this only takes away.
    """
    pieces = _sentence_pieces(quote)
    if pieces and not pieces[-1][1] and _only_ever_asked(quote, user_sources):
        pieces[-1] = (pieces[-1][0], True)
    kept, at = [], 0
    for text, is_question in pieces:
        lo, hi = at, at + len(text)
        at = hi
        if is_question:
            kept.append(text.strip())
            continue
        if "i" not in _TOKEN_RE.findall(text):
            continue
        # Everywhere the user said these words, for the reason _only_ever_asked
        # gives: said as their own once, it stands. A quote the ledger could
        # not place (never the case after step 3) is judged on its own words.
        owned, placed = "", False
        for turn in user_sources:
            source = turn["normalized"]
            found = source.find(quote)
            while found != -1 and not owned:
                placed = True
                owned = _owned_text(source, found + lo, found + hi)
                found = source.find(quote, found + 1)
            if owned:
                break
        if not placed:
            owned = _owned_text(quote, lo, hi)
        if owned:
            kept.append(owned)
    return " ".join(kept)
