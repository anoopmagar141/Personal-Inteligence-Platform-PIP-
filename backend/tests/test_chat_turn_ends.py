"""
D-16 (docs/FREEZE_LIST.md §7.23): every chat turn ends, on the socket, with
exactly one terminal event - done, error or stopped. The Flutter client keeps
its composer locked until one arrives (chat_view.dart, _isStreaming), so a turn
that ends without one leaves the chat "writing" until the user leaves it.

Through the real /ws/chat and the real pipeline. test_ws_chat.py replaces
pipeline.run with a fake in every test, and the fake always ends in "done" -
which is how a pipeline path that ended with no terminal event at all went
unseen: when Stage 8 left no provider to ask, the pipeline returned its error
result to the server, which keeps that result for bookkeeping and forwards
nothing.

Events are read on a background thread. TestClient's receive_json() blocks with
no timeout, and the defect under test is an event that never comes.

The second half is D-22 (§7.25): a pipeline that raises instead of returning.
The exception left ws_chat's loop and closed the socket mid-turn, so the client
got no terminal event there either - and lost the connection with it.

The third is what a review of D-22 found (§7.44), and the tests it found
missing:
- D-24: a Stop that reached the server with nothing left to stop was answered
  with "message is required". D-22's early return made it easy to hit: the
  turn's Stop is only read between events, so one sent while the pipeline was
  blocked and then raised was still queued when the turn ended.
- D-25: D-22 added a fold of every forwarded event, and put it after the send
  and outside the guard. A token that is not text - the OpenAI-compatible
  provider yields a structured `content` as it finds it - was sent to the
  client and then raised out of ws_chat's loop, D-22's symptom again, reached
  by the line D-22 added.
- The tests never counted terminal events after the LAST turn of a test (the
  first terminal ends _Events.turn(), so a duplicate was only ever seen when
  it leaked into a following turn), never raised after an `error` or a
  `stopped` (the guard against a second terminal event was only exercised after
  `done`), and never looked at the log the client is sent to.

The last is D-26 (§7.45), the one that review left open: the database writes
around a turn were not guarded, so a write that failed closed the connection -
with no terminal event if it came before the turn, and with the reply already
shown if it came after. Not an exotic failure: foreign keys are enforced, so a
message sent with a project id that no longer exists fails in
create_conversation, and a conversation deleted under an open chat fails in
append_message. Those two are the real triggers used below; the rest are
injected, since a locked or full database cannot be produced on demand.
"""

import datetime
import logging
import queue
import sqlite3
import threading
import time

import pytest
from fastapi.testclient import TestClient

from backend.api import server
from backend.core import auth, response_cache
from backend.core.types import TIMESTAMP_FORMAT
from backend.memory import conversation_store, llm_endpoint_store, vector_store
from backend.providers.base_provider import ProviderUnavailableError
from backend.providers.ollama_provider import OllamaProvider
from backend.stages import stage_06_web_search as stage_06
from backend.tests.test_consent_before_sending import _Stub
from backend.tests.test_ws_chat import _onboard, _session_count

TERMINAL = ("done", "error", "stopped")


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setattr(vector_store, "CHROMA_DB_PATH", str(tmp_path / "chroma"))
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(vector_store, "_collection", None)


