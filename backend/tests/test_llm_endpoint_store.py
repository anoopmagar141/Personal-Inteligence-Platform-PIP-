"""
Configured endpoints, and the consent record that has to exist beside each one.

The behaviour worth protecting here is not the CRUD. It is the three couplings
that are easy to break silently: an endpoint saved without consent is refused
by a gate that points at the wrong file, a cloud endpoint that consents itself
makes "nothing leaves the machine without agreement" false, and a removed
endpoint that leaves its consent behind lets a later endpoint inherit a yes
that was said about a different URL.
"""

import sqlite3

import pytest

from backend.core import pipeline
from backend.memory import llm_endpoint_store as store
from backend.memory.profile_store import initialize_schema
from backend.providers.ollama_provider import OllamaProvider
from backend.providers.openai_compatible_provider import OpenAICompatibleProvider


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    initialize_schema(connection)
    yield connection
    connection.close()


def consent_row(conn, provider_id):
    row = conn.execute(
        "SELECT * FROM provider_consent WHERE provider_id = ?", (provider_id,)
    ).fetchone()
    return dict(row) if row else None


def add_local(conn, provider_id="lm-studio", **kwargs):
    defaults = dict(
        provider_id=provider_id,
        label="LM Studio",
        base_url="http://localhost:1234",
        model_name="local-model",
        is_local=True,
    )
    defaults.update(kwargs)
    store.add_endpoint(conn, **defaults)


def add_cloud(conn, provider_id="openrouter", **kwargs):
    defaults = dict(
        provider_id=provider_id,
        label="OpenRouter",
        base_url="https://openrouter.ai/api",
        model_name="some/model",
        api_key="sk-test",
        is_local=False,
    )
    defaults.update(kwargs)
    store.add_endpoint(conn, **defaults)


# --- storage ----------------------------------------------------------------


def test_an_endpoint_round_trips(conn):
    add_cloud(conn)
    saved = store.get_endpoint(conn, "openrouter")
    assert saved["base_url"] == "https://openrouter.ai/api"
    assert saved["api_key"] == "sk-test"
    assert saved["is_local"] == 0


def test_re_adding_the_same_id_updates_rather_than_duplicating(conn):
    """
    The realistic reason to save the same id twice is fixing a typo in a URL or
    replacing a rotated key. Refusing would leave the user correcting a row by
    deleting one they cannot see.
    """
    add_cloud(conn, api_key="sk-old", model_name="old-model")
    add_cloud(conn, api_key="sk-new", model_name="new-model")

    assert len(store.list_endpoints(conn)) == 1
    saved = store.get_endpoint(conn, "openrouter")
    assert saved["api_key"] == "sk-new"
    assert saved["model_name"] == "new-model"


def test_endpoints_come_back_in_priority_order(conn):
    add_local(conn, provider_id="third", priority=200)
    add_local(conn, provider_id="first", priority=10)
    add_local(conn, provider_id="second", priority=100)

    assert [e["provider_id"] for e in store.list_endpoints(conn)] == [
        "first",
        "second",
        "third",
    ]


def test_disabled_endpoints_are_kept_but_excluded(conn):
    """Switching off is 'not right now' and keeps the URL and key; removing is
    'not this provider' and takes the key with it."""
    add_local(conn)
    store.set_enabled(conn, "lm-studio", False)

    assert store.list_endpoints(conn, enabled_only=True) == []
    assert store.get_endpoint(conn, "lm-studio")["api_key"] is None
    assert len(store.list_endpoints(conn)) == 1


# --- consent coupling -------------------------------------------------------


def test_adding_an_endpoint_creates_the_consent_row_it_needs(conn):
    """
    Without this, stage_08 fails closed on an id it has never seen and the
    endpoint is silently never used - a failure that points at the consent
    gate rather than at the endpoint that was just saved.
    """
    add_local(conn)
    assert consent_row(conn, "lm-studio") is not None


def test_a_local_endpoint_is_consented_by_being_added(conn):
    """The user typed the address of a server on their own machine. There is
    no third party to agree to."""
    add_local(conn)
    row = consent_row(conn, "lm-studio")
    assert row["user_consented"] == 1
    assert row["is_cloud"] == 0
    assert row["consent_date"] is not None


