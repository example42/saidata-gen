# Saidata Generator Examples

This directory contains example configurations, scripts, and use cases for the saidata generator tool.

## Directory Structure

- `configs/` - Example configuration files for different use cases
- `scripts/` - Sample automation scripts and workflows
- `rag/` - RAG configuration examples and prompt templates
- `workflows/` - Best practices and recommended workflows
- `use-cases/` - Complete examples for specific scenarios

## Quick Start

1. **Basic Generation**: See `configs/basic.yaml` for minimal configuration
2. **Enterprise Setup**: Check `configs/enterprise.yaml` for production environments
3. **CI/CD Integration**: Look at `scripts/ci-cd-pipeline.sh` for automation
4. **AI Enhancement**: Explore `rag/` directory for AI-powered metadata generation

## New Directory Structure Output

saidata-gen now generates structured directory output:

```
nginx/
├── defaults.yaml              # Software-specific base configuration
└── providers/                 # Provider-specific overrides (only when different from defaults)
    ├── apt.yaml              # Only created if apt config differs from provider_defaults.yaml
    ├── brew.yaml             # Only created if brew config differs from provider_defaults.yaml
    └── docker.yaml           # Only created if docker config differs from provider_defaults.yaml
```

All examples have been updated to work with this new structure.

## Configuration Examples

Each configuration example includes:
- YAML configuration file
- Usage instructions
- Expected output samples
- Troubleshooting tips

## Script Examples

All scripts include:
- Detailed comments explaining each step
- Error handling and logging
- Configurable parameters
- Example outputs

## Best Practices

See `workflows/best-practices.md` for recommended approaches to:
- Configuration management
- Batch processing optimization
- Quality assurance workflows
- Performance tuning