"""
AI module for saidata-gen.

This module provides AI-enhanced metadata generation capabilities using
various LLM providers including OpenAI, Anthropic, and local models.
"""

from .enhancer import AIMetadataEnhancer

__all__ = ["AIMetadataEnhancer"]