@pytest.fixture(autouse=True)
def token(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token"))
    return auth.get_or_create_token(tmp_path / "api_token")


@pytest.fixture(autouse=True)
def no_real_observer_calls(monkeypatch):
    # Every turn here leaves the connection with unobserved turns, so closing
    # it would run the Observer against whatever model is on this machine.
    async def fake_run_observer_now(*args, **kwargs):
        return {"memory_results": [], "decision_results": []}

    monkeypatch.setattr(server.session_lifecycle, "run_observer_now", fake_run_observer_now)


@pytest.fixture(autouse=True)
def fresh_caches(monkeypatch):
    # A cached answer would end the turn without consulting any provider.
    response_cache.clear()
    monkeypatch.setattr(stage_06, "_cache", {})
    yield
    response_cache.clear()


@pytest.fixture
def ollama_down(monkeypatch):
    def refuse(self, *args, **kwargs):
        raise ProviderUnavailableError("Ollama is not running")
        yield  # pragma: no cover - makes this a generator like the real chat

    monkeypatch.setattr(OllamaProvider, "is_available", lambda self: False)
    monkeypatch.setattr(OllamaProvider, "chat", refuse)


@pytest.fixture
def stub():
    s = _Stub()
    yield s
    s.close()


def _add_remote_endpoint(tmp_path, url):
    conn = server.open_app_connection(str(tmp_path / "pip.db"), None)
    try:
        llm_endpoint_store.add_endpoint(
            conn, provider_id="cloud-box", label="cloud box", base_url=url,
            model_name="m", is_local=False,
        )
    finally:
        conn.close()


def _grant(tmp_path, provider_id):
    conn = server.open_app_connection(str(tmp_path / "pip.db"), None)
    try:
        server.api_grant_consent(conn, provider_id, "full_inference")
    finally:
        conn.close()


class _Events:
    """Everything the server sends, read off the socket as it arrives."""

    def __init__(self, ws):
        self._queue: queue.Queue = queue.Queue()
        threading.Thread(target=self._read, args=(ws,), daemon=True).start()

    def _read(self, ws):
        try:
            while True:
                self._queue.put(ws.receive_json())
        except Exception:
            pass  # the socket closed

    def next(self, timeout=20.0):
        return self._queue.get(timeout=timeout)

    def turn(self, timeout=20.0):
        """Every event up to and including the first terminal one."""
        events = []
        deadline = time.monotonic() + timeout
        while True:
            try:
                event = self._queue.get(timeout=max(deadline - time.monotonic(), 0.01))
            except queue.Empty:
                pytest.fail(
                    f"the turn never ended: no done, error or stopped within {timeout}s "
                    f"(received {[e['type'] for e in events]})"
                )
            events.append(event)
            if event["type"] in TERMINAL:
                return events

    def settled(self, seconds=0.5):
        """
        What arrives in the next half second, once a turn has ended. Nothing
        may. turn() stops at the first terminal event, so on its own it can
        never show a second one: a duplicate was only ever noticed when it
        happened to land at the start of the NEXT turn, and the last turn of a
        test has no next turn.
        """
        time.sleep(seconds)
        left = []
        while True:
            try:
                left.append(self._queue.get_nowait())
            except queue.Empty:
                return left


def _terminals(events):
    return [e for e in events if e["type"] in TERMINAL]


def _tokens(events):
    return [e["data"] for e in events if e["type"] == "token"]


def test_a_turn_no_provider_may_answer_ends_with_one_error(tmp_path, token, stub, ollama_down):
    """
    Ollama is down, so the chain is the one remote endpoint - which has no
    consent. Stage 8 removes it and nothing is left to ask. The user must be
    told so, once, and must be able to send the next message: the second turn
    starts clean, with no stray terminal event left over from the first.
    """
    _add_remote_endpoint(tmp_path, stub.url)

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works"})
        first = events.turn()

        ws.send_json({"message": "explain how a linked list works"})
        second = events.turn()
        after = events.settled()

    for turn in (first, second):
        assert [e["type"] for e in _terminals(turn)] == ["error"]
        assert "consent" in turn[-1]["data"].lower()
        assert not any(e["type"] == "token" for e in turn)
    # The second turn begins with its own work, not with a late event from the first.
    assert second[0]["type"] == "stage"
    assert after == [], "something more was sent after the last turn had ended"
    assert stub.sent == [], "an unconsented endpoint was sent the prompt"


def test_control_ollama_down_with_nothing_else_configured_ends_with_one_error(token, ollama_down):
    """Ollama stays in the chain when it is the only provider, so Stage 9
    tries it and reports the failure. This path already ended properly."""
    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works"})
        turn = events.turn()
        after = events.settled()

    assert [e["type"] for e in _terminals(turn)] == ["error"]
    assert "All providers failed" in turn[-1]["data"]
    assert after == [], "something more was sent after the turn had ended"


def test_control_a_consented_endpoint_still_streams_its_answer(tmp_path, token, stub, ollama_down):
    _add_remote_endpoint(tmp_path, stub.url)
    _grant(tmp_path, "cloud-box")

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works"})
        turn = events.turn()
        after = events.settled()

    assert [e["type"] for e in _terminals(turn)] == ["done"]
    assert "".join(_tokens(turn)) == "STUB-REPLY"
    assert len(stub.sent) == 1
    assert after == [], "something more was sent after the turn had ended"


# --- D-22: a pipeline that raises -------------------------------------------


def _fails_at_once():
    raise ValueError("unexpected response shape from the model server")
    yield  # pragma: no cover - makes this a generator like the real chat


def _fails_after(text):
    def step():
        yield text
        raise ValueError("unexpected response shape from the model server")
    return step


def _answers(text):
    def step():
        yield text
    return step


def _yields(*tokens):
    def step():
        yield from tokens
    return step


@pytest.fixture
def ollama_script(monkeypatch):
    """
    Ollama available; each chat() call plays the next scripted step. A
    ValueError is not one of the two provider errors Stage 9 falls back on,
    so it travels out of the pipeline - the crash, from a place that is
    reachable: the shipped providers turn every error they raise into a
    provider error, so what actually gets out is a failure elsewhere (a
    database read, the cache write) or a value the provider yielded that
    nothing downstream can use (D-25, below).
    """
    script = []

    def chat(self, messages, *args, **kwargs):
        yield from script.pop(0)()

    monkeypatch.setattr(OllamaProvider, "is_available", lambda self: True)
    monkeypatch.setattr(OllamaProvider, "chat", chat)
    return script


class _Gate:
    """
    A scripted provider that stops partway through a turn until the test lets
    it go. `reached` is set once the provider is actually waiting, so the test
    sends nothing until the server is blocked inside next() - which is after
    the last time it looks at what the client has sent. Without that, a Stop
    sent too early is read by the turn itself and the test passes for the wrong
    reason.
    """

    def __init__(self):
        self.reached = threading.Event()
        self.release = threading.Event()

    def wait(self):
        self.reached.set()
        assert self.release.wait(10), "the test never released the provider"


def _blocks_then_fails(gate):
    def step():
        gate.wait()
        raise ValueError("unexpected response shape from the model server")
        yield  # pragma: no cover - makes this a generator like the real chat
    return step


def _streams_until_stopped(gate):
    def step():
        yield "A"
        gate.wait()
        # Paced, and bounded: Stop is read between events, so the provider has
        # to keep producing for it to take effect, and must not run forever if
        # it never does.
        for _ in range(200):
            yield "x"
            time.sleep(0.05)
    return step


def _messages(tmp_path, conversation_id):
    conn = server.open_app_connection(str(tmp_path / "pip.db"), None)
    try:
        return [(m["role"], m["content"]) for m in conversation_store.get_messages(conn, conversation_id)]
    finally:
        conn.close()


def _conversation_id(turn):
    return next(e["data"]["conversation_id"] for e in turn if e["type"] == "session_info")


def test_a_pipeline_that_raises_before_answering_ends_the_turn_with_one_error(token, ollama_script, caplog):
    """
    The turn ends with one error, and the connection survives it: the next
    message on the same socket is answered. The exception's own text stays in
    the backend log - an exception can carry whatever it was handed, model
    output or message text included, and the client is told only that the
    reply was abandoned. It is told that the details are in the log, so they
    have to be.
    """
    caplog.set_level(logging.ERROR, logger="backend.api.server")
    ollama_script.extend([_fails_at_once, _answers("LOCAL-OLLAMA")])

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works"})
        first = events.turn()

        ws.send_json({"message": "explain how a linked list works"})
        second = events.turn()
        after = events.settled()

    assert [e["type"] for e in _terminals(first)] == ["error"]
    assert not any(e["type"] == "token" for e in first)
    assert first[-1]["data"]
    assert "unexpected response shape" not in first[-1]["data"]
    assert any(
        r.name == "backend.api.server" and r.exc_info
        and isinstance(r.exc_info[1], ValueError)
        and "unexpected response shape" in str(r.exc_info[1])
        for r in caplog.records
    ), "the client was sent to the backend log, and the traceback is not in it"

    assert second[0]["type"] == "stage"
    assert [e["type"] for e in _terminals(second)] == ["done"]
    assert "".join(_tokens(second)) == "LOCAL-OLLAMA"
    assert after == [], "something more was sent after the last turn had ended"


def test_a_pipeline_that_raises_mid_reply_ends_with_one_error_and_saves_no_partial_reply(tmp_path, token, ollama_script):
    """
    Part of the reply had already streamed. The client drops it when the error
    arrives (chat_view.dart's error case), so it is not saved as an assistant
    turn either: what is stored is what the user was left looking at. The
    user's own message is kept.
    """
    ollama_script.extend([_fails_after("PARTIAL"), _answers("LOCAL-OLLAMA")])

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works"})
        first = events.turn()

        ws.send_json({"message": "explain how a linked list works"})
        second = events.turn()
        after = events.settled()

    assert [e["type"] for e in first if e["type"] in ("token",) + TERMINAL] == ["token", "error"]
    assert [e["type"] for e in _terminals(second)] == ["done"]
    assert after == [], "something more was sent after the last turn had ended"
    # Only the first turn's rows are certain here: the server saves a turn
    # after sending its terminal event, and the first turn's save finished
    # before the second message was taken. So: the user's first message, and
    # next to it either nothing yet or the second message - never the partial.
    rows = _messages(tmp_path, _conversation_id(first))
    assert rows[0] == ("user", "explain how a hash map works")
    assert rows[1:2] in ([], [("user", "explain how a linked list works")])
    assert ("assistant", "PARTIAL") not in rows


def test_a_pipeline_that_raises_after_its_answer_is_done_sends_nothing_more(tmp_path, token, ollama_script, monkeypatch):
    """
    The crash comes after "done" has already reached the client - here, while
    the answer is being cached. The turn has ended; a second terminal event
    would arrive at the start of the next turn and end that one before it
    began. The answer the user was shown is saved, as any finished answer is.
    """
    ollama_script.extend([_answers("FIRST-ANSWER"), _answers("SECOND-ANSWER")])

    def refuse(*args, **kwargs):
        raise RuntimeError("cache write failed")

    monkeypatch.setattr(server.pipeline.response_cache, "set", refuse)

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works"})
        first = events.turn()

        ws.send_json({"message": "explain how a linked list works"})
        second = events.turn()
        after = events.settled()

    assert [e["type"] for e in _terminals(first)] == ["done"]
    assert second[0]["type"] == "stage"
    assert [e["type"] for e in _terminals(second)] == ["done"]
    assert after == [], "something more was sent after the last turn had ended"
    assert _messages(tmp_path, _conversation_id(first))[:2] == [
        ("user", "explain how a hash map works"),
        ("assistant", "FIRST-ANSWER"),
    ]


def test_a_pipeline_that_raises_after_an_error_has_gone_out_sends_nothing_more(token, ollama_down, monkeypatch):
    """
    The same promise after `error`. Stage 9 reports "All providers failed" and
    the pipeline then fails in delivery. That error is the turn's terminal
    event; a second one - the generic "something went wrong" - would be read as
    the start of the next turn's. The guard against it used to be exercised
    only after `done`, and a version of it that remembered only `done` passed
    every test.
    """
    def refuse(*args, **kwargs):
        raise RuntimeError("delivery failed")

    monkeypatch.setattr(server.pipeline.stage_10, "run", refuse)

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works"})
        first = events.turn()

        ws.send_json({"message": "explain how a linked list works"})
        second = events.turn()
        after = events.settled()

    for turn in (first, second):
        assert [e["type"] for e in _terminals(turn)] == ["error"]
        assert "All providers failed" in turn[-1]["data"]
    assert second[0]["type"] == "stage", "a second terminal event was left over from the first turn"
    assert after == [], "something more was sent after the last turn had ended"


def test_a_pipeline_that_raises_after_a_stop_has_gone_out_sends_nothing_more(tmp_path, token, ollama_script, monkeypatch):
    """
    And after `stopped`. The user pressed Stop, the answer was cut short and
    saved as shown, and delivery then failed: the turn already ended on the
    `stopped`, so nothing more goes out.
    """
    gate = _Gate()
    ollama_script.extend([_streams_until_stopped(gate), _answers("SECOND-ANSWER")])

    def refuse(*args, **kwargs):
        raise RuntimeError("delivery failed")

    monkeypatch.setattr(server.pipeline.stage_10, "run", refuse)

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works"})
        assert gate.reached.wait(10), "the provider was never reached"
        ws.send_json({"type": "stop"})
        time.sleep(0.3)  # long enough for the server to have queued it
        gate.release.set()
        first = events.turn()

        ws.send_json({"message": "explain how a linked list works"})
        second = events.turn()
        after = events.settled()

    assert [e["type"] for e in _terminals(first)] == ["stopped"]
    assert second[0]["type"] == "stage", "a second terminal event was left over from the first turn"
    assert [e["type"] for e in _terminals(second)] == ["done"]
    assert after == [], "something more was sent after the last turn had ended"
    shown = "".join(_tokens(first))
    assert shown.startswith("A")
    assert _messages(tmp_path, _conversation_id(first))[:2] == [
        ("user", "explain how a hash map works"),
        ("assistant", shown),
    ]


def test_a_pipeline_that_ends_without_completing_ends_the_turn_with_one_error(token, monkeypatch):
    """
    A generator that stops with no pipeline_complete used to raise out of the
    loop. Nothing in the pipeline does this today - Stage 9 always ends in
    done, error or stopped - so it is the transport's own check that is being
    held to its word here.
    """
    hint = {"decision_log_hit": False, "web_search_used": False, "cache_hit": False, "model_loading": False}

    def truncated(*args, **kwargs):
        yield {"type": "stage_hint", "data": hint}
        yield {"type": "token", "data": "PART "}

    def whole(*args, **kwargs):
        yield {"type": "stage_hint", "data": hint}
        yield {"type": "token", "data": "WHOLE "}
        yield {"type": "done", "data": None}
        yield {"type": "pipeline_complete", "data": {
            "trace_id": "t1", "response_text": "WHOLE ", "status": "success", "stage_hints": {},
        }}

    plays = [truncated, whole]
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: plays.pop(0)(*a, **kw))

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works"})
        first = events.turn()

        ws.send_json({"message": "explain how a linked list works"})
        second = events.turn()
        after = events.settled()

    assert [e["type"] for e in _terminals(first)] == ["error"]
    assert _tokens(first) == ["PART "]
    assert second[0]["type"] == "stage_hint"
    assert [e["type"] for e in _terminals(second)] == ["done"]
    assert after == [], "something more was sent after the last turn had ended"


