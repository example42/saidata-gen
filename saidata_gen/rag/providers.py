"""
LLM provider implementations for RAG integration.
"""

import json
import os
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .exceptions import (
    LLMProviderError, APIKeyError, RateLimitError, 
    TokenLimitError, ModelNotAvailableError
)


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str
    model: str
    usage: Dict[str, int]
    finish_reason: str
    metadata: Dict[str, Any]


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, model: str, api_key: Optional[str] = None, 
                 base_url: Optional[str] = None, **kwargs):
        """
        Initialize the LLM provider.
        
        Args:
            model: Model name to use
            api_key: API key for authentication
            base_url: Base URL for the API
            **kwargs: Additional provider-specific configuration
        """
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.config = kwargs
        
    @abstractmethod
    def generate(self, prompt: str, temperature: float = 0.1, 
                max_tokens: int = 1000, **kwargs) -> LLMResponse:
        """
        Generate text using the LLM.
        
        Args:
            prompt: Input prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional generation parameters
            
        Returns:
            LLMResponse with generated content
            
        Raises:
            LLMProviderError: If generation fails
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is available.
        
        Returns:
            True if provider is available, False otherwise
        """
        pass
    
    @abstractmethod
    def get_models(self) -> List[str]:
        """
        Get list of available models.
        
        Returns:
            List of model names
        """
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""
    
    def __init__(self, model: str = "gpt-3.5-turbo", api_key: Optional[str] = None,
                 base_url: Optional[str] = None, **kwargs):
        """
        Initialize OpenAI provider.
        
        Args:
            model: OpenAI model name
            api_key: OpenAI API key (or from OPENAI_API_KEY env var)
            base_url: Custom base URL for OpenAI API
            **kwargs: Additional OpenAI-specific parameters
        """
        super().__init__(model, api_key, base_url, **kwargs)
        
        # Get API key from environment if not provided
        if not self.api_key:
            self.api_key = os.getenv('OPENAI_API_KEY')
            
        if not self.api_key:
            raise APIKeyError("OpenAI API key is required")
            
        # Set default base URL
        if not self.base_url:
            self.base_url = "https://api.openai.com/v1"
            
        # Initialize OpenAI client (lazy import to avoid dependency issues)
        self._client = None
        
    def _get_client(self):
        """Get OpenAI client with lazy initialization."""
        if self._client is None:
            try:
                import openai
                self._client = openai.OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
            except ImportError:
                raise LLMProviderError(
                    "OpenAI library not installed. Install with: pip install openai"
                )
        return self._client
    
    def generate(self, prompt: str, temperature: float = 0.1,
                max_tokens: int = 1000, **kwargs) -> LLMResponse:
        """Generate text using OpenAI API."""
        client = self._get_client()
        
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            choice = response.choices[0]
            usage = response.usage
            
            return LLMResponse(
                content=choice.message.content,
                model=response.model,
                usage={
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens
                },
                finish_reason=choice.finish_reason,
                metadata={"response_id": response.id}
            )
            
        except Exception as e:
            error_msg = str(e)
            
            # Handle specific OpenAI errors
            if "rate_limit" in error_msg.lower():
                raise RateLimitError(f"OpenAI rate limit exceeded: {error_msg}")
            elif "token" in error_msg.lower() and "limit" in error_msg.lower():
                raise TokenLimitError(f"OpenAI token limit exceeded: {error_msg}")
            elif "model" in error_msg.lower() and "not found" in error_msg.lower():
                raise ModelNotAvailableError(f"OpenAI model not available: {self.model}")
            else:
                raise LLMProviderError(f"OpenAI API error: {error_msg}")
    
    def is_available(self) -> bool:
        """Check if OpenAI provider is available."""
        try:
            client = self._get_client()
            # Try to list models as a health check
            client.models.list()
            return True
        except Exception:
            return False
    
    def get_models(self) -> List[str]:
        """Get list of available OpenAI models."""
        try:
            client = self._get_client()
            models = client.models.list()
            return [model.id for model in models.data]
        except Exception as e:
            raise LLMProviderError(f"Failed to get OpenAI models: {e}")


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""
    
    def __init__(self, model: str = "claude-3-haiku-20240307", api_key: Optional[str] = None,
                 base_url: Optional[str] = None, **kwargs):
        """
        Initialize Anthropic provider.
        
        Args:
            model: Anthropic model name
            api_key: Anthropic API key (or from ANTHROPIC_API_KEY env var)
            base_url: Custom base URL for Anthropic API
            **kwargs: Additional Anthropic-specific parameters
        """
        super().__init__(model, api_key, base_url, **kwargs)
        
        # Get API key from environment if not provided
        if not self.api_key:
            self.api_key = os.getenv('ANTHROPIC_API_KEY')
            
        if not self.api_key:
            raise APIKeyError("Anthropic API key is required")
            
        # Set default base URL
        if not self.base_url:
            self.base_url = "https://api.anthropic.com"
            
        # Initialize Anthropic client (lazy import to avoid dependency issues)
        self._client = None
        
    def _get_client(self):
        """Get Anthropic client with lazy initialization."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
            except ImportError:
                raise LLMProviderError(
                    "Anthropic library not installed. Install with: pip install anthropic"
                )
        return self._client
    
    def generate(self, prompt: str, temperature: float = 0.1,
                max_tokens: int = 1000, **kwargs) -> LLMResponse:
        """Generate text using Anthropic API."""
        client = self._get_client()
        
        try:
            response = client.messages.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            content = response.content[0].text if response.content else ""
            usage = response.usage
            
            return LLMResponse(
                content=content,
                model=response.model,
                usage={
                    "prompt_tokens": usage.input_tokens,
                    "completion_tokens": usage.output_tokens,
                    "total_tokens": usage.input_tokens + usage.output_tokens
                },
                finish_reason=response.stop_reason,
                metadata={"response_id": response.id}
            )
            
        except Exception as e:
            error_msg = str(e)
            
            # Handle specific Anthropic errors
            if "rate_limit" in error_msg.lower():
                raise RateLimitError(f"Anthropic rate limit exceeded: {error_msg}")
            elif "token" in error_msg.lower() and "limit" in error_msg.lower():
                raise TokenLimitError(f"Anthropic token limit exceeded: {error_msg}")
            elif "model" in error_msg.lower() and "not found" in error_msg.lower():
                raise ModelNotAvailableError(f"Anthropic model not available: {self.model}")
            else:
                raise LLMProviderError(f"Anthropic API error: {error_msg}")
    
    def is_available(self) -> bool:
        """Check if Anthropic provider is available."""
        try:
            # Simple test to check if API is accessible
            client = self._get_client()
            # Try a minimal request to test connectivity
            client.messages.create(
                model=self.model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            return True
        except Exception:
            return False
    
    def get_models(self) -> List[str]:
        """Get list of available Anthropic models."""
        # Anthropic doesn't provide a models endpoint, so return known models
        return [
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229", 
            "claude-3-haiku-20240307",
            "claude-2.1",
            "claude-2.0",
            "claude-instant-1.2"
        ]


class LocalModelProvider(LLMProvider):
    """Local model provider for Ollama and similar local model servers."""
    
    def __init__(self, model: str, api_key: Optional[str] = None,
                 base_url: str = "http://localhost:11434", **kwargs):
        """
        Initialize local model provider.
        
        Args:
            model: Local model name
            api_key: API key (usually not needed for local models)
            base_url: Base URL for local model server (default: Ollama)
            **kwargs: Additional local model parameters
        """
        super().__init__(model, api_key, base_url, **kwargs)
        
        # Local models typically don't need API keys
        self.api_key = api_key
        
    def generate(self, prompt: str, temperature: float = 0.1,
                max_tokens: int = 1000, **kwargs) -> LLMResponse:
        """Generate text using local model server."""
        import requests
        
        try:
            # Ollama API format
            payload = {
                "model": self.model,
                "prompt": prompt,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    **kwargs
                },
                "stream": False
            }
            
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                headers=headers,
                timeout=120
            )
            
            if response.status_code != 200:
                raise LLMProviderError(f"Local model server error: {response.text}")
            
            result = response.json()
            
            return LLMResponse(
                content=result.get("response", ""),
                model=self.model,
                usage={
                    "prompt_tokens": result.get("prompt_eval_count", 0),
                    "completion_tokens": result.get("eval_count", 0),
                    "total_tokens": result.get("prompt_eval_count", 0) + result.get("eval_count", 0)
                },
                finish_reason=result.get("done_reason", "stop"),
                metadata={
                    "eval_duration": result.get("eval_duration", 0),
                    "load_duration": result.get("load_duration", 0)
                }
            )
            
        except requests.exceptions.ConnectionError:
            raise LLMProviderError(
                f"Cannot connect to local model server at {self.base_url}. "
                "Make sure Ollama or your local model server is running."
            )
        except requests.exceptions.Timeout:
            raise LLMProviderError("Local model server request timed out")
        except Exception as e:
            raise LLMProviderError(f"Local model server error: {e}")
    
    def is_available(self) -> bool:
        """Check if local model server is available."""
        import requests
        
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
    
    def get_models(self) -> List[str]:
        """Get list of available local models."""
        import requests
        
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
            else:
                raise LLMProviderError(f"Failed to get models: {response.text}")
        except Exception as e:
            raise LLMProviderError(f"Failed to get local models: {e}")