# Saidata Testing Sets

This directory contains curated test sets of software packages designed for testing saidata generation across different providers, operating systems, and software categories. These sets are specifically designed to validate the robustness and accuracy of the saidata-gen tool.

## Test Set Files

### `test_10_basic.txt` - Quick Validation Set
**Purpose**: Fast smoke testing and basic validation
**Size**: 10 packages
**Coverage**: 
- Essential system tools (htop, curl, git)
- Cross-platform applications (vlc, firefox, libreoffice)
- Development essentials (python3, nodejs, docker, nginx)

**Use Cases**:
- Quick functionality tests
- CI/CD pipeline validation
- Initial setup verification
- Performance benchmarking baseline

### `test_50_diverse.txt` - Balanced Coverage Set
**Purpose**: Comprehensive testing across major categories
**Size**: 50 packages
**Coverage**:
- System utilities (10 packages)
- Development tools (10 packages) 
- Web browsers (5 packages)
- Media/graphics (5 packages)
- Productivity (5 packages)
- Databases (5 packages)
- Web servers (5 packages)
- Security tools (5 packages)

**Use Cases**:
- Provider compatibility testing
- Category-specific validation
- Quality assessment across domains
- Template testing for different software types

### `test_100_comprehensive.txt` - Full Spectrum Set
**Purpose**: Maximum diversity and edge case testing
**Size**: 100 packages
**Coverage**:
- 20+ programming languages and runtimes
- Multiple package managers (apt, dnf, brew, npm, pip, cargo, etc.)
- Cross-platform applications
- Enterprise and consumer software
- Open source and proprietary tools
- Legacy and modern applications

**Use Cases**:
- Comprehensive provider testing
- Schema validation across all software types
- Performance testing with larger datasets
- Quality metrics baseline establishment
- Full integration testing

## Provider Coverage

These test sets are designed to test packages from multiple providers:

### Linux Package Managers
- **apt** (Debian/Ubuntu): htop, curl, nginx, postgresql, firefox
- **dnf/yum** (RHEL/Fedora): git, python3, docker, nodejs, vim
- **pacman** (Arch): rust, go, tmux, wireshark, blender
- **zypper** (openSUSE): php, ruby, apache2, mysql, thunderbird
- **pkg** (FreeBSD): perl, lua, caddy, redis, keepassxc

### macOS Package Managers
- **brew**: most development tools, media applications, utilities
- **MacPorts**: alternative versions and specialized tools
- **App Store**: consumer applications where applicable

### Windows Package Managers
- **winget**: modern Windows applications and tools
- **chocolatey**: development tools and utilities
- **scoop**: portable applications and command-line tools

### Language-Specific Managers
- **npm** (Node.js): nodejs, yarn, various web tools
- **pip** (Python): python packages and CLI tools
- **cargo** (Rust): rust toolchain and applications
- **gem** (Ruby): ruby applications and tools
- **composer** (PHP): php applications and frameworks

### Container Registries
- **Docker Hub**: containerized applications
- **Quay.io**: enterprise container images
- **GitHub Container Registry**: open source containers

## Operating System Coverage

### Linux Distributions
- **Ubuntu/Debian**: apt-based packages
- **RHEL/CentOS/Fedora**: dnf/yum packages
- **Arch Linux**: pacman packages
- **openSUSE**: zypper packages
- **Alpine Linux**: apk packages
- **Gentoo**: portage packages

### macOS
- **Homebrew**: primary package manager
- **MacPorts**: alternative package manager
- **App Store**: consumer applications

### Windows
- **Windows Package Manager**: winget packages
- **Chocolatey**: community packages
- **Scoop**: portable applications

### BSD Systems
- **FreeBSD**: pkg packages
- **OpenBSD**: pkg_add packages
- **NetBSD**: pkgsrc packages

## Usage Examples

### Basic Testing
```bash
# Quick smoke test
saidata-gen generate --batch --input-file software_lists/test_sets/test_10_basic.txt

# Test specific provider
saidata-gen generate --provider apt --batch --input-file software_lists/test_sets/test_10_basic.txt
```

### Provider Comparison
```bash
# Test same packages across multiple providers
for provider in apt brew winget; do
    saidata-gen generate --provider $provider --batch --input-file software_lists/test_sets/test_50_diverse.txt
done
```

### Comprehensive Testing
```bash
# Full test suite
saidata-gen generate --batch --input-file software_lists/test_sets/test_100_comprehensive.txt

# Parallel testing across providers
parallel -j 4 saidata-gen generate --provider {} --batch --input-file software_lists/test_sets/test_100_comprehensive.txt ::: apt dnf brew winget
```

### Quality Assessment
```bash
# Generate with quality scoring
saidata-gen generate --batch --quality-check --input-file software_lists/test_sets/test_50_diverse.txt

# Validation against schema
saidata-gen validate --schema saidata-0.1.schema.json --batch --input-file software_lists/test_sets/test_100_comprehensive.txt
```

## Expected Results

### Success Rates by Provider
- **apt/dnf**: 90-95% success rate (mature ecosystems)
- **brew**: 85-90% success rate (good metadata)
- **winget**: 70-80% success rate (newer ecosystem)
- **npm/pip**: 60-70% success rate (variable quality)

### Common Issues to Test
1. **Package name variations**: nodejs vs node, python3 vs python
2. **Missing packages**: provider-specific availability
3. **Metadata quality**: description completeness, categorization
4. **Version handling**: latest vs specific versions
5. **Dependencies**: complex dependency trees
6. **Licensing**: various license formats and detection

### Performance Benchmarks
- **10 packages**: < 30 seconds
- **50 packages**: < 2 minutes  
- **100 packages**: < 5 minutes

## Validation Criteria

### Metadata Completeness
- Package name and version
- Description and summary
- License information
- Dependencies (where available)
- Homepage/repository URLs
- Maintainer information

### Schema Compliance
- Valid JSON structure
- Required fields present
- Correct data types
- Enum values within allowed ranges
- URL format validation

### Quality Metrics
- Description length and clarity
- License detection accuracy
- Category assignment correctness
- Dependency resolution completeness
- URL accessibility

## Continuous Integration

These test sets are ideal for CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Test Basic Set
  run: saidata-gen generate --batch --input-file software_lists/test_sets/test_10_basic.txt

- name: Test Provider Coverage
  run: |
    for provider in apt brew winget; do
      saidata-gen generate --provider $provider --batch --input-file software_lists/test_sets/test_50_diverse.txt
    done

- name: Comprehensive Test
  run: saidata-gen generate --batch --quality-check --input-file software_lists/test_sets/test_100_comprehensive.txt
```

## Contributing

When adding packages to test sets:
1. **Maintain diversity**: Include packages from different categories
2. **Test edge cases**: Add packages with complex metadata
3. **Provider balance**: Ensure good coverage across package managers
4. **Update regularly**: Keep packages current and relevant
5. **Document rationale**: Explain why specific packages were chosen

These test sets provide a solid foundation for validating saidata-gen functionality across the diverse landscape of software package management systems.