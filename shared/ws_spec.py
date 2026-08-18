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

from typing import Any, Literal, TypedDict, Union


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


# Part 14.3: the only four event shapes ever sent over the /ws/chat wire, in
# emission order stage_hint (always first) -> token* -> done, or -> error.
WSChatEvent = Union[StageHintEvent, TokenEvent, DoneEvent, ErrorEvent]


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
