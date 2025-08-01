# saidata-gen

A standalone Python tool for generating saidata YAML files for software packages.

## Overview

saidata-gen is a comprehensive Python package that automates the creation, validation, and management of software metadata in YAML format following the saidata-0.1.schema.json specification. The tool integrates traditional package repository scraping with modern AI capabilities including RAG (Retrieval-Augmented Generation) and model fine-tuning for enhanced metadata generation.

## Features

- Generate complete YAML files conforming to saidata-0.1.schema.json
- **Structured directory output** with `$software/defaults.yaml` and `$software/providers/$provider.yaml`
- Fetch metadata from multiple package repositories (apt, dnf, brew, winget, etc.)
- **Comprehensive provider defaults** with `provider_defaults.yaml` configuration
- Validate generated files against the official schema
- Search for software packages across multiple repositories
- Batch process multiple software packages
- Configure data sources and providers
- Verify the accuracy of generated metadata
- Integrate with CI/CD pipelines
- Enhance metadata generation with RAG (Retrieval-Augmented Generation)
- Export training data for model fine-tuning
- **Enhanced fetcher reliability** with retry logic and graceful degradation

## Installation

### PyPI Package (Recommended)

```bash
# Basic installation
pip install saidata-gen

# With AI/RAG capabilities
pip install saidata-gen[rag]

# With ML capabilities
pip install saidata-gen[ml]

# With all features
pip install saidata-gen[rag,ml]
```

### Docker Container

```bash
# Pull and run
docker pull saidata/saidata-gen:latest
docker run --rm -v $(pwd):/workspace saidata/saidata-gen:latest generate nginx

# Or use in docker-compose
docker-compose run saidata-gen generate nginx
```

### Standalone Binary

Download the appropriate binary for your platform from the [releases page](https://github.com/sai/saidata-gen/releases):

```bash
# Linux/macOS
curl -L https://github.com/sai/saidata-gen/releases/latest/download/saidata-gen-linux-x86_64 -o saidata-gen
chmod +x saidata-gen
./saidata-gen --help

# Windows
curl -L https://github.com/sai/saidata-gen/releases/latest/download/saidata-gen-windows-x86_64.exe -o saidata-gen.exe
saidata-gen.exe --help
```

### Development Installation

```bash
git clone https://github.com/sai/saidata-gen.git
cd saidata-gen
pip install -e .[dev,rag,ml]
```

## Usage

### Basic Usage

```bash
# Generate metadata for a single software (creates structured directory)
saidata-gen generate nginx

# Generate with specific providers
saidata-gen generate nginx --providers apt,brew,docker

# Generate in specific output directory
saidata-gen generate nginx --output ./generated/

# Batch processing
saidata-gen batch --input software_list.txt --output ./generated/

# Search for software
saidata-gen search "web server"

# Validate generated files
saidata-gen validate nginx/defaults.yaml
```

### Advanced Usage

```bash
# Fetch repository data
saidata-gen fetch --providers apt,brew --cache-dir ./cache/

# AI-enhanced generation
saidata-gen generate nginx --ai --ai-provider openai

# Generate with custom output directory
saidata-gen generate nginx --output /path/to/output/

# Export training data
saidata-gen ml export-training-data --format jsonl --output training.jsonl

# Fine-tune model
saidata-gen ml fine-tune --dataset training.jsonl --model-config config.yaml
```

## Output Structure

saidata-gen now generates a structured directory format for each software package:

```
nginx/
├── defaults.yaml              # Software-specific base configuration
└── providers/                 # Provider-specific overrides (only when different from defaults)
    ├── apt.yaml              # Only created if apt config differs from provider_defaults.yaml
    ├── brew.yaml             # Only created if brew config differs from provider_defaults.yaml
    └── docker.yaml           # Only created if docker config differs from provider_defaults.yaml
```

### Provider Defaults

The system uses a comprehensive `provider_defaults.yaml` file containing default configurations for all 33+ supported providers. This eliminates configuration duplication and ensures consistency across software packages.

Provider-specific files are only created when they differ from the defaults, keeping the output clean and focused.

## License

MIT