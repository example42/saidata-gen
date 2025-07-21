"""
Tests for RAG LLM providers.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from saidata_gen.rag.providers import (
    LLMProvider, LLMResponse, OpenAIProvider, AnthropicProvider, LocalModelProvider
)
from saidata_gen.rag.exceptions import (
    LLMProviderError, APIKeyError, RateLimitError, 
    TokenLimitError, ModelNotAvailableError
)


class TestLLMResponse:
    """Test LLM response data class."""
    
    def test_llm_response_creation(self):
        """Test creating LLM response."""
        response = LLMResponse(
            content="Test content",
            model="gpt-3.5-turbo",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            finish_reason="stop",
            metadata={"response_id": "test-123"}
        )
        
        assert response.content == "Test content"
        assert response.model == "gpt-3.5-turbo"
        assert response.usage["total_tokens"] == 30
        assert response.finish_reason == "stop"
        assert response.metadata["response_id"] == "test-123"


class TestOpenAIProvider:
    """Test OpenAI provider."""
    
    def test_initialization_with_api_key(self):
        """Test OpenAI provider initialization with API key."""
        provider = OpenAIProvider(
            model="gpt-4",
            api_key="test-key",
            base_url="https://custom.openai.com"
        )
        
        assert provider.model == "gpt-4"
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://custom.openai.com"
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'env-key'})
    def test_initialization_with_env_key(self):
        """Test OpenAI provider initialization with environment API key."""
        provider = OpenAIProvider(model="gpt-3.5-turbo")
        
        assert provider.api_key == "env-key"
        assert provider.base_url == "https://api.openai.com/v1"
    
    def test_initialization_no_api_key(self):
        """Test OpenAI provider initialization without API key raises error."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(APIKeyError, match="OpenAI API key is required"):
                OpenAIProvider(model="gpt-3.5-turbo")
    
    @patch('builtins.__import__')
    def test_get_client_success(self, mock_import):
        """Test getting OpenAI client successfully."""
        mock_openai_module = Mock()
        mock_client = Mock()
        mock_openai_module.OpenAI.return_value = mock_client
        
        def mock_import_func(name, *args, **kwargs):
            if name == 'openai':
                return mock_openai_module
            return __import__(name, *args, **kwargs)
        
        mock_import.side_effect = mock_import_func
        
        provider = OpenAIProvider(model="gpt-3.5-turbo", api_key="test-key")
        client = provider._get_client()
        
        assert client == mock_client
        mock_openai_module.OpenAI.assert_called_once_with(
            api_key="test-key",
            base_url="https://api.openai.com/v1"
        )
    
    @patch('builtins.__import__')
    def test_get_client_import_error(self, mock_import):
        """Test getting OpenAI client with import error."""
        def mock_import_func(name, *args, **kwargs):
            if name == 'openai':
                raise ImportError("No module named 'openai'")
            return __import__(name, *args, **kwargs)
        
        mock_import.side_effect = mock_import_func
        
        provider = OpenAIProvider(model="gpt-3.5-turbo", api_key="test-key")
        
        with pytest.raises(LLMProviderError, match="OpenAI library not installed"):
            provider._get_client()
    
    @patch('saidata_gen.rag.providers.OpenAIProvider._get_client')
    def test_generate_success(self, mock_get_client):
        """Test successful text generation."""
        # Setup mock response
        mock_choice = Mock()
        mock_choice.message.content = "Generated text"
        mock_choice.finish_reason = "stop"
        
        mock_usage = Mock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 20
        mock_usage.total_tokens = 30
        
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.usage = mock_usage
        mock_response.model = "gpt-3.5-turbo"
        mock_response.id = "response-123"
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        provider = OpenAIProvider(model="gpt-3.5-turbo", api_key="test-key")
        result = provider.generate("Test prompt", temperature=0.5, max_tokens=100)
        
        assert isinstance(result, LLMResponse)
        assert result.content == "Generated text"
        assert result.model == "gpt-3.5-turbo"
        assert result.usage["total_tokens"] == 30
        assert result.finish_reason == "stop"
        assert result.metadata["response_id"] == "response-123"
        
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Test prompt"}],
            temperature=0.5,
            max_tokens=100
        )
    
    @patch('saidata_gen.rag.providers.OpenAIProvider._get_client')
    def test_generate_rate_limit_error(self, mock_get_client):
        """Test generation with rate limit error."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("rate_limit exceeded")
        mock_get_client.return_value = mock_client
        
        provider = OpenAIProvider(model="gpt-3.5-turbo", api_key="test-key")
        
        with pytest.raises(RateLimitError, match="OpenAI rate limit exceeded"):
            provider.generate("Test prompt")
    
    @patch('saidata_gen.rag.providers.OpenAIProvider._get_client')
    def test_generate_token_limit_error(self, mock_get_client):
        """Test generation with token limit error."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("token limit exceeded")
        mock_get_client.return_value = mock_client
        
        provider = OpenAIProvider(model="gpt-3.5-turbo", api_key="test-key")
        
        with pytest.raises(TokenLimitError, match="OpenAI token limit exceeded"):
            provider.generate("Test prompt")
    
    @patch('saidata_gen.rag.providers.OpenAIProvider._get_client')
    def test_generate_model_not_found_error(self, mock_get_client):
        """Test generation with model not found error."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("model not found")
        mock_get_client.return_value = mock_client
        
        provider = OpenAIProvider(model="invalid-model", api_key="test-key")
        
        with pytest.raises(ModelNotAvailableError, match="OpenAI model not available"):
            provider.generate("Test prompt")
    
    @patch('saidata_gen.rag.providers.OpenAIProvider._get_client')
    def test_is_available_true(self, mock_get_client):
        """Test provider availability check - available."""
        mock_client = Mock()
        mock_client.models.list.return_value = Mock()
        mock_get_client.return_value = mock_client
        
        provider = OpenAIProvider(model="gpt-3.5-turbo", api_key="test-key")
        assert provider.is_available() is True
    
    @patch('saidata_gen.rag.providers.OpenAIProvider._get_client')
    def test_is_available_false(self, mock_get_client):
        """Test provider availability check - not available."""
        mock_client = Mock()
        mock_client.models.list.side_effect = Exception("API error")
        mock_get_client.return_value = mock_client
        
        provider = OpenAIProvider(model="gpt-3.5-turbo", api_key="test-key")
        assert provider.is_available() is False
    
    @patch('saidata_gen.rag.providers.OpenAIProvider._get_client')
    def test_get_models(self, mock_get_client):
        """Test getting available models."""
        mock_model1 = Mock()
        mock_model1.id = "gpt-3.5-turbo"
        mock_model2 = Mock()
        mock_model2.id = "gpt-4"
        
        mock_models_response = Mock()
        mock_models_response.data = [mock_model1, mock_model2]
        
        mock_client = Mock()
        mock_client.models.list.return_value = mock_models_response
        mock_get_client.return_value = mock_client
        
        provider = OpenAIProvider(model="gpt-3.5-turbo", api_key="test-key")
        models = provider.get_models()
        
        assert models == ["gpt-3.5-turbo", "gpt-4"]


class TestAnthropicProvider:
    """Test Anthropic provider."""
    
    def test_initialization_with_api_key(self):
        """Test Anthropic provider initialization with API key."""
        provider = AnthropicProvider(
            model="claude-3-sonnet-20240229",
            api_key="test-key",
            base_url="https://custom.anthropic.com"
        )
        
        assert provider.model == "claude-3-sonnet-20240229"
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://custom.anthropic.com"
    
    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'env-key'})
    def test_initialization_with_env_key(self):
        """Test Anthropic provider initialization with environment API key."""
        provider = AnthropicProvider()
        
        assert provider.api_key == "env-key"
        assert provider.base_url == "https://api.anthropic.com"
    
    def test_initialization_no_api_key(self):
        """Test Anthropic provider initialization without API key raises error."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(APIKeyError, match="Anthropic API key is required"):
                AnthropicProvider()
    
    @patch('builtins.__import__')
    def test_get_client_success(self, mock_import):
        """Test getting Anthropic client successfully."""
        mock_anthropic_module = Mock()
        mock_client = Mock()
        mock_anthropic_module.Anthropic.return_value = mock_client
        
        def mock_import_func(name, *args, **kwargs):
            if name == 'anthropic':
                return mock_anthropic_module
            return __import__(name, *args, **kwargs)
        
        mock_import.side_effect = mock_import_func
        
        provider = AnthropicProvider(api_key="test-key")
        client = provider._get_client()
        
        assert client == mock_client
        mock_anthropic_module.Anthropic.assert_called_once_with(
            api_key="test-key",
            base_url="https://api.anthropic.com"
        )
    
    @patch('builtins.__import__')
    def test_get_client_import_error(self, mock_import):
        """Test getting Anthropic client with import error."""
        def mock_import_func(name, *args, **kwargs):
            if name == 'anthropic':
                raise ImportError("No module named 'anthropic'")
            return __import__(name, *args, **kwargs)
        
        mock_import.side_effect = mock_import_func
        
        provider = AnthropicProvider(api_key="test-key")
        
        with pytest.raises(LLMProviderError, match="Anthropic library not installed"):
            provider._get_client()
    
    def test_get_models(self):
        """Test getting available Anthropic models."""
        provider = AnthropicProvider(api_key="test-key")
        models = provider.get_models()
        
        assert "claude-3-opus-20240229" in models
        assert "claude-3-sonnet-20240229" in models
        assert "claude-3-haiku-20240307" in models


