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

```bash
pip install saidata-gen
```

For RAG capabilities:

```bash
pip install saidata-gen[rag]
```

For ML capabilities:

```bash
pip install saidata-gen[ml]
```

For development:

```bash
pip install saidata-gen[dev]
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