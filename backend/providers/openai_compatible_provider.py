"""
One provider class for everything that speaks OpenAI's chat-completions API.

WHY THIS IS ONE CLASS AND NOT SEVEN
-----------------------------------
llama.cpp's server, LM Studio, Jan, KoboldCpp, vLLM and text-generation-webui
all expose POST /v1/chat/completions with the same request and response shape,
and so do OpenAI, Groq, OpenRouter, Together and Mistral. They are not seven
integrations; they are one protocol with seven hostnames. What separates them
is configuration - a base URL, a key, a model name - which is data, not code.

That is also why nothing here is named after a vendor. A class called
OpenAIProvider would invite a second one called GroqProvider that differed
only in a string, and the third would copy the second's bugs.

WHY provider_id IS A CONSTRUCTOR ARGUMENT
-----------------------------------------
Consent in PIP is keyed by provider_id: stage_08 looks the id up in
provider_consent and fails closed when there is no row. If every endpoint
configured through this class reported the same id, then consenting to a
LM Studio instance running on localhost would silently also consent to an
OpenAI key added later - the user would have approved a local model and
received a cloud one.

So each configured endpoint carries its own id, and each is consented
separately. The gate stays meaningful precisely because this class refuses to
speak for all of them at once.

is_local is a constructor argument for the same reason and is not inferred
from the URL. A hostname is a bad proxy for where data goes - a private
gateway on a company network is remote but not public, a tunnelled endpoint on
localhost is local-looking and not local - and a wrong guess here is a wrong
claim about the user's privacy. It is recorded as told.

WHAT IS DELIBERATELY NOT SENT
-----------------------------
The API key never appears in get_model_info(), because that dict is read by
the pipeline for provider_id and reaches the trace log. A secret that ends up
in a trace is a secret written to the database in plaintext, which is the one
thing this project's key handling exists to avoid. It is also kept out of
every exception message here, since those are logged too.
"""

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Iterator, List, Optional

from backend.providers.base_provider import (
    BaseLLMProvider,
    ProviderExecutionError,
    ProviderUnavailableError,
)


