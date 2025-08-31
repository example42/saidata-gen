# API Reference

Complete reference for the saidata-gen Python API for programmatic usage.

## Overview

The saidata-gen package provides a comprehensive Python API for generating, validating, and managing software metadata. The main entry point is the `SaidataEngine` class.

## Installation

```python
pip install saidata-gen
```

## Quick Start

```python
from saidata_gen import SaidataEngine
from saidata_gen.core.interfaces import GenerationOptions

# Initialize the engine
engine = SaidataEngine()

# Generate metadata
options = GenerationOptions(providers=['apt', 'brew'])
result = engine.generate_metadata('nginx', options)

# Access the generated metadata
print(result.metadata.description)
print(result.metadata.packages)
```

## Core Classes

### AIMetadataEnhancer

The AI metadata enhancer provides capabilities for enhancing software metadata using various LLM providers including OpenAI, Anthropic, and local models.

```python
from saidata_gen.ai.enhancer import AIMetadataEnhancer, AIProviderConfig

# Initialize with default OpenAI configuration
enhancer = AIMetadataEnhancer(provider="openai")

# Initialize with custom configuration
config = AIProviderConfig(
    provider="anthropic",
    model="claude-3-haiku-20240307",
    temperature=0.1,
    max_tokens=1000,
    rate_limit_requests_per_minute=30
)
enhancer = AIMetadataEnhancer(provider="anthropic", config=config)

# Enhance metadata for missing fields
result = enhancer.enhance_metadata(
    software_name="nginx",
    base_metadata=base_metadata,
    enhancement_types=["description", "categorization", "field_completion"]
)

if result.success:
    print(f"Enhanced metadata with confidence scores: {result.confidence_scores}")
else:
    print(f"Enhancement failed: {result.error_message}")
```

#### Methods

##### enhance_metadata()

Enhance metadata using AI for missing fields.

```python
def enhance_metadata(
    self,
    software_name: str,
    base_metadata: Dict[str, Any],
    enhancement_types: Optional[List[str]] = None
) -> AIEnhancementResult
```

**Parameters:**
- `software_name` (str): Name of the software
- `base_metadata` (Dict[str, Any]): Base metadata from repositories
- `enhancement_types` (Optional[List[str]]): Types of enhancement to apply. Defaults to ["description", "categorization", "field_completion"]

**Returns:**
- `AIEnhancementResult`: Result containing enhanced metadata, confidence scores, and processing information

**Example:**
```python
# Enhance metadata with specific enhancement types
result = enhancer.enhance_metadata(
    software_name="nginx",
    base_metadata={"version": "0.1", "packages": {}},
    enhancement_types=["description", "field_completion"]
)

if result.success:
    enhanced_data = result.enhanced_metadata
    print(f"Description: {enhanced_data.get('description')}")
    print(f"Website: {enhanced_data.get('urls', {}).get('website')}")
```

##### get_missing_fields()

Identify fields that are missing or have null values.

```python
def get_missing_fields(self, metadata: Dict[str, Any]) -> List[str]
```

**Parameters:**
- `metadata` (Dict[str, Any]): Metadata to analyze

**Returns:**
- `List[str]`: List of missing field paths

**Example:**
```python
# Identify missing fields
missing = enhancer.get_missing_fields({
    "version": "0.1",
    "packages": {"default": {"name": "nginx"}},
    "description": None,
    "urls": {}
})
print(missing)  # ['description', 'urls.website', 'urls.source', ...]
```

##### is_available()

Check if the AI provider is available and properly configured.

```python
def is_available(self) -> bool
```

**Returns:**
- `bool`: True if provider is available, False otherwise

**Example:**
```python
if enhancer.is_available():
    result = enhancer.enhance_metadata(software_name, metadata)
else:
    print("AI provider not available, skipping enhancement")
```

#### Configuration Classes

##### AIProviderConfig

Configuration for AI providers with security and rate limiting features.

```python
@dataclass
class AIProviderConfig:
    provider: str
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 1000
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit_requests_per_minute: int = 60
    rate_limit_tokens_per_minute: int = 90000
    enable_response_validation: bool = True
    api_key_env_var: Optional[str] = None
```

