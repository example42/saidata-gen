# Repository URL Management

This guide explains the centralized repository URL management system in saidata-gen, which eliminates hardcoded URLs in fetchers and provides flexible configuration with OS and version-specific overrides.

## Overview

The repository URL management system consists of:

1. **Central Configuration** (`saidata_gen/templates/repository_urls.yaml`) - Contains all repository URLs
2. **URL Manager** (`saidata_gen/core/repository_url_manager.py`) - Manages URL resolution and template substitution
3. **Fetcher Integration** - Fetchers use the URL manager instead of hardcoded URLs

## Benefits

- **No Hardcoded URLs**: All URLs are centrally managed in YAML configuration
- **OS/Version Overrides**: Different URLs for different operating systems and versions
- **Template Variables**: Dynamic URL generation with context-aware substitution
- **Fallback Support**: Multiple fallback URLs for reliability
- **Easy Maintenance**: Update URLs in one place instead of across multiple files

## Configuration Structure

### Basic Structure

```yaml
version: 0.1

provider_name:
  default:
    primary_url: "https://example.com/api/v1"
    fallback_urls:
      - "https://backup.example.com/api/v1"
  
  # OS-specific overrides
  os:
    ubuntu:
      primary_url: "http://ubuntu.example.com/api/v1"
      
      # Version-specific overrides
      versions:
        "22.04":
          primary_url: "http://jammy.ubuntu.example.com/api/v1"
```

### Template Variables

URLs support template variables that are automatically substituted:

- `{{ software_name }}` - Name of the software being processed
- `{{ version }}` - OS or software version
- `{{ arch }}` - System architecture (x86_64, aarch64, etc.)
- `{{ os }}` - Operating system name
- `{{ provider }}` - Provider name

### Example Configuration

```yaml
apt:
  default:
    primary_url: "https://deb.debian.org/debian/dists/{{ version }}"
    fallback_urls:
      - "https://archive.debian.org/debian/dists/{{ version }}"
  
  os:
    ubuntu:
      primary_url: "http://archive.ubuntu.com/ubuntu/dists/{{ version }}"
      fallback_urls:
        - "http://us.archive.ubuntu.com/ubuntu/dists/{{ version }}"
      
      versions:
        jammy:  # 22.04 LTS
          primary_url: "http://archive.ubuntu.com/ubuntu/dists/jammy"
          security_url: "http://security.ubuntu.com/ubuntu/dists/jammy-security"

npm:
  default:
    registry_url: "https://registry.npmjs.org"
    search_url: "https://registry.npmjs.org/-/v1/search?text={{ software_name }}"
    package_url: "https://registry.npmjs.org/{{ software_name }}"
```

## Using the URL Manager

### Basic Usage

```python
from saidata_gen.core.repository_url_manager import get_repository_url_manager

# Get the global URL manager instance
url_manager = get_repository_url_manager()

# Get primary URL for a provider
primary_url = url_manager.get_primary_url('apt')

# Get fallback URLs
fallback_urls = url_manager.get_fallback_urls('apt')

# Get all URLs for a provider
urls = url_manager.get_urls('apt')
```

### With Context

```python
# Get URLs with OS and version context
urls = url_manager.get_urls(
    provider='apt',
    os_name='ubuntu',
    os_version='jammy',
    architecture='x86_64'
)

# Get search URL with software name
search_url = url_manager.get_search_url('npm', 'express')

# Get package-specific URL
package_url = url_manager.get_package_url('pypi', 'requests')
```

### Custom Context Variables

```python
# Provide additional context for template substitution
context = {
    'repo_name': 'fedora-40',
    'component': 'main'
}

urls = url_manager.get_urls(
    provider='dnf',
    os_name='fedora',
    os_version='40',
    context=context
)
```

## Integrating with Fetchers

### Step 1: Import the URL Manager

```python
from saidata_gen.core.repository_url_manager import get_repository_url_manager
```

### Step 2: Initialize in Constructor

