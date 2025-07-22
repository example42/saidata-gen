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