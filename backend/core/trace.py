import uuid
import json
import os
from pathlib import Path
from backend.core.types import now_utc

TRACE_LOG_PATH = Path(__file__).parent.parent / "logs" / "trace_log.json"

def generate_trace_id() -> str:
    """Generates a unique trace ID using UUIDv4."""
    return str(uuid.uuid4())

def stage_log(trace_id: str, stage: str, status: str, message: str, error_detail: str = "") -> None:
    """Appends a trace log entry as a JSON object to trace_log.json."""
    entry = {
        "trace_id": trace_id,
        "timestamp": now_utc(),
        "stage": stage,
        "status": status,
        "message": message,
        "error_detail": error_detail
    }
    
    # Ensure directory exists
    TRACE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Append entry to file
    try:
        if TRACE_LOG_PATH.exists():
            with open(TRACE_LOG_PATH, "r+", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = []
                data.append(entry)
                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()
        else:
            with open(TRACE_LOG_PATH, "w", encoding="utf-8") as f:
                json.dump([entry], f, indent=2)
    except Exception as e:
        # Prevent logging errors from crashing the main pipeline
        print(f"Failed to write to trace log: {e}")