# --- D-24: a Stop with nothing left to stop ---------------------------------


def test_a_stop_with_nothing_streaming_is_dropped_not_answered(token, ollama_script):
    """
    ws_chat_client.stop() says sending a Stop when nothing is streaming is
    harmless because the backend just drops it. The backend answered it with
    "message is required": the main loop reads whatever the turn's own loop
    did not, and a Stop is a dict with no message. The client turns any error
    into a visible "Error:" row.
    """
    ollama_script.append(_answers("LOCAL-OLLAMA"))

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"type": "stop"})
        ws.send_json({"message": "explain how a hash map works"})
        turn = events.turn()
        after = events.settled()

    assert [e["type"] for e in _terminals(turn)] == ["done"], (
        f"the Stop was answered: {[e.get('data') for e in turn if e['type'] == 'error']}"
    )
    assert "".join(_tokens(turn)) == "LOCAL-OLLAMA"
    assert after == [], "something more was sent after the turn had ended"


def test_a_stop_during_a_turn_that_then_raises_is_not_answered_afterwards(token, ollama_script):
    """
    The turn reads a Stop only between events. Sent while the provider is
    blocked on a slow first token and the pipeline then raises, it is still
    queued when D-22's early return ends the turn - and the next pass through
    the main loop answered it with a second error, right behind the first.
    """
    gate = _Gate()
    ollama_script.extend([_blocks_then_fails(gate), _answers("LOCAL-OLLAMA")])

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works"})
        assert gate.reached.wait(10), "the provider was never reached"
        ws.send_json({"type": "stop"})
        time.sleep(0.3)  # long enough for the server to have queued it
        gate.release.set()
        first = events.turn()

        ws.send_json({"message": "explain how a linked list works"})
        second = events.turn()
        after = events.settled()

    assert [e["type"] for e in _terminals(first)] == ["error"]
    assert second[0]["type"] == "stage", (
        f"the Stop was answered after the turn ended: {second[0].get('data')!r}"
    )
    assert [e["type"] for e in _terminals(second)] == ["done"]
    assert after == [], "something more was sent after the last turn had ended"