```python
def __init__(self, config: Optional[FetcherConfig] = None):
    super().__init__(base_url="https://example.com", config=config)
    
    # Initialize repository URL manager
    self.url_manager = get_repository_url_manager()
```

### Step 3: Load URLs from Manager

```python
def _load_repositories_from_url_manager(self):
    """Load repository configurations from URL manager."""
    try:
        # Get URLs for this provider
        urls = self.url_manager.get_urls(provider="apt")
        
        # Create repository objects
        repositories = []
        if 'primary_url' in urls:
            repositories.append(self._create_repository(urls['primary_url']))
        
        return repositories
        
    except Exception as e:
        logger.error(f"Failed to load repositories: {e}")
        return self._get_fallback_repositories()
```

### Step 4: Use URLs in Methods

```python
def fetch_package_info(self, package_name: str):
    """Fetch package information."""
    # Get package-specific URL
    package_url = self.url_manager.get_package_url(
        provider="pypi",
        software_name=package_name
    )
    
    if package_url:
        response = self._fetch_url(package_url)
        return self._parse_response(response)
    
    return None
```

## Complete Fetcher Example

Here's a complete example of a fetcher using the URL manager:

```python
from saidata_gen.core.repository_url_manager import get_repository_url_manager
from saidata_gen.fetcher.base import HttpRepositoryFetcher

class ExampleFetcher(HttpRepositoryFetcher):
    def __init__(self, config=None):
        super().__init__(base_url="https://example.com", config=config)
        
        # Initialize URL manager
        self.url_manager = get_repository_url_manager()
        
        # Load repositories from URL manager
        self.repositories = self._load_repositories_from_url_manager()
    
    def _load_repositories_from_url_manager(self):
        """Load repositories from URL manager."""
        repositories = []
        
        try:
            # Get URLs for this provider
            urls = self.url_manager.get_urls(provider="example")
            
            if 'primary_url' in urls:
                repositories.append({
                    'name': 'primary',
                    'url': urls['primary_url']
                })
            
            # Add fallback repositories
            for fallback_url in urls.get('fallback_urls', []):
                repositories.append({
                    'name': 'fallback',
                    'url': fallback_url
                })
                
        except Exception as e:
            logger.error(f"Failed to load repositories: {e}")
            # Fallback to hardcoded repositories
            repositories = self._get_fallback_repositories()
        
        return repositories
    
    def get_package_info(self, package_name: str):
        """Get package information."""
        # Get package-specific URL
        package_url = self.url_manager.get_package_url(
            provider="example",
            software_name=package_name
        )
        
        if package_url:
            try:
                response = self._fetch_url(package_url)
                return self._parse_package_response(response)
            except Exception as e:
                logger.error(f"Failed to fetch package info: {e}")
                
                # Try fallback URLs
                fallback_urls = self.url_manager.get_fallback_urls("example")
                for fallback_url in fallback_urls:
                    try:
                        response = self._fetch_url(fallback_url)
                        return self._parse_package_response(response)
                    except Exception:
                        continue
        
        return None
```

## Migration Guide

### Migrating Existing Fetchers

1. **Add URL Manager Import**:
   ```python
   from saidata_gen.core.repository_url_manager import get_repository_url_manager
   ```

2. **Initialize URL Manager**:
   ```python
   self.url_manager = get_repository_url_manager()
   ```

3. **Replace Hardcoded URLs**:
   ```python
   # Before
   url = "https://api.example.com/packages"
   
   # After
   url = self.url_manager.get_primary_url("example")
   ```

4. **Add Fallback Handling**:
   ```python
   # Try primary URL
   try:
       response = self._fetch_url(primary_url)
   except Exception:
       # Try fallback URLs
       for fallback_url in self.url_manager.get_fallback_urls("example"):
           try:
               response = self._fetch_url(fallback_url)
               break
           except Exception:
               continue
   ```

5. **Update Configuration**:
   Add your provider's URLs to `repository_urls.yaml`.

### Migration Tools

Use the provided migration tools to help with the process:

