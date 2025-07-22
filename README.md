# saidata-gen

A standalone Python tool for generating saidata YAML files for software packages.

## Overview

saidata-gen is a comprehensive Python package that automates the creation, validation, and management of software metadata in YAML format following the saidata-0.1.schema.json specification. The tool integrates traditional package repository scraping with modern AI capabilities including RAG (Retrieval-Augmented Generation) and model fine-tuning for enhanced metadata generation.

## Features

- Generate complete YAML files conforming to saidata-0.1.schema.json
- Fetch metadata from multiple package repositories (apt, dnf, brew, winget, etc.)
- Validate generated files against the official schema
- Search for software packages across multiple repositories
- Batch process multiple software packages
- Configure data sources and providers
- Verify the accuracy of generated metadata
- Integrate with CI/CD pipelines
- Enhance metadata generation with RAG (Retrieval-Augmented Generation)
- Export training data for model fine-tuning

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
# Generate metadata for a single software
saidata-gen generate nginx

# Generate with specific providers
saidata-gen generate nginx --providers apt,brew,docker

# Batch processing
saidata-gen batch --input software_list.txt --output ./generated/

# Search for software
saidata-gen search "web server"

# Validate generated files
saidata-gen validate nginx.yaml
```

### Advanced Usage

```bash
# Fetch repository data
saidata-gen fetch --providers apt,brew --cache-dir ./cache/

# RAG-enhanced generation
saidata-gen generate nginx --use-rag --rag-provider openai

# Export training data
saidata-gen ml export-training-data --format jsonl --output training.jsonl

# Fine-tune model
saidata-gen ml fine-tune --dataset training.jsonl --model-config config.yaml
```

## License

MIT