def test_control_a_request_with_no_message_that_is_not_a_stop_still_gets_an_error(token, ollama_script):
    """The fix drops a Stop and nothing else: a request with no text is still
    a mistake the client is told about."""
    ollama_script.append(_answers("LOCAL-OLLAMA"))

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"type": "stopp"})
        refused = events.turn()
        ws.send_json({"message": "explain how a hash map works"})
        answered = events.turn()
        after = events.settled()

    assert [(e["type"], e["data"]) for e in refused] == [("error", "message is required")]
    assert [e["type"] for e in _terminals(answered)] == ["done"]
    assert after == []


# --- D-25: a token that is not text -----------------------------------------
#
# Stage 9 now refuses these itself (D-27, below and in test_stage_09_llm_
# streaming.py), so they no longer get as far as the transport. The transport's
# own guard is held here with a pipeline that hands it the event directly: it
# has to stand on its own, for whatever produces an event it cannot fold.


@pytest.mark.parametrize(
    "tokens, shown",
    [
        pytest.param(["PART", [{"type": "text", "text": "hi"}], "NEVER"], ["PART"], id="structured-content-after-text"),
        pytest.param(["PART", None, "NEVER"], ["PART"], id="null-after-text"),
        pytest.param([[{"type": "text", "text": "hi"}], "NEVER"], [], id="structured-content-first"),
    ],
)
def test_a_token_that_is_not_text_never_reaches_the_client_and_ends_the_turn_with_one_error(
    token, monkeypatch, tokens, shown
):
    """
    The transport folds every event it forwards to know what the client was
    shown. That fold raised on a token that is not text - after the token had
    been sent, and outside the guard, so the connection closed with no terminal
    event. The client does `event.data as String` on every token, so a token
    that is not text must never be sent either.
    """
    hint = {"decision_log_hit": False, "web_search_used": False, "cache_hit": False, "model_loading": False}

    def broken(*args, **kwargs):
        yield {"type": "stage_hint", "data": hint}
        for piece in tokens:
            yield {"type": "token", "data": piece}
        yield {"type": "done", "data": None}
        yield {"type": "pipeline_complete", "data": {
            "trace_id": "t1", "response_text": "", "status": "success", "stage_hints": {},
        }}

    def whole(*args, **kwargs):
        yield {"type": "stage_hint", "data": hint}
        yield {"type": "token", "data": "LOCAL-OLLAMA"}
        yield {"type": "done", "data": None}
        yield {"type": "pipeline_complete", "data": {
            "trace_id": "t2", "response_text": "LOCAL-OLLAMA", "status": "success", "stage_hints": {},
        }}

    plays = [broken, whole]
    monkeypatch.setattr(server.pipeline, "run", lambda *a, **kw: plays.pop(0)(*a, **kw))

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works"})
        first = events.turn()

        ws.send_json({"message": "explain how a linked list works"})
        second = events.turn()
        after = events.settled()

    assert _tokens(first) == shown, "a token that is not text was sent to the client"
    assert [e["type"] for e in _terminals(first)] == ["error"]
    assert second[0]["type"] == "stage_hint"
    assert [e["type"] for e in _terminals(second)] == ["done"]
    assert "".join(_tokens(second)) == "LOCAL-OLLAMA"
    assert after == [], "something more was sent after the last turn had ended"


