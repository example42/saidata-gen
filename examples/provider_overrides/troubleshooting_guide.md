# Provider Override Troubleshooting Guide

This guide helps you troubleshoot common issues when working with the new override-only provider configuration system.

## Common Issues and Solutions

### 1. Provider Template Not Found

**Problem:** Error message like "Provider template not found for 'xyz'"

**Symptoms:**
```
ERROR: Provider template not found for 'xyz'
FileNotFoundError: No such file or directory: 'templates/providers/xyz.yaml'
```

**Solutions:**
1. **Check provider name spelling:**
   ```bash
   # List available providers
   ls saidata_gen/templates/providers/
   ```

2. **Create missing provider template:**
   ```yaml
   # templates/providers/xyz.yaml
   version: 0.1
   packages:
     default:
       name: "{{ software_name }}"
   ```

3. **Use hierarchical structure if needed:**
   ```
   templates/providers/xyz/
   ├── default.yaml
   ├── linux.yaml
   └── windows.yaml
   ```

### 2. Redundant Configuration Keys

**Problem:** Provider templates contain keys that match defaults

**Symptoms:**
```
WARNING: Key 'services.default.name' matches default value and can be removed
Quality Score: 0.45 (low due to redundancy)
```

**Solutions:**
1. **Use the configuration validator:**
   ```python
   from saidata_gen.validation.config_validator import ConfigurationValidator
   
   validator = ConfigurationValidator()
   removable = validator.suggest_removable_keys(provider_config)
   print(f"Remove these keys: {removable}")
   ```

2. **Remove redundant keys manually:**
   ```yaml
   # BEFORE (redundant)
   version: 0.1
   packages:
     default:
       name: nginx        # Same as software name
       version: latest    # Same as default
   services:
     default:
       name: nginx        # Same as software name
   
   # AFTER (clean)
   version: 0.1
   # Only include if different from defaults
   ```

3. **Use the cleanup script:**
   ```bash
   python scripts/cleanup_provider_configs.py --provider apt --dry-run
   ```

### 3. AI Enhancement Not Working

**Problem:** AI enhancement fails or returns empty results

**Symptoms:**
```
WARNING: AI provider openai is not available
ERROR: Enhancement failed: API key not found
```

**Solutions:**
1. **Check API key configuration:**
   ```bash
   # Set environment variable
   export OPENAI_API_KEY="your-api-key-here"
   
   # Or store securely
   python -c "
   from saidata_gen.ai.enhancer import APIKeyManager
   manager = APIKeyManager()
   manager.store_api_key('openai', 'your-api-key-here')
   "
   ```

2. **Verify provider availability:**
   ```python
   from saidata_gen.ai.enhancer import AIMetadataEnhancer
   
   enhancer = AIMetadataEnhancer(provider="openai")
   if enhancer.is_available():
       print("AI provider is available")
   else:
       print("AI provider is not available")
   ```

3. **Use local model as fallback:**
   ```python
   # Set up local model (e.g., Ollama)
   enhancer = AIMetadataEnhancer(provider="local")
   ```

4. **Check rate limits:**
   ```python
   # Configure rate limiting
   from saidata_gen.ai.enhancer import AIProviderConfig
   
   config = AIProviderConfig(
       provider="openai",
       rate_limit_requests_per_minute=30,  # Lower rate
       max_retries=5
   )
   ```

### 4. Template Variable Substitution Issues

**Problem:** Variables like `{{ software_name }}` not being replaced

**Symptoms:**
```yaml
packages:
  default:
    name: "{{ software_name }}"  # Not replaced
```

**Solutions:**
1. **Check variable syntax:**
   ```yaml
   # Correct syntax
   name: "{{ software_name }}"
   
   # Also supported
   name: "$software_name"
   name: "${software_name}"
   ```

2. **Verify context variables:**
   ```python
   context = {
       "software_name": "nginx",
       "provider": "apt",
       "platforms": ["linux"]
   }
   result = template_engine.apply_template("nginx", context=context)
   ```

3. **Debug template processing:**
   ```python
   # Enable debug logging
   import logging
   logging.getLogger('saidata_gen.generator.templates').setLevel(logging.DEBUG)
   ```

### 5. Provider Support Detection Issues

**Problem:** Provider incorrectly marked as supported/unsupported

**Symptoms:**
```yaml
# Provider should be supported but shows:
supported: false
```

**Solutions:**
1. **Check repository data:**
   ```python
   # Ensure repository data is provided
   repository_data = {
       "name": "nginx",
       "version": "1.18.0",
       "available": True
   }
   
   is_supported = template_engine.is_provider_supported(
       "nginx", "apt", repository_data
   )
   ```

2. **Clear provider support cache:**
   ```python
   template_engine.clear_provider_support_cache("nginx", "apt")
   ```

3. **Override support detection:**
   ```yaml
   # Explicitly set in provider template
   version: 0.1
   supported: true
   packages:
     default:
       name: nginx-custom
   ```

### 6. Configuration Validation Errors

**Problem:** Generated configurations fail schema validation

**Symptoms:**
```
ValidationError: 'version' is a required property
ValidationError: Additional properties are not allowed ('unsupported_key')
```