class OpenAICompatibleProvider(BaseLLMProvider):
    def __init__(
        self,
        model_name: str,
        base_url: str,
        *,
        provider_id: str,
        api_key: Optional[str] = None,
        is_local: bool = False,
        supports_response_format: bool = False,
    ):
        self.model_name = model_name
        # Trailing slashes are stripped so that a base_url given either way
        # produces one well-formed URL. Users type both, and "//v1/chat" fails
        # on some servers and silently 404s on others.
        self.base_url = base_url.rstrip("/")
        self.provider_id = provider_id
        self.api_key = api_key
        self.is_local = is_local
        self.supports_response_format = supports_response_format

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        # Omitted entirely rather than sent empty. A local llama.cpp server
        # needs no key, and some reject a malformed Authorization header that
        # they would have been happy to receive not at all.
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def chat(
        self,
        messages: List[Dict[str, str]],
        context: Optional[str] = None,
        max_tokens: int = 2000,
        timeout_seconds: int = 30,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Iterator[str]:
        if context:
            messages = [{"role": "system", "content": context}] + messages

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "max_tokens": max_tokens,
        }

        # Structured output is opt-in, and off by default, which is the
        # opposite of the Ollama provider's handling of the same argument.
        #
        # BaseLLMProvider.chat is explicit that a provider unable to honour
        # response_format must ignore it rather than raise: asking for
        # structure is never allowed to become a hard failure. Forwarding it
        # blindly would break that promise, because support is genuinely
        # uneven across this protocol - OpenAI takes a json_schema object,
        # several local servers take nothing and answer 400 to an unknown
        # field, and a 400 is exactly the hard failure the contract forbids.
        #
        # So the default is to drop it, and the caller keeps working with
        # unstructured output - which every caller already tolerates, since
        # that is the contract's other half. Whoever configures an endpoint
        # they know supports it can turn it on.
        if response_format is not None and self.supports_response_format:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "response", "schema": response_format},
            }

        req = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                for raw in response:
                    for token in self._tokens_from_line(raw):
                        yield token
        except urllib.error.HTTPError as e:
            raise ProviderExecutionError(self._describe_http_error(e))
        except urllib.error.URLError as e:
            # Connection-level failure is ProviderUnavailableError, which is
            # the distinction Stage 9's fallback chain runs on: unavailable
            # means try the next provider, execution error means this request
            # was wrong and the next provider would fail the same way.
            raise ProviderUnavailableError(
                f"{self.provider_id} is unreachable at {self.base_url}: {e.reason}"
            )
        except (ProviderExecutionError, ProviderUnavailableError):
            raise
        except Exception as e:
            raise ProviderExecutionError(
                f"Unexpected error during {self.provider_id} execution: {e}"
            )

    @staticmethod
    def _tokens_from_line(raw: bytes) -> Iterator[str]:
        """
        The content, if any, carried by one line of a server-sent-event stream.

        The wire format is text/event-stream, not the newline-delimited JSON
        Ollama returns, so the payload sits behind a "data: " prefix and the
        stream is punctuated by blank separator lines and terminated by the
        literal sentinel "data: [DONE]". None of those three carry content and
        none of them is an error.

        A chunk with no content is also normal rather than exceptional: the
        first frame of most streams announces the assistant role and nothing
        else, and finish-reason frames carry a null content. Yielding "" for
        those would be wrong in a way that matters - Stage 9 treats a provider
        that yields nothing usable as having violated its contract, and would
        fail over to the next provider mid-answer.
        """
        line = raw.decode("utf-8").strip()
        if not line or not line.startswith("data:"):
            return
        data = line[len("data:"):].strip()
        if data == "[DONE]":
            return
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            # A torn or non-JSON keepalive frame. The tokens before it were
            # still real, so this is skipped rather than raised on.
            return
        choices = chunk.get("choices") or []
        if not choices:
            return
        content = (choices[0].get("delta") or {}).get("content")
        if content:
            yield content

    def _describe_http_error(self, e: urllib.error.HTTPError) -> str:
        """
        An HTTP failure said in terms of what the user has to change.

        The body is read because these APIs put the actual reason there -
        "model not found", "insufficient quota" - and a bare "400 Bad Request"
        sends somebody to inspect a request they cannot see. It is truncated
        because an error body is not always small, and it is wrapped in its own
        try because a failure while explaining a failure should not replace the
        original one.

        401 and 404 are named specifically. They are the two mistakes that
        configuring an endpoint by hand actually produces - a wrong or expired
        key, and a model name that this particular server does not serve -
        and both are indistinguishable from "the service is broken" unless
        somebody says so.
        """
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            body = ""

        if e.code == 401:
            hint = f"{self.provider_id} rejected the API key (401)."
        elif e.code == 404:
            hint = (
                f"{self.provider_id} has no model '{self.model_name}' "
                f"at {self.base_url} (404)."
            )
        else:
            hint = f"{self.provider_id} returned {e.code}: {e.reason}."

        return f"{hint} {body}".strip()

    def is_available(self) -> bool:
        """
        GET /v1/models, which every implementation of this protocol serves and
        which needs no model name to be valid - so this answers "is there
        something there, and does it accept my key" without depending on the
        model being correct.

        Must complete quickly and must not raise, per the base class. The
        timeout is short for the same reason Ollama's is: this is called to
        decide whether to bother, and a slow "no" is worse than a fast one.
        """
        req = urllib.request.Request(
            f"{self.base_url}/v1/models", headers=self._headers(), method="GET"
        )
        try:
            with urllib.request.urlopen(req, timeout=3) as response:
                return response.status == 200
        except Exception:
            return False

    def get_model_info(self) -> Dict[str, Any]:
        # No api_key. See the module docstring: this dict reaches the trace log.
        return {
            "provider_id": self.provider_id,
            "is_local": self.is_local,
            "model_name": self.model_name,
            "host": self.base_url,
        }
