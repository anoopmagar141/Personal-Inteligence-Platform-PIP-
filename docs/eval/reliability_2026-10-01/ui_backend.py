"""Isolated backend for the rendered-UI check. Prints the port, keeps running until killed."""
import sys
import time
from pathlib import Path

from journey import API, Backend, log

root = Path(sys.argv[1]).resolve()
fresh = not (root / "profiles.json").exists()
b = Backend(root)
b.start()
if fresh:
    for name, pw in (("Mira Testcase", "mira-ui-pw-1"), ("Otto Testcase", "otto-ui-pw-2")):
        slug = b.post(f"{API}/auth/profiles", {"name": name}).json()["slug"]
        b.post(f"{API}/auth/setup", {"password": pw, "profile": slug})
        b.post(f"{API}/onboarding/complete", {"name": name, "language_preference": "English"})
        b.post(f"{API}/llm/active-model", {"model_name": "qwen2.5:7b"})
        b.post(f"{API}/auth/lock")
log("PORT", b.port)
(root / "port.txt").write_text(str(b.port))
while b.proc.poll() is None:
    time.sleep(2)
