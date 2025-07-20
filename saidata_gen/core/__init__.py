"""Core components for the saidata generator."""

from .engine import SaidataEngine
from .interfaces import (
    FetcherConfig,
    FetchResult,
    PackageInfo,
    PackageDetails,
    RepositoryData
)
from .exceptions import (
    SaidataGenError,
    ValidationError,
    FetchError,
    GenerationError,
    RAGError,
    ConfigurationError
)

__all__ = [
    "SaidataEngine",
    "FetcherConfig",
    "FetchResult",
    "PackageInfo",
    "PackageDetails",
    "RepositoryData",
    "SaidataGenError",
    "ValidationError",
    "FetchError",
    "GenerationError",
    "RAGError",
    "ConfigurationError"
]