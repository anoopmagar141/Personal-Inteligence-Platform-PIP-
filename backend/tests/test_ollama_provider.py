import pytest
import json
from unittest.mock import patch, MagicMock
import urllib.error

from backend.providers.ollama_provider import OllamaProvider
from backend.providers.base_provider import ProviderUnavailableError, ProviderExecutionError

def test_ollama_provider_get_model_info():
    provider = OllamaProvider(model_name="test-model")
    info = provider.get_model_info()
    assert info["provider_id"] == "ollama"
    assert info["is_local"] is True
    assert info["model_name"] == "test-model"

@patch('urllib.request.urlopen')
def test_ollama_provider_is_available_true(mock_urlopen):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    provider = OllamaProvider()
    assert provider.is_available() is True

@patch('urllib.request.urlopen')
def test_ollama_provider_is_available_false(mock_urlopen):
    mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
    
    provider = OllamaProvider()
    assert provider.is_available() is False

@patch('urllib.request.urlopen')
def test_ollama_provider_chat_success(mock_urlopen):
    mock_response = MagicMock()
    # Mocking a streamed response with two chunks
    chunk1 = json.dumps({"message": {"content": "Hello "}}).encode('utf-8') + b'\n'
    chunk2 = json.dumps({"message": {"content": "World!"}}).encode('utf-8') + b'\n'
    mock_response.__iter__.return_value = [chunk1, chunk2]
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    provider = OllamaProvider()
    tokens = list(provider.chat([{"role": "user", "content": "hi"}]))
    
    assert tokens == ["Hello ", "World!"]

@patch('urllib.request.urlopen')
def test_ollama_provider_chat_unavailable(mock_urlopen):
    # Simulate connection refused
    mock_urlopen.side_effect = urllib.error.URLError(ConnectionRefusedError("Connection refused"))
    
    provider = OllamaProvider()
    with pytest.raises(ProviderUnavailableError) as exc:
        list(provider.chat([{"role": "user", "content": "hi"}]))
    
    assert "Ollama is unreachable" in str(exc.value)

@patch('urllib.request.urlopen')
def test_ollama_provider_chat_execution_error(mock_urlopen):
    # Simulate some other HTTP error (e.g. 404 Model Not Found)
    mock_urlopen.side_effect = urllib.error.HTTPError("http://localhost:11434/api/chat", 404, "Not Found", {}, None)
    
    provider = OllamaProvider()
    with pytest.raises(ProviderExecutionError) as exc:
        list(provider.chat([{"role": "user", "content": "hi"}]))
        
    assert "Ollama returned 404" in str(exc.value)
    assert "is the model pulled?" in str(exc.value)
