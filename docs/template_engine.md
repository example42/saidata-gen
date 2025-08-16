# Template Engine Documentation

The template engine is a core component of the saidata-gen tool that provides powerful templating capabilities for generating saidata metadata. It supports variable substitution, conditional logic, loops, function calls, and template inclusion.

## Features

- **Variable Substitution**: Replace variables in templates with values from the context
- **Conditional Logic**: Include or exclude sections based on conditions
- **Loops**: Iterate over lists or dictionaries to generate repeated content
- **Function Calls**: Call built-in or custom functions to transform data
- **Template Inclusion**: Include other templates to promote reuse
- **Provider Overrides**: Override specific paths in the base template for different providers
- **Platform-Specific Sections**: Include sections only for specific platforms
- **Hierarchical Template Support**: Load templates from both flat files and hierarchical directory structures
- **Override-Only Generation**: Generate provider configurations containing only overrides from defaults
- **Enhanced Merging**: Type-safe merging with null removal, override precedence, and redundancy elimination
- **Data Validation**: Automatic validation of type overrides and new key additions
- **Intelligent Caching**: Provider support decisions cached with configurable TTL and storage backends
- **Performance Optimization**: Compiled regex patterns, early returns, and optimized deep copying
- **Security Enhancements**: Path validation, recursion depth limits, and safe expression evaluation

## Usage

### Basic Usage

```python
from saidata_gen.generator.templates import TemplateEngine
from saidata_gen.core.cache import CacheManager, CacheConfig, CacheBackend

# Create a template engine with default caching
engine = TemplateEngine()

# Or create with custom cache configuration
cache_config = CacheConfig(
    backend=CacheBackend.MEMORY,
    default_ttl=3600,  # 1 hour cache
    max_size=1000
)
cache_manager = CacheManager(cache_config)
engine = TemplateEngine(cache_manager=cache_manager)

# Apply a template
result = engine.apply_template(
    software_name="nginx",
    providers=["apt", "brew"],
    platforms=["linux", "macos"],
    context={"current_user": "admin"}
)
```

### Override-Only Template Generation

The template engine now supports generating provider configurations that contain only overrides from defaults:

```python
# Generate only provider-specific overrides
overrides = engine.apply_provider_overrides_only("nginx", "apt", repository_data)

# Merge overrides with defaults
merged = engine.merge_with_defaults(engine.default_template, overrides)

# Check if a provider is supported
is_supported = engine.is_provider_supported("nginx", "apt", repository_data)

# Clear provider support cache when needed
cleared_count = engine.clear_provider_support_cache("nginx", "apt")

# Get cache statistics
cache_stats = engine.get_provider_support_cache_stats()
```

### Variable Substitution

The template engine supports two forms of variable substitution:

1. Simple variables: `$variable_name`
2. Complex expressions: `${variable.path | default_value}`

Examples:

```yaml
# Simple variable substitution
name: $software_name
version: $version

# Complex expressions with defaults
owner: ${current_user | root}
group: ${current_group | root}

# Nested path access
setting: ${config.settings.theme}
```

### Conditional Logic

Conditional directives allow you to include or exclude sections based on conditions:

```yaml
# If condition
$if: software_type == 'web_server'
category:
  default: "web"
  sub: "server"
  tags: ["http", "web", "server"]
$endif

# If-elif-else condition
$if: software_type == 'web_server'
category:
  default: "web"
$elif: software_type == 'database'
category:
  default: "database"
$else
category:
  default: "application"
$endif

# Existence check
$if: exists license
license: ${license | MIT}
$endif

# Platform-specific sections
$platform: linux
directories:
  config:
    path: /etc/$software_name
$endif
```

### Loops

Loop directives allow you to iterate over lists or dictionaries:

```yaml
# Loop through a list
$for: platform in platforms
platform_$platform:
  supported: true
$endfor

# Loop through versions
$for: version in versions
version_$version:
  download_url: "https://download.example.com/$software_name/$version"
$endfor
```

### Function Calls

Function call directives allow you to call built-in or custom functions:

```yaml
# Call the lower function
$function: lower(software_name)
  lowercase_name

# Call the join function with arguments
$function: join(platforms, " | ")
  platforms_string

# Call a function with the value as input
$function: yaml
  name: $software_name
  version: latest
```

### Template Inclusion

Include directives allow you to include other templates:

```yaml
# Include a template
$include: common_urls

# Include a template with overrides
$include: common_urls
  website: "https://custom.example.com/$software_name"
```

### Provider Overrides

Provider override directives allow you to override specific paths in the base template:

```yaml
# Override a specific path
$provider_override: urls.website
https://packages.debian.org/$software_name

# Override a nested path
$provider_override: services.default.enabled
true
```

## Built-in Functions

The template engine includes several built-in functions:

- `lower(s)`: Convert a string to lowercase
- `upper(s)`: Convert a string to uppercase
- `capitalize(s)`: Capitalize a string
- `title(s)`: Convert a string to title case
- `strip(s)`: Remove leading and trailing whitespace
- `len(obj)`: Get the length of an object
- `join(items, sep=",")`: Join a list of items with a separator
- `split(s, sep=",")`: Split a string into a list
- `replace(s, old, new)`: Replace occurrences of `old` with `new` in a string
- `format(s, *args, **kwargs)`: Format a string using Python's format syntax
- `json(obj)`: Convert an object to JSON
- `yaml(obj)`: Convert an object to YAML

## Custom Functions

You can register custom functions to extend the template engine:

```python
# Define a custom function
def reverse(s):
    return s[::-1]

# Register the function
engine.register_function("reverse", reverse)

# Use the function in a template
template = {
    "$function: reverse(software_name)": "reversed_name"
}

# Apply the template
result = engine._process_template(template, {"software_name": "nginx"})
# result["reversed_name"] == "xnign"
```

## Template Directory Structure

The template engine supports both flat and hierarchical template structures:

### Flat Structure
- `defaults.yaml`: Default template for all software
- `providers/*.yaml`: Provider-specific templates (e.g., `apt.yaml`, `brew.yaml`)
- `*.yaml`: Other templates that can be included

### Hierarchical Structure
- `defaults.yaml`: Default template for all software
- `providers/{provider}/default.yaml`: Provider-specific templates in directories
- `providers/{provider}/{os}.yaml`: OS-specific overrides (future enhancement)
- `*.yaml`: Other templates that can be included

The engine automatically detects and loads both structures, with hierarchical templates taking precedence when both exist for the same provider.

## Best Practices

1. **Use defaults.yaml for common patterns**: Put common patterns in the default template
2. **Create provider-specific templates**: Create separate templates for each provider
3. **Use includes for reusable components**: Extract reusable parts into separate templates
4. **Use conditional logic for variations**: Use conditional directives for variations
5. **Use loops for repetitive content**: Use loop directives for repetitive content
6. **Use functions for transformations**: Use function calls for data transformations
7. **Use provider overrides for specific changes**: Use provider overrides for specific changes