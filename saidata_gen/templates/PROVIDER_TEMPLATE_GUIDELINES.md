# Provider Template Guidelines

## Overview

Provider templates should contain **only provider-specific overrides** that differ from the defaults. The system now supports hierarchical provider templates to handle OS/distro/version-specific configurations.

### Template Structure

```
saidata_gen/templates/providers/
├── yum/
│   ├── default.yaml          # Base YUM configuration
│   ├── rhel.yaml            # RHEL-specific overrides
│   ├── centos.yaml          # CentOS-specific overrides
│   ├── almalinux.yaml       # AlmaLinux-specific overrides
│   ├── rocky.yaml           # Rocky Linux-specific overrides
│   └── rhel/                # Version-specific overrides
│       ├── 7.yaml           # RHEL 7-specific
│       └── 8.yaml           # RHEL 8-specific
├── apt/
│   ├── default.yaml          # Base APT configuration
│   ├── ubuntu.yaml          # Ubuntu-specific overrides
│   ├── debian.yaml          # Debian-specific overrides
│   └── ubuntu/              # Version-specific overrides
│       ├── 20.04.yaml       # Ubuntu 20.04-specific
│       └── 22.04.yaml       # Ubuntu 22.04-specific
```

### Configuration Merging

Templates are merged in hierarchical order:
1. **defaults.yaml** (base system defaults)
2. **provider/default.yaml** (provider base configuration)
3. **provider/distro.yaml** (distro-specific overrides)
4. **provider/distro/version.yaml** (version-specific overrides)

For detailed information about the hierarchical system, see [HIERARCHICAL_PROVIDERS.md](HIERARCHICAL_PROVIDERS.md).

## Key Principles

### 1. Override-Only Structure
- **DO NOT** duplicate configurations that match `defaults.yaml`
- **DO** include only settings that are different for this provider
- **DO** include the `version: 0.1` field in all provider templates

### 2. Package Name Overrides
Package names often differ between providers for the same software:

```yaml
# Examples of when to override package names:

# apt.yaml - Apache HTTP Server
packages:
  default:
    name: apache2

# yum.yaml - Apache HTTP Server  
packages:
  default:
    name: httpd

# apt.yaml - Node.js
packages:
  default:
    name: nodejs

# brew.yaml - Node.js
packages:
  default:
    name: node
```

### 3. When to Include Package Configuration

**Include `packages` section when:**
- Package name differs from `{{ software_name }}` (always valid override)
- Special naming conventions (e.g., Scoop's `bucket:package` format)
- Provider-specific versioning or installation options that differ from defaults
- Provider-specific install_options that differ from defaults

**Omit `packages` section when:**
- Package name matches `{{ software_name }}` AND all other package configs match defaults
- Version is `latest` (default) AND no other overrides needed
- No special installation options that differ from defaults

**Note:** Package name overrides (`packages.default.name`) are always considered valid provider-specific configurations, even if they appear to match the software name, because different providers often use different naming conventions for the same software.

### 4. Provider-Specific Paths and Configurations

Each provider should override paths, permissions, and configurations that are specific to that platform:

```yaml
# brew.yaml - Homebrew-specific paths
directories:
  config:
    path: "/opt/homebrew/etc/{{ software_name }}"
    group: admin

# winget.yaml - Windows-specific paths
directories:
  config:
    path: "C:\\ProgramData\\{{ software_name }}"
    owner: Administrator
    group: Administrators
```

### 5. URL Configuration Guidelines

**Official Website URL**: Should be defined in `defaults.yaml` only
- `urls.website` = Official software website (same for all providers)

**Provider-Specific URLs**: Use provider name as key
- `urls.apt` = APT package repository URL
- `urls.brew` = Homebrew formula URL  
- `urls.winget` = Winget package URL
- `urls.choco` = Chocolatey package URL
- `urls.yum` = YUM/CentOS package URL
- `urls.zypper` = Zypper/openSUSE package URL
- `urls.scoop` = Scoop package URL

```yaml
# defaults.yaml
urls:
  website: "https://example-software.org"

# brew.yaml
urls:
  brew: "https://brew.sh/formula/{{ software_name }}"

# apt.yaml (only if there's a specific APT repository URL)
urls:
  apt: "https://packages.ubuntu.com/{{ software_name }}"

# yum.yaml
urls:
  yum: "https://centos.pkgs.org/{{ software_name }}"
```

### 6. Platform Support Configuration

**Platforms**: Should be defined in `defaults.yaml` only
- `platforms` = Array of platforms the **software** supports (not the provider)
- This is a property of the software itself, not the provider
- Examples: `["linux", "windows", "macos"]`, `["linux"]`, `["windows"]`

```yaml
# defaults.yaml - Software platform support
platforms:
  - linux
  - windows
  - macos

# Provider templates should NOT include platforms
# The provider's availability on platforms is implicit from the provider type
```

**Important**: Do not include `platforms` in provider templates. The fact that APT works on Linux or Winget works on Windows is implicit from the provider type.

## Template Structure

### Base Provider Template (`provider/default.yaml`)
```yaml
# Provider base configuration - common across all OS/distros
version: 0.1

# Common provider-specific service configurations
services:
  default:
    enabled: true  # If different from default
    status: enabled

# Common provider-specific directory configurations
directories:
  config:
    mode: "0644"  # If different from default

# Common provider-specific file configurations
files:
  init:
    path: "/provider/specific/init/file"
```

### Distro-Specific Template (`provider/distro.yaml`)
```yaml
# Distro-specific overrides
version: 0.1

# Only include if package name differs from software_name
packages:
  default:
    name: "distro-specific-package-name"

# Distro-specific URLs (use provider name as key)
urls:
  provider_name: "https://distro.example.com/{{ software_name }}"

# Distro-specific file configurations
files:
  repo:
    path: "/distro/specific/repo/file"
```

### Version-Specific Template (`provider/distro/version.yaml`)
```yaml
# Version-specific overrides
version: 0.1

# Version-specific URLs
urls:
  provider_name: "https://distro.example.com/version/{{ software_name }}"

# Version-specific service management
files:
  service:
    path: "/version/specific/service/file"
```

## Common Mistakes to Avoid

❌ **Don't include redundant configurations:**
```yaml
# BAD - These match defaults
packages:
  provider_name:  # Provider name should be inferred from filename
    name: "{{ software_name }}"  # This is the default
    version: latest  # This is the default
    install_options: null  # This is the default
```

✅ **Do include only necessary overrides:**
```yaml
# GOOD - Only provider-specific differences
packages:
  default:
    name: "apache2"  # Different from software_name

directories:
  config:
    mode: "0644"  # Different from default mode
```

## Validation

Use the analysis script to verify templates:
```bash
python scripts/analyze_provider_templates.py
```

This script will identify:
- Redundant configurations that can be removed
- Provider-specific configurations that should be kept
- Overall redundancy percentage

Target: **0% redundancy** while maintaining all necessary provider-specific overrides.