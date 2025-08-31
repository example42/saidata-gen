# Installation Guide

This guide covers various ways to install and upgrade saidata-gen.

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

## Installation Methods

### 1. PyPI Installation (Recommended)

Install the latest stable version from PyPI:

```bash
pip install saidata-gen
```

#### Optional Dependencies

Install with RAG capabilities for AI-enhanced metadata generation:

```bash
pip install saidata-gen[rag]
```

Install with ML capabilities for training data export and model fine-tuning:

```bash
pip install saidata-gen[ml]
```

Install with all optional dependencies:

```bash
pip install saidata-gen[rag,ml]
```

### 2. Development Installation

For development or to get the latest features:

```bash
git clone https://github.com/sai/saidata-gen.git
cd saidata-gen
pip install -e .[dev]
```

### 3. Docker Installation

Run saidata-gen in a Docker container:

```bash
docker pull saidata/saidata-gen:latest
docker run --rm -v $(pwd):/workspace saidata/saidata-gen:latest generate nginx
```

### 4. Standalone Binary

Download the standalone binary for your platform from the [releases page](https://github.com/sai/saidata-gen/releases):

```bash
# Linux/macOS
curl -L https://github.com/sai/saidata-gen/releases/latest/download/saidata-gen-linux -o saidata-gen
chmod +x saidata-gen
./saidata-gen --help

# Windows
curl -L https://github.com/sai/saidata-gen/releases/latest/download/saidata-gen-windows.exe -o saidata-gen.exe
saidata-gen.exe --help
```

## Verification

Verify your installation:

```bash
saidata-gen --version
saidata-gen --help
```

## Configuration

After installation, you may want to configure saidata-gen:

```bash
# Create default configuration
saidata-gen config init

# Set up repository caches
saidata-gen fetch --providers apt,brew,winget

# Configure RAG (if installed with RAG support)
export OPENAI_API_KEY="your-api-key"
saidata-gen config set rag.provider openai
```

## Upgrading

### Upgrade from PyPI

```bash
pip install --upgrade saidata-gen
```

### Upgrade with Optional Dependencies

```bash
pip install --upgrade saidata-gen[rag,ml]
```

### Upgrade Development Installation

```bash
cd saidata-gen
git pull origin main
pip install -e .[dev]
```

## Uninstallation

To remove saidata-gen:

```bash
pip uninstall saidata-gen
```

Clean up configuration and cache files:

```bash
rm -rf ~/.saidata-gen/
```

## Troubleshooting

### Common Issues

#### Permission Errors

If you encounter permission errors during installation:

```bash
pip install --user saidata-gen
```

#### Python Version Issues

Ensure you're using Python 3.8 or higher:

```bash
python --version
# or
python3 --version
```

#### Missing Dependencies

If you encounter import errors, try reinstalling with all dependencies:

```bash
pip uninstall saidata-gen
pip install saidata-gen[rag,ml]
```

#### Network Issues

If you're behind a corporate firewall:

```bash
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org saidata-gen
```

### Getting Help

If you encounter issues:

1. Check the [troubleshooting guide](troubleshooting.md)
2. Search existing [issues](https://github.com/sai/saidata-gen/issues)
3. Create a new issue with:
   - Your operating system
   - Python version
   - Installation method used
   - Complete error message

## Platform-Specific Notes

### Windows

- Use PowerShell or Command Prompt
- Consider using Windows Subsystem for Linux (WSL) for better compatibility
- Some package managers may require additional setup

### macOS

- Homebrew integration works out of the box
- Consider using pyenv for Python version management

### Linux

- Most package managers are supported natively
- Ensure you have the necessary permissions for system package queries
- Some distributions may require additional packages for full functionality

## Next Steps

After installation, see:

- [Quick Start Guide](quickstart.md)
- [Configuration Guide](configuration.md)
- [CLI Reference](cli-reference.md)
- [API Reference](api-reference.md)