# --- D-27: Stage 9 refuses a token that is not text --------------------------


def _add_local_endpoint(tmp_path, url):
    """A second provider that needs no consent, behind Ollama in the chain."""
    conn = server.open_app_connection(str(tmp_path / "pip.db"), None)
    try:
        llm_endpoint_store.add_endpoint(
            conn, provider_id="lan-box", label="lan box", base_url=url, model_name="m", is_local=True,
        )
    finally:
        conn.close()


def test_a_provider_that_streams_structured_content_first_is_passed_over_for_the_next(
    tmp_path, token, stub, ollama_script
):
    """
    End to end through the real chat. Ollama leads the chain and its first
    token is a list of content parts, which is what an OpenAI-compatible server
    that streams structured content sends. It used to end the turn in an error
    that named nothing, with the endpoint behind it never asked. It is now a
    provider that failed before showing anything, and the endpoint answers.
    """
    _add_local_endpoint(tmp_path, stub.url)
    ollama_script.append(_yields([{"type": "text", "text": "hi"}], "NEVER"))

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works"})
        turn = events.turn()
        after = events.settled()

    assert [e["type"] for e in _terminals(turn)] == ["done"]
    assert _tokens(turn) == ["STUB-REPLY"]
    assert len(stub.sent) == 1
    assert after == [], "something more was sent after the turn had ended"