**Example:**
```python
# Configure for local model
local_config = AIProviderConfig(
    provider="local",
    model="llama2",
    base_url="http://localhost:11434",
    temperature=0.2,
    max_tokens=1500,
    rate_limit_requests_per_minute=120
)

enhancer = AIMetadataEnhancer(provider="local", config=local_config)
```

##### AIEnhancementResult

Result of AI metadata enhancement with detailed information.

```python
@dataclass
class AIEnhancementResult:
    enhanced_metadata: Dict[str, Any]
    confidence_scores: Dict[str, float]
    sources_used: List[str]
    processing_time: float
    enhancement_metadata: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error_message: Optional[str] = None
```

**Example:**
```python
result = enhancer.enhance_metadata("nginx", base_metadata)

print(f"Success: {result.success}")
print(f"Processing time: {result.processing_time:.2f}s")
print(f"Confidence scores: {result.confidence_scores}")
print(f"Sources used: {result.sources_used}")

if result.success:
    enhanced_data = result.enhanced_metadata
    # Use enhanced data...
```

### ConfigurationValidator

The configuration validator provides comprehensive functionality to validate provider configurations, identify redundant settings, and suggest optimizations for the override-only template system.

```python
from saidata_gen.validation.config_validator import ConfigurationValidator

# Initialize validator
validator = ConfigurationValidator()

# Validate a single provider override
result = validator.validate_provider_override(
    provider="apt",
    override_config={
        "version": "0.1",
        "packages": {"default": {"name": "nginx-core"}},
        "supported": True  # This might be redundant
    }
)

print(f"Valid: {result.valid}")
print(f"Quality score: {result.quality_score:.2f}")
print(f"Redundant keys: {result.redundant_keys}")
print(f"Suggestions: {len(result.suggestions)}")

# Validate multiple provider configurations
provider_configs = {
    "apt": {"version": "0.1", "packages": {"default": {"name": "nginx-core"}}},
    "brew": {"version": "0.1", "packages": {"default": {"name": "nginx"}}},
    "winget": {"version": "0.1", "supported": False}
}

report = validator.validate_configuration_consistency(provider_configs)
print(f"Overall quality: {report.overall_quality_score:.2f}")
print(f"Total redundant keys: {report.total_redundant_keys}")
```

#### Methods

##### validate_provider_override()

Validate that provider override only contains necessary overrides.

```python
def validate_provider_override(
    self,
    provider: str,
    override_config: Dict[str, Any],
    defaults: Optional[Dict[str, Any]] = None
) -> ProviderOverrideValidationResult
```

**Parameters:**
- `provider` (str): Provider name (e.g., 'apt', 'brew', 'winget')
- `override_config` (Dict[str, Any]): Provider override configuration
- `defaults` (Optional[Dict[str, Any]]): Default configuration to compare against

**Returns:**
- `ProviderOverrideValidationResult`: Validation details with suggestions

**Example:**
```python
# Validate APT provider configuration
apt_config = {
    "version": "0.1",
    "packages": {"default": {"name": "nginx-core"}},
    "directories": {"config": {"path": "/etc/nginx"}}  # Might be redundant
}

result = validator.validate_provider_override("apt", apt_config)

if not result.valid:
    print("Configuration issues found:")
    for issue in result.issues:
        print(f"  {issue.level.value}: {issue.message}")

print("Optimization suggestions:")
for suggestion in result.suggestions:
    print(f"  {suggestion.type}: {suggestion.path} - {suggestion.reason}")
```

##### suggest_removable_keys()

Suggest keys that can be removed from provider config.

```python
def suggest_removable_keys(
    self,
    provider_config: Dict[str, Any],
    defaults: Optional[Dict[str, Any]] = None
) -> List[str]
```

**Parameters:**
- `provider_config` (Dict[str, Any]): Provider configuration
- `defaults` (Optional[Dict[str, Any]]): Default configuration to compare against

**Returns:**
- `List[str]`: List of keys that match defaults and can be removed

