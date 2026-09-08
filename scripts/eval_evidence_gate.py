"""
Score the evidence gate against the labelled corpus and print the numbers.

Run from the repo root:

    python scripts/eval_evidence_gate.py

Reads backend/tests/evidence_cases.py - the same list backend/tests/
test_evidence_gate.py asserts - so a case cannot be measured here and missing
from the suite, or asserted there and quietly excluded from the score.

Why a separate script when the suite already asserts every case: a green suite
tells you nothing failed, not how the gate BEHAVES. Passing thirty rejections
is indistinguishable from a gate that rejects everything, and passing nine
accepts is indistinguishable from one that accepts everything, unless the two
are counted against each other. The numbers below are what makes that visible,
and what a later change to the marker lists can be checked against.

FALSE ACCEPT is the number that matters. A false reject costs a memory that
will be learned again the next time the user says it plainly, or through the
pending-candidate queue where the user is asked. A false accept is a belief
about the user, written into the profile, that the user never expressed - and
from then on it reaches every prompt PIP assembles. The two are not
symmetrical and the report does not present them as though they were.

Touches no database and needs no running backend: every case is a string and
a dict.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.evidence_gate import (  # noqa: E402
    AUTHENTICITY_STATES,
    SUPPORT_STATES,
    EvidenceLedger,
    adjudicate,
)
from backend.tests.evidence_cases import CASES, HELD_OUT  # noqa: E402


def _rule(char: str = "-") -> str:
    return char * 68


def _pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "  n/a"
    return f"{100.0 * numerator / denominator:5.1f}%"


def score(cases) -> list[dict]:
    results = []
    for case in cases:
        verdict = adjudicate(
            case["candidate"], EvidenceLedger.from_transcript(case["transcript"])
        )
        results.append({
            "case": case,
            "state": verdict.state,
            "detail": verdict.detail,
            "accepted": verdict.sufficient,
            "state_correct": verdict.state == case["expected_state"],
        })
    return results


def report(title: str, caveat: str, results: list[dict]) -> int:
    """Prints one set's numbers and returns how many were falsely accepted."""
    total = len(results)
    expected_accepts = [r for r in results if r["case"]["should_accept"]]
    expected_rejects = [r for r in results if not r["case"]["should_accept"]]

    correct_accepts = [r for r in expected_accepts if r["accepted"]]
    correct_rejects = [r for r in expected_rejects if not r["accepted"]]
    false_accepts = [r for r in expected_rejects if r["accepted"]]
    false_rejects = [r for r in expected_accepts if not r["accepted"]]

    # Whether a rejection was for the RIGHT REASON, not merely a rejection. A
    # fabricated quote turned away as "not entailing" is a gate that is right
    # by accident, and the next transcript is where the accident stops.
    authenticity = [r for r in results if r["case"]["question"] == "authenticity"]
    support = [r for r in results if r["case"]["question"] == "support"]
    authenticity_correct = [r for r in authenticity if r["state_correct"]]
    support_correct = [r for r in support if r["state_correct"]]

    print()
    print(_rule("="))
    print(title)
    print(_rule("="))
    print(f"  {caveat}")
    print()
    print(f"  total evidence/inference cases      {total:>5}")
    print(f"    expected to be accepted           {len(expected_accepts):>5}")
    print(f"    expected to be rejected           {len(expected_rejects):>5}")
    print()
    print(f"  correctly accepted                  {len(correct_accepts):>5}   "
          f"({_pct(len(correct_accepts), len(expected_accepts))} of expected accepts)")
    print(f"  correctly rejected                  {len(correct_rejects):>5}   "
          f"({_pct(len(correct_rejects), len(expected_rejects))} of expected rejects)")
    print(f"  FALSE ACCEPTS  (critical failure)   {len(false_accepts):>5}")
    print(f"  false rejects  (recoverable)        {len(false_rejects):>5}")
    print()
    print(f"  evidence-authenticity accuracy      {_pct(len(authenticity_correct), len(authenticity))}"
          f"   ({len(authenticity_correct)}/{len(authenticity)} cases in the exact expected state)")
    print(f"  inference-support accuracy          {_pct(len(support_correct), len(support))}"
          f"   ({len(support_correct)}/{len(support)} cases in the exact expected state)")
    print(f"  exact-state accuracy overall        "
          f"{_pct(sum(1 for r in results if r['state_correct']), total)}")
    print()

    print(_rule())
    print("verdicts by state")
    print(_rule())
    for state, count in sorted(Counter(r["state"] for r in results).items()):
        bucket = (
            "authenticity" if state in AUTHENTICITY_STATES
            else "support" if state in SUPPORT_STATES
            else "pass"
        )
        print(f"  {state:<28} {count:>3}   ({bucket})")
    print()

    wrong_state = [r for r in results if not r["state_correct"]]
    if wrong_state:
        print(_rule())
        print("rejected, but not for the reason expected")
        print(_rule())
        for r in wrong_state:
            print(f"  {r['case']['id']}")
            print(f"    expected {r['case']['expected_state']}")
            print(f"    got      {r['state']}  ({r['detail']})")
        print()

    if false_accepts:
        print(_rule("!"))
        print("FALSE ACCEPTS - an unsupported claim would have been believed")
        print(_rule("!"))
        for r in false_accepts:
            cand = r["case"]["candidate"]
            print(f"  {r['case']['id']}")
            print(f"    {cand['target_table']}.{cand['field_name']} = {cand['proposed_value']!r}")
            print(f"    on: {cand['evidence_text']!r}")
        print()

    print(_rule())
    print("examples correctly REJECTED")
    print(_rule())
    for r in correct_rejects:
        cand = r["case"]["candidate"]
        print(f"  [{r['state']}]")
        print(f"    evidence : {str(cand['evidence_text'])[:70]!r}")
        print(f"    claim    : {cand['target_table']}.{cand['field_name']} = {cand['proposed_value']!r}")
    print()

    print(_rule())
    print("examples correctly ACCEPTED")
    print(_rule())
    for r in correct_accepts:
        cand = r["case"]["candidate"]
        print(f"    evidence : {str(cand['evidence_text'])[:70]!r}")
        print(f"    claim    : {cand['target_table']}.{cand['field_name']} = {cand['proposed_value']!r}")
    print()

    if false_rejects:
        print(_rule())
        print("false rejects - supported claims the allowlist did not recognise")
        print(_rule())
        for r in false_rejects:
            cand = r["case"]["candidate"]
            print(f"  {r['case']['id']}")
            print(f"    evidence : {str(cand['evidence_text'])[:70]!r}")
            print(f"    got      : {r['state']}  ({r['detail']})")
        print()

    return len(false_accepts)


def evaluate() -> int:
    """
    Returns a process exit code: non-zero if anything was falsely accepted, in
    either set. A false reject never fails this - it is a cost the design
    accepts on purpose, and turning it into a build failure would create
    exactly the pressure to loosen the gate that the design exists to resist.
    """
    tuned = report(
        "PIP evidence gate - labelled corpus (TUNED)",
        "the gate was built against these; a perfect score here proves "
        "consistency, not generalisation",
        score(CASES),
    )
    untuned = report(
        "PIP evidence gate - held-out set (NOT tuned against)",
        "written after the gate was finished; this is where the false-reject "
        "cost is actually visible",
        score(HELD_OUT),
    )

    print(_rule("="))
    print("bottom line")
    print(_rule("="))
    print(f"  false accepts, tuned corpus     {tuned:>3}")
    print(f"  false accepts, held-out set     {untuned:>3}")
    print("  A false accept is an unjustified belief written into the profile.")
    print("  A false reject is a memory learned one session later, or via the")
    print("  pending-candidate queue where the user is asked directly.")
    print()
    return 1 if (tuned or untuned) else 0


if __name__ == "__main__":
    raise SystemExit(evaluate())
