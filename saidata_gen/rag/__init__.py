"""
RAG (Retrieval-Augmented Generation) integration for AI-enhanced metadata generation.

This module provides RAG capabilities for enhancing software metadata using
Large Language Models (LLMs) from various providers.
"""

from .engine import RAGEngine
from .providers import LLMProvider, OpenAIProvider, AnthropicProvider, LocalModelProvider
from .exceptions import RAGError, LLMProviderError, PromptError

__all__ = [
    'RAGEngine',
    'LLMProvider',
    'OpenAIProvider', 
    'AnthropicProvider',
    'LocalModelProvider',
    'RAGError',
    'LLMProviderError',
    'PromptError'
]