**Example:**
```python
# Get suggestions for removable keys
removable = validator.suggest_removable_keys({
    "version": "0.1",
    "packages": {"default": {"name": "nginx"}},  # Might match default
    "services": {"default": {"name": "nginx"}}   # Might match default
})

print(f"Keys that can be removed: {removable}")
```

##### validate_configuration_consistency()

Validate consistency across multiple provider configurations.

```python
def validate_configuration_consistency(
    self,
    provider_configs: Dict[str, Dict[str, Any]]
) -> ConfigurationValidationReport
```

**Parameters:**
- `provider_configs` (Dict[str, Dict[str, Any]]): Dictionary of provider name -> configuration

**Returns:**
- `ConfigurationValidationReport`: Comprehensive analysis report

**Example:**
```python
# Validate consistency across all providers
all_configs = {
    "apt": {"version": "0.1", "packages": {"default": {"name": "nginx-core"}}},
    "brew": {"version": "0.1", "packages": {"default": {"name": "nginx"}}},
    "winget": {"version": "0.1", "packages": {"default": {"name": "nginx"}}},
    "choco": {"version": "0.1", "supported": False}
}

report = validator.validate_configuration_consistency(all_configs)

print(f"Overall quality score: {report.overall_quality_score:.2f}")
print(f"Providers with high optimization potential: {report.optimization_summary['high_optimization']}")

if report.consistency_issues:
    print("Consistency issues:")
    for issue in report.consistency_issues:
        print(f"  - {issue}")

print("Recommendations:")
for rec in report.recommendations:
    print(f"  - {rec}")
```

##### validate_provider_template_file()

Validate a provider template file directly.

```python
def validate_provider_template_file(self, file_path: Union[str, Path]) -> ProviderOverrideValidationResult
```

**Parameters:**
- `file_path` (Union[str, Path]): Path to the provider template file

**Returns:**
- `ProviderOverrideValidationResult`: Validation result for the template file

**Example:**
```python
# Validate a template file
result = validator.validate_provider_template_file("templates/providers/apt.yaml")

if result.valid:
    print(f"Template is valid with quality score: {result.quality_score:.2f}")
else:
    print("Template validation failed:")
    for issue in result.issues:
        print(f"  {issue.level.value}: {issue.message}")
```

#### Result Classes

##### ProviderOverrideValidationResult

Result of provider override validation with detailed analysis.

```python
@dataclass
class ProviderOverrideValidationResult:
    provider: str
    valid: bool
    necessary_overrides: Dict[str, Any] = field(default_factory=dict)
    redundant_keys: List[str] = field(default_factory=list)
    missing_keys: List[str] = field(default_factory=list)
    suggestions: List[ConfigurationSuggestion] = field(default_factory=list)
    issues: List[ValidationIssue] = field(default_factory=list)
    quality_score: float = 0.0
    optimization_potential: float = 0.0
```

##### ConfigurationValidationReport

Comprehensive configuration validation report for multiple providers.

```python
@dataclass
class ConfigurationValidationReport:
    provider_results: Dict[str, ProviderOverrideValidationResult] = field(default_factory=dict)
    overall_quality_score: float = 0.0
    total_redundant_keys: int = 0
    total_suggestions: int = 0
    optimization_summary: Dict[str, int] = field(default_factory=dict)
    consistency_issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
```

### SaidataEngine

The central orchestrator that coordinates all operations.

```python
class SaidataEngine:
    def __init__(self, config_path: Optional[str] = None)
    def generate_metadata(self, software_name: str, options: GenerationOptions) -> MetadataResult
    def validate_metadata(self, file_path: str) -> ValidationResult
    def batch_process(self, software_list: List[str], options: BatchOptions) -> BatchResult
    def search_software(self, query: str) -> List[SoftwareMatch]
    def fetch_repository_data(self, providers: List[str]) -> FetchResult
```

#### Constructor

```python
engine = SaidataEngine(config_path="/path/to/config.yaml")
```

**Parameters:**
- `config_path` (Optional[str]): Path to configuration file. If None, uses default configuration.

#### Methods

##### generate_metadata()

