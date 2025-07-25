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

This generates a complete saidata YAML file for nginx by gathering information from multiple package repositories.

### 2. Save to File

```bash
saidata-gen generate nginx --output nginx.yaml
```

### 3. Use Specific Providers

```bash
saidata-gen generate nginx --providers apt,brew,docker
```

### 4. Validate Generated Files

```bash
saidata-gen validate nginx.yaml
```

### 5. Search for Software

```bash
saidata-gen search "web server"
```

## Common Workflows

### Workflow 1: Single Package Generation

```bash
# Generate metadata
saidata-gen generate apache2 --output apache2.yaml

# Validate the result
saidata-gen validate apache2.yaml

# View the generated file
cat apache2.yaml
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
saidata-gen generate nginx --use-rag --rag-provider openai
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
export SAIDATA_GEN_USE_RAG="true"
export SAIDATA_GEN_RAG_PROVIDER="openai"
export OPENAI_API_KEY="your-api-key"
export SAIDATA_GEN_CACHE_DIR="~/.saidata-gen/cache"
```

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
- `--use-rag`: Enable AI enhancement
- `--rag-provider`: AI provider (openai, anthropic, local)
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