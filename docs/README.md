# Saidata Generator Documentation

Welcome to the comprehensive documentation for saidata-gen, a standalone Python tool for generating, validating, and managing software metadata in YAML format following the saidata-0.1.schema.json specification.

## Table of Contents

- [Installation](installation.md)
- [Quick Start](quickstart.md)
- [Configuration Guide](configuration.md) - **New comprehensive configuration documentation**
- [CLI Reference](cli-reference.md)
- [API Reference](api-reference.md)
- [Troubleshooting](troubleshooting.md) - **Enhanced with fetcher reliability and new features**
- [Examples](examples/)
- [FAQ](faq.md)

## Overview

Saidata-gen is a comprehensive tool that automates the creation of software metadata files by:

- **Structured Directory Output**: Generates organized `$software/defaults.yaml` and `$software/providers/$provider.yaml` structure
- **Provider Defaults System**: Uses comprehensive `provider_defaults.yaml` for all 33+ supported providers
- Fetching data from multiple package repositories (apt, dnf, brew, winget, npm, pypi, cargo, etc.)
- **Enhanced Fetcher Reliability**: Robust error handling, retry logic, and graceful degradation
- Generating comprehensive YAML metadata following the saidata-0.1.schema.json specification
- Validating generated files against the official schema
- Supporting AI-enhanced metadata generation through RAG integration
- Providing batch processing capabilities for large software inventories
- Offering ML training data export and model fine-tuning features

## Key Features

- **Structured Directory Output**: Organized `$software/defaults.yaml` and `$software/providers/$provider.yaml` format
- **Provider Defaults System**: Comprehensive `provider_defaults.yaml` eliminates configuration duplication
- **Enhanced Fetcher Reliability**: Robust networking with retry logic, SSL handling, and graceful degradation
- **Multi-source Data Aggregation**: Combines information from 33+ package managers and repositories
- **Schema Validation**: Ensures compliance with saidata-0.1.schema.json
- **RAG Integration**: AI-enhanced metadata generation with OpenAI, Anthropic, and local models
- **Batch Processing**: Efficient processing of large software lists with parallel execution
- **Flexible Output**: Supports YAML and JSON output formats
- **Intelligent Caching**: Performance optimization for repeated operations
- **CI/CD Integration**: Environment variable configuration and appropriate exit codes
- **Extensible Architecture**: Plugin system for custom providers and templates

## Getting Started

1. **Installation**: `pip install saidata-gen`
2. **Basic Usage**: `saidata-gen generate nginx` (creates structured directory)
3. **Validation**: `saidata-gen validate nginx/defaults.yaml`
4. **Search**: `saidata-gen search "web server"`

### New Directory Structure

saidata-gen now generates organized directory structures:

```
nginx/
├── defaults.yaml              # Software-specific base configuration
└── providers/                 # Provider-specific overrides (only when different from defaults)
    ├── apt.yaml              # Only created if apt config differs from provider_defaults.yaml
    └── brew.yaml             # Only created if brew config differs from provider_defaults.yaml
```

For detailed instructions, see the [Quick Start Guide](quickstart.md).

## Support

- **Documentation**: This comprehensive guide
- **Issues**: [GitHub Issues](https://github.com/sai/saidata-gen/issues)
- **Discussions**: [GitHub Discussions](https://github.com/sai/saidata-gen/discussions)