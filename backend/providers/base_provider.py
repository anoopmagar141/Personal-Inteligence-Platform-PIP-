from abc import ABC, abstractmethod
from typing import Iterator, Optional, List, Dict, Any

class ProviderUnavailableError(Exception):
    """Raised when the provider is unreachable (connection-level failure)."""
    pass

class ProviderExecutionError(Exception):
    """Raised when the provider is reachable but the request failed (runtime-level failure)."""
    pass

class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers in PIP."""

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        context: Optional[str] = None,
        max_tokens: int = 2000,
        timeout_seconds: int = 30
    ) -> Iterator[str]:
        """
        Stream response tokens one by one.
        messages: list of {role: str, content: str}
        Yields: str — one token or word fragment at a time
        Raises: ProviderUnavailableError, ProviderExecutionError
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Returns True if provider can accept requests.
        Must complete quickly. Must not raise exceptions.
        """
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """
        Returns metadata about the provider and model.
        Returns dict with keys like: model_name, context_window, is_local, provider_id
        """
        pass