Generate metadata for a software package.

```python
def generate_metadata(self, software_name: str, options: GenerationOptions) -> MetadataResult
```

**Parameters:**
- `software_name` (str): Name of the software package
- `options` (GenerationOptions): Generation configuration options

**Returns:**
- `MetadataResult`: Contains generated metadata, validation results, and confidence scores

**Example:**
```python
from saidata_gen.core.interfaces import GenerationOptions

options = GenerationOptions(
    providers=['apt', 'brew', 'winget'],
    use_rag=True,
    rag_provider='openai',
    confidence_threshold=0.8
)

result = engine.generate_metadata('nginx', options)
print(f"Generated metadata for: {result.metadata.description}")
```

### TemplateEngine

The template engine provides advanced templating capabilities with override-only template support, caching, and enhanced security.

```python
from saidata_gen.generator.templates import TemplateEngine
from saidata_gen.core.cache import CacheManager, CacheConfig, CacheBackend

# Initialize with custom cache configuration
cache_config = CacheConfig(
    backend=CacheBackend.MEMORY,
    default_ttl=3600,
    max_size=1000
)
cache_manager = CacheManager(cache_config)
engine = TemplateEngine(cache_manager=cache_manager)

# Generate override-only configurations
overrides = engine.apply_provider_overrides_only("nginx", "apt", repository_data)
merged = engine.merge_with_defaults(engine.default_template, overrides)

# Check provider support with intelligent caching
is_supported = engine.is_provider_supported("nginx", "apt", repository_data)

# Manage cache for performance optimization
engine.clear_provider_support_cache("nginx", "apt")
cache_stats = engine.get_provider_support_cache_stats()
```

#### New Override-Only Methods

##### apply_provider_overrides_only()

Generate provider-specific configuration containing only overrides.

```python
def apply_provider_overrides_only(
    self, 
    software_name: str, 
    provider: str, 
    repository_data: Dict[str, Any] = None
) -> Dict[str, Any]
```

**Parameters:**
- `software_name` (str): Name of the software
- `provider` (str): Provider name (e.g., 'apt', 'brew', 'winget')
- `repository_data` (Dict[str, Any], optional): Data fetched from provider repository

**Returns:**
- `Dict[str, Any]`: Dictionary containing only provider-specific overrides

**Example:**
```python
# Generate APT-specific overrides for nginx
overrides = engine.apply_provider_overrides_only("nginx", "apt", repository_data)
print(overrides)
# Output: {'packages': {'default': {'name': 'nginx-core'}}, 'supported': True}
```

##### merge_with_defaults()

Merge provider overrides with defaults, handling null removal.

```python
def merge_with_defaults(
    self, 
    defaults: Dict[str, Any], 
    provider_overrides: Dict[str, Any]
) -> Dict[str, Any]
```

**Parameters:**
- `defaults` (Dict[str, Any]): Base defaults configuration
- `provider_overrides` (Dict[str, Any]): Provider-specific overrides

**Returns:**
- `Dict[str, Any]`: Merged configuration with nulls removed

**Example:**
```python
# Merge overrides with defaults
merged = engine.merge_with_defaults(engine.default_template, overrides)
print(merged['packages']['default']['name'])  # nginx-core (from override)
print(merged['version'])  # 0.1 (from defaults)
```

##### is_provider_supported()

Determine if a provider supports the given software.

```python
def is_provider_supported(
    self, 
    software_name: str, 
    provider: str, 
    repository_data: Dict[str, Any] = None
) -> bool
```

**Parameters:**
- `software_name` (str): Name of the software
- `provider` (str): Provider name
- `repository_data` (Dict[str, Any], optional): Data fetched from provider repository

**Returns:**
- `bool`: True if provider supports the software, False otherwise

**Example:**
```python
# Check if Chocolatey supports nginx
is_supported = engine.is_provider_supported("nginx", "choco", repository_data)
if not is_supported:
    print("Chocolatey does not support nginx")
```

##### validate_metadata()

Validate a metadata file against the schema.

```python
def validate_metadata(self, file_path: str) -> ValidationResult
```