**Solutions:**
1. **Use the configuration validator:**
   ```python
   from saidata_gen.validation.config_validator import ConfigurationValidator
   
   validator = ConfigurationValidator()
   result = validator.validate_provider_override("apt", config)
   
   if not result.valid:
       for issue in result.issues:
           print(f"{issue.level}: {issue.message}")
   ```

2. **Check required fields:**
   ```yaml
   # Always include version
   version: 0.1
   
   # For unsupported providers
   version: 0.1
   supported: false
   ```

3. **Remove invalid keys:**
   ```python
   # Get suggestions for cleanup
   suggestions = result.suggestions
   for suggestion in suggestions:
       if suggestion.type == 'remove':
           print(f"Remove key: {suggestion.path}")
   ```

### 7. Hierarchical Template Issues

**Problem:** Hierarchical provider templates not loading correctly

**Symptoms:**
```
WARNING: Hierarchical provider directory found but no default.yaml
ERROR: Failed to load hierarchical provider template
```

**Solutions:**
1. **Ensure proper structure:**
   ```
   templates/providers/yum/
   ├── default.yaml      # Required base template
   ├── centos.yaml       # OS-specific override
   ├── rhel.yaml         # OS-specific override
   └── rhel/             # Version-specific overrides
       ├── 7.yaml
       └── 8.yaml
   ```

2. **Create default.yaml:**
   ```yaml
   # templates/providers/yum/default.yaml
   version: 0.1
   packages:
     default:
       name: "{{ software_name }}"
   ```

3. **Check file permissions:**
   ```bash
   chmod 644 templates/providers/yum/*.yaml
   ```

### 8. Performance Issues

**Problem:** Template processing is slow

**Symptoms:**
- Long processing times
- High memory usage
- Cache misses

**Solutions:**
1. **Enable caching:**
   ```python
   from saidata_gen.core.cache import CacheManager, CacheConfig
   
   cache_config = CacheConfig(
       backend=CacheBackend.MEMORY,
       default_ttl=3600,
       max_size=1000
   )
   cache_manager = CacheManager(cache_config)
   template_engine = TemplateEngine(cache_manager=cache_manager)
   ```

2. **Optimize provider templates:**
   ```bash
   # Remove redundant configurations
   python scripts/analyze_provider_templates.py --optimize
   ```

3. **Use batch processing:**
   ```python
   # Process multiple software packages together
   software_list = ["nginx", "apache2", "mysql"]
   results = engine.batch_process(software_list, options)
   ```

## Debugging Tips

### Enable Debug Logging

```python
import logging

# Enable debug logging for all saidata_gen modules
logging.getLogger('saidata_gen').setLevel(logging.DEBUG)

# Or enable for specific modules
logging.getLogger('saidata_gen.generator.templates').setLevel(logging.DEBUG)
logging.getLogger('saidata_gen.ai.enhancer').setLevel(logging.DEBUG)
logging.getLogger('saidata_gen.validation.config_validator').setLevel(logging.DEBUG)
```

### Inspect Template Processing

```python
# Debug template variable substitution
template_engine = TemplateEngine()
context = {"software_name": "nginx", "provider": "apt"}

# Process step by step
raw_template = template_engine.provider_templates["apt"]
processed = template_engine._process_template(raw_template, context)
print(f"Processed template: {processed}")
```

### Validate Configuration Step by Step

```python
from saidata_gen.validation.config_validator import ConfigurationValidator

validator = ConfigurationValidator()

# Check individual aspects
config = {"version": "0.1", "packages": {"default": {"name": "nginx"}}}

# Check if overrides are necessary
necessary = validator._is_override_necessary("packages.default.name", "nginx", defaults)
print(f"Override necessary: {necessary}")

# Get removable keys
removable = validator.suggest_removable_keys(config)
print(f"Removable keys: {removable}")
```

### Test AI Enhancement Locally

```python
# Test with mock data to avoid API calls
from saidata_gen.ai.enhancer import AIMetadataEnhancer

enhancer = AIMetadataEnhancer(provider="openai")

# Check missing fields without AI call
missing = enhancer.get_missing_fields({
    "version": "0.1",
    "packages": {"default": {"name": "nginx"}},
    "description": None
})
print(f"Missing fields: {missing}")
```

## Getting Help

If you're still experiencing issues:

1. **Check the logs:** Enable debug logging to see detailed processing information
2. **Validate your configuration:** Use the ConfigurationValidator to identify issues
3. **Test with minimal examples:** Start with simple configurations and build up
4. **Review the examples:** Check the working examples in this directory
5. **Check the documentation:** Review the API reference and best practices guide

## Common Error Messages

| Error Message | Likely Cause | Solution |
|---------------|--------------|----------|
| `Provider template not found` | Missing template file | Create the provider template |
| `API key not found` | Missing AI API key | Set environment variable or store key |
| `Rate limit exceeded` | Too many AI requests | Reduce rate or wait |
| `Validation failed` | Invalid configuration | Use ConfigurationValidator |
| `Template variable not substituted` | Missing context | Provide required variables |
| `Hierarchical template error` | Missing default.yaml | Create base template file |
| `Cache error` | Cache configuration issue | Check cache settings |
| `Permission denied` | File permission issue | Fix file permissions |