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
        timeout_seconds: int = 30
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
