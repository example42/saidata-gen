"""Core components for the saidata generator."""

from .engine import SaidataEngine
from .configuration import ConfigurationManager
from .directory_structure import DirectoryStructureGenerator
from .system_dependency_checker import SystemDependencyChecker
from .graceful_degradation import GracefulDegradationManager
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
    "ConfigurationManager",
    "DirectoryStructureGenerator",
    "SystemDependencyChecker",
    "GracefulDegradationManager",
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