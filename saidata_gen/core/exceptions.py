"""
Exceptions for saidata-gen.

This module contains the exception hierarchy for saidata-gen operations.
"""


class SaidataGenError(Exception):
    """Base exception for saidata-gen operations."""
    pass


class ValidationError(SaidataGenError):
    """Raised when schema validation fails."""
    pass


class FetchError(SaidataGenError):
    """Raised when repository fetching fails."""
    pass


class GenerationError(SaidataGenError):
    """Raised when metadata generation fails."""
    pass


class RAGError(SaidataGenError):
    """Raised when RAG operations fail."""
    pass


class ConfigurationError(SaidataGenError):
    """Raised when configuration is invalid."""
    pass