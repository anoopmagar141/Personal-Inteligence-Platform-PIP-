"""
PROBE: is information the user rejected re-introduced? Real session-end path
(grounding, real evidence gate, Stage 12 + Constitution, Stage 13); only the
Observer's LLM is scripted, as in test_observer_governance.py.
"""
import pytest

from backend.memory import candidate_store
from backend.tests.test_observer_governance import GATED, _observe, _pending, conn  # noqa: F401


@pytest.mark.parametrize("said, gated, stored", GATED)
def test_RI1_dismissed_question_after_same_transcript_is_observed_again(conn, said, gated, stored):
    """The same transcript observed twice (e.g. a catch-up re-run) after the user said 'no'."""
    _observe(conn, f"User: {said}\n", gated)
    q = [p for p in _pending(conn) if p["target_table"] == gated["target_table"]]
    assert len(q) == 1
    candidate_store.dismiss_memory_candidate(conn, q[0]["id"])
    _observe(conn, f"User: {said}\n", gated)
    again = [p for p in _pending(conn) if p["target_table"] == gated["target_table"]]
    print(gated["target_table"], "re-queued after dismissal (same words):", len(again))
    assert not again, "a dismissed question came back from the same words"
    assert conn.execute(stored).fetchone() is None


@pytest.mark.parametrize("said, gated, stored", GATED)
def test_RI2_pending_question_is_not_duplicated(conn, said, gated, stored):
    _observe(conn, f"User: {said}\n", gated)
    _observe(conn, f"User: {said}\n", gated)
    q = [p for p in _pending(conn) if p["target_table"] == gated["target_table"]]
    print(gated["target_table"], "pending rows after two observations:", len(q))
    assert len(q) == 1, "the same question was queued twice"
