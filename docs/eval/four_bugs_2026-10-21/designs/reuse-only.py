"""
Angle "reuse-only": a replacement for evidence_gate._topic_raising_text that fixes D-46 with the gate's own
_HYPOTHETICAL_MARKERS and reads no new word. D-41 is NOT fixed here; the reason is at the bottom of this docstring and
in the comment above the function.

Same contract as the gate's function: `quote` is the normalised (lower-case) quote, `user_sources` the user turns it
was found in; the result is the part of the quote that raises a topic as the USER's, "" for none.

Why D-41 stays open under this angle. Nothing in evidence_gate.py separates the user's own words from someone else's
INSIDE one sentence: the ledger's roles work per turn, the first-person support lists match reported speech as
readily as the user's own ("Priya keeps telling me I need to try Svelte" carries _GOAL_MARKERS' "i need to", and
goal_memory accepts "try Svelte" from it today), and _STOPWORDS's his/her/its/our/their are there for token matching,
not for who is speaking. The one reading that needs no word at all - the "I" must be its clause's subject, taken as
"at most one word before it in its clause" (clauses cut as _style_marker_is_negated cuts them) - was built and
measured (variant_position.py): it refuses the recorded marathon sentence and five of the six reported sentences in
probes_mine.json, and it also refuses nine of the thirteen first-person sentences there that a user plainly said about
themselves ("Last week I started reading about Raft", "At work I maintain a Kafka cluster", "Rust is something I keep
coming back to"). No position threshold can tell "he thinks I" from "last week I". The recorded D-41 sentence can be
refused cheaply only by reading the possessive "my" on its own (variant_possessive.py), a word the gate holds only
inside phrases ("my goal", "my project"); that is outside this angle, so it is not shipped here.
"""
from backend.core.evidence_gate import _HYPOTHETICAL_MARKERS, _TOKEN_RE, _only_ever_asked, _sentence_pieces


# D-46 (FREEZE_LIST §7.67, found by the replays of the three gate fixes): "If I ever had a free summer I might look at
# Elixir, but honestly that is not going to happen. What is it actually good at?" was written as the user's topic
# "Elixir", a trap the long-chat set labels. D-33's rule (§7.61) takes any sentence with the pronoun "I" as the user
# raising a topic, and the hypothetical check that every other table runs at step 6 of adjudicate() is skipped for
# topics, because that check refuses the whole quote and a topic quote is allowed to be a question.
#
# So the check comes back here, with the same list the other tables use and nothing added to it, but per SENTENCE and
# only on the first-person statements: a statement the user frames as a might-be ("might", "maybe", "someday", "if i
# ever") does not raise its topic, and a question still does, whatever hedge it carries ("Maybe this is silly, but
# what is a monad?" is a question the user asked; rule 2 of the owner's brief). Per sentence rather than per clause,
# because a hypothetical's scope runs past a comma: "If I ever get time, I'll learn Zig" cut at the comma would leave
# "I'll learn Zig" standing on its own. Per sentence rather than per quote, so "I use Go at work. Maybe I'll try Rust
# later." still raises Go.
#
# A quote cut short of its hedge ("I'll look at Zig" out of "Maybe I'll look at Zig") is not this function's job:
# step 7 (_adjudicate_partial_quote) already refuses a quote that left "might", "maybe" or "if i" behind in its turn,
# for topics too. "someday" is not on that list, so a quote cut to exclude it still passes (a known limit, as it is
# for every other table).
#
# The cost, measured, not hidden: the gate's list cannot tell a hedge about the topic from a hedge about something
# else in the same sentence. M-1(a)'s blind grader graded topic "Swift" from "I might learn Swift someday, not sure
# yet." as supported (item 102), and this refuses it; so are "I use Go daily, maybe too much." and "I've been reading
# about Zookeeper and might write a toy version." The owner's statement of D-46 is that a hypothetical first-person
# sentence should not raise a topic, and "Maybe someday I'll look at Zig" means what the Swift sentence means, so the
# two cannot be split without reading meaning; the refusal is the safe direction.
def topic_raising_text(quote: str, user_sources: list) -> str:
    pieces = _sentence_pieces(quote)
    # Unchanged from D-33: a quote cut short of its sentence's question mark is still that question.
    if pieces and not pieces[-1][1] and _only_ever_asked(quote, user_sources):
        pieces[-1] = (pieces[-1][0], True)
    return " ".join(
        text.strip()
        for text, is_question in pieces
        if is_question
        or ("i" in _TOKEN_RE.findall(text) and not _HYPOTHETICAL_MARKERS.search(text))
    )
