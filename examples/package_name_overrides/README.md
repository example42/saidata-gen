# Package Name Override Examples

This directory contains examples of how to handle package name overrides when the same software has different package names across different providers.

## Apache HTTP Server Example

Apache HTTP Server demonstrates a common scenario where package names differ:

- **APT (Debian/Ubuntu)**: `apache2`
- **YUM/DNF (RHEL/CentOS/Fedora)**: `httpd`  
- **Homebrew (macOS)**: `httpd`

### Key Points

1. **Software Name**: `apache-httpd` (generic identifier)
2. **Package Names**: Vary by provider as shown above
3. **Override Pattern**: Use `packages.default.name` to specify the actual package name

### Template Structure

```yaml
# Provider specific overrides
version: 0.1

# Override package name when it differs from software name
packages:
  default:
    name: actual-package-name

# Provider-specific URL (use provider name as key)
urls:
  provider_name: "https://provider.example.com/actual-package-name"

# Other provider-specific configurations...
```

### URL Configuration

- **Official Website**: Defined in `defaults.yaml` as `urls.website`
- **Provider URLs**: Use provider name as key (e.g., `urls.apt`, `urls.brew`, `urls.yum`)

```yaml
# defaults.yaml (hypothetical)
urls:
  website: "https://httpd.apache.org"

# apt.yaml
urls:
  apt: "https://packages.ubuntu.com/apache2"

# yum.yaml  
urls:
  yum: "https://centos.pkgs.org/httpd"
```

### When to Use Package Name Overrides

- Package name differs from the software identifier
- Provider uses different naming conventions
- Legacy vs modern package names
- Namespace differences (e.g., `nodejs` vs `node`)

### When NOT to Use Package Name Overrides

- Package name matches the software name exactly
- Only version or installation options differ
- Provider-specific paths or configurations (use other override sections)

### Platform Support

**Important**: The `platforms` key should only be defined in `defaults.yaml` as it indicates which platforms the **software** supports, not which platforms the **provider** supports. Provider platform support is implicit (e.g., APT works on Linux, Winget works on Windows).

This pattern ensures that each provider can correctly identify and install the right package while maintaining a consistent software identifier across the system.