"""
D-50 (docs/FREEZE_LIST.md §7.74): every call to Ollama waited two seconds before it began.

Found by measuring answer speed for the report (2026-10-21): the first word of every answer took
about 4.5 s, while Ollama itself answered a prompt of the same size in 0.05-0.26 s. PIP called
Ollama at "http://localhost:11434". On Windows "localhost" resolves to the IPv6 address ::1 first,
Ollama listens on 127.0.0.1 only (its default), and a refused connection is retried for about two
seconds before the next address is tried: a request to localhost took 2.04 s, the same request to
127.0.0.1 took 0.001 s. A chat message makes two such requests - the pipeline's provider list asks
is_available(), then chat() streams the answer - so about 4 s of every message was that wait, and
the Observer, the model list and a pull paid it too.

What is asserted is where each call really tries to connect, at the socket layer, for every
function in PIP that reaches Ollama. Nothing is contacted: the connection is refused on the spot
and recorded. The two-second retry itself belongs to the operating system and is not reproduced;
it is the reason for the address, not the property under test.
"""

import http.client
import urllib.request

import pytest

from backend.api import server
from backend.core import pipeline
from backend.providers import ollama_provider
from backend.providers.base_provider import ProviderExecutionError, ProviderUnavailableError
from backend.providers.ollama_provider import OllamaProvider

MODEL = "qwen2.5:7b"


@pytest.fixture
def connections(monkeypatch):
    """Every (host, port) an HTTP request tries to open. Each is refused at once."""
    seen = []

    def refuse(self):
        seen.append((self.host, self.port))
        raise ConnectionRefusedError("refused by the test")

    monkeypatch.setattr(http.client.HTTPConnection, "connect", refuse)
    # A proxy setting on the machine would put the proxy's address here instead of Ollama's.
    monkeypatch.setattr(urllib.request, "getproxies", lambda: {})
    monkeypatch.setattr(urllib.request, "_opener", None)
    return seen


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    connection = server.open_app_connection(str(tmp_path / "pip.db"), None)
    yield connection
    connection.close()


def _call(fn):
    try:
        fn()
    except (ProviderUnavailableError, ProviderExecutionError):
        pass  # refused, as the fixture arranged: what matters is where it went


@pytest.mark.parametrize("call", [
    pytest.param(lambda: OllamaProvider(model_name=MODEL).is_available(), id="is_available"),
    pytest.param(lambda: list(OllamaProvider(model_name=MODEL).chat([{"role": "user", "content": "hi"}])),
                 id="chat"),
    pytest.param(lambda: ollama_provider.list_models(), id="list_models"),
    pytest.param(lambda: ollama_provider.delete_model(MODEL), id="delete_model"),
    pytest.param(lambda: ollama_provider.pull_model(MODEL, lambda progress: None), id="pull_model"),
])
def test_every_call_to_ollama_goes_to_127_0_0_1(connections, call):
    _call(call)

    assert connections == [("127.0.0.1", 11434)]


def test_the_provider_the_chat_pipeline_builds_for_itself_goes_to_127_0_0_1(connections, conn):
    providers = pipeline._default_providers(conn)  # asks is_available() first, as every message does

    assert connections == [("127.0.0.1", 11434)]
    assert [p.host for p in providers if isinstance(p, OllamaProvider)] == ["http://127.0.0.1:11434"]


def test_the_observers_provider_goes_to_127_0_0_1(connections, monkeypatch):
    # With Ollama down and nothing else configured the Observer gets no provider; the call it made to
    # find that out is what is asserted.
    def no_database():
        raise RuntimeError("no database here")

    monkeypatch.setattr(server, "_conn", no_database)
    _call(lambda: server._default_observer_provider(MODEL))

    assert connections == [("127.0.0.1", 11434)]


def test_control_a_host_given_explicitly_is_still_the_one_used(connections):
    _call(lambda: OllamaProvider(model_name=MODEL, host="http://10.1.2.3:8080").is_available())
    _call(lambda: ollama_provider.list_models(host="http://10.1.2.3:8080"))

    assert connections == [("10.1.2.3", 8080), ("10.1.2.3", 8080)]
