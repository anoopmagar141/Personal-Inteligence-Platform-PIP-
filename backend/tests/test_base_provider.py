import pytest
from typing import Iterator, List, Dict, Optional, Any
from backend.providers.base_provider import BaseLLMProvider, ProviderUnavailableError, ProviderExecutionError

def test_base_provider_cannot_be_instantiated():
    with pytest.raises(TypeError) as exc:
        # Attempting to instantiate the ABC directly
        BaseLLMProvider()
    assert "Can't instantiate abstract class" in str(exc.value)

def test_concrete_provider_can_be_instantiated():
    # A minimal concrete subclass implementing all three abstract methods
    class DummyProvider(BaseLLMProvider):
        def chat(
            self,
            messages: List[Dict[str, str]],
            context: Optional[str] = None,
            max_tokens: int = 2000,
            timeout_seconds: int = 30
        ) -> Iterator[str]:
            yield "dummy_token"

        def is_available(self) -> bool:
            return True

        def get_model_info(self) -> Dict[str, Any]:
            return {"model_name": "dummy_model", "is_local": True}

    # Should instantiate without errors
    provider = DummyProvider()
    
    # Verify the methods work
    assert provider.is_available() is True
    assert provider.get_model_info()["model_name"] == "dummy_model"
    
    tokens = list(provider.chat([{"role": "user", "content": "hello"}]))
    assert tokens == ["dummy_token"]

def test_custom_exceptions():
    # Confirm ProviderUnavailableError can be raised and caught
    with pytest.raises(ProviderUnavailableError) as exc_unavail:
        raise ProviderUnavailableError("Provider offline")
    assert "Provider offline" in str(exc_unavail.value)

    # Confirm ProviderExecutionError can be raised and caught
    with pytest.raises(ProviderExecutionError) as exc_exec:
        raise ProviderExecutionError("Invalid request format")
    assert "Invalid request format" in str(exc_exec.value)
