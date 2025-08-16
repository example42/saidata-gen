# Provider Override Examples

This directory contains examples demonstrating the new override-only provider configuration system introduced in the provider structure refactoring.

## Overview

The new provider structure follows an override-only pattern where provider templates contain only settings that differ from the general defaults. This makes configurations cleaner, easier to maintain, and reduces redundancy.

## Examples

- `basic_override_example.py` - Basic example showing override-only provider configuration
- `ai_enhanced_generation.py` - Example demonstrating AI-enhanced metadata generation
- `troubleshooting_guide.md` - Common configuration issues and solutions
- `best_practices.md` - Best practices for creating provider override templates
- `apache_httpd/` - Real-world example showing Apache HTTP Server configuration across providers

## Key Concepts

### Override-Only Templates

Provider templates now contain only settings that differ from defaults:

```yaml
# OLD: Full provider template (redundant)
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

# NEW: Override-only template (clean)
version: 0.1
packages:
  default:
    name: nginx-core  # Only override what's different
```

### Unsupported Providers

For providers that don't support a package:

```yaml
version: 0.1
supported: false
```

### AI Enhancement

AI can fill missing metadata fields while respecting repository data precedence:

```python
# Repository data takes precedence over AI data
result = generator.generate_with_ai_enhancement(
    software_name="nginx",
    sources=repository_sources,
    ai_provider="openai"
)
```

## Getting Started

1. Run the basic override example:
   ```bash
   python examples/provider_overrides/basic_override_example.py
   ```

2. Try AI-enhanced generation:
   ```bash
   python examples/provider_overrides/ai_enhanced_generation.py
   ```

3. Review the troubleshooting guide for common issues

4. Follow best practices when creating your own provider templates