**Parameters:**
- `file_path` (str): Path to the metadata file

**Returns:**
- `ValidationResult`: Validation status and detailed issues

**Example:**
```python
result = engine.validate_metadata('nginx.yaml')
if result.valid:
    print("File is valid!")
else:
    for issue in result.issues:
        print(f"{issue.level.value}: {issue.message}")
```

##### batch_process()

Process multiple software packages in batch.

```python
def batch_process(self, software_list: List[str], options: BatchOptions) -> BatchResult
```

**Parameters:**
- `software_list` (List[str]): List of software package names
- `options` (BatchOptions): Batch processing configuration

**Returns:**
- `BatchResult`: Results for each package and summary statistics

**Example:**
```python
from saidata_gen.core.interfaces import BatchOptions

software_list = ['nginx', 'apache2', 'mysql-server']
options = BatchOptions(
    output_dir='./generated',
    max_concurrent=3,
    continue_on_error=True
)

results = engine.batch_process(software_list, options)
print(f"Processed {len(results.results)} packages")
```

##### search_software()

Search for software packages across repositories.

```python
def search_software(self, query: str) -> List[SoftwareMatch]
```

**Parameters:**
- `query` (str): Search query string

**Returns:**
- `List[SoftwareMatch]`: List of matching packages with scores

**Example:**
```python
matches = engine.search_software("web server")
for match in matches:
    print(f"{match.name} ({match.provider}): {match.score:.2f}")
```

##### fetch_repository_data()

Fetch data from package repositories.

```python
def fetch_repository_data(self, providers: List[str]) -> FetchResult
```

**Parameters:**
- `providers` (List[str]): List of provider names to fetch from

**Returns:**
- `FetchResult`: Success status and detailed results per provider

**Example:**
```python
result = engine.fetch_repository_data(['apt', 'brew'])
for provider, success in result.providers.items():
    status = "✓" if success else "✗"
    print(f"{status} {provider}")
```

## Data Models

### SaidataMetadata

Core data model representing saidata metadata.

```python
@dataclass
class SaidataMetadata:
    version: str = "0.1"
    packages: Dict[str, PackageConfig] = field(default_factory=dict)
    services: Dict[str, ServiceConfig] = field(default_factory=dict)
    directories: Dict[str, DirectoryConfig] = field(default_factory=dict)
    processes: Dict[str, ProcessConfig] = field(default_factory=dict)
    ports: Dict[str, PortConfig] = field(default_factory=dict)
    containers: Dict[str, ContainerConfig] = field(default_factory=dict)
    charts: Dict[str, dict] = field(default_factory=dict)
    repos: Dict[str, dict] = field(default_factory=dict)
    urls: URLConfig = field(default_factory=lambda: URLConfig())
    language: Optional[str] = None
    description: Optional[str] = None
    category: CategoryConfig = field(default_factory=lambda: CategoryConfig())
    license: Optional[str] = None
    platforms: List[str] = field(default_factory=list)
```

**Example:**
```python
# Access generated metadata
metadata = result.metadata
print(f"Description: {metadata.description}")
print(f"License: {metadata.license}")
print(f"Website: {metadata.urls.website}")

# Access package configurations
for provider, config in metadata.packages.items():
    print(f"{provider}: {config.name} v{config.version}")
```

### Configuration Classes

#### GenerationOptions

Options for metadata generation.

```python
@dataclass
class GenerationOptions:
    providers: List[str] = field(default_factory=list)
    use_rag: bool = False
    rag_provider: str = "openai"
    include_dev_packages: bool = False
    confidence_threshold: float = 0.7
    output_format: str = "yaml"
    validate_schema: bool = True
```

**Example:**
```python
options = GenerationOptions(
    providers=['apt', 'brew', 'npm'],
    use_rag=True,
    rag_provider='anthropic',
    confidence_threshold=0.8,
    output_format='json'
)
```

#### BatchOptions

Options for batch processing.

```python
@dataclass
class BatchOptions:
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
```

#### RAGConfig

Configuration for RAG integration.

