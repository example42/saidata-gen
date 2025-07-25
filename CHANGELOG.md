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
- Provider template analysis script for identifying redundant configurations
- Development tools for template refactoring and optimization
- URL configuration guidelines for provider templates

### Enhanced
- Provider template analysis script now properly handles package name overrides as valid provider-specific configurations
- Improved performance of template analysis through optimized dictionary operations and reduced redundant processing
- Enhanced security with better file path validation and error handling
- Updated provider template guidelines with comprehensive URL configuration patterns

### Documentation
- Added URL configuration section to package name override examples
- Enhanced provider template guidelines with URL configuration best practices
- Clarified distinction between official website URLs and provider-specific URLs
- Added platform support clarification to package name override examples, emphasizing that `platforms` should only be defined in `defaults.yaml` as it indicates software platform support, not provider platform support

### Tools
- `scripts/analyze_provider_templates.py`: Analyzes provider templates against defaults to identify redundant keys and suggest optimizations
  - Now recognizes package name overrides (`packages.default.name`) as always valid provider-specific configurations
  - Improved performance through optimized template variable normalization
  - Enhanced error handling and path security
  - Added support for hierarchical provider template structure analysis
  - Enhanced provider naming for hierarchical templates with path-based identifiers

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