"""
PROBE (not part of the suite): the response cache is written AFTER the "done"
event reaches the client (pipeline.py: stage 9 yields done, then
response_cache.set runs). A sign-out that lands in that gap empties the cache
before the write, and the write then puts the signed-out profile's answer back.

The gap is widened deterministically by delaying only the cache write; nothing
else is changed. The control runs the same sequence with no delay.
"""
import time

import pytest
from fastapi.testclient import TestClient

from backend.api import server
from backend.core import response_cache
from backend.tests.test_profile_boundary import (  # noqa: F401  (fixtures)
    API, QUESTION, _ask, _headers, _new_profile, forget_the_key, provider, token,
)


@pytest.mark.parametrize("delay", [0.0, 1.0], ids=["no-delay", "write-delayed-1s"])
def test_CR1_answer_written_after_sign_out(provider, token, monkeypatch, delay):
    real_set = response_cache.set

    def late_set(*args, **kwargs):
        time.sleep(delay)
        return real_set(*args, **kwargs)

    monkeypatch.setattr(response_cache, "set", late_set)
    with TestClient(server.app) as client:
        _new_profile(client, token, "Alice", "alice-password-1")
        alice_answer, _ = _ask(client, token, QUESTION)
        assert client.post(f"{API}/auth/lock", headers=_headers(token)).status_code == 200
        _new_profile(client, token, "Bob", "bob-password-22")
        time.sleep(delay + 0.5)  # let Alice's late write land before Bob asks
        calls_before = len(provider.calls)
        bob_answer, bob_hints = _ask(client, token, QUESTION)
    print(f"\n[delay={delay}] alice={alice_answer!r} bob={bob_answer!r} "
          f"bob_cache_hit={bob_hints.get('cache_hit')} bob_model_called={len(provider.calls) > calls_before}")
    assert len(provider.calls) == calls_before + 1, "Bob's question never reached his model"
    assert bob_answer != alice_answer, "Bob was served Alice's answer"