```python
@dataclass
class RAGConfig:
    provider: str = "openai"
    model: str = "gpt-3.5-turbo"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 1000
```

### Result Classes

#### MetadataResult

Result of metadata generation.

```python
@dataclass
class MetadataResult:
    metadata: SaidataMetadata
    file_path: Optional[str] = None
    validation_result: Optional[ValidationResult] = None
    confidence_scores: Dict[str, float] = field(default_factory=dict)
```

**Example:**
```python
result = engine.generate_metadata('nginx', options)

# Access metadata
print(result.metadata.description)

# Check validation
if result.validation_result and not result.validation_result.valid:
    print("Validation failed!")

# View confidence scores
for field, score in result.confidence_scores.items():
    print(f"{field}: {score:.2f}")
```

#### ValidationResult

Result of schema validation.

```python
@dataclass
class ValidationResult:
    valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    file_path: Optional[str] = None
```

#### BatchResult

Result of batch processing.

```python
@dataclass
class BatchResult:
    results: Dict[str, Union[MetadataResult, Exception]] = field(default_factory=dict)
    summary: Dict[str, int] = field(default_factory=dict)
```

**Example:**
```python
batch_result = engine.batch_process(software_list, options)

# Check individual results
for name, result in batch_result.results.items():
    if isinstance(result, Exception):
        print(f"Failed: {name} - {result}")
    else:
        print(f"Success: {name}")

# View summary
print(f"Total: {batch_result.summary.get('total', 0)}")
print(f"Successful: {batch_result.summary.get('successful', 0)}")
```

## Exception Handling

### Exception Hierarchy

```python
class SaidataGenError(Exception):
    """Base exception for saidata-gen operations"""

class ValidationError(SaidataGenError):
    """Raised when schema validation fails"""

class FetchError(SaidataGenError):
    """Raised when repository fetching fails"""

class GenerationError(SaidataGenError):
    """Raised when metadata generation fails"""

class RAGError(SaidataGenError):
    """Raised when RAG operations fail"""

class ConfigurationError(SaidataGenError):
    """Raised when configuration is invalid"""
```

### Error Handling Example

```python
from saidata_gen import SaidataEngine
from saidata_gen.core.exceptions import GenerationError, ValidationError

try:
    engine = SaidataEngine()
    result = engine.generate_metadata('nginx', options)
except GenerationError as e:
    print(f"Generation failed: {e}")
except ValidationError as e:
    print(f"Validation failed: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Advanced Usage

### Custom Configuration

```python
import yaml
from pathlib import Path

# Create custom configuration
config = {
    'providers': {
        'apt': {'enabled': True, 'cache_ttl': 3600},
        'brew': {'enabled': True, 'cache_ttl': 7200}
    },
    'rag': {
        'provider': 'openai',
        'model': 'gpt-4',
        'temperature': 0.1
    }
}

# Save configuration
config_path = Path('~/.saidata-gen/config.yaml').expanduser()
config_path.parent.mkdir(parents=True, exist_ok=True)
with open(config_path, 'w') as f:
    yaml.dump(config, f)

# Use custom configuration
engine = SaidataEngine(config_path=str(config_path))
```

### Async Usage

For high-performance applications, use async patterns:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def generate_multiple(software_list):
    """Generate metadata for multiple packages concurrently."""
    engine = SaidataEngine()
    options = GenerationOptions(providers=['apt', 'brew'])
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(
                executor, 
                engine.generate_metadata, 
                software, 
                options
            )
            for software in software_list
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results

# Usage
software_list = ['nginx', 'apache2', 'mysql-server']
results = asyncio.run(generate_multiple(software_list))
```

### MetadataGenerator

The metadata generator provides core functionality for generating saidata metadata from multiple sources with AI enhancement capabilities.

```python
from saidata_gen.generator.core import MetadataGenerator
from saidata_gen.ai.enhancer import AIMetadataEnhancer

# Initialize with AI enhancement
ai_enhancer = AIMetadataEnhancer(provider="openai")
generator = MetadataGenerator(ai_enhancer=ai_enhancer)

# Generate metadata with AI enhancement
result = generator.generate_with_ai_enhancement(
    software_name="nginx",
    sources=package_sources,
    providers=["apt", "brew", "winget"],
    ai_provider="openai",
    enhancement_types=["description", "categorization", "field_completion"]
)

print(f"Enhanced metadata: {result.metadata}")
print(f"Confidence scores: {result.confidence_scores}")
```

