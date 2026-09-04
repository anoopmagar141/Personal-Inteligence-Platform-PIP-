import json
import urllib.request
import urllib.error
from typing import Iterator, Optional, List, Dict, Any

from backend.providers.base_provider import BaseLLMProvider, ProviderUnavailableError, ProviderExecutionError

class OllamaProvider(BaseLLMProvider):
    def __init__(self, model_name: str = "llama3.1:8b", host: str = "http://localhost:11434"):
        self.model_name = model_name
        self.host = host

    def chat(
        self,
        messages: List[Dict[str, str]],
        context: Optional[str] = None,
        max_tokens: int = 2000,
        timeout_seconds: int = 30,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Iterator[str]:
        if context:
            messages = [{"role": "system", "content": context}] + messages

        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "options": {
                "num_predict": max_tokens
            }
        }

        # Ollama's structured-output field: given a JSON Schema it constrains
        # sampling so only tokens keeping the output valid against that schema
        # can be emitted. Malformed JSON stops being something the prompt asks
        # the model to avoid and becomes something it cannot produce.
        #
        # Streaming is unaffected - chunks still arrive token by token and the
        # completed text is valid JSON - so this stays compatible with the
        # generator interface Stage 9 relies on, even though the one caller
        # that uses it (the Observer) joins the whole stream before parsing.
        if response_format is not None:
            payload["format"] = response_format

        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                for line in response:
                    if line:
                        chunk = json.loads(line.decode('utf-8'))
                        if 'message' in chunk and 'content' in chunk['message']:
                            yield chunk['message']['content']
        except urllib.error.HTTPError as e:
            raise ProviderExecutionError(f"Ollama returned {e.code}: {e.reason} — is the model pulled?")
        except urllib.error.URLError as e:
            if isinstance(e.reason, ConnectionRefusedError) or "Connection refused" in str(e.reason):
                raise ProviderUnavailableError(f"Ollama is unreachable at {self.host}: {str(e)}")
            raise ProviderExecutionError(f"Network error during Ollama execution: {str(e)}")
        except Exception as e:
            raise ProviderExecutionError(f"Unexpected error during Ollama execution: {str(e)}")

    def is_available(self) -> bool:
        req = urllib.request.Request(f"{self.host}/api/tags", method='GET')
        try:
            with urllib.request.urlopen(req, timeout=2) as response:
                return response.status == 200
        except Exception:
            return False

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "provider_id": "ollama",
            "is_local": True,
            "model_name": self.model_name,
            "host": self.host
        }


def list_models(host: str = "http://localhost:11434") -> List[Dict[str, Any]]:
    """
    Every model Ollama has locally pulled, via its GET /api/tags endpoint -
    standalone rather than an OllamaProvider method, since it isn't tied to
    any one model_name (a model picker needs this BEFORE a model_name is
    chosen, not after).
    """
    req = urllib.request.Request(f"{host}/api/tags", method='GET')
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data.get('models', [])
    except urllib.error.URLError as e:
        raise ProviderUnavailableError(f"Ollama is unreachable at {host}: {e}")
    except Exception as e:
        raise ProviderExecutionError(f"Unexpected error listing Ollama models: {e}")


# Models worth suggesting, with what they cost to run.
#
# A curated list rather than a live catalogue because Ollama has no public
# library API - and scraping its website would make PIP's model picker depend
# on somebody else's HTML. This is guidance, not a limit: the pull endpoint
# accepts any name, so anything in Ollama's library works whether or not it
# appears here.
#
# vram_gb is what the quantised weights need resident, which is the number that
# decides whether a model is usable rather than merely downloadable. It is
# approximate by nature - context length and KV cache push real usage above it -
# so it is used to warn, never to refuse.
MODEL_CATALOG: List[Dict[str, Any]] = [
    {"name": "llama3.1:8b", "size_gb": 4.7, "vram_gb": 6.0,
     "note": "PIP's default. Good general reasoning, and what the Observer was benchmarked on."},
    {"name": "qwen2.5:7b", "size_gb": 4.7, "vram_gb": 6.0,
     "note": "Strong at structured output, which is most of what the pipeline asks for."},
    {"name": "mistral:7b", "size_gb": 4.1, "vram_gb": 5.5,
     "note": "Fast and light. Weaker at long multi-step reasoning."},
    {"name": "gemma2:9b", "size_gb": 5.4, "vram_gb": 7.0,
     "note": "Good writing quality. Close to the limit of an 8GB card."},
    {"name": "phi3:3.8b", "size_gb": 2.2, "vram_gb": 3.5,
     "note": "Small and quick. Useful on a laptop GPU or alongside other work."},
    {"name": "deepseek-r1:8b", "size_gb": 4.9, "vram_gb": 6.5,
     "note": "Reasoning-focused. Produces long deliberation before answering."},
    {"name": "qwen2.5:14b", "size_gb": 9.0, "vram_gb": 11.0,
     "note": "Noticeably better reasoning, and past what an 8GB card holds."},
]


def detect_vram_gb() -> Optional[float]:
    """
    Total VRAM on the first GPU, or None if it cannot be determined.

    Best effort through nvidia-smi, and None is a perfectly good answer: no
    NVIDIA GPU, no driver, a CPU-only machine, or an AMD card all land here.
    The caller warns when it knows the number and stays quiet when it does not,
    which is better than inventing a limit for hardware it cannot see.
    """
    import shutil
    import subprocess

    binary = shutil.which("nvidia-smi")
    if not binary:
        return None
    try:
        out = subprocess.run(
            [binary, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=True,
        )
        first = out.stdout.strip().splitlines()[0]
        return round(int(first.strip()) / 1024, 1)
    except Exception:
        return None


def pull_model(name: str, on_progress, host: str = "http://localhost:11434") -> None:
    """
    Pull a model, reporting progress as Ollama streams it.

    POST /api/pull answers with newline-delimited JSON - one object per status
    change, carrying `completed` and `total` byte counts during the download
    itself. Read line by line rather than with json.load(): the whole point is
    to report progress while it happens, and a parser that waits for the body
    to end would report nothing until there was nothing left to report.

    on_progress is called with each decoded object. Raises on transport failure
    and on any object carrying an `error`, which is how Ollama reports a name
    that does not exist in its library - the one mistake a free-text model field
    makes easy.
    """
    payload = json.dumps({"name": name, "stream": True}).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/api/pull", data=payload, method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        # No timeout on the response itself: a 5GB pull on a slow connection is
        # a legitimately long-running request, and the progress callback is what
        # tells the caller it is still alive.
        with urllib.request.urlopen(req) as response:
            for raw in response:
                line = raw.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("error"):
                    raise ProviderExecutionError(f"Ollama could not pull '{name}': {event['error']}")
                on_progress(event)
    except urllib.error.URLError as e:
        raise ProviderUnavailableError(f"Ollama is unreachable at {host}: {e}")
