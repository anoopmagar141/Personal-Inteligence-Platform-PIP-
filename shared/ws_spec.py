# PIP - Shared WS Message Type Definitions (Part 17 [FROZEN] folder structure,
# Part 14.3 wire protocol)
#
# Single source of truth for the /ws/chat event shapes, so backend/stages/
# stage_09_llm_streaming.py (producer), backend/core/pipeline.py (relay), and
# backend/api/server.py (forwarder to the client) all type against the same
# definitions instead of each hand-rolling matching dict literals. TypedDict,
# not Pydantic, to match the convention already established across the stage
# modules (stage_00/01/02/07/11, core/types.py) - no other module in this
# codebase uses Pydantic despite FastAPI pulling it in transitively, so
# introducing it here alone would be an inconsistency, not an improvement.
# shared/models.py (Pydantic REST request/response models, also named in Part
# 17) is a separate, considerably larger decision - whether to move every REST
# endpoint off raw dict payloads - and is deliberately not part of this file.
#
# These are compile-time/documentation types only, matching TypedDict's usual
# role in this codebase: nothing here performs runtime validation. The actual
# dicts yielded by stage_09.run() and forwarded by server.py's ws_chat() are
# unchanged by this module - it documents their shape, it doesn't enforce it.

from typing import Any, Literal, Optional, TypedDict, Union


class StageHintData(TypedDict):
    decision_log_hit: bool
    web_search_used: bool
    cache_hit: bool
    model_loading: bool


class StageHintEvent(TypedDict):
    type: Literal["stage_hint"]
    data: StageHintData


class TokenEvent(TypedDict):
    type: Literal["token"]
    data: str


class DoneEvent(TypedDict):
    type: Literal["done"]
    data: None


class ErrorEvent(TypedDict):
    type: Literal["error"]
    data: str


class StoppedEvent(TypedDict):
    """
    Terminal event when the client interrupts generation mid-stream (a
    ChatRequest-shaped {"type": "stop"} message sent while tokens are still
    arriving). Distinct from DoneEvent/ErrorEvent: this is a normal
    user-initiated outcome, not a completion or a failure, and the client
    should keep whatever partial text it already rendered rather than
    discarding it.
    """

    type: Literal["stopped"]
    data: None


class StageData(TypedDict):
    """
    One retrieval or generation step, reported as it finishes.

    `stage` is the stable identifier a client may branch on; `label` and
    `detail` are the sentences shown to a person. Both are written HERE rather
    than mapped from `stage` in the client, on this project's usual split: the
    backend is the only side that knows a lookup found three passages or none,
    and a frontend that assembled that sentence itself would be inventing
    knowledge it does not have.

    `status` distinguishes the case that matters most and reads identically to
    success from outside: "skipped" is a stage that never ran, "empty" is a
    stage that ran and found nothing. An answer built on an empty RAG lookup is
    exactly the failure this project spent a session chasing while every
    surface said things were fine.
    """

    stage: str
    label: str
    detail: str
    status: Literal["ok", "empty", "skipped", "error"]


class StageEvent(TypedDict):
    """
    Emitted as each pipeline stage completes, before the first token.

    Additive to the wire protocol, and safe for an older client by
    construction: server.py forwards every event that is not
    pipeline_complete without inspecting it, and a client that does not know
    this type ignores it the same way it ignores anything else unrecognised.
    """

    type: Literal["stage"]
    data: StageData


# Part 14.3: the event shapes ever sent over the /ws/chat wire, in emission
# order stage* -> stage_hint -> token* -> (done | error | stopped).
WSChatEvent = Union[StageEvent, StageHintEvent, TokenEvent, DoneEvent, ErrorEvent, StoppedEvent]


# What a client sends into /ws/chat while a response is actively streaming, to
# interrupt it early (Part 15.2 extension - stop is the only message meaningful
# mid-turn, since the connection is otherwise one ChatRequest per turn).
class StopRequest(TypedDict):
    type: Literal["stop"]


class SessionMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str
    # When the message was written, as messages.created_at holds it:
    # "%Y-%m-%dT%H:%M:%SZ", always UTC. The client converts to local time for
    # display - a transcript resumed on a machine in another timezone should
    # read in that machine's, and only the sender's clock could be trusted to
    # say what "3pm" meant anyway.
    #
    # Carried here and NOT into conversation_history: that list is prompt
    # input, and a timestamp on every prior turn is tokens spent telling the
    # model something it was not asked about. See _resolve_connection_state.
    created_at: str


class SessionInfoEvent(TypedDict):
    """
    Sent immediately after the WS connection is accepted and before any
    ChatRequest is expected - not part of the stage_hint -> token* ->
    (done|error|stopped) sequence above, that only ever describes one turn's
    streaming. This describes the CONNECTION: which conversation_id it
    resumed (?conversation_id=... query param), its title, and every prior
    message so the client can replay them into its transcript instead of
    starting blank.

    Sent TWICE, not once, for a brand-new conversation (no conversation_id
    given, or an unknown one): first right after connect with
    conversation_id: null - a fresh conversation isn't actually created (and
    committed to the DB) until the first real message arrives, so an idle
    connection that never sends anything doesn't litter the history sidebar
    with an empty "New chat" row - then again once that first message
    triggers creation, this time carrying the real id. A resumed
    conversation (conversation_id was known and valid) only ever gets the
    one, upfront send.
    """

    type: Literal["session_info"]
    data: "SessionInfoData"


class SessionInfoData(TypedDict):
    conversation_id: Optional[str]
    title: str
    messages: list[SessionMessage]


class PipelineCompleteEvent(TypedDict):
    """
    Yielded exactly once by core/pipeline.py's run() generator, after the
    WSChatEvent sequence above. Consumed internally by server.py's
    stream_pipeline_to_websocket() and never forwarded to the client - it is
    Python-generator plumbing (how the caller gets Stage 10's aggregated
    result without driving the StopIteration.value dance), not part of the
    wire protocol, which is exactly why it's typed separately from
    WSChatEvent rather than folded into that union.
    """

    type: Literal["pipeline_complete"]
    data: dict[str, Any]


# What a client actually sends into /ws/chat (Part 15.2): one JSON object per
# turn. project_id is optional - omitted/None means "no active project."
class ChatRequest(TypedDict, total=False):
    message: str
    project_id: str | None