#### AI Enhancement Methods

##### generate_with_ai_enhancement()

Generate metadata with AI enhancement for missing fields.

```python
def generate_with_ai_enhancement(
    self,
    software_name: str,
    sources: List[PackageInfo],
    providers: Optional[List[str]] = None,
    ai_provider: str = "openai",
    enhancement_types: Optional[List[str]] = None
) -> MetadataResult
```

**Parameters:**
- `software_name` (str): Name of the software
- `sources` (List[PackageInfo]): List of package information from repositories
- `providers` (Optional[List[str]]): List of providers to include
- `ai_provider` (str): AI provider to use (openai, anthropic, local)
- `enhancement_types` (Optional[List[str]]): Types of AI enhancement to apply

**Returns:**
- `MetadataResult`: Result with AI-enhanced metadata

**Example:**
```python
# Generate AI-enhanced metadata
result = generator.generate_with_ai_enhancement(
    software_name="nginx",
    sources=repository_sources,
    providers=["apt", "brew", "winget"],
    ai_provider="anthropic",
    enhancement_types=["description", "field_completion"]
)

if result.validation_result and result.validation_result.valid:
    print("Enhanced metadata is valid")
    print(f"Description: {result.metadata.description}")
    print(f"Website: {result.metadata.urls.website}")
else:
    print("Validation issues found")
```

##### merge_ai_with_repository_data()

Merge AI-generated data with repository data, prioritizing repository data.

```python
def merge_ai_with_repository_data(
    self,
    repository_data: Dict[str, Any],
    ai_data: Dict[str, Any]
) -> Dict[str, Any]
```

**Parameters:**
- `repository_data` (Dict[str, Any]): Data from package repositories (authoritative)
- `ai_data` (Dict[str, Any]): Data from AI/LLM (supplementary)

**Returns:**
- `Dict[str, Any]`: Merged data with repository data taking precedence

**Example:**
```python
# Merge AI and repository data
repository_data = {
    "version": "0.1",
    "packages": {"default": {"name": "nginx", "version": "1.18.0"}},
    "description": None  # Missing from repository
}

ai_data = {
    "version": "0.1", 
    "packages": {"default": {"name": "nginx", "version": "latest"}},  # Different version
    "description": "High-performance web server",  # AI-generated
    "urls": {"website": "https://nginx.org"}  # AI-generated
}

merged = generator.merge_ai_with_repository_data(repository_data, ai_data)

print(merged["packages"]["default"]["version"])  # "1.18.0" (repository wins)
print(merged["description"])  # "High-performance web server" (AI fills gap)
print(merged["urls"]["website"])  # "https://nginx.org" (AI fills gap)
```

### Working with Raw Data

```python
# Access raw repository data
fetch_result = engine.fetch_repository_data(['apt'])

# Process raw package information
from saidata_gen.fetcher.factory import FetcherFactory

factory = FetcherFactory()
apt_fetcher = factory.create_fetcher('apt')
packages = apt_fetcher.search_package('nginx')

for package in packages:
    print(f"Found: {package.name} v{package.version}")
    print(f"Description: {package.description}")
```

### Custom Templates

```python
from saidata_gen.generator.templates import TemplateEngine

# Create custom template engine
template_engine = TemplateEngine(template_dir='./custom_templates')

# Apply custom templates
metadata_dict = {
    'name': 'nginx',
    'description': 'Web server'
}

enhanced_metadata = template_engine.apply_defaults(metadata_dict)
```

## Integration Examples

### Django Integration

