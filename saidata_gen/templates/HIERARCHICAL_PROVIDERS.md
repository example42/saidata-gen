# Hierarchical Provider Templates

## Overview

The hierarchical provider template system addresses the challenge of handling OS/distro/version-specific configurations within the same provider. Instead of having one monolithic template per provider, the system now supports a hierarchical structure that allows for precise configuration management across different environments.

## Problem Solved

Previously, a single `yum.yaml` file had to handle all YUM-based distributions (RHEL, CentOS, AlmaLinux, Rocky Linux), leading to:
- Generic configurations that didn't reflect real-world differences
- Incorrect URLs and package names for specific distributions
- Difficulty maintaining version-specific configurations
- No way to handle distribution-specific package repositories

## Solution: Hierarchical Templates

### Directory Structure

```
saidata_gen/templates/providers/
├── yum/
│   ├── default.yaml          # Base YUM configuration
│   ├── rhel.yaml            # RHEL-specific overrides
│   ├── centos.yaml          # CentOS-specific overrides
│   ├── almalinux.yaml       # AlmaLinux-specific overrides
│   ├── rocky.yaml           # Rocky Linux-specific overrides
│   └── rhel/                # Version-specific configurations
│       ├── 7.yaml           # RHEL 7-specific
│       ├── 8.yaml           # RHEL 8-specific
│       └── 9.yaml           # RHEL 9-specific
├── apt/
│   ├── default.yaml          # Base APT configuration
│   ├── ubuntu.yaml          # Ubuntu-specific overrides
│   ├── debian.yaml          # Debian-specific overrides
│   └── ubuntu/              # Version-specific configurations
│       ├── 20.04.yaml       # Ubuntu 20.04 LTS
│       ├── 22.04.yaml       # Ubuntu 22.04 LTS
│       └── 24.04.yaml       # Ubuntu 24.04 LTS
├── brew/
│   ├── default.yaml          # Base Homebrew configuration
│   ├── macos.yaml           # macOS-specific paths
│   └── linux.yaml           # Linux-specific paths
```

### Configuration Merging Hierarchy

Templates are merged in the following order (later overrides earlier):

1. **System Defaults** (`defaults.yaml`)
2. **Provider Base** (`provider/default.yaml`)
3. **OS/Distro Specific** (`provider/distro.yaml`)
4. **Version Specific** (`provider/distro/version.yaml`)

### Example: Apache HTTP Server on RHEL 8

For Apache HTTP Server on RHEL 8, the system would merge:

1. `defaults.yaml` (system-wide defaults)
2. `yum/default.yaml` (YUM base configuration)
3. `yum/rhel.yaml` (RHEL-specific overrides)
4. `yum/rhel/8.yaml` (RHEL 8-specific overrides)

## Real-World Examples

### YUM Provider Hierarchy

#### Base Configuration (`yum/default.yaml`)
```yaml
version: 0.1
services:
  default:
    enabled: true
    status: enabled
directories:
  config:
    mode: "0644"
files:
  init:
    path: "/etc/sysconfig/{{ software_name }}"
```

#### RHEL-Specific (`yum/rhel.yaml`)
```yaml
version: 0.1
packages:
  default:
    name: httpd  # Apache package name on RHEL
urls:
  yum: "https://access.redhat.com/solutions/{{ software_name }}"
files:
  repo:
    path: "/etc/yum.repos.d/{{ software_name }}.repo"
```

#### CentOS-Specific (`yum/centos.yaml`)
```yaml
version: 0.1
packages:
  default:
    name: httpd  # Apache package name on CentOS
urls:
  yum: "https://centos.pkgs.org/{{ software_name }}"
files:
  repo:
    path: "/etc/yum.repos.d/{{ software_name }}.repo"
```

#### RHEL 7-Specific (`yum/rhel/7.yaml`)
```yaml
version: 0.1
files:
  init_script:
    path: "/etc/init.d/{{ software_name }}"  # RHEL 7 uses init.d
    mode: "0755"
urls:
  yum: "https://access.redhat.com/solutions/rhel7/{{ software_name }}"
```

### APT Provider Hierarchy

#### Ubuntu-Specific (`apt/ubuntu.yaml`)
```yaml
version: 0.1
packages:
  default:
    name: apache2  # Apache package name on Ubuntu
urls:
  apt: "https://packages.ubuntu.com/{{ software_name }}"
```

#### Ubuntu 22.04-Specific (`apt/ubuntu/22.04.yaml`)
```yaml
version: 0.1
urls:
  apt: "https://packages.ubuntu.com/jammy/{{ software_name }}"
```

## Benefits

### 1. **Accuracy**
- Correct package names per distribution
- Accurate repository URLs
- Proper file paths and configurations

### 2. **Maintainability**
- Changes isolated to specific files
- Clear separation of concerns
- Easy to add new distributions or versions

### 3. **Scalability**
- Simple to add new OS/distro support
- Version-specific configurations handled cleanly
- No explosion of monolithic files

### 4. **Flexibility**
- Can handle any level of specificity needed
- Supports both distro and version differences
- Maintains override-only pattern

## Implementation Guidelines

### Adding a New Distribution

1. Create distro-specific file: `provider/newdistro.yaml`
2. Include only configurations that differ from the provider base
3. Follow the override-only pattern

### Adding Version-Specific Configuration

1. Create subdirectory: `provider/distro/`
2. Add version files: `provider/distro/version.yaml`
3. Include only version-specific overrides

### Template Content Rules

- **Base templates** (`default.yaml`): Common provider configurations
- **Distro templates**: Only distro-specific differences
- **Version templates**: Only version-specific differences
- **All templates**: Follow override-only pattern

## Migration from Flat Structure

The system supports both flat and hierarchical structures during transition:

1. **Legacy flat files** (e.g., `yum.yaml`) are still supported
2. **Hierarchical files** take precedence when both exist
3. **Analysis tools** work with both structures
4. **Gradual migration** is possible

## Analysis and Validation

The updated analysis script handles hierarchical templates:

```bash
python scripts/analyze_provider_templates.py
```

Output shows all templates in the hierarchy:
- `yum_default`
- `yum_rhel`
- `yum_rhel_8`
- `apt_ubuntu_22.04`

## Future Enhancements

### Planned Features

1. **Automatic OS Detection**: Runtime detection of target OS/distro/version
2. **Template Validation**: Ensure hierarchical consistency
3. **Merge Visualization**: Tools to show final merged configuration
4. **Template Generation**: Automated creation of distro-specific templates

### Extensibility

The system is designed to handle:
- New package managers
- New operating systems
- New distribution families
- Complex version dependencies

## Conclusion

The hierarchical provider template system transforms saidata generation from a one-size-fits-all approach to a precise, maintainable, and scalable solution that accurately reflects the diversity of modern software deployment environments.