def test_a_cloud_endpoint_is_stored_unconsented(conn):
    """
    The claim "nothing leaves this machine without being agreed to" is only
    true if adding a cloud endpoint is not itself the agreement. It is stored,
    and stays inert until somebody says yes to it by name.
    """
    add_cloud(conn)
    row = consent_row(conn, "openrouter")
    assert row["user_consented"] == 0
    assert row["is_cloud"] == 1
    assert row["consent_date"] is None, "an agreement that has not happened has no date"


def test_re_saving_an_endpoint_does_not_re_grant_revoked_consent(conn):
    """
    The reason the consent row is INSERT-only while the endpoint upserts. An
    'update everything' would let editing a URL quietly restore a permission
    the user had deliberately taken away.
    """
    add_cloud(conn)
    conn.execute(
        "UPDATE provider_consent SET user_consented = 0, revoked = 1 "
        "WHERE provider_id = 'openrouter'"
    )
    conn.commit()

    add_cloud(conn, model_name="a-different-model")

    row = consent_row(conn, "openrouter")
    assert row["revoked"] == 1
    assert row["user_consented"] == 0


def test_removing_an_endpoint_takes_its_consent_with_it(conn):
    """
    stage_08's fail-closed default only means something if a provider that is
    gone is genuinely unknown again. Left behind, the row would let a later
    endpoint reusing the id inherit a yes said about a different URL and key.
    """
    add_local(conn)
    assert store.remove_endpoint(conn, "lm-studio") is True

    assert store.get_endpoint(conn, "lm-studio") is None
    assert consent_row(conn, "lm-studio") is None


def test_removing_something_that_is_not_there_reports_it(conn):
    assert store.remove_endpoint(conn, "never-existed") is False
    assert store.set_enabled(conn, "never-existed", True) is False


# --- the pipeline's fallback chain ------------------------------------------


def test_the_chain_is_just_ollama_when_nothing_is_configured(conn):
    providers = pipeline._default_providers(conn)
    assert len(providers) == 1
    assert isinstance(providers[0], OllamaProvider)


def test_a_configured_endpoint_joins_the_chain(conn):
    add_local(conn)
    providers = pipeline._default_providers(conn)

    assert [p.get_model_info()["provider_id"] for p in providers] == [
        "ollama",
        "lm-studio",
    ]
    assert isinstance(providers[1], OpenAICompatibleProvider)


def test_an_endpoint_sits_behind_the_local_model_by_default(conn):
    """
    The default priority of 100 is behind OLLAMA_PRIORITY on purpose: adding
    an endpoint must never silently start sending a conversation off the
    machine.
    """
    add_cloud(conn)
    assert pipeline._default_providers(conn)[0].get_model_info()["provider_id"] == "ollama"


def test_a_lower_priority_puts_an_endpoint_first(conn):
    """Someone who wants a cloud provider to lead has to say so."""
    add_cloud(conn, priority=pipeline.OLLAMA_PRIORITY - 1)

    first = pipeline._default_providers(conn)[0].get_model_info()
    assert first["provider_id"] == "openrouter"
    assert first["is_local"] is False


def test_a_disabled_endpoint_is_not_in_the_chain(conn):
    add_local(conn)
    store.set_enabled(conn, "lm-studio", False)

    providers = pipeline._default_providers(conn)
    assert [p.get_model_info()["provider_id"] for p in providers] == ["ollama"]


def test_the_configured_key_reaches_the_provider(conn):
    add_cloud(conn, api_key="sk-configured")
    endpoint = pipeline._default_providers(conn)[1]
    assert endpoint.api_key == "sk-configured"
    assert "sk-configured" not in str(endpoint.get_model_info())


def test_a_broken_row_costs_that_endpoint_and_not_the_conversation(monkeypatch, conn):
    """
    One endpoint that cannot be constructed should not take away the user's
    ability to hold a conversation - the local model is still behind it.

    Forced through a raising constructor rather than a malformed row, because
    the schema will not accept one: base_url, model_name and label are all NOT
    NULL, which is the first line of this defence and was confirmed by trying.
    What remains reachable is a provider class that rejects something the
    database was happy to store, so that is what this simulates.
    """
    add_local(conn, provider_id="fine")

    def refuse(*args, **kwargs):
        raise ValueError("unsupported configuration")

    monkeypatch.setattr(pipeline, "OpenAICompatibleProvider", refuse)

    providers = pipeline._default_providers(conn)
    assert [p.get_model_info()["provider_id"] for p in providers] == ["ollama"]