class TestLocalModelProvider:
    """Test local model provider."""
    
    def test_initialization(self):
        """Test local model provider initialization."""
        provider = LocalModelProvider(
            model="llama2",
            base_url="http://localhost:8080"
        )
        
        assert provider.model == "llama2"
        assert provider.base_url == "http://localhost:8080"
        assert provider.api_key is None
    
    @patch('requests.post')
    def test_generate_success(self, mock_post):
        """Test successful text generation with local model."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Generated text",
            "prompt_eval_count": 10,
            "eval_count": 20,
            "done_reason": "stop",
            "eval_duration": 1000000,
            "load_duration": 500000
        }
        mock_post.return_value = mock_response
        
        provider = LocalModelProvider(model="llama2")
        result = provider.generate("Test prompt", temperature=0.5, max_tokens=100)
        
        assert isinstance(result, LLMResponse)
        assert result.content == "Generated text"
        assert result.model == "llama2"
        assert result.usage["prompt_tokens"] == 10
        assert result.usage["completion_tokens"] == 20
        assert result.usage["total_tokens"] == 30
        assert result.finish_reason == "stop"
        
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://localhost:11434/api/generate"
        
        payload = call_args[1]['json']
        assert payload['model'] == "llama2"
        assert payload['prompt'] == "Test prompt"
        assert payload['options']['temperature'] == 0.5
        assert payload['options']['num_predict'] == 100
    
    @patch('requests.post')
    def test_generate_server_error(self, mock_post):
        """Test generation with server error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_post.return_value = mock_response
        
        provider = LocalModelProvider(model="llama2")
        
        with pytest.raises(LLMProviderError, match="Local model server error"):
            provider.generate("Test prompt")
    
    @patch('requests.post')
    def test_generate_connection_error(self, mock_post):
        """Test generation with connection error."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        provider = LocalModelProvider(model="llama2")
        
        with pytest.raises(LLMProviderError, match="Cannot connect to local model server"):
            provider.generate("Test prompt")
    
    @patch('requests.get')
    def test_is_available_true(self, mock_get):
        """Test provider availability check - available."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        provider = LocalModelProvider(model="llama2")
        assert provider.is_available() is True
    
    @patch('requests.get')
    def test_is_available_false(self, mock_get):
        """Test provider availability check - not available."""
        mock_get.side_effect = Exception("Connection error")
        
        provider = LocalModelProvider(model="llama2")
        assert provider.is_available() is False
    
    @patch('requests.get')
    def test_get_models(self, mock_get):
        """Test getting available local models."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama2"},
                {"name": "codellama"},
                {"name": "mistral"}
            ]
        }
        mock_get.return_value = mock_response
        
        provider = LocalModelProvider(model="llama2")
        models = provider.get_models()
        
        assert models == ["llama2", "codellama", "mistral"]
    
    @patch('requests.get')
    def test_get_models_error(self, mock_get):
        """Test getting models with error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Server error"
        mock_get.return_value = mock_response
        
        provider = LocalModelProvider(model="llama2")
        
        with pytest.raises(LLMProviderError, match="Failed to get models"):
            provider.get_models()