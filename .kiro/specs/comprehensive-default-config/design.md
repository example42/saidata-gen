# Design Document

## Overview

This design addresses three critical aspects of the saidata-gen system: restructuring the configuration system to eliminate duplication, implementing a structured directory-based output format, and improving fetcher reliability across all supported package managers. The solution involves creating a separate `provider_defaults.yaml` file containing comprehensive provider-specific settings, implementing a new output structure (`$software/defaults.yaml` and `$software/providers/$provider.yaml`), simplifying the CLI by removing deprecated options, and enhancing fetcher robustness with better error handling and retry mechanisms.

## Architecture

### Configuration System Restructure

The new configuration system separates concerns by using three distinct configuration files:

1. **`saidata_gen/templates/defaults.yaml`** - Base software configurations (unchanged)
2. **`saidata_gen/templates/provider_defaults.yaml`** - Provider-specific defaults for all providers
3. **Software-specific overrides** - Generated in structured directory format

```yaml
# NEW: saidata_gen/templates/provider_defaults.yaml
version: 0.1

apt:
  services:
    default:
      enabled: true
      status: enabled
  urls:
    apt: "https://packages.ubuntu.com/search?keywords={{ software_name }}"
  files:
    init:
      path: "/etc/default/{{ software_name }}"
  directories:
    config:
      mode: "0644"

brew:
  urls:
    brew: "https://brew.sh/formula/{{ software_name }}"
  services:
    default:
      enabled: true
      status: enabled

# ... (all other providers with their specific defaults)
```

### Output Directory Structure

The new output format creates a structured directory for each software package:

```
$software/
├── defaults.yaml              # Software-specific base configuration
└── providers/                 # Provider-specific overrides (only if different from provider_defaults.yaml)
    ├── apt.yaml              # Only created if apt config differs from provider_defaults.yaml
    ├── brew.yaml             # Only created if brew config differs from provider_defaults.yaml
    └── ...
```

### Fetcher Reliability Enhancement

The fetcher subsystem will be enhanced with a multi-layered approach to handle failures:

1. **Network Layer**: Enhanced retry logic with exponential backoff
2. **SSL/TLS Layer**: Certificate validation handling with fallback options
3. **Data Layer**: Graceful handling of malformed responses
4. **System Layer**: Dependency checking and graceful degradation

## Components and Interfaces

### 1. Restructured Configuration System

#### ConfigurationManager
```python
class ConfigurationManager:
    def load_base_defaults(self) -> Dict[str, Any]
    def load_provider_defaults(self) -> Dict[str, Dict[str, Any]]
    def get_provider_config(self, provider: str, software_name: str) -> Dict[str, Any]
    def should_create_provider_file(self, provider: str, config: Dict) -> bool
```

#### DirectoryStructureGenerator
```python
class DirectoryStructureGenerator:
    def create_software_directory(self, software_name: str, output_path: str) -> Path
    def write_defaults_file(self, software_config: Dict, output_path: Path) -> None
    def write_provider_files(self, provider_configs: Dict, output_path: Path) -> None
    def cleanup_empty_provider_directory(self, output_path: Path) -> None
```

#### ProviderConfigValidator
```python
class ProviderConfigValidator:
    def validate_provider_config(self, provider: str, config: Dict) -> ValidationResult
    def compare_with_defaults(self, provider: str, config: Dict) -> bool
    def get_missing_defaults(self, provider: str) -> List[str]
```

### 2. Enhanced Fetcher Base Classes

#### ResilientHttpFetcher (extends HttpRepositoryFetcher)
```python
class ResilientHttpFetcher(HttpRepositoryFetcher):
    def _create_session_with_ssl_handling(self) -> requests.Session
    def _fetch_with_fallback(self, url: str, fallback_urls: List[str] = None) -> requests.Response
    def _handle_ssl_errors(self, url: str, error: SSLError) -> requests.Response
    def _validate_response_content(self, response: requests.Response) -> bool
```

#### SystemDependencyChecker
```python
class SystemDependencyChecker:
    def check_command_availability(self, command: str) -> bool
    def get_installation_instructions(self, command: str) -> str
    def log_missing_dependency(self, command: str, provider: str) -> None
```

### 3. Error Handling and Recovery

#### FetcherErrorHandler
```python
class FetcherErrorHandler:
    def handle_network_error(self, error: Exception, context: Dict) -> FetchResult
    def handle_ssl_error(self, error: SSLError, url: str) -> Optional[requests.Response]
    def handle_malformed_data(self, data: bytes, format_type: str) -> Optional[Dict]
    def should_retry(self, error: Exception, attempt: int) -> bool
```

#### GracefulDegradationManager
```python
class GracefulDegradationManager:
    def mark_provider_unavailable(self, provider: str, reason: str) -> None
    def get_alternative_sources(self, provider: str) -> List[str]
    def log_degradation_event(self, provider: str, error: str) -> None
```

## Data Models

### Enhanced Configuration Models

```python
@dataclass
class ProviderDefaults:
    name: str
    services: Dict[str, Any] = field(default_factory=dict)
    files: Dict[str, Any] = field(default_factory=dict)
    directories: Dict[str, Any] = field(default_factory=dict)
    urls: Dict[str, str] = field(default_factory=dict)
    packages: Dict[str, Any] = field(default_factory=dict)
    ssl_verify: bool = True
    fallback_urls: List[str] = field(default_factory=list)
    required_commands: List[str] = field(default_factory=list)

@dataclass
class SoftwareConfiguration:
    name: str
    base_config: Dict[str, Any]
    provider_configs: Dict[str, Dict[str, Any]]
    output_path: Path

@dataclass
class EnhancedFetcherConfig(FetcherConfig):
    ssl_verify: bool = True
    ssl_fallback_enabled: bool = True
    max_retries: int = 3
    retry_backoff_factor: float = 0.5
    timeout: int = 30
    graceful_degradation: bool = True
    log_missing_dependencies: bool = True
```

### Error Tracking Models

```python
@dataclass
class FetcherError:
    provider: str
    error_type: str  # 'network', 'ssl', 'data', 'dependency'
    error_message: str
    url: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
    resolved: bool = False

@dataclass
class EnhancedFetchResult(FetchResult):
    degraded_providers: Dict[str, str] = field(default_factory=dict)
    missing_dependencies: Dict[str, List[str]] = field(default_factory=dict)
    ssl_issues: Dict[str, str] = field(default_factory=dict)
    malformed_responses: Dict[str, str] = field(default_factory=dict)
```

## Error Handling

### Network Error Handling Strategy

1. **HTTP Errors (4xx/5xx)**:
   - Implement exponential backoff with jitter
   - Try alternative mirrors/endpoints if available
   - Log detailed error information for debugging

2. **SSL Certificate Errors**:
   - Log certificate validation failures
   - Provide option to disable SSL verification for specific providers (with warnings)
   - Attempt to use alternative URLs with valid certificates

3. **Timeout Errors**:
   - Increase timeout for subsequent retries
   - Switch to alternative endpoints if available
   - Mark provider as temporarily unavailable after max retries

### Data Validation Error Handling

1. **Malformed JSON/XML/YAML**:
   - Log parsing errors with context
   - Attempt alternative parsing strategies
   - Skip malformed entries and continue processing

2. **Encoding Issues**:
   - Try multiple encoding formats (utf-8, latin-1, etc.)
   - Log encoding detection results
   - Provide fallback to binary processing where applicable

3. **Missing Required Fields**:
   - Use default values where possible
   - Log missing field warnings
   - Continue processing with partial data

### System Dependency Error Handling

1. **Missing Commands**:
   - Check for command availability before execution
   - Provide clear installation instructions
   - Skip providers that require unavailable commands

2. **Command Execution Failures**:
   - Log command output and error streams
   - Retry with alternative command arguments
   - Gracefully skip failed operations

## Testing Strategy

### Unit Testing

1. **Configuration Template Tests**:
   - Test default value loading for all providers
   - Validate provider-specific configuration merging
   - Test backward compatibility with existing templates

2. **Fetcher Resilience Tests**:
   - Mock network failures and test retry logic
   - Test SSL error handling with invalid certificates
   - Test malformed response handling

3. **Error Handler Tests**:
   - Test each error type handling scenario
   - Validate graceful degradation behavior
   - Test logging and reporting functionality

### Integration Testing

1. **End-to-End Provider Testing**:
   - Test metadata generation with all providers
   - Validate error handling in real network conditions
   - Test performance with degraded providers

2. **Configuration Validation Testing**:
   - Test configuration loading with various provider combinations
   - Validate template inheritance and overrides
   - Test configuration validation and error reporting

### Performance Testing

1. **Concurrent Fetcher Testing**:
   - Test multiple provider fetching simultaneously
   - Measure impact of retry logic on performance
   - Test cache effectiveness with error scenarios

2. **Large Dataset Testing**:
   - Test with repositories containing thousands of packages
   - Validate memory usage with large responses
   - Test timeout handling with slow repositories

### Error Scenario Testing

1. **Network Condition Simulation**:
   - Test with simulated network outages
   - Test with high latency connections
   - Test with intermittent connectivity

2. **Repository Condition Simulation**:
   - Test with temporarily unavailable repositories
   - Test with repositories returning malformed data
   - Test with repositories requiring authentication

## Implementation Phases

### Phase 1: Configuration System Restructure
- Create `provider_defaults.yaml` with comprehensive provider defaults
- Implement `ConfigurationManager` and `DirectoryStructureGenerator` classes
- Update template loading logic to use the new structure

### Phase 2: CLI Simplification
- Remove deprecated CLI options (--directory-structure, --comprehensive, --use-rag, --rag-provider)
- Update CLI to always generate structured directory output
- Add proper error messages for removed options

### Phase 3: Fetcher Base Class Enhancement
- Enhance base fetcher classes with resilient networking
- Implement SSL error handling and fallback mechanisms
- Add system dependency checking

### Phase 4: Provider-Specific Error Handling
- Update individual fetcher implementations
- Add provider-specific error handling strategies
- Implement graceful degradation for each provider

### Phase 5: Testing and Documentation
- Add comprehensive tests for new configuration system
- Update documentation to reflect new directory structure
- Add migration guide for users of the old system