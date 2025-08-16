# Design Document

## Overview

This design outlines the refactoring of the saidata provider structure to implement a more efficient and maintainable configuration system. The current system has provider templates that contain redundant information duplicating general defaults. The new system will follow the pattern established in `examples/saidata/example/`, where provider files only contain settings that differ from general defaults.

The refactoring includes:
1. Restructuring provider template files to contain only overrides
2. Implementing a configuration merging system that combines defaults with provider-specific settings
3. Adding support for `supported: false` to indicate unsupported providers
4. Enhancing the CLI generate command with an AI option for LLM-enhanced metadata generation
5. Ensuring comprehensive provider coverage with templates for all supported package managers

## Architecture

### Current Architecture

The current system uses:
- `saidata_gen/templates/defaults.yaml` - Contains base template structure
- `saidata_gen/templates/providers/*.yaml` - Contains full provider configurations with redundant data
- `TemplateEngine` class that applies templates and merges configurations
- `MetadataGenerator` class that orchestrates the generation process

### New Architecture

The new system will maintain the same core components but with enhanced functionality:

```
saidata_gen/
├── templates/
│   ├── defaults.yaml (enhanced with comprehensive defaults)
│   └── providers/
│       ├── apt.yaml (only overrides)
│       ├── brew.yaml (only overrides)
│       ├── winget.yaml (only overrides)
│       ├── choco.yaml (only overrides)
│       ├── scoop.yaml (only overrides)
│       ├── yum.yaml (only overrides)
│       ├── dnf.yaml (only overrides)
│       ├── zypper.yaml (only overrides)
│       ├── pacman.yaml (only overrides)
│       ├── apk.yaml (only overrides)
│       ├── snap.yaml (only overrides)
│       ├── flatpak.yaml (only overrides)
│       ├── docker.yaml (only overrides)
│       ├── helm.yaml (only overrides)
│       ├── npm.yaml (only overrides)
│       ├── pypi.yaml (only overrides)
│       ├── cargo.yaml (only overrides)
│       ├── nuget.yaml (only overrides)
│       ├── gem.yaml (only overrides)
│       ├── composer.yaml (only overrides)
│       ├── maven.yaml (only overrides)
│       ├── gradle.yaml (only overrides)
│       ├── go.yaml (only overrides)
│       ├── nix.yaml (only overrides)
│       ├── nixpkgs.yaml (only overrides)
│       ├── guix.yaml (only overrides)
│       ├── spack.yaml (only overrides)
│       ├── portage.yaml (only overrides)
│       ├── emerge.yaml (only overrides)
│       ├── xbps.yaml (only overrides)
│       ├── slackpkg.yaml (only overrides)
│       ├── opkg.yaml (only overrides)
│       └── pkg.yaml (only overrides)
```

### Generated Output Structure

When generating saidata for a software package, the system will create:

```
<software_name>/
├── defaults.yaml (merged defaults + provider data + AI enhancements)
└── providers/
    ├── apt.yaml (provider-specific overrides only)
    ├── brew.yaml (provider-specific overrides only)
    ├── winget.yaml (provider-specific overrides only)
    ├── choco.yaml (supported: false if not supported)
    └── ... (other providers)
```

## Components and Interfaces

### Enhanced TemplateEngine

The `TemplateEngine` class will be enhanced with new methods:

```python
class TemplateEngine:
    def apply_provider_overrides_only(
        self, 
        software_name: str, 
        provider: str, 
        repository_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Generate provider-specific configuration containing only overrides.
        
        Args:
            software_name: Name of the software
            provider: Provider name
            repository_data: Data fetched from provider repository
            
        Returns:
            Dictionary containing only provider-specific overrides
        """
    
    def merge_with_defaults(
        self, 
        defaults: Dict[str, Any], 
        provider_overrides: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge provider overrides with defaults, handling null removal.
        
        Args:
            defaults: Base defaults configuration
            provider_overrides: Provider-specific overrides
            
        Returns:
            Merged configuration with nulls removed
        """
    
    def is_provider_supported(
        self, 
        software_name: str, 
        provider: str, 
        repository_data: Dict[str, Any] = None
    ) -> bool:
        """
        Determine if a provider supports the given software.
        
        Args:
            software_name: Name of the software
            provider: Provider name
            repository_data: Data fetched from provider repository
            
        Returns:
            True if provider supports the software, False otherwise
        """
```