```bash
# Analyze hardcoded URLs in fetchers
python scripts/migrate_fetchers_to_url_manager.py analyze

# Check URL manager coverage
python scripts/migrate_fetchers_to_url_manager.py coverage

# Generate template for a provider
python scripts/migrate_fetchers_to_url_manager.py template my_provider
```

## Testing

### Unit Tests

Test your fetcher's URL manager integration:

```python
import unittest
from unittest.mock import patch, MagicMock

class TestMyFetcher(unittest.TestCase):
    @patch('saidata_gen.core.repository_url_manager.get_repository_url_manager')
    def test_url_manager_integration(self, mock_get_manager):
        # Mock URL manager
        mock_manager = MagicMock()
        mock_manager.get_primary_url.return_value = "https://test.example.com"
        mock_get_manager.return_value = mock_manager
        
        # Test fetcher
        fetcher = MyFetcher()
        
        # Verify URL manager was called
        mock_manager.get_primary_url.assert_called_with("my_provider")
```

### Integration Tests

Test with real URL manager:

```python
def test_real_url_manager(self):
    """Test with real URL manager and configuration."""
    fetcher = MyFetcher()
    
    # Should load URLs from configuration
    self.assertIsNotNone(fetcher.url_manager)
    
    # Should have repositories loaded
    self.assertGreater(len(fetcher.repositories), 0)
```

## Best Practices

### Configuration

1. **Use Template Variables**: Leverage `{{ variable }}` syntax for dynamic URLs
2. **Provide Fallbacks**: Always include fallback URLs for reliability
3. **OS/Version Specific**: Use OS and version overrides when needed
4. **Keep URLs Current**: Regularly update URLs as repositories change

### Implementation

1. **Error Handling**: Always handle URL manager failures gracefully
2. **Fallback Logic**: Implement proper fallback URL handling
3. **Logging**: Log URL resolution for debugging
4. **Caching**: Cache resolved URLs when appropriate

### Testing

1. **Mock URL Manager**: Use mocks for unit tests
2. **Test Fallbacks**: Verify fallback URL handling
3. **Integration Tests**: Test with real configuration
4. **URL Validation**: Verify URLs are accessible

## Troubleshooting

### Common Issues

1. **Provider Not Found**:
   ```
   WARNING: No URL configuration found for provider: xyz
   ```
   **Solution**: Add the provider to `repository_urls.yaml`

2. **Template Variables Not Substituted**:
   ```
   URL still contains: {{ software_name }}
   ```
   **Solution**: Ensure context is provided when calling URL manager methods

3. **Fallback URLs Not Working**:
   ```
   All URLs failed to load
   ```
   **Solution**: Verify fallback URLs are accessible and properly configured

### Debug Logging

Enable debug logging to see URL resolution:

```python
import logging
logging.getLogger('saidata_gen.core.repository_url_manager').setLevel(logging.DEBUG)
```

### Configuration Validation

Validate your configuration:

```python
from saidata_gen.core.repository_url_manager import get_repository_url_manager

manager = get_repository_url_manager()

# Check if provider exists
if manager.has_provider('my_provider'):
    print("Provider configured")
else:
    print("Provider not found")

# Get provider configuration
config = manager.get_provider_config('my_provider')
print(f"Provider config: {config}")
```

## Advanced Usage

### Custom Configuration Files

Use custom configuration files:

```python
from saidata_gen.core.repository_url_manager import RepositoryUrlManager

# Use custom configuration
manager = RepositoryUrlManager(config_path='/path/to/custom/urls.yaml')
```

### Dynamic URL Generation

Generate URLs dynamically:

```python
# Get URLs with custom context
context = {
    'api_version': 'v2',
    'region': 'us-east-1'
}

urls = manager.get_urls(
    provider='my_provider',
    context=context
)
```

### Configuration Reloading

Reload configuration at runtime:

```python
# Reload configuration
manager.reload_configuration()
```

This centralized URL management system provides a robust, flexible, and maintainable approach to handling repository URLs across all fetchers in saidata-gen.