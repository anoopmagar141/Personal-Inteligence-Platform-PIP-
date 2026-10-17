"""
G-6 (docs/FREEZE_LIST.md §7.51): the older web client does not grant consent.

frontend/web/ is the HTML/JS client PIP was proven with before Flutter, and the
backend still serves it at "/". Its Providers tab had a "Grant consent" button
that sent `consent_scope: "full_inference"` for any provider on one click: the
broadest of the four scopes, not the narrowest one that would do, with no
sentence saying what would leave the machine. The Flutter client stopped doing
that - its own header comment says the button used to send full_inference for
every provider, "in this client and in the web prototype before it" - and asks
for one scope, with nothing preselected, each saying what actually leaves. The
web client was never changed.

It has no test harness, so this reads what the server actually serves: the same
bytes a browser would run. Not a behaviour test of the page, and not pretending
to be: it pins that the call is not there. Granting is done where the scopes are
explained, in the app; revoking, which only ever narrows, stays.

The server still accepts any valid scope for any provider from any caller, and the
command-line client still defaults to full_inference; see the record for both.
"""

import pytest
from fastapi.testclient import TestClient

from backend.api import server


@pytest.fixture
def served():
    """
    No lifespan, on purpose: static files need none, and starting one is how a test
    ends up opening a database.
    """
    client = TestClient(server.app)
    script = client.get("/app.js")
    page = client.get("/")
    assert script.status_code == 200 and page.status_code == 200, "the web client is not being served"
    return script.text, page.text


def test_the_web_client_has_no_call_that_grants_consent(served):
    script, page = served

    assert "/consent" not in script, "the web client can still post a consent grant"
    assert "data-consent" not in script, "the web client still has a grant button"
    assert "full_inference" not in script, "the web client still names the broadest scope"


def test_the_web_client_says_where_consent_is_given(served):
    """
    A provider that is not consented to must say how it can be, or the tab reads as
    broken. The words a person sees, not a mention in a comment.
    """
    script, page = served

    assert "Grant it in the PIP app" in script, "a provider that is not consented to no longer says where to grant it"
    assert "Consent is given in the PIP app" in page, "the Providers paragraph no longer says where consent is given"


def test_control_the_web_client_can_still_revoke(served):
    """Revoking only ever narrows what PIP may do, so it stays: the button and what handles it."""
    script, page = served

    assert ">Revoke</button>" in script, "the Revoke button is gone"
    assert "data-revoke" in script and "/revoke" in script, "nothing handles a click on Revoke"
