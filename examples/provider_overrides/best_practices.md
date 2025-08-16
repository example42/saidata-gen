# Best Practices for Provider Override Templates

This guide outlines best practices for creating and maintaining provider override templates in the new override-only system.

## Core Principles

### 1. Override Only What's Different

**✅ Good:**
```yaml
# Only include settings that differ from defaults
version: 0.1
packages:
  default:
    name: nginx-core  # Different from default "nginx"
```

**❌ Bad:**
```yaml
# Don't repeat default values
version: 0.1
packages:
  default:
    name: nginx       # Same as software name (default)
    version: latest   # Same as default
services:
  default:
    name: nginx       # Same as software name (default)
directories:
  config:
    path: /etc/nginx  # Might be the same as default
```

### 2. Use Explicit Support Declaration

**✅ Good:**
```yaml
# For unsupported providers
version: 0.1
supported: false
```

**✅ Good:**
```yaml
# For supported providers with overrides
version: 0.1
packages:
  default:
    name: custom-package-name
# supported: true is implicit when overrides exist
```

**❌ Bad:**
```yaml
# Don't explicitly set supported: true unless necessary
version: 0.1
supported: true  # Redundant if overrides exist
packages:
  default:
    name: nginx
```

### 3. Minimize Configuration Complexity

**✅ Good:**
```yaml
# Simple, focused overrides
version: 0.1
packages:
  default:
    name: httpd  # Apache on RHEL/CentOS
```

**❌ Bad:**
```yaml
# Overly complex nested overrides
version: 0.1
packages:
  default:
    name: httpd
    metadata:
      custom_field: value
      another_field: another_value
  alternative:
    name: apache2
    metadata:
      different_field: different_value
```

## Template Organization

### Flat vs Hierarchical Structure

**Use flat structure for simple providers:**
```
templates/providers/
├── apt.yaml
├── brew.yaml
├── winget.yaml
└── npm.yaml
```

**Use hierarchical structure for complex providers:**
```
templates/providers/yum/
├── default.yaml      # Base YUM configuration
├── centos.yaml       # CentOS-specific overrides
├── rhel.yaml         # RHEL-specific overrides
└── rhel/             # Version-specific overrides
    ├── 7.yaml
    └── 8.yaml
```

### Hierarchical Template Best Practices

1. **Always provide default.yaml:**
   ```yaml
   # templates/providers/yum/default.yaml
   version: 0.1
   packages:
     default:
       name: "{{ software_name }}"
   ```

2. **Keep OS-specific overrides minimal:**
   ```yaml
   # templates/providers/yum/rhel.yaml
   version: 0.1
   packages:
     default:
       name: "{{ software_name }}-rhel"
   ```

3. **Use version-specific overrides sparingly:**
   ```yaml
   # templates/providers/yum/rhel/8.yaml
   version: 0.1
   services:
     default:
       manager: systemd  # Only if different from RHEL 7
   ```

## Provider-Specific Guidelines

### Package Managers

#### APT (Debian/Ubuntu)
```yaml
version: 0.1
packages:
  default:
    name: "{{ software_name }}-core"  # If different from software name
# Implicit: platforms: [linux], manager: apt
```

#### Homebrew (macOS/Linux)
```yaml
version: 0.1
packages:
  default:
    name: "{{ software_name }}"
# Usually no overrides needed unless formula name differs
```

#### Winget (Windows)
```yaml
version: 0.1
packages:
  default:
    name: "Publisher.{{ software_name | title }}"  # Windows naming convention
```

#### Chocolatey (Windows)
```yaml
version: 0.1
packages:
  default:
    name: "{{ software_name }}"
# Often no overrides needed
```

### Language Package Managers

#### NPM (Node.js)
```yaml
version: 0.1
packages:
  default:
    name: "@scope/{{ software_name }}"  # If scoped package
```

#### PyPI (Python)
```yaml
version: 0.1
packages:
  default:
    name: "{{ software_name | replace('-', '_') }}"  # Python naming convention
```

#### Cargo (Rust)
```yaml
version: 0.1
packages:
  default:
    name: "{{ software_name | replace('_', '-') }}"  # Rust naming convention
```

### Container Registries

#### Docker Hub
```yaml
version: 0.1
containers:
  default:
    image: "library/{{ software_name }}"  # Official images
    # or
    image: "{{ software_name }}/{{ software_name }}"  # User images
```

## Configuration Validation

### Use the Configuration Validator

Always validate your templates:

```python
from saidata_gen.validation.config_validator import ConfigurationValidator

validator = ConfigurationValidator()

# Validate individual provider
result = validator.validate_provider_override("apt", config)
if not result.valid:
    print("Issues found:")
    for issue in result.issues:
        print(f"  {issue.level}: {issue.message}")

# Check for removable keys
removable = validator.suggest_removable_keys(config)
if removable:
    print(f"Consider removing: {removable}")
```

### Quality Metrics

Aim for these quality metrics:
- **Quality Score:** > 0.8
- **Optimization Potential:** < 0.2
- **Redundant Keys:** 0

```python
# Check quality metrics
result = validator.validate_provider_override("apt", config)
print(f"Quality Score: {result.quality_score:.2f}")
print(f"Optimization Potential: {result.optimization_potential:.2f}")
```

## Template Variables and Functions

### Use Appropriate Variable Syntax

**✅ Good:**
```yaml
packages:
  default:
    name: "{{ software_name }}"           # Jinja2 style
    # or
    name: "${software_name}"              # Shell style
    # or  
    name: "$software_name"                # Simple style
```

### Leverage Built-in Functions

```yaml
packages:
  default:
    name: "{{ software_name | lower }}"   # Convert to lowercase
    # or
    name: "{{ software_name | replace('-', '_') }}"  # Replace characters
```

