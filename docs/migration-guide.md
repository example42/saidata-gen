# Migration Guide: Provider Structure Refactoring

This guide helps you migrate from the old provider template system to the new override-only structure introduced in the provider structure refactoring.

## Overview of Changes

The provider structure refactoring introduces several key changes:

1. **Override-Only Templates**: Provider templates now contain only settings that differ from defaults
2. **AI Enhancement**: New AI-powered metadata enhancement with multiple provider support
3. **Hierarchical Output**: Option to generate hierarchical directory structures
4. **Enhanced Validation**: Improved configuration validation and optimization suggestions
5. **Provider Support Detection**: Automatic detection of provider support

## Breaking Changes

### 1. Provider Template Structure

**Before (Full Templates):**
```yaml
# providers/apt.yaml
version: 0.1
packages:
  default:
    name: nginx
    version: latest
services:
  default:
    name: nginx
directories:
  config:
    path: /etc/nginx
    owner: root
    group: root
    mode: "0755"
# ... many more redundant settings
```

**After (Override-Only):**
```yaml
# providers/apt.yaml
version: 0.1
packages:
  default:
    name: nginx-core  # Only if different from software name
# Only include settings that differ from defaults
```

### 2. CLI Options

**Before:**
```bash
saidata-gen generate nginx --use-rag --rag-provider openai
```

**After:**
```bash
saidata-gen generate nginx --ai --ai-provider openai
```

### 3. Environment Variables

**Before:**
```bash
export SAIDATA_GEN_USE_RAG=true
export SAIDATA_GEN_RAG_PROVIDER=openai
```

**After:**
```bash
export SAIDATA_GEN_AI=true
export SAIDATA_GEN_AI_PROVIDER=openai
```

## Migration Steps

### Step 1: Update Provider Templates

Use the configuration validator to identify redundant settings:

```python
from saidata_gen.validation.config_validator import ConfigurationValidator

validator = ConfigurationValidator()

# Analyze existing provider template
with open('providers/apt.yaml', 'r') as f:
    config = yaml.safe_load(f)

result = validator.validate_provider_override('apt', config)

# Get suggestions for optimization
removable_keys = validator.suggest_removable_keys(config)
print(f"Keys that can be removed: {removable_keys}")

# Check quality score
print(f"Quality score: {result.quality_score:.2f}")
```

### Step 2: Use the Cleanup Script

Run the automated cleanup script to optimize your provider templates:

```bash
# Analyze all provider templates
python scripts/analyze_provider_templates.py

# Clean up specific provider (dry run first)
python scripts/cleanup_provider_configs.py --provider apt --dry-run

# Apply cleanup
python scripts/cleanup_provider_configs.py --provider apt
```

### Step 3: Update CLI Usage

Replace old CLI options with new ones:

```bash
# Old way
saidata-gen generate nginx --use-rag --rag-provider openai

# New way
saidata-gen generate nginx --ai --ai-provider openai

# With specific enhancement types
saidata-gen generate nginx --ai --enhancement-types description,field_completion
```

### Step 4: Update Environment Variables

Update your environment configuration:

```bash
# Old variables (still supported but deprecated)
export SAIDATA_GEN_USE_RAG=true
export SAIDATA_GEN_RAG_PROVIDER=openai

# New variables
export SAIDATA_GEN_AI=true
export SAIDATA_GEN_AI_PROVIDER=openai
export SAIDATA_GEN_ENHANCEMENT_TYPES=description,categorization,field_completion
```

### Step 5: Update Scripts and Automation

Update any scripts or automation that use saidata-gen:

**Before:**
```bash
#!/bin/bash
for software in nginx apache2 mysql; do
    saidata-gen generate $software --use-rag --providers apt,brew
done
```

**After:**
```bash
#!/bin/bash
for software in nginx apache2 mysql; do
    saidata-gen generate $software --ai --ai-provider openai --providers apt,brew
done
```

### Step 6: Validate Migration

Use the new validation commands to ensure everything is working:

```bash
# Validate all provider configurations
saidata-gen validate-config

# List all available providers
saidata-gen list-providers --validate

# Test generation with new options
saidata-gen generate nginx --ai --output-structure hierarchical
```

## Compatibility and Deprecation

### Backward Compatibility

The following features are maintained for backward compatibility but are deprecated:

1. **RAG CLI Options**: `--use-rag` and `--rag-provider` still work but show deprecation warnings
2. **RAG Environment Variables**: `SAIDATA_GEN_USE_RAG` and `SAIDATA_GEN_RAG_PROVIDER` still work
3. **Full Provider Templates**: Old-style templates still work but are not optimal

### Deprecation Timeline

- **Current Release**: Old options work with deprecation warnings
- **Next Major Release**: Old options will be removed
- **Migration Period**: 6 months to update configurations

### Deprecation Warnings

You'll see warnings like:

```
DeprecationWarning: --use-rag is deprecated, use --ai instead
DeprecationWarning: SAIDATA_GEN_RAG_PROVIDER is deprecated, use SAIDATA_GEN_AI_PROVIDER instead
```

## New Features Available After Migration

### 1. AI Enhancement Types

Specify exactly what AI should enhance:

