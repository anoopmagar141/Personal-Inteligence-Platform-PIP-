# TEST HOOK, loaded only by the throwaway interpreters this journey builds.
# getpass reads the Windows console, not a pipe, so the real launchers cannot
# be driven unattended; this answers its prompts from PIP_TEST_ANSWERS and
# changes nothing else. The embedding stand-in is loaded because Smart App
# Control blocks torch on this machine (FREEZE_LIST §7.16, D-02).
#
# An answer may also be {"answer": "...", "post": url, "token": t, "json": {}}:
# the hook makes that request to the running backend first, then answers -
# the application writing something while the person is still typing.
import json
import os

if os.environ.get("PIP_TEST_ANSWERS"):
    import getpass

    _answers = iter(json.loads(os.environ["PIP_TEST_ANSWERS"]))

    def _answer(prompt=""):
        a = next(_answers)
        if isinstance(a, dict):
            import urllib.request

            req = urllib.request.Request(
                a["post"], data=json.dumps(a.get("json") or {}).encode("utf-8"), method="POST",
                headers={"Authorization": f"Bearer {a['token']}", "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                r.read()
            return a["answer"]
        return a

    getpass.getpass = _answer

try:
    import pip_embed_shim  # noqa: F401
except Exception:
    pass
