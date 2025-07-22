# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release preparation
- PyPI package distribution setup
- Docker container support
- Standalone binary distribution

## [0.1.0] - 2025-01-21

### Added
- Initial release of saidata-gen
- Core metadata generation functionality
- Support for multiple package managers (apt, dnf, brew, winget, scoop, etc.)
- Schema validation against saidata-0.1.schema.json
- Software search and discovery across repositories
- Batch processing capabilities
- Configuration management system
- Caching and performance optimization
- RAG integration for AI-enhanced metadata generation
- ML training data export and model fine-tuning
- Comprehensive CLI interface
- Quality assurance and validation system
- Extensive test coverage
- Documentation and examples

### Features
- **Repository Fetchers**: Support for 30+ package managers and repositories
- **AI Integration**: RAG capabilities with OpenAI, Anthropic, and local models
- **ML Pipeline**: Training data export and model fine-tuning
- **Validation**: Comprehensive schema validation and quality scoring
- **Performance**: Intelligent caching and concurrent processing
- **CLI**: Rich command-line interface with progress reporting
- **Configuration**: Flexible YAML-based configuration system

[Unreleased]: https://github.com/sai/saidata-gen/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sai/saidata-gen/releases/tag/v0.1.0