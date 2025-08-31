# Configuration Guide

This guide covers the configuration system in saidata-gen, including the new provider defaults system and directory structure output.

## Overview

saidata-gen uses a hierarchical configuration system with three main components:

1. **Base Defaults** (`saidata_gen/templates/defaults.yaml`) - Core software configuration templates
2. **Provider Defaults** (`saidata_gen/templates/provider_defaults.yaml`) - Default configurations for all providers
3. **Software-Specific Overrides** - Generated in structured directory format

## Provider Defaults System

### provider_defaults.yaml

The `provider_defaults.yaml` file contains comprehensive default configurations for all 33+ supported providers. This eliminates configuration duplication and ensures consistency across software packages.

#### Structure

```yaml
version: 0.1

# Linux Package Managers
apt:
  services:
    default:
      enabled: true
      status: enabled
  directories:
    config:
      mode: "0644"
  files:
    init:
      path: "/etc/default/{{ software_name }}"
  urls:
    apt: "https://packages.ubuntu.com/search?keywords={{ software_name }}"
  packages:
    default:
      name: "{{ software_name }}"
      version: latest
      install_options: ~

brew:
  services:
    default:
      enabled: true
      status: enabled
  urls:
    brew: "https://brew.sh/formula/{{ software_name }}"
  packages:
    default:
      name: "{{ software_name }}"
      version: latest
      install_options: ~

# ... (all other providers)
```

#### Supported Providers

The provider_defaults.yaml includes configurations for:

**Linux Package Managers:**
- `apt` - Debian, Ubuntu, and derivatives
- `dnf` - Fedora, RHEL 8+, CentOS 8+
- `yum` - RHEL 7, CentOS 7, older Red Hat systems
- `zypper` - openSUSE, SUSE Linux Enterprise
- `pacman` - Arch Linux, Manjaro
- `apk` - Alpine Linux
- `emerge` - Gentoo Linux
- `portage` - Gentoo Linux (alternative interface)
- `xbps` - Void Linux
- `slackpkg` - Slackware Linux
- `opkg` - OpenWrt, embedded systems

**BSD Package Managers:**
- `pkg` - FreeBSD, DragonFly BSD

**macOS Package Managers:**
- `brew` - Homebrew

**Windows Package Managers:**
- `winget` - Windows Package Manager
- `choco` - Chocolatey
- `scoop` - Scoop

**Universal/Cross-Platform:**
- `flatpak` - Universal Linux packages
- `snap` - Universal Linux packages

**Functional/Declarative:**
- `nix` - NixOS and other systems
- `nixpkgs` - Nix package collection
- `guix` - GNU Guix

**Scientific/HPC:**
- `spack` - Scientific computing packages

**Language-Specific:**
- `npm` - Node.js packages
- `pypi` - Python packages
- `cargo` - Rust packages
- `gem` - Ruby packages
- `go` - Go modules
- `composer` - PHP packages
- `nuget` - .NET packages
- `maven` - Java packages
- `gradle` - Java/Kotlin packages

**Container/Orchestration:**
- `docker` - Container platform
- `helm` - Kubernetes package manager

## Directory Structure Output

### Generated Structure

When you run `saidata-gen generate nginx`, it creates:

```
nginx/
├── defaults.yaml              # Software-specific base configuration
└── providers/                 # Provider-specific overrides (only when different from defaults)
    ├── apt.yaml              # Only created if apt config differs from provider_defaults.yaml
    ├── brew.yaml             # Only created if brew config differs from provider_defaults.yaml
    └── docker.yaml           # Only created if docker config differs from provider_defaults.yaml
```

### Configuration Merging

The system merges configurations in this order:

1. **Provider Defaults** - Base configuration from `provider_defaults.yaml`
2. **Software-Specific Overrides** - Values from `nginx/providers/apt.yaml` (if exists)
3. **Runtime Context** - Template variables like `{{ software_name }}`

### When Provider Files Are Created

Provider-specific files are only created when they contain values that differ from the provider defaults. This keeps the output clean and focused on actual customizations.

For example, if nginx's apt configuration is identical to the default apt configuration, no `nginx/providers/apt.yaml` file will be created.

## Configuration Options

### Environment Variables

You can configure saidata-gen behavior using environment variables:

```bash
# Provider selection
export SAIDATA_GEN_PROVIDERS="apt,brew,winget,npm,pypi"

# AI enhancement
export SAIDATA_GEN_AI="true"
export SAIDATA_GEN_AI_PROVIDER="openai"
export OPENAI_API_KEY="your-api-key"

# Output configuration
export SAIDATA_GEN_OUTPUT="/path/to/output"
export SAIDATA_GEN_FORMAT="yaml"

# Validation
export SAIDATA_GEN_NO_VALIDATE="false"

# Logging
export SAIDATA_GEN_LOG_LEVEL="INFO"
export SAIDATA_GEN_VERBOSE="false"

# Caching
export SAIDATA_GEN_CACHE_DIR="~/.saidata-gen/cache"

# Confidence threshold for AI enhancement
export SAIDATA_GEN_CONFIDENCE_THRESHOLD="0.7"
```

