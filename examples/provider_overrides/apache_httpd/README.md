# Apache HTTP Server Provider Override Example

This example demonstrates real-world provider override configurations for Apache HTTP Server, showing how package names and configurations differ across different package managers and operating systems.

## The Challenge

Apache HTTP Server has different package names across providers:
- **APT (Debian/Ubuntu):** `apache2`
- **YUM/DNF (RHEL/CentOS/Fedora):** `httpd`
- **Homebrew:** `httpd`
- **Winget:** `Apache.HTTPServer`
- **Chocolatey:** `apache-httpd`

This is a perfect example of why override-only templates are valuable - each provider only needs to specify what's different.

## Provider Configurations

### Default Template (Base Configuration)

```yaml
# defaults.yaml (simplified for this example)
version: 0.1
packages:
  default:
    name: "{{ software_name }}"  # Would be "apache-httpd"
    version: latest
services:
  default:
    name: "{{ software_name }}"  # Would be "apache-httpd"
directories:
  config:
    path: "/etc/{{ software_name }}"
    owner: root
    group: root
    mode: "0755"
  data:
    path: "/var/www"
    owner: www-data
    group: www-data
    mode: "0755"
ports:
  http:
    number: 80
    protocol: tcp
  https:
    number: 443
    protocol: tcp
platforms:
  - linux
  - windows
  - macos
```

### APT Provider Override

```yaml
# providers/apt.yaml
version: 0.1
packages:
  default:
    name: apache2  # Different from default "apache-httpd"
services:
  default:
    name: apache2  # Service name also differs
directories:
  config:
    path: /etc/apache2  # APT-specific path
  modules:
    path: /etc/apache2/mods-available
    owner: root
    group: root
    mode: "0644"
```

### YUM/DNF Provider Override

```yaml
# providers/yum.yaml (also used by DNF)
version: 0.1
packages:
  default:
    name: httpd  # Different from default "apache-httpd"
services:
  default:
    name: httpd  # Service name also differs
directories:
  config:
    path: /etc/httpd  # RHEL/CentOS-specific path
  modules:
    path: /etc/httpd/conf.modules.d
    owner: root
    group: root
    mode: "0644"
```

### Homebrew Provider Override

```yaml
# providers/brew.yaml
version: 0.1
packages:
  default:
    name: httpd  # Different from default "apache-httpd"
directories:
  config:
    path: /usr/local/etc/httpd  # Homebrew-specific path
  data:
    path: /usr/local/var/www
    owner: "{{ ansible_user | default('www') }}"
    group: staff
    mode: "0755"
```

### Winget Provider Override

```yaml
# providers/winget.yaml
version: 0.1
packages:
  default:
    name: Apache.HTTPServer  # Windows-specific naming
services:
  default:
    name: Apache2.4  # Windows service name
directories:
  config:
    path: "C:\\Apache24\\conf"
    owner: Administrators
    group: Administrators
    mode: "0755"
  data:
    path: "C:\\Apache24\\htdocs"
    owner: Administrators
    group: Administrators
    mode: "0755"
```

### Chocolatey Provider Override

```yaml
# providers/choco.yaml
version: 0.1
packages:
  default:
    name: apache-httpd  # Matches our software name, but explicit for clarity
# Most other settings can use defaults for Windows
```

### Unsupported Provider Example

```yaml
# providers/snap.yaml
version: 0.1
supported: false  # Apache HTTP Server not available via Snap
```

## Hierarchical Example: YUM with OS-Specific Overrides

For more complex scenarios, you can use hierarchical templates:

```
providers/yum/
├── default.yaml      # Base YUM configuration
├── centos.yaml       # CentOS-specific overrides
├── rhel.yaml         # RHEL-specific overrides
└── rhel/             # RHEL version-specific
    ├── 7.yaml        # RHEL 7 specific
    └── 8.yaml        # RHEL 8 specific
```

### YUM Default

```yaml
# providers/yum/default.yaml
version: 0.1
packages:
  default:
    name: httpd
services:
  default:
    name: httpd
directories:
  config:
    path: /etc/httpd
```

### RHEL-Specific Override

```yaml
# providers/yum/rhel.yaml
version: 0.1
packages:
  default:
    name: httpd
    # RHEL might have additional package requirements
  additional:
    - httpd-tools
    - mod_ssl
```

### RHEL 8-Specific Override

```yaml
# providers/yum/rhel/8.yaml
version: 0.1
services:
  default:
    manager: systemd  # Explicit systemd for RHEL 8
    enabled: true
    state: started
```

## Usage Example

```python
#!/usr/bin/env python3
"""
Apache HTTP Server provider override example.
"""

from saidata_gen.generator.templates import TemplateEngine
from saidata_gen.validation.config_validator import ConfigurationValidator

def demonstrate_apache_overrides():
    """Demonstrate Apache HTTP Server provider overrides."""
    
    template_engine = TemplateEngine()
    validator = ConfigurationValidator()
    
    software_name = "apache-httpd"
    
    # Test different providers
    providers = ["apt", "yum", "brew", "winget", "choco", "snap"]
    
    print(f"=== Apache HTTP Server Provider Overrides ===\n")
    
    for provider in providers:
        print(f"Provider: {provider}")
        print("-" * 40)
        
        # Generate override configuration
        try:
            override_config = template_engine.apply_provider_overrides_only(
                software_name=software_name,
                provider=provider,
                repository_data={"name": "httpd", "version": "2.4.41"}
            )
            
            print("Override Configuration:")
            for key, value in override_config.items():
                if key == "packages" and isinstance(value, dict):
                    pkg_name = value.get("default", {}).get("name", "N/A")
                    print(f"  Package name: {pkg_name}")
                elif key == "services" and isinstance(value, dict):
                    svc_name = value.get("default", {}).get("name", "N/A")
                    print(f"  Service name: {svc_name}")
                elif key == "supported":
                    print(f"  Supported: {value}")
            
            # Validate configuration
            validation_result = validator.validate_provider_override(
                provider, override_config
            )
            print(f"  Quality Score: {validation_result.quality_score:.2f}")
            
            if validation_result.redundant_keys:
                print(f"  Redundant keys: {validation_result.redundant_keys}")
            
        except Exception as e:
            print(f"  Error: {e}")
        
        print()

if __name__ == "__main__":
    demonstrate_apache_overrides()
```

## Key Observations

1. **Package Names Vary Significantly:**
   - APT: `apache2`
   - YUM/DNF: `httpd`
   - Winget: `Apache.HTTPServer`

2. **Service Names Follow Package Names:**
   - Usually match the package name
   - Windows has specific service naming

3. **Directory Structures Differ:**
   - APT: `/etc/apache2/`
   - YUM: `/etc/httpd/`
   - Homebrew: `/usr/local/etc/httpd/`
   - Windows: `C:\Apache24\conf\`

4. **Override-Only Templates Are Clean:**
   - Each provider only specifies what's different
   - Unsupported providers use `supported: false`
   - Common settings inherit from defaults

5. **Hierarchical Templates Handle Complexity:**
   - OS-specific differences within the same package manager
   - Version-specific configurations
   - Maintains clean separation of concerns

This example shows why the override-only system is valuable for real-world software with complex cross-platform differences.