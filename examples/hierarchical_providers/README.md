# Hierarchical Provider Templates Example

This directory demonstrates the new hierarchical provider template structure that handles OS/distro/version-specific configurations.

## Structure Overview

```
apache-httpd/providers/
├── yum/
│   ├── default.yaml          # Base YUM configuration
│   ├── rhel.yaml            # RHEL-specific overrides
│   └── centos.yaml          # CentOS-specific overrides
└── apt/
    ├── default.yaml          # Base APT configuration
    └── ubuntu.yaml          # Ubuntu-specific overrides
```

## Configuration Merging

For a specific software package on a specific OS/distro, configurations are merged in this order:

1. **System defaults** (`defaults.yaml`)
2. **Provider base** (`yum/default.yaml`)
3. **Distro-specific** (`yum/rhel.yaml`)
4. **Version-specific** (`yum/rhel/8.yaml`) - if exists

## Example: Apache HTTP Server on RHEL

### Final merged configuration would include:
- Base system defaults
- YUM provider defaults (service enabled, config mode, init file)
- RHEL-specific overrides (package name 'httpd', RHEL URL, repo file)

### Key differences handled:
- **Package names**: `httpd` on RHEL/CentOS vs `apache2` on Ubuntu
- **URLs**: Different package repository URLs per distro
- **File paths**: Different repository configuration paths
- **Service management**: Distro-specific service configurations

## Benefits

1. **Eliminates redundancy**: Common provider settings in base files
2. **Handles variations**: Distro/version-specific differences cleanly separated
3. **Maintainable**: Changes isolated to appropriate files
4. **Scalable**: Easy to add new distros or versions
5. **Clear hierarchy**: Obvious override precedence

## Usage

When generating saidata, the system detects the target OS/distro/version and merges the appropriate template hierarchy to create the final configuration.