### Configuration File

You can create a configuration file at `~/.saidata-gen/config.yaml`:

```yaml
# Default providers to use
providers:
  - apt
  - brew
  - winget
  - npm
  - pypi
  - docker

# AI enhancement settings
ai:
  enabled: false
  provider: openai
  confidence_threshold: 0.7

# Output settings
output:
  format: yaml
  validate: true

# Cache settings
cache:
  directory: ~/.saidata-gen/cache
  ttl: 3600

# Logging settings
logging:
  level: INFO
  verbose: false
```

## Template Variables

The configuration system supports template variables that are substituted at runtime:

### Available Variables

- `{{ software_name }}` - The name of the software being processed
- `{{ provider }}` - The current provider being processed
- `{{ platform }}` - The target platform (linux, macos, windows)
- `{{ architecture }}` - The target architecture (x86_64, arm64, etc.)

### Usage Examples

```yaml
# In provider_defaults.yaml
apt:
  urls:
    apt: "https://packages.ubuntu.com/search?keywords={{ software_name }}"
  files:
    init:
      path: "/etc/default/{{ software_name }}"
  packages:
    default:
      name: "{{ software_name }}"

# In software-specific provider file
# nginx/providers/apt.yaml
version: 0.1
packages:
  default:
    name: "nginx-full"  # Override default {{ software_name }}
urls:
  apt: "https://packages.ubuntu.com/nginx"  # Override default URL
```

## Hierarchical Provider Templates

For complex providers that need platform or version-specific configurations, you can use hierarchical templates:

```
saidata_gen/templates/providers/yum/
├── default.yaml              # Base configuration
├── centos.yaml               # CentOS-specific overrides
├── rhel.yaml                 # RHEL-specific overrides
└── rhel/                     # Version-specific overrides
    ├── 7.yaml               # RHEL 7 specific
    └── 8.yaml               # RHEL 8 specific
```

The system loads configurations in this order:
1. `default.yaml` (required)
2. Platform-specific file (e.g., `centos.yaml`)
3. Version-specific file (e.g., `rhel/8.yaml`)

## Validation and Quality

### Schema Validation

All generated configurations are validated against the saidata-0.1.schema.json schema by default. You can disable validation with:

```bash
saidata-gen generate nginx --no-validate
```

### Configuration Quality Assessment

The system includes quality assessment that:

- Identifies redundant configurations that match defaults
- Suggests removable keys to reduce duplication
- Validates required fields are present
- Checks for common configuration errors

### Quality Metrics

- **Completeness**: Percentage of required fields populated
- **Accuracy**: Validation against schema and known patterns
- **Efficiency**: Ratio of unique vs. default configurations
- **Consistency**: Alignment with provider conventions

## Troubleshooting Configuration Issues

### Common Issues

1. **Provider template not found**
   - Ensure the provider name is correct
   - Check that the provider is supported
   - Verify template files exist

2. **Template variables not substituted**
   - Check variable syntax: `{{ variable_name }}`
   - Ensure required context is provided
   - Verify template processing is enabled

3. **Configuration validation errors**
   - Use `--no-validate` to bypass validation temporarily
   - Check schema requirements
   - Validate JSON/YAML syntax

4. **Redundant configurations**
   - Review provider_defaults.yaml for existing defaults
   - Remove keys that match default values
   - Use configuration quality assessment

### Debug Configuration Loading

Enable debug logging to see configuration processing:

```bash
export SAIDATA_GEN_LOG_LEVEL=DEBUG
saidata-gen generate nginx --verbose
```

This will show:
- Which configuration files are loaded
- Template variable substitutions
- Configuration merging process
- Validation results

## Best Practices

### Provider Configuration

1. **Use defaults when possible** - Only override when necessary
2. **Keep configurations minimal** - Remove redundant keys
3. **Use template variables** - Leverage `{{ software_name }}` etc.
4. **Follow naming conventions** - Use consistent provider names
5. **Document custom configurations** - Add comments for complex overrides

### Directory Structure

1. **Organize by software** - Keep each software in its own directory
2. **Use provider subdirectories** - Separate provider-specific configs
3. **Validate regularly** - Run validation on generated configs
4. **Version control** - Track configuration changes
5. **Review quality metrics** - Monitor configuration efficiency

### Performance

1. **Enable caching** - Use cache for repeated operations
2. **Limit providers** - Only use needed providers
3. **Batch processing** - Process multiple software packages together
4. **Monitor resources** - Watch memory and CPU usage
5. **Optimize templates** - Remove unnecessary complexity

## Migration from Legacy System

If you're migrating from the old system:

1. **Review existing configurations** - Identify custom overrides
2. **Check provider_defaults.yaml** - See what's now included by default
3. **Remove redundant configs** - Delete keys that match defaults
4. **Update file paths** - Use new directory structure
5. **Test thoroughly** - Validate all configurations work correctly

The new system is designed to be backward compatible, but you may need to adjust custom configurations to take advantage of the new provider defaults system.