```bash
# Only enhance description and categorization
saidata-gen generate nginx --ai --enhancement-types description,categorization

# Only fill missing fields
saidata-gen generate nginx --ai --enhancement-types field_completion
```

### 2. Hierarchical Output Structure

Generate organized directory structures:

```bash
# Generate hierarchical structure
saidata-gen generate nginx --output-structure hierarchical

# Output:
# nginx/
# ├── defaults.yaml
# └── providers/
#     ├── apt.yaml
#     ├── brew.yaml
#     └── winget.yaml
```

### 3. Enhanced Provider Management

```bash
# List all available providers
saidata-gen list-providers

# Validate provider configurations
saidata-gen validate-config --show-suggestions

# Check specific provider quality
saidata-gen validate-config --provider apt --quality-threshold 0.8
```

### 4. Multiple AI Providers

```bash
# Use OpenAI
saidata-gen generate nginx --ai --ai-provider openai

# Use Anthropic
saidata-gen generate nginx --ai --ai-provider anthropic

# Use local model
saidata-gen generate nginx --ai --ai-provider local
```

### 5. Advanced Configuration Validation

```python
from saidata_gen.validation.config_validator import ConfigurationValidator

validator = ConfigurationValidator()

# Get comprehensive report
report = validator.validate_configuration_consistency(all_provider_configs)

print(f"Overall quality: {report.overall_quality_score:.2f}")
print(f"Optimization opportunities: {report.optimization_summary}")

for recommendation in report.recommendations:
    print(f"Recommendation: {recommendation}")
```

## Common Migration Issues

### Issue 1: Provider Templates Too Large

**Problem**: Provider templates contain many redundant settings

**Solution**: Use the cleanup script and validator

```bash
python scripts/cleanup_provider_configs.py --provider apt
```

### Issue 2: AI Enhancement Not Working

**Problem**: AI enhancement fails with API key errors

**Solution**: Configure API keys properly

```bash
# Set environment variable
export OPENAI_API_KEY="your-api-key"

# Or store securely
python -c "
from saidata_gen.ai.enhancer import APIKeyManager
manager = APIKeyManager()
manager.store_api_key('openai', 'your-api-key')
"
```

### Issue 3: Validation Errors

**Problem**: Generated configurations fail validation

**Solution**: Use the configuration validator

```python
from saidata_gen.validation.config_validator import ConfigurationValidator

validator = ConfigurationValidator()
result = validator.validate_provider_override('apt', config)

if not result.valid:
    for issue in result.issues:
        print(f"Fix: {issue.message}")
```

### Issue 4: Performance Degradation

**Problem**: Generation is slower after migration

**Solution**: Enable caching and optimize templates

```python
from saidata_gen.core.cache import CacheManager, CacheConfig

# Enable caching
cache_config = CacheConfig(default_ttl=3600, max_size=1000)
cache_manager = CacheManager(cache_config)
```

## Testing Your Migration

### 1. Validate Template Quality

```bash
# Check all provider templates
saidata-gen validate-config

# Should show high quality scores (>0.8)
```

### 2. Test Generation

```bash
# Test basic generation
saidata-gen generate nginx

# Test AI enhancement
saidata-gen generate nginx --ai

# Test hierarchical output
saidata-gen generate nginx --output-structure hierarchical
```

### 3. Compare Output

```bash
# Generate with old and new systems
saidata-gen generate nginx --output old-nginx.yaml
saidata-gen generate nginx --ai --output new-nginx.yaml

# Compare results
diff old-nginx.yaml new-nginx.yaml
```

### 4. Performance Testing

```bash
# Test batch processing
echo -e "nginx\napache2\nmysql" > test-list.txt
time saidata-gen batch --input test-list.txt --ai
```

## Getting Help

If you encounter issues during migration:

1. **Check the troubleshooting guide**: `examples/provider_overrides/troubleshooting_guide.md`
2. **Review best practices**: `examples/provider_overrides/best_practices.md`
3. **Run validation tools**: Use `saidata-gen validate-config` and `saidata-gen list-providers`
4. **Enable debug logging**: Set `SAIDATA_GEN_LOG_LEVEL=DEBUG`
5. **Test with examples**: Try the examples in `examples/provider_overrides/`

## Migration Checklist

- [ ] Analyzed existing provider templates with validator
- [ ] Cleaned up redundant configurations
- [ ] Updated CLI commands to use `--ai` instead of `--use-rag`
- [ ] Updated environment variables
- [ ] Updated scripts and automation
- [ ] Tested AI enhancement functionality
- [ ] Validated all provider configurations
- [ ] Tested hierarchical output structure
- [ ] Performance tested the new system
- [ ] Updated documentation and team knowledge

## Post-Migration Benefits

After completing the migration, you'll benefit from:

1. **Cleaner Templates**: Easier to maintain and understand
2. **Better Performance**: Reduced redundancy and improved caching
3. **AI Enhancement**: Automatic filling of missing metadata fields
4. **Better Validation**: Comprehensive quality checks and suggestions
5. **Flexible Output**: Choose between flat and hierarchical structures
6. **Multiple AI Providers**: Not locked into a single AI service
7. **Enhanced Debugging**: Better error messages and troubleshooting tools