```python
from django.http import JsonResponse
from saidata_gen import SaidataEngine
from saidata_gen.core.interfaces import GenerationOptions

def generate_metadata_view(request, software_name):
    """Django view for generating metadata."""
    try:
        engine = SaidataEngine()
        options = GenerationOptions(
            providers=request.GET.get('providers', '').split(','),
            use_rag=request.GET.get('use_rag') == 'true'
        )
        
        result = engine.generate_metadata(software_name, options)
        
        return JsonResponse({
            'success': True,
            'metadata': result.metadata.__dict__,
            'confidence_scores': result.confidence_scores
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
```

### Flask Integration

```python
from flask import Flask, request, jsonify
from saidata_gen import SaidataEngine

app = Flask(__name__)
engine = SaidataEngine()

@app.route('/generate/<software_name>')
def generate_metadata(software_name):
    """Flask endpoint for metadata generation."""
    try:
        options = GenerationOptions(
            providers=request.args.get('providers', '').split(','),
            use_rag=request.args.get('use_rag') == 'true'
        )
        
        result = engine.generate_metadata(software_name, options)
        
        return jsonify({
            'metadata': result.metadata.__dict__,
            'valid': result.validation_result.valid if result.validation_result else True
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

### Celery Task

```python
from celery import Celery
from saidata_gen import SaidataEngine
from saidata_gen.core.interfaces import GenerationOptions

app = Celery('saidata_tasks')

@app.task
def generate_metadata_task(software_name, providers=None):
    """Celery task for background metadata generation."""
    engine = SaidataEngine()
    options = GenerationOptions(providers=providers or [])
    
    try:
        result = engine.generate_metadata(software_name, options)
        return {
            'success': True,
            'metadata': result.metadata.__dict__,
            'confidence_scores': result.confidence_scores
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
```

## Testing

### Unit Testing

```python
import unittest
from unittest.mock import Mock, patch
from saidata_gen import SaidataEngine
from saidata_gen.core.interfaces import GenerationOptions

class TestSaidataEngine(unittest.TestCase):
    def setUp(self):
        self.engine = SaidataEngine()
    
    @patch('saidata_gen.fetcher.factory.FetcherFactory')
    def test_generate_metadata(self, mock_factory):
        """Test metadata generation."""
        # Mock fetcher
        mock_fetcher = Mock()
        mock_fetcher.search_package.return_value = [
            Mock(name='nginx', version='1.18.0', description='Web server')
        ]
        mock_factory.return_value.create_fetcher.return_value = mock_fetcher
        
        # Test generation
        options = GenerationOptions(providers=['apt'])
        result = self.engine.generate_metadata('nginx', options)
        
        self.assertIsNotNone(result.metadata)
        self.assertEqual(result.metadata.version, '0.1')
```

### Integration Testing

```python
import pytest
from saidata_gen import SaidataEngine

@pytest.fixture
def engine():
    return SaidataEngine()

def test_full_workflow(engine):
    """Test complete workflow."""
    # Generate metadata
    options = GenerationOptions(providers=['apt'])
    result = engine.generate_metadata('nginx', options)
    
    # Validate result
    assert result.metadata is not None
    assert result.metadata.version == '0.1'
    
    # Test validation
    validation_result = engine.validate_metadata('nginx.yaml')
    assert validation_result.valid
```

## Performance Optimization

### Caching

```python
from saidata_gen.core.cache import CacheManager

# Configure caching
cache_manager = CacheManager(
    cache_dir='~/.saidata-gen/cache',
    ttl=3600
)

# Use cached data
cached_data = cache_manager.get_cached_data('apt_packages')
if cached_data is None:
    # Fetch fresh data
    data = fetch_repository_data()
    cache_manager.cache_data('apt_packages', data)
```

### Connection Pooling

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure session with connection pooling
session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
session.mount("http://", adapter)
session.mount("https://", adapter)
```

## Best Practices

1. **Error Handling**: Always wrap API calls in try-catch blocks
2. **Configuration**: Use configuration files for production deployments
3. **Caching**: Enable caching for better performance
4. **Logging**: Configure appropriate logging levels
5. **Resource Management**: Use context managers for file operations
6. **Async Processing**: Use async patterns for high-throughput applications
7. **Testing**: Write comprehensive tests for custom integrations
8. **Monitoring**: Implement monitoring for production usage