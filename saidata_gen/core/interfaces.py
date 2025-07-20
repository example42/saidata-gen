"""
Core interfaces for saidata-gen.

This module contains the core interfaces and data models used throughout the application.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Union


@dataclass
class SaidataMetadata:
    """
    Core data model for saidata metadata.
    """
    version: str = "0.1"
    packages: Dict[str, "PackageConfig"] = field(default_factory=dict)
    services: Dict[str, "ServiceConfig"] = field(default_factory=dict)
    directories: Dict[str, "DirectoryConfig"] = field(default_factory=dict)
    processes: Dict[str, "ProcessConfig"] = field(default_factory=dict)
    ports: Dict[str, "PortConfig"] = field(default_factory=dict)
    containers: Dict[str, "ContainerConfig"] = field(default_factory=dict)
    charts: Dict[str, dict] = field(default_factory=dict)
    repos: Dict[str, dict] = field(default_factory=dict)
    urls: "URLConfig" = field(default_factory=lambda: URLConfig())
    language: Optional[str] = None
    description: Optional[str] = None
    category: "CategoryConfig" = field(default_factory=lambda: CategoryConfig())
    license: Optional[str] = None
    platforms: List[str] = field(default_factory=list)


@dataclass
class PackageConfig:
    """
    Configuration for a software package.
    """
    name: Optional[str] = None
    version: Optional[str] = None
    install_options: Optional[str] = None


@dataclass
class ServiceConfig:
    """
    Configuration for a service.
    """
    name: Optional[str] = None
    enabled: bool = False
    status: Optional[str] = None


@dataclass
class DirectoryConfig:
    """
    Configuration for a directory.
    """
    path: Optional[str] = None
    owner: Optional[str] = None
    group: Optional[str] = None
    mode: Optional[str] = None


@dataclass
class ProcessConfig:
    """
    Configuration for a process.
    """
    name: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None


@dataclass
class PortConfig:
    """
    Configuration for a port.
    """
    number: Optional[int] = None
    protocol: Optional[str] = None
    service: Optional[str] = None


@dataclass
class ContainerConfig:
    """
    Configuration for a container.
    """
    name: Optional[str] = None
    image: Optional[str] = None
    tag: Optional[str] = None


@dataclass
class URLConfig:
    """
    Configuration for URLs.
    """
    website: Optional[str] = None
    sbom: Optional[str] = None
    issues: Optional[str] = None
    documentation: Optional[str] = None
    support: Optional[str] = None
    source: Optional[str] = None
    license: Optional[str] = None
    changelog: Optional[str] = None
    download: Optional[str] = None
    icon: Optional[str] = None


@dataclass
class CategoryConfig:
    """
    Configuration for categories.
    """
    default: Optional[str] = None
    sub: Optional[str] = None
    tags: Optional[List[str]] = None


@dataclass
class GenerationOptions:
    """
    Options for metadata generation.
    """
    providers: List[str] = field(default_factory=list)
    use_rag: bool = False
    rag_provider: str = "openai"
    include_dev_packages: bool = False
    confidence_threshold: float = 0.7
    output_format: str = "yaml"
    validate_schema: bool = True


@dataclass
class BatchOptions:
    """
    Options for batch processing.
    """
    output_dir: str = "."
    providers: List[str] = field(default_factory=list)
    use_rag: bool = False
    rag_provider: str = "openai"
    include_dev_packages: bool = False
    confidence_threshold: float = 0.7
    output_format: str = "yaml"
    validate_schema: bool = True
    max_concurrent: int = 5
    continue_on_error: bool = True


@dataclass
class RAGConfig:
    """
    Configuration for RAG.
    """
    provider: str = "openai"
    model: str = "gpt-3.5-turbo"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 1000


@dataclass
class FetcherConfig:
    """
    Configuration for fetcher.
    """
    cache_dir: str = "~/.saidata-gen/cache"
    cache_ttl: int = 3600
    concurrent_requests: int = 5
    request_timeout: int = 30
    retry_count: int = 3


class ValidationLevel(Enum):
    """
    Validation level.
    """
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """
    Validation issue.
    """
    level: ValidationLevel
    message: str
    path: str
    schema_path: Optional[str] = None


@dataclass
class ValidationResult:
    """
    Result of validation.
    """
    valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    file_path: Optional[str] = None


@dataclass
class BatchValidationResult:
    """
    Result of batch validation.
    """
    results: Dict[str, ValidationResult] = field(default_factory=dict)
    summary: Dict[str, int] = field(default_factory=dict)


@dataclass
class MetadataResult:
    """
    Result of metadata generation.
    """
    metadata: SaidataMetadata
    file_path: Optional[str] = None
    validation_result: Optional[ValidationResult] = None
    confidence_scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class BatchResult:
    """
    Result of batch processing.
    """
    results: Dict[str, Union[MetadataResult, Exception]] = field(default_factory=dict)
    summary: Dict[str, int] = field(default_factory=dict)


@dataclass
class SoftwareMatch:
    """
    Match for a software package.
    """
    name: str
    provider: str
    version: Optional[str] = None
    description: Optional[str] = None
    score: float = 0.0
    details: Dict[str, any] = field(default_factory=dict)


@dataclass
class FetchResult:
    """
    Result of repository data fetching.
    """
    success: bool
    providers: Dict[str, bool] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    cache_hits: Dict[str, bool] = field(default_factory=dict)


@dataclass
class RepositoryData:
    """
    Data from a repository.
    """
    provider: str
    packages: Dict[str, Dict[str, any]] = field(default_factory=dict)
    timestamp: Optional[float] = None
    source_url: Optional[str] = None


@dataclass
class PackageInfo:
    """
    Information about a package.
    """
    name: str
    provider: str
    version: Optional[str] = None
    description: Optional[str] = None
    details: Dict[str, any] = field(default_factory=dict)


@dataclass
class PackageDetails:
    """
    Detailed information about a package.
    """
    name: str
    provider: str
    version: Optional[str] = None
    description: Optional[str] = None
    license: Optional[str] = None
    homepage: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    maintainer: Optional[str] = None
    source_url: Optional[str] = None
    download_url: Optional[str] = None
    checksum: Optional[str] = None
    raw_data: Dict[str, any] = field(default_factory=dict)