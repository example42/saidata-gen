# Quick Start Guide

Get up and running with saidata-gen in minutes.

## Installation

```bash
pip install saidata-gen
```

## Basic Usage

### 1. Generate Metadata for a Single Package

```bash
saidata-gen generate nginx
```

This generates a structured directory with complete saidata YAML files for nginx by gathering information from multiple package repositories.

### 2. Generate in Specific Directory

```bash
saidata-gen generate nginx --output ./generated/
```

This creates the nginx directory structure under `./generated/nginx/`.

### 3. Use Specific Providers

```bash
saidata-gen generate nginx --providers apt,brew,docker
```

### 4. Validate Generated Files

```bash
saidata-gen validate nginx/defaults.yaml
saidata-gen validate nginx/providers/apt.yaml
```

### 5. Search for Software

```bash
saidata-gen search "web server"
```

## Common Workflows

### Workflow 1: Single Package Generation

```bash
# Generate metadata (creates structured directory)
saidata-gen generate apache2

# Validate the results
saidata-gen validate apache2/defaults.yaml

# View the generated files
cat apache2/defaults.yaml
ls apache2/providers/
```

### Workflow 2: Batch Processing

Create a file `software_list.txt`:
```
nginx
apache2
mysql-server
postgresql
redis
```

Process all packages:
```bash
saidata-gen batch --input software_list.txt --output ./generated/
```

### Workflow 3: AI-Enhanced Generation

```bash
# Set up OpenAI API key
export OPENAI_API_KEY="your-api-key-here"

# Generate with AI enhancement
saidata-gen generate nginx --ai --ai-provider openai
```

### Workflow 4: CI/CD Integration

```bash
# Environment-based configuration
export SAIDATA_GEN_PROVIDERS="apt,brew,winget"
export SAIDATA_GEN_OUTPUT_FORMAT="json"

# Batch process with JSON progress
saidata-gen batch --input packages.txt --progress-format json
```

## Configuration

### Initialize Configuration

```bash
saidata-gen config init
```

This creates `~/.saidata-gen/config.yaml` with default settings.

### Environment Variables

Common environment variables:

```bash
export SAIDATA_GEN_PROVIDERS="apt,brew,winget,npm,pypi"
export SAIDATA_GEN_AI="true"
export SAIDATA_GEN_AI_PROVIDER="openai"
export OPENAI_API_KEY="your-api-key"
export SAIDATA_GEN_CACHE_DIR="~/.saidata-gen/cache"
```

## Directory Structure Output

saidata-gen now generates a structured directory format for each software package:

```
nginx/
├── defaults.yaml              # Software-specific base configuration
└── providers/                 # Provider-specific overrides (only when different from defaults)
    ├── apt.yaml              # Only created if apt config differs from provider_defaults.yaml
    ├── brew.yaml             # Only created if brew config differs from provider_defaults.yaml
    └── docker.yaml           # Only created if docker config differs from provider_defaults.yaml
```

### Benefits of Directory Structure

- **Organized**: Clear separation between base configuration and provider-specific overrides
- **Efficient**: Provider files are only created when they differ from defaults
- **Maintainable**: Easy to understand and modify individual provider configurations
- **Scalable**: Supports complex software packages with many provider variations

## Output Formats

### YAML Output (Default)

```yaml
version: "0.1"
description: "High-performance HTTP server and reverse proxy"
category:
  default: "web-server"
  tags: ["http", "proxy", "load-balancer"]
packages:
  apt:
    name: "nginx"
    version: "1.18.0"
  brew:
    name: "nginx"
    version: "1.25.1"
urls:
  website: "https://nginx.org"
  documentation: "https://nginx.org/en/docs/"
  source: "https://github.com/nginx/nginx"
```

### JSON Output

```bash
saidata-gen generate nginx --format json
```

```json
{
  "version": "0.1",
  "description": "High-performance HTTP server and reverse proxy",
  "category": {
    "default": "web-server",
    "tags": ["http", "proxy", "load-balancer"]
  },
  "packages": {
    "apt": {
      "name": "nginx",
      "version": "1.18.0"
    }
  }
}
```

## Common Options

### Global Options

- `--config, -c`: Configuration file path
- `--verbose, -v`: Enable verbose logging

### Generation Options

- `--providers, -p`: Comma-separated provider list
- `--ai`: Enable AI enhancement
- `--ai-provider`: AI provider (openai, anthropic, local)
- `--format, -f`: Output format (yaml, json)
- `--output, -o`: Output file path
- `--no-validate`: Skip schema validation

### Search Options

- `--providers, -p`: Providers to search
- `--limit, -l`: Maximum results
- `--min-score`: Minimum match score

### Batch Options

- `--input, -i`: Input file with package names
- `--output, -o`: Output directory
- `--max-concurrent`: Parallel processing limit
- `--continue-on-error`: Continue on failures
- `--progress-format`: Progress display format

## Next Steps

- Read the [CLI Reference](cli-reference.md) for complete command documentation
- Check out [Examples](examples/) for advanced use cases
- Learn about [Configuration](configuration.md) options
- Explore [API Reference](api-reference.md) for programmatic usage

## Getting Help

```bash
# General help
saidata-gen --help

# Command-specific help
saidata-gen generate --help
saidata-gen batch --help
saidata-gen validate --help
```

For more help:
- [Troubleshooting Guide](troubleshooting.md)
- [FAQ](faq.md)
- [GitHub Issues](https://github.com/sai/saidata-gen/issues)