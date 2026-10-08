"""
Two first-run imports at once cannot trample each other (FREEZE_LIST 7.29).

Activating a profile points the whole process (paths and environment) at it, so a second import
that activated its own profile while the first was between "register" and "install" moved the
first one's target mid-way: one of two simultaneous imports failed with a 500 and the other
reported the other profile's state.
"""

import threading

from backend.core import restore
from backend.tests.test_first_run_import import (  # noqa: F401  (fixtures)
    LIVE_KEY, _empty, _load, fresh, forget_the_key,
)
from backend.tests._import_export_helpers import NEW, OLD, NON_ASCII_PASSWORDS, _backup, _import


# ---------------------------------------------------------------------------
# One import at a time
# ---------------------------------------------------------------------------


def test_a_second_import_while_one_is_running_is_refused_and_the_first_finishes(fresh, tmp_path, monkeypatch):
    client, headers, data = fresh
    first = _backup(tmp_path, monkeypatch, name="BatMan", filename="a.pipbak")
    second = _backup(tmp_path, monkeypatch, name="Robin", filename="b.pipbak")

    reached = threading.Event()
    release = threading.Event()
    real_preflight = restore.preflight

    def held_preflight(*args, **kwargs):
        reached.set()
        assert release.wait(timeout=60), "the test never released the first import"
        return real_preflight(*args, **kwargs)

    monkeypatch.setattr(restore, "preflight", held_preflight)
    outcome = {}
    runner = threading.Thread(target=lambda: outcome.setdefault("first", _import(client, headers, first)))
    runner.start()
    assert reached.wait(timeout=60), "the first import never started"

    refused = _import(client, headers, second)
    release.set()
    runner.join(timeout=120)

    assert refused.status_code == 409, f"{refused.status_code} {refused.text}"
    assert "already" in refused.json()["detail"].lower()
    assert outcome["first"].status_code == 200, outcome["first"].text
    listed = client.get("/api/v1/auth/profiles", headers=headers).json()["profiles"]
    assert [(p["slug"], p["exists"]) for p in listed] == [("batman", True)]
