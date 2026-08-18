# PIP Message Pipeline - Stage 9: LLM Streaming
#
# Transport-agnostic by design: yields WS-protocol-shaped events (Part 14.3), not
# WebSocket frames directly. The eventual /ws/chat endpoint (Phase 8, not built)
# just forwards each yielded dict as JSON over the socket - this stage has no
# knowledge of WebSockets at all, matching Stage 7's "assemble the interface the
# caller needs" approach rather than assuming a specific transport.
#
# "Failure: try next local provider, never cloud without consent" (Part 7 Stage 9
# spec) - the "never cloud without consent" half is Stage 8's job (the Provider
# Gate runs before this stage and only ever hands this stage providers that already
# passed consent). Stage 9 itself just does ordered fallback across whatever
# provider list it's given.

import logging
from typing import Any, Iterator, Optional

from backend.providers.base_provider import (
    BaseLLMProvider,
    ProviderExecutionError,
    ProviderUnavailableError,
)
from shared.ws_spec import WSChatEvent

logger = logging.getLogger(__name__)


def run(
    context: str,
    messages: list[dict[str, str]],
    providers: list[BaseLLMProvider],
    *,
    decision_log_hit: bool = False,
    web_search_used: bool = False,
    cache_hit: bool = False,
    model_loading: bool = False,
    max_tokens: int = 2000,
    timeout_seconds: int = 30,
) -> Iterator[WSChatEvent]:
    """
    Streams a response as an ordered sequence of Part 14.3 WS events:
    stage_hint (always first) -> token* -> done, or stage_hint -> error.

    Tries each provider in `providers` in order. If a provider fails before
    yielding any tokens, falls through to the next one. If a provider fails AFTER
    already yielding tokens, does NOT fall through - partial output has already
    reached the caller, and starting a second provider from scratch would produce
    a duplicated/garbled response, not a clean retry. Surfaces an error instead.
    """
    yield {
        "type": "stage_hint",
        "data": {
            "decision_log_hit": decision_log_hit,
            "web_search_used": web_search_used,
            "cache_hit": cache_hit,
            "model_loading": model_loading,
        },
    }

    last_error: Optional[Exception] = None

    for provider in providers:
        yielded_any = False
        try:
            for token in provider.chat(messages, context=context, max_tokens=max_tokens, timeout_seconds=timeout_seconds):
                yield {"type": "token", "data": token}
                yielded_any = True

            if not yielded_any:
                # Contract violation (BaseLLMProvider.chat() must yield at least
                # one token or raise) - treat as a failure, try the next provider,
                # don't silently emit "done" for an empty response.
                raise ProviderExecutionError("provider returned without yielding any tokens")

            yield {"type": "done", "data": None}
            return

        except (ProviderUnavailableError, ProviderExecutionError) as e:
            provider_id = provider.get_model_info().get("provider_id", "unknown")
            if yielded_any:
                logger.error(f"Stage 9: {provider_id} failed mid-stream after partial output: {e}")
                yield {"type": "error", "data": f"Response interrupted: {e}"}
                return
            logger.warning(f"Stage 9: {provider_id} failed before yielding any tokens, trying next: {e}")
            last_error = e
            continue

    yield {"type": "error", "data": f"All providers failed: {last_error}"}


def collect(event_iterator: Iterator[WSChatEvent]) -> dict[str, Any]:
    """
    Drains a run() event stream synchronously and returns the aggregated result.
    For callers that don't need live token-by-token forwarding (tests, a CLI,
    Stage 10). A live WS caller should iterate run() directly instead, forwarding
    each event as it arrives, and build its own accumulator alongside if it also
    needs the final text.
    """
    response_text = ""
    status = "error"
    error: Optional[str] = None
    stage_hints: dict[str, Any] = {}

    for event in event_iterator:
        if event["type"] == "stage_hint":
            stage_hints = event["data"]
        elif event["type"] == "token":
            response_text += event["data"]
        elif event["type"] == "done":
            status = "success"
        elif event["type"] == "error":
            status = "error"
            error = event["data"]

    return {
        "response_text": response_text,
        "status": status,
        "error": error,
        "stage_hints": stage_hints,
    }