### Common Template Patterns

**Package name transformation:**
```yaml
# For providers with different naming conventions
packages:
  default:
    name: "{{ software_name | replace('-', '_') }}"  # Python style
    # or
    name: "{{ software_name | replace('_', '-') }}"  # Rust style
```

**Conditional configuration:**
```yaml
# Platform-specific settings
$if: linux in platforms
directories:
  config:
    path: "/etc/{{ software_name }}"
$endif

$if: windows in platforms  
directories:
  config:
    path: "C:\\Program Files\\{{ software_name }}"
$endif
```

## Testing and Validation

### Test Template Processing

```python
from saidata_gen.generator.templates import TemplateEngine

engine = TemplateEngine()

# Test variable substitution
result = engine.apply_provider_overrides_only(
    software_name="nginx",
    provider="apt",
    repository_data={"name": "nginx-core"}
)

print(f"Generated config: {result}")
```

### Validate Against Schema

```python
from saidata_gen.validation.schema import SchemaValidator

validator = SchemaValidator()
result = validator.validate(generated_config)

if not result.valid:
    for issue in result.issues:
        print(f"Schema issue: {issue.message}")
```

### Test with Real Data

```python
# Test with actual repository data
repository_data = {
    "name": "nginx-core",
    "version": "1.18.0",
    "description": "High-performance web server"
}

config = engine.apply_provider_overrides_only(
    "nginx", "apt", repository_data
)
```

## Performance Considerations

### Minimize Template Complexity

**✅ Good:**
```yaml
# Simple, fast processing
version: 0.1
packages:
  default:
    name: nginx-core
```

**❌ Bad:**
```yaml
# Complex nested conditionals (slow)
version: 0.1
$for: platform in platforms
  $if: platform == "linux"
    packages:
      default:
        name: "{{ software_name }}-linux"
  $elif: platform == "windows"
    packages:
      default:
        name: "{{ software_name }}-win"
  $endif
$endfor
```

### Use Caching Effectively

```python
from saidata_gen.core.cache import CacheManager, CacheConfig

# Configure caching for better performance
cache_config = CacheConfig(
    backend=CacheBackend.MEMORY,
    default_ttl=3600,  # 1 hour
    max_size=1000
)

cache_manager = CacheManager(cache_config)
template_engine = TemplateEngine(cache_manager=cache_manager)
```

## Documentation and Comments

### Document Complex Logic

```yaml
# Provider override for Apache HTTP Server on RHEL/CentOS
# Package name differs from Debian/Ubuntu (apache2 vs httpd)
version: 0.1
packages:
  default:
    name: httpd  # RHEL/CentOS uses 'httpd' instead of 'apache2'
services:
  default:
    name: httpd  # Service name also differs
```

### Include Rationale for Overrides

```yaml
# Override for Nginx on APT systems
version: 0.1
packages:
  default:
    name: nginx-core  # Use nginx-core for minimal installation
                      # nginx-full includes additional modules
```

## Maintenance and Updates

### Regular Validation

Set up automated validation:

```bash
#!/bin/bash
# validate_templates.sh

for template in templates/providers/*.yaml; do
    echo "Validating $template..."
    python -c "
from saidata_gen.validation.config_validator import ConfigurationValidator
validator = ConfigurationValidator()
result = validator.validate_provider_template_file('$template')
if not result.valid:
    print('FAILED: $template')
    exit(1)
else:
    print('PASSED: $template')
"
done
```

### Monitor Quality Metrics

```python
# Generate quality report
from saidata_gen.validation.config_validator import ConfigurationValidator

validator = ConfigurationValidator()
provider_configs = load_all_provider_configs()

report = validator.validate_configuration_consistency(provider_configs)
print(f"Overall quality: {report.overall_quality_score:.2f}")

if report.recommendations:
    print("Recommendations:")
    for rec in report.recommendations:
        print(f"  - {rec}")
```

### Version Control Best Practices

1. **Commit templates separately:** Each provider template should be in its own commit
2. **Include validation results:** Add quality metrics to commit messages
3. **Test before merging:** Always validate templates before merging
4. **Document changes:** Explain why overrides are necessary

## Common Pitfalls to Avoid

### 1. Over-Engineering Templates

**❌ Don't:**
- Create complex conditional logic for edge cases
- Add every possible configuration option
- Use deeply nested structures unnecessarily

**✅ Do:**
- Keep templates simple and focused
- Only override what's actually different
- Use hierarchical structure only when needed

### 2. Ignoring Validation

**❌ Don't:**
- Skip configuration validation
- Ignore quality score warnings
- Leave redundant keys in templates

**✅ Do:**
- Always validate templates before deployment
- Aim for high quality scores
- Remove redundant configurations

### 3. Inconsistent Naming

**❌ Don't:**
- Use different naming conventions across providers
- Ignore provider-specific naming patterns
- Hardcode values that should be variables

**✅ Do:**
- Follow provider naming conventions
- Use template variables consistently
- Document naming decisions

### 4. Missing Documentation

**❌ Don't:**
- Leave complex overrides unexplained
- Skip rationale for unusual configurations
- Forget to update documentation when changing templates

**✅ Do:**
- Document why overrides are necessary
- Explain provider-specific requirements
- Keep documentation up to date

## Summary Checklist

Before finalizing a provider template:

- [ ] Contains only necessary overrides
- [ ] Passes configuration validation
- [ ] Quality score > 0.8
- [ ] No redundant keys
- [ ] Uses appropriate template variables
- [ ] Follows provider naming conventions
- [ ] Includes documentation for complex logic
- [ ] Tested with real repository data
- [ ] Validated against schema
- [ ] Performance impact considered