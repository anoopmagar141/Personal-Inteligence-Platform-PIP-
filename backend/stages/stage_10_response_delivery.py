# PIP Message Pipeline - Stage 10: Response Delivery
#
# Part 7 spec: "User receives output. Main pipeline complete. All learning happens
# AFTER this stage." "Learning" refers to Stage 11 Observer, which is explicitly
# NOT triggered from here - Rule 3 (Part 12.1) requires Observer to run at session
# end only (10-min idle OR process exit), never per-message. Calling it from this
# stage would violate that rule outright, not just bend it.
#
# Takes stage_09_llm_streaming.collect()'s output rather than the raw event
# generator - Stage 9 already separates "produce events" (run(), for live WS
# forwarding) from "aggregate the final result" (collect()); Stage 10 only needs
# the aggregated form to finalize the trace record.

from typing import Any, Optional

from backend.core import trace


def run(
    trace_id: str,
    collected: dict[str, Any],
    conn: Optional[Any] = None,
) -> dict[str, Any]:
    """
    Finalizes the pipeline run: writes the terminal trace_log entry for this
    trace_id, and returns a summary the caller can use for conversation-history
    bookkeeping (e.g. appending to the next turn's conversation_history for
    Stage 7). This is the last pipeline stage - nothing here writes to memory,
    Decision Log, or any other store; those already happened (or didn't) earlier
    in the pipeline. conn is accepted but unused for now - kept for interface
    symmetry with the other stages and in case future delivery bookkeeping
    (e.g. a message-history table) needs it; not exercised by this stage today.
    """
    status = collected.get("status", "error")
    response_text = collected.get("response_text", "")

    if status == "success":
        trace.stage_log(
            trace_id,
            "stage_10_response_delivery",
            "ok",
            f"Response delivered ({len(response_text)} chars)",
        )
    else:
        trace.stage_log(
            trace_id,
            "stage_10_response_delivery",
            "error",
            "Response delivery failed",
            error_detail=collected.get("error") or "unknown error",
        )

    return {
        "trace_id": trace_id,
        "response_text": response_text,
        "status": status,
        "stage_hints": collected.get("stage_hints", {}),
    }