def test_a_provider_that_streams_structured_content_after_text_ends_the_turn_and_is_not_passed_over(
    tmp_path, token, stub, ollama_script
):
    """
    After something was shown, the next provider is not asked: starting a
    second answer under the first would give a garbled one. The turn ends with
    the interruption, naming the kind of thing that was wrong and none of what
    was sent.
    """
    _add_local_endpoint(tmp_path, stub.url)
    ollama_script.append(_yields("PART", [{"type": "text", "text": "SECRET-CONTENT"}], "NEVER"))

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works"})
        turn = events.turn()
        after = events.settled()

    assert _tokens(turn) == ["PART"]
    assert [e["type"] for e in _terminals(turn)] == ["error"]
    assert turn[-1]["data"].startswith("Response interrupted")
    assert "list" in turn[-1]["data"]
    assert "SECRET-CONTENT" not in turn[-1]["data"]
    assert stub.sent == [], "a second provider was asked after part of an answer had been shown"
    assert after == [], "something more was sent after the turn had ended"


# --- D-26: the writes around a turn -----------------------------------------


def _not_saved(event):
    """The one thing a client is told when the chat cannot be written to: that
    it was not answered, what to do, and nothing from inside the exception."""
    assert event["type"] == "error"
    text = event["data"]
    assert "could not be saved" in text and "not answered" in text
    for inside in ("FOREIGN KEY", "constraint", "IntegrityError", "OperationalError", "database is locked"):
        assert inside not in text, f"the error leaks what the exception said: {inside!r}"
    return text


