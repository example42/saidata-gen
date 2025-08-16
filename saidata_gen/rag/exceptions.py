"""
RAG-specific exceptions.
"""

from saidata_gen.core.exceptions import SaidataGenError


class RAGError(SaidataGenError):
    """Base exception for RAG operations."""
    pass


class LLMProviderError(RAGError):
    """Raised when LLM provider operations fail."""
    pass


class PromptError(RAGError):
    """Raised when prompt template operations fail."""
    pass


class ModelNotAvailableError(LLMProviderError):
    """Raised when the requested model is not available."""
    pass


class APIKeyError(LLMProviderError):
    """Raised when API key is missing or invalid."""
    pass


class RateLimitError(LLMProviderError):
    """Raised when API rate limit is exceeded."""
    pass


class TokenLimitError(LLMProviderError):
    """Raised when token limit is exceeded."""
    pass