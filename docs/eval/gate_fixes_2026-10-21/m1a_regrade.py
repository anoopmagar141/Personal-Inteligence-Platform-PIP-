"""Run M-1(a)'s 116 graded items through the gate of the current directory's tree; print verdicts as JSON."""
import json, sys
sys.path.insert(0, ".")
from backend.core.evidence_gate import EvidenceLedger, adjudicate
key = json.load(open(sys.argv[1], encoding="utf-8"))
out = {}
for k, it in key["items"].items():
    lines = []
    if it.get("before"):
        lines.append("Assistant: " + it["before"])
    lines.append("User: " + it["message"])
    cand = {"target_table": it["table"], "field_name": it["field"], "proposed_value": it["value"],
            "label": it.get("label", "explicit"), "evidence_count": 1, "evidence_text": it["quote"]}
    out[k] = adjudicate(cand, EvidenceLedger.from_transcript("\n".join(lines))).state
print(json.dumps(out))