def _stored(tmp_path):
    """Every message in the database, oldest first, across all conversations."""
    conn = server.open_app_connection(str(tmp_path / "pip.db"), None)
    try:
        return [(r["role"], r["content"], r["created_at"]) for r in conn.execute(
            "SELECT role, content, created_at FROM messages ORDER BY id").fetchall()]
    finally:
        conn.close()


def _conversations(tmp_path):
    conn = server.open_app_connection(str(tmp_path / "pip.db"), None)
    try:
        return conversation_store.list_conversations(conn)
    finally:
        conn.close()


def _wait_until_stored(tmp_path, count, seconds=10.0):
    """The server saves a turn AFTER it has sent the terminal event, so a test
    that acts on the database straight after `done` races the save."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if len(_stored(tmp_path)) >= count:
            return
        time.sleep(0.05)
    pytest.fail(f"the turn was not saved within {seconds}s ({len(_stored(tmp_path))} of {count} rows)")


def test_a_message_whose_conversation_cannot_be_created_is_refused_and_the_connection_survives(
    tmp_path, token, ollama_script, caplog
):
    """
    Real trigger: foreign keys are enforced, and a message names the project it
    belongs to, so one that names a project which no longer exists makes
    create_conversation raise. That used to end the handler: the client got
    nothing at all - not even the stage lines, which come later - and the chat
    sat "writing". Now the message is refused with one error, nothing reaches
    the model, no conversation row is left behind, and the next message on the
    same socket is answered.
    """
    caplog.set_level(logging.ERROR, logger="backend.api.server")
    ollama_script.append(_answers("LOCAL-OLLAMA"))

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works", "project_id": "a-project-that-was-deleted"})
        refused = events.turn()
        assert len(ollama_script) == 1, "the refused message reached the model"

        ws.send_json({"message": "explain how a linked list works"})
        answered = events.turn()
        after = events.settled()
        _wait_until_stored(tmp_path, 2)

    assert len(refused) == 1, f"the refusal came with other events: {[e['type'] for e in refused]}"
    _not_saved(refused[0])
    assert [e["type"] for e in _terminals(answered)] == ["done"]
    assert answered[0]["type"] == "session_info", "the conversation was not created for the message that could be saved"
    assert "".join(_tokens(answered)) == "LOCAL-OLLAMA"
    assert after == [], "something more was sent after the last turn had ended"
    assert len(_conversations(tmp_path)) == 1, "the refused message left a conversation behind"
    assert [(role, text) for role, text, _ in _stored(tmp_path)] == [
        ("user", "explain how a linked list works"),
        ("assistant", "LOCAL-OLLAMA"),
    ]
    assert any(
        r.name == "backend.api.server" and r.exc_info and isinstance(r.exc_info[1], sqlite3.IntegrityError)
        for r in caplog.records
    ), "the reason is not in the backend log, and the client was sent there"


def test_a_session_that_cannot_be_counted_is_refused_and_counted_once_when_it_can(
    tmp_path, token, ollama_script, monkeypatch
):
    """
    Injected: begin_session raising as a locked database does. The flag that
    says "this connection's session is counted" was set BEFORE the write, so a
    write that failed - on a handler that used to die - would have been counted
    as done. It is set after, so the next message tries again, and the session
    is counted exactly once: not zero times, which is the failure the counter's
    own comment worries about, and not twice.
    """
    _onboard(tmp_path)
    assert _session_count(tmp_path) == 1
    real = server.profile_store.begin_session
    calls = {"n": 0}

    def locked_once(conn):
        calls["n"] += 1
        if calls["n"] == 1:
            raise sqlite3.OperationalError("database is locked")
        return real(conn)

    monkeypatch.setattr(server.profile_store, "begin_session", locked_once)
    ollama_script.append(_answers("LOCAL-OLLAMA"))

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "explain how a hash map works"})
        refused = events.turn()
        assert len(ollama_script) == 1, "the refused message reached the model"

        ws.send_json({"message": "explain how a hash map works"})
        answered = events.turn()
        after = events.settled()

    assert len(refused) == 1
    _not_saved(refused[0])
    assert [e["type"] for e in _terminals(answered)] == ["done"]
    assert after == []
    assert calls["n"] == 2
    assert _session_count(tmp_path) == 2, "the session was counted zero or two times"


@pytest.mark.parametrize("failing_role", ["user", "assistant"])
def test_a_turn_that_cannot_be_saved_is_saved_in_order_before_the_next_one_is_answered(
    tmp_path, token, ollama_script, monkeypatch, failing_role
):
    """
    Injected: one write of the turn fails HALFWAY - the row is inserted and the
    write then fails, as a full disk does at the commit. The turn has already
    been shown, so nothing is sent for it; it is kept, and written before the
    next message is looked at. Three things are held here:
    - it is rolled back, or the half-written row sits in the connection's open
      transaction and the next write's commit saves it a second time;
    - the rows land in order, whichever of the pair failed;
    - they keep the time the turn happened, not the time of the retry. Seconds
      are the resolution of created_at, so the test waits long enough to tell.
    """
    real = conversation_store.append_message
    state = {"failed": False}

    def halfway(conn, conversation_id, role, content, *, timestamp=None):
        if role == failing_role and not state["failed"]:
            state["failed"] = True
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (conversation_id, role, content, timestamp or "1999-01-01T00:00:00Z"),
            )
            raise sqlite3.OperationalError("database or disk is full")
        return real(conn, conversation_id, role, content, timestamp=timestamp)

    monkeypatch.setattr(conversation_store, "append_message", halfway)
    ollama_script.extend([_answers("FIRST-ANSWER"), _answers("SECOND-ANSWER")])

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "first question"})
        first = events.turn()
        first_done = datetime.datetime.now(datetime.timezone.utc)
        time.sleep(1.5)

        ws.send_json({"message": "second question"})
        second = events.turn()
        after = events.settled()
        _wait_until_stored(tmp_path, 4)

    assert state["failed"], "the injected failure never happened"
    assert [e["type"] for e in _terminals(first)] == ["done"], "a failed save changed how the turn ended"
    assert [e["type"] for e in _terminals(second)] == ["done"]
    assert after == [], "something more was sent after the last turn had ended"
    stored = _stored(tmp_path)
    assert [(role, text) for role, text, _ in stored] == [
        ("user", "first question"),
        ("assistant", "FIRST-ANSWER"),
        ("user", "second question"),
        ("assistant", "SECOND-ANSWER"),
    ], "the rows are missing, doubled or out of order"

    def stamp(text):
        return datetime.datetime.strptime(text, TIMESTAMP_FORMAT).replace(tzinfo=datetime.timezone.utc)

    for role, text, created_at in stored[:2]:
        assert stamp(created_at) < first_done + datetime.timedelta(seconds=1), (
            f"the first turn's {role} row was stamped {created_at}, the time of the retry"
        )


def test_a_conversation_that_cannot_be_saved_to_refuses_the_next_message_and_says_so(
    tmp_path, token, ollama_script, caplog
):
    """
    Real trigger: the conversation is deleted while a chat is open on it, so
    every write for it fails the foreign key. The turn that was already being
    answered is shown and ends as any turn does - the user is not told then,
    there being no event that is not the end of a turn - and is kept. The next
    message finds it still cannot be written, and is refused rather than
    answered into a chat that is not being kept, with the reason in the log and
    a way out in the message. A fourth is refused the same way: nothing piles up
    and nothing is answered.
    """
    caplog.set_level(logging.ERROR, logger="backend.api.server")
    ollama_script.extend([_answers("FIRST-ANSWER"), _answers("SECOND-ANSWER"), _answers("NEVER-ANSWERED")])

    with TestClient(server.app).websocket_connect(f"/ws/chat?token={token}") as ws:
        events = _Events(ws)
        assert events.next()["type"] == "session_info"

        ws.send_json({"message": "first question"})
        first = events.turn()
        _wait_until_stored(tmp_path, 2)
        conn = server.open_app_connection(str(tmp_path / "pip.db"), None)
        try:
            server.api_delete_conversation(conn, _conversation_id(first))
        finally:
            conn.close()

        ws.send_json({"message": "second question"})
        second = events.turn()
        quiet = events.settled()
        assert len(ollama_script) == 1, "a third answer was consumed already"

        ws.send_json({"message": "third question"})
        refused = events.turn()
        ws.send_json({"message": "fourth question"})
        refused_again = events.turn()
        after = events.settled()

    assert [e["type"] for e in _terminals(second)] == ["done"], "the turn that could not be saved was not answered normally"
    assert "".join(_tokens(second)) == "SECOND-ANSWER"
    assert quiet == [], "the failed save was announced with an event of its own"
    for turn in (refused, refused_again):
        assert len(turn) == 1, f"the refusal came with other events: {[e['type'] for e in turn]}"
        _not_saved(turn[0])
    assert len(ollama_script) == 1, "a refused message was answered"
    assert after == []
    messages = [r.getMessage() for r in caplog.records if r.name == "backend.api.server" and r.exc_info]
    assert any("tried again" in m for m in messages), "the failed save was not logged where the user is sent to look"
    assert any("refused" in m for m in messages), "the refusal was not logged"
