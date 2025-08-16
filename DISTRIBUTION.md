# Distribution Guide

This document describes how to build and distribute saidata-gen across different platforms and package formats.

## Overview

saidata-gen supports multiple distribution methods:

1. **PyPI Package** - Python package for pip installation
2. **Docker Container** - Containerized deployment
3. **Standalone Binary** - Self-contained executables
4. **GitHub Releases** - Automated release management

## PyPI Package Distribution

### Building for PyPI

Use the build script to create wheel and source distributions:

```bash
python scripts/build_dist.py
```

This will:
- Clean previous builds
- Install build dependencies
- Create wheel and source distributions
- Validate the distributions

### Manual Upload to PyPI

For testing on Test PyPI:

```bash
python -m twine upload --repository testpypi dist/*
```

For production PyPI:

```bash
python -m twine upload dist/*
```

### Automated PyPI Release

The GitHub Actions workflow automatically publishes to PyPI when a version tag is pushed:

```bash
git tag v0.1.1
git push origin v0.1.1
```

## Docker Container Distribution

### Building Docker Images

Build a single-architecture image:

```bash
python scripts/build_docker.py --test
```

Build multi-architecture image:

```bash
python scripts/build_docker.py --multi-arch --push
```

### Docker Hub Publishing

Images are automatically built and pushed to Docker Hub via GitHub Actions when tags are pushed.

Manual push:

```bash
docker build -t saidata/saidata-gen:latest .
docker push saidata/saidata-gen:latest
```

### Container Registry Options

The tool is published to multiple registries:

- **Docker Hub**: `saidata/saidata-gen:latest`
- **GitHub Container Registry**: `ghcr.io/sai/saidata-gen:latest`

## Standalone Binary Distribution

### Building Binaries

Build for current platform:

```bash
python scripts/build_binary.py --test
```

The binary will be created in the `dist/` directory with platform-specific naming:
- Linux: `saidata-gen-linux-x86_64`
- macOS: `saidata-gen-darwin-x86_64`
- Windows: `saidata-gen-windows-x86_64.exe`

### Cross-Platform Building

For cross-platform builds, use the GitHub Actions workflow which builds for:
- Linux x86_64
- macOS x86_64
- macOS ARM64 (Apple Silicon)
- Windows x86_64

### Binary Features

The standalone binaries include:
- All core functionality
- Embedded Python runtime
- Required dependencies
- Configuration templates
- Schema files

## GitHub Releases

### Automated Releases

GitHub releases are automatically created when version tags are pushed:

1. **Tag Creation**: `git tag v0.1.1 && git push origin v0.1.1`
2. **Automated Build**: GitHub Actions builds all assets
3. **Release Creation**: Release is created with all binaries and Docker images
4. **PyPI Publishing**: Package is published to PyPI

### Release Assets

Each release includes:
- Source code (zip and tar.gz)
- Wheel distribution (.whl)
- Source distribution (.tar.gz)
- Linux binary (x86_64)
- macOS binary (x86_64 and ARM64)
- Windows binary (x86_64)
- Docker images (multi-arch)

### Release Notes

Release notes are automatically generated from `CHANGELOG.md`. Ensure the changelog is updated before creating releases.

## Version Management

### Version Bumping

Use the version management script:

```bash
# Show current version
python scripts/version_manager.py show

# Bump patch version (0.1.0 -> 0.1.1)
python scripts/version_manager.py bump patch

# Bump minor version (0.1.0 -> 0.2.0)
python scripts/version_manager.py bump minor

# Bump major version (0.1.0 -> 1.0.0)
python scripts/version_manager.py bump major

# Set specific version
python scripts/version_manager.py set 1.0.0
```

### Version Synchronization

The version is maintained in:
- `pyproject.toml` - Package metadata
- `saidata_gen/__init__.py` - Python module
- `CHANGELOG.md` - Release history

## Distribution Checklist

Before creating a new release:

### Pre-Release Checklist

- [ ] Update `CHANGELOG.md` with new version and changes
- [ ] Bump version using `scripts/version_manager.py`
- [ ] Run full test suite: `pytest`
- [ ] Build and test PyPI package: `python scripts/build_dist.py`
- [ ] Test Docker configuration: `python scripts/test_docker_config.py`
- [ ] Update documentation if needed
- [ ] Commit all changes

### Release Process

1. **Create and Push Tag**:
   ```bash
   git tag v0.1.1
   git push origin v0.1.1
   ```

2. **Monitor GitHub Actions**:
   - Check that all builds complete successfully
   - Verify PyPI upload
   - Confirm Docker images are pushed
   - Ensure GitHub release is created

3. **Post-Release Verification**:
   ```bash
   # Test PyPI installation
   pip install --upgrade saidata-gen
   saidata-gen --version
   
   # Test Docker image
   docker pull saidata/saidata-gen:latest
   docker run --rm saidata/saidata-gen:latest --version
   
   # Test binary download
   curl -L https://github.com/sai/saidata-gen/releases/latest/download/saidata-gen-linux-x86_64 -o test-binary
   chmod +x test-binary
   ./test-binary --version
   ```

## Platform-Specific Notes

### Linux

- Binaries are built on Ubuntu 20.04 for maximum compatibility
- Supports both x86_64 architecture
- Docker images support both amd64 and arm64

### macOS

- Separate binaries for Intel (x86_64) and Apple Silicon (arm64)
- Binaries are not code-signed (users may need to allow in Security settings)
- Homebrew formula could be added in the future

### Windows

- Single binary for x86_64 architecture
- Built with PyInstaller for maximum compatibility
- May trigger antivirus warnings (false positives)

## Troubleshooting Distribution

### Common Build Issues

1. **PyInstaller Errors**:
   - Ensure all dependencies are properly declared
   - Check for missing data files in spec file
   - Test binary on clean system

2. **Docker Build Failures**:
   - Verify Dockerfile syntax
   - Check for missing files in build context
   - Ensure base image is available

3. **PyPI Upload Issues**:
   - Verify package metadata in `pyproject.toml`
   - Check for duplicate version numbers
   - Ensure proper authentication

### Testing Distributions

Always test distributions before release:

```bash
# Test PyPI package in clean environment
python -m venv test-env
source test-env/bin/activate
pip install saidata-gen
saidata-gen --version
deactivate
rm -rf test-env

# Test Docker image
docker run --rm saidata/saidata-gen:latest --version

# Test binary
./dist/saidata-gen-* --version
```

## Security Considerations

### Supply Chain Security

- All builds are performed in GitHub Actions with auditable logs
- Dependencies are pinned to specific versions
- Docker images use official Python base images
- Binaries are built from source in isolated environments

### Code Signing

Currently, binaries are not code-signed. Consider implementing:
- macOS: Apple Developer ID signing
- Windows: Authenticode signing
- Linux: GPG signing

### Vulnerability Scanning

- Docker images are scanned for vulnerabilities
- Dependencies are monitored for security updates
- Regular security audits of the codebase

## Future Distribution Enhancements

### Package Managers

Consider adding support for:
- **Homebrew**: macOS package manager
- **Chocolatey**: Windows package manager
- **Snap**: Universal Linux packages
- **AppImage**: Portable Linux applications

### Cloud Marketplaces

Potential distribution channels:
- AWS Marketplace
- Google Cloud Marketplace
- Azure Marketplace
- Docker Hub Verified Publisher

### Enterprise Distribution

For enterprise customers:
- Private package repositories
- Custom Docker registries
- Signed binaries
- Support for air-gapped environments