### Enhanced MetadataGenerator

The `MetadataGenerator` class will be enhanced with AI integration:

```python
class MetadataGenerator:
    def generate_with_ai_enhancement(
        self,
        software_name: str,
        sources: List[PackageInfo],
        providers: Optional[List[str]] = None,
        ai_provider: str = "openai"
    ) -> MetadataResult:
        """
        Generate metadata with AI enhancement for missing fields.
        
        Args:
            software_name: Name of the software
            sources: List of package information from repositories
            providers: List of providers to include
            ai_provider: AI provider to use (openai, anthropic, local)
            
        Returns:
            MetadataResult with AI-enhanced metadata
        """
    
    def merge_ai_with_repository_data(
        self,
        repository_data: Dict[str, Any],
        ai_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge AI-generated data with repository data, prioritizing repository data.
        
        Args:
            repository_data: Data from package repositories (authoritative)
            ai_data: Data from AI/LLM (supplementary)
            
        Returns:
            Merged data with repository data taking precedence
        """
```

### AI Integration Service

A new service will be created for AI integration:

```python
class AIMetadataEnhancer:
    def __init__(self, provider: str = "openai"):
        """
        Initialize AI metadata enhancer.
        
        Args:
            provider: AI provider (openai, anthropic, local)
        """
    
    def enhance_metadata(
        self,
        software_name: str,
        base_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Enhance metadata using AI for missing fields.
        
        Args:
            software_name: Name of the software
            base_metadata: Base metadata from repositories
            
        Returns:
            Enhanced metadata with AI-filled gaps
        """
    
    def get_missing_fields(
        self,
        metadata: Dict[str, Any]
    ) -> List[str]:
        """
        Identify fields that are missing or have null values.
        
        Args:
            metadata: Metadata to analyze
            
        Returns:
            List of missing field paths
        """
```

### Configuration Validator

A new validator will ensure configuration integrity:

```python
class ConfigurationValidator:
    def validate_provider_override(
        self,
        provider: str,
        override_config: Dict[str, Any],
        defaults: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate that provider override only contains necessary overrides.
        
        Args:
            provider: Provider name
            override_config: Provider override configuration
            defaults: Default configuration
            
        Returns:
            ValidationResult with any issues found
        """
    
    def suggest_removable_keys(
        self,
        provider_config: Dict[str, Any],
        defaults: Dict[str, Any]
    ) -> List[str]:
        """
        Suggest keys that can be removed from provider config.
        
        Args:
            provider_config: Provider configuration
            defaults: Default configuration
            
        Returns:
            List of keys that match defaults and can be removed
        """
```

## Data Models

### Enhanced Provider Configuration

Provider configurations will follow this structure:

```yaml
# For supported providers (only overrides)
version: 0.1
packages:
  default:
    name: "{{ software_name }}-custom"  # Only if different from default
directories:
  config:
    path: "/opt/{{ software_name }}/config"  # Only if different from default
platforms:
  - linux  # Only if different from default platforms
```

```yaml
# For unsupported providers
version: 0.1
supported: false
```

### AI Enhancement Data Model

```python
@dataclass
class AIEnhancementRequest:
    software_name: str
    base_metadata: Dict[str, Any]
    missing_fields: List[str]
    provider: str = "openai"

@dataclass
class AIEnhancementResult:
    enhanced_metadata: Dict[str, Any]
    confidence_scores: Dict[str, float]
    sources_used: List[str]
    processing_time: float
```

## Error Handling

### Provider Support Detection

The system will handle provider support detection gracefully:

1. **Repository Check**: First check if the software exists in the provider's repository
2. **Template Check**: Check if there's a provider template available
3. **AI Fallback**: Use AI to determine support if repository data is inconclusive
4. **Default to Unsupported**: If all checks fail, mark as `supported: false`

### Configuration Merging Errors

Error handling for configuration merging:

