# Saidata Generator Documentation

Welcome to the comprehensive documentation for saidata-gen, a standalone Python tool for generating, validating, and managing software metadata in YAML format following the saidata-0.1.schema.json specification.

## Table of Contents

- [Installation](installation.md)
- [Quick Start](quickstart.md)
- [CLI Reference](cli-reference.md)
- [API Reference](api-reference.md)
- [Configuration](configuration.md)
- [Examples](examples/)
- [Troubleshooting](troubleshooting.md)
- [FAQ](faq.md)

## Overview

Saidata-gen is a comprehensive tool that automates the creation of software metadata files by:

- Fetching data from multiple package repositories (apt, dnf, brew, winget, npm, pypi, cargo, etc.)
- Generating comprehensive YAML metadata following the saidata-0.1.schema.json specification
- Validating generated files against the official schema
- Supporting AI-enhanced metadata generation through RAG integration
- Providing batch processing capabilities for large software inventories
- Offering ML training data export and model fine-tuning features

## Key Features

- **Multi-source Data Aggregation**: Combines information from 25+ package managers and repositories
- **Schema Validation**: Ensures compliance with saidata-0.1.schema.json
- **RAG Integration**: AI-enhanced metadata generation with OpenAI, Anthropic, and local models
- **Batch Processing**: Efficient processing of large software lists with parallel execution
- **Flexible Output**: Supports YAML and JSON output formats
- **Caching**: Intelligent caching system for improved performance
- **CI/CD Integration**: Environment variable configuration and appropriate exit codes
- **Extensible**: Plugin architecture for custom providers and templates

## Getting Started

1. **Installation**: `pip install saidata-gen`
2. **Basic Usage**: `saidata-gen generate nginx`
3. **Validation**: `saidata-gen validate nginx.yaml`
4. **Search**: `saidata-gen search "web server"`

For detailed instructions, see the [Quick Start Guide](quickstart.md).

## Support

- **Documentation**: This comprehensive guide
- **Issues**: [GitHub Issues](https://github.com/sai/saidata-gen/issues)
- **Discussions**: [GitHub Discussions](https://github.com/sai/saidata-gen/discussions)