1. **Type Conflicts**: Handle cases where defaults and overrides have different types
2. **Invalid Overrides**: Validate that overrides are meaningful and not duplicates
3. **Missing Dependencies**: Ensure required fields are present after merging

### AI Integration Errors

Error handling for AI enhancement:

1. **API Failures**: Graceful degradation when AI services are unavailable
2. **Invalid Responses**: Validation and sanitization of AI-generated content
3. **Rate Limiting**: Implement backoff strategies for API rate limits
4. **Fallback Modes**: Continue with repository data only if AI fails

## Testing Strategy

### Unit Tests

1. **Template Engine Tests**:
   - Test provider override generation
   - Test configuration merging with null removal
   - Test provider support detection

2. **AI Enhancement Tests**:
   - Test AI metadata enhancement with mocked responses
   - Test data merging prioritization (repository over AI)
   - Test error handling for AI failures

3. **Configuration Validator Tests**:
   - Test validation of provider overrides
   - Test suggestion of removable keys
   - Test detection of redundant configurations

### Integration Tests

1. **End-to-End Generation Tests**:
   - Test complete metadata generation with AI enhancement
   - Test provider override-only output
   - Test directory structure creation

2. **CLI Integration Tests**:
   - Test new `--ai` flag functionality
   - Test provider coverage in example scripts
   - Test backward compatibility

### Performance Tests

1. **Template Processing Performance**:
   - Benchmark override-only generation vs full templates
   - Test memory usage with large provider lists
   - Test concurrent processing performance

2. **AI Enhancement Performance**:
   - Benchmark AI response times
   - Test caching effectiveness
   - Test batch processing with AI

## Migration Strategy

### Phase 1: Template Refactoring

1. Create comprehensive defaults.yaml with all necessary base configurations
2. Refactor existing provider templates to contain only overrides
3. Update TemplateEngine to handle override-only templates
4. Ensure backward compatibility during transition

### Phase 2: AI Integration

1. Implement AIMetadataEnhancer service
2. Add AI enhancement to MetadataGenerator
3. Update CLI with `--ai` flag
4. Add configuration options for AI providers

### Phase 3: Provider Coverage

1. Create templates for all supported providers
2. Update example scripts to use all providers by default
3. Add validation for provider template completeness
4. Document provider-specific configurations

### Phase 4: Validation and Cleanup

1. Implement ConfigurationValidator
2. Add automated tools for detecting redundant configurations
3. Create migration scripts for existing configurations
4. Update documentation and examples

## Security Considerations

### AI Integration Security

1. **API Key Management**: Secure storage and handling of AI provider API keys
2. **Input Sanitization**: Validate and sanitize software names before sending to AI
3. **Output Validation**: Validate AI responses before incorporating into metadata
4. **Rate Limiting**: Implement proper rate limiting to avoid service abuse

### Configuration Security

1. **Template Injection**: Prevent template injection attacks in variable substitution
2. **Path Traversal**: Validate file paths in generated configurations
3. **Privilege Escalation**: Ensure generated configurations don't contain dangerous permissions

## Performance Optimization

### Template Processing

1. **Caching**: Cache processed templates and provider configurations
2. **Lazy Loading**: Load provider templates only when needed
3. **Parallel Processing**: Process multiple providers concurrently
4. **Memory Optimization**: Minimize memory usage during large batch operations

### AI Enhancement

1. **Batch Processing**: Group multiple AI requests when possible
2. **Response Caching**: Cache AI responses for common software packages
3. **Selective Enhancement**: Only use AI for truly missing fields
4. **Timeout Management**: Implement reasonable timeouts for AI requests

## Monitoring and Observability

### Metrics

1. **Generation Metrics**: Track success rates, processing times, provider coverage
2. **AI Enhancement Metrics**: Track AI usage, response times, enhancement quality
3. **Error Metrics**: Track error rates by provider and error type
4. **Performance Metrics**: Track memory usage, CPU usage, cache hit rates

### Logging

1. **Structured Logging**: Use structured logging for better analysis
2. **Debug Information**: Include detailed debug information for troubleshooting
3. **Audit Trail**: Log all AI enhancements and data sources used
4. **Performance Logging**: Log performance bottlenecks and optimization opportunities