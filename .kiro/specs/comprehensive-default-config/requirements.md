# Requirements Document

## Introduction

This feature will restructure the configuration system to use separate provider defaults and implement a new directory-based output structure, while addressing critical fetcher reliability issues. Currently, provider-specific configurations are scattered across individual provider templates, leading to data duplication. The new system will use a common `provider_defaults.yaml` file for all software packages, with software-specific overrides in a structured directory format: `$software/defaults.yaml` and `$software/providers/$provider.yaml`. Additionally, analysis of error logs shows multiple fetcher failures across providers due to network issues, SSL certificate problems, missing dependencies, and malformed responses. This enhancement will eliminate configuration duplication, provide a cleaner output structure, and improve fetcher robustness. The CLI will also be simplified by removing deprecated options and always generating the structured directory format.

## Requirements

### Requirement 1

**User Story:** As a developer using saidata-gen, I want a separate provider_defaults.yaml file that contains explicit defaults for all supported providers, so that configuration is not duplicated across software packages and I can understand all available provider-specific options in one place.

#### Acceptance Criteria

1. WHEN the system loads configuration THEN it SHALL use a common `saidata_gen/templates/provider_defaults.yaml` file containing explicit defaults for all 33+ supported providers
2. WHEN a provider-specific configuration is not overridden in a software-specific provider file THEN the system SHALL use the value from provider_defaults.yaml
3. WHEN examining the provider_defaults.yaml file THEN users SHALL be able to see all available provider-specific configuration options for all providers

### Requirement 2

**User Story:** As a user generating metadata, I want the system to output a structured directory format for each software package, so that configuration files are organized and easy to manage.

#### Acceptance Criteria

1. WHEN running saidata-gen generate THEN it SHALL create a directory structure `$software/defaults.yaml` and `$software/providers/$provider.yaml` under the specified path
2. WHEN provider-specific configurations match the provider_defaults.yaml THEN no provider-specific file SHALL be created to avoid duplication
3. WHEN the --output option is specified THEN the software directory SHALL be created under that path, otherwise under the current working directory

### Requirement 3

**User Story:** As a system administrator, I want provider-specific URLs, services, files, and directories to be explicitly defined in the provider_defaults.yaml configuration, so that I can easily reference all provider-specific settings in one place.

#### Acceptance Criteria

1. WHEN the provider_defaults.yaml file is processed THEN it SHALL contain URL configurations for all providers including apt, brew, winget, dnf, yum, pacman, apk, and others
2. WHEN the provider_defaults.yaml file is loaded THEN it SHALL contain explicit service configurations (enabled, status) for all providers
3. WHEN generating metadata THEN provider-specific URLs SHALL be properly templated with software_name variables

### Requirement 4

**User Story:** As a developer extending saidata-gen, I want the provider_defaults.yaml configuration to be well-documented and organized by provider type, so that I can easily understand and maintain the configuration structure.

#### Acceptance Criteria

1. WHEN examining the provider_defaults.yaml file THEN provider configurations SHALL be organized in logical sections with clear comments
2. WHEN adding new providers THEN the configuration structure SHALL be consistent and follow established patterns
3. WHEN the provider_defaults.yaml file is updated THEN it SHALL maintain backward compatibility with existing software-specific configurations

### Requirement 5

**User Story:** As a user of the saidata-gen CLI, I want deprecated and redundant command-line options to be removed, so that the interface is clean and focused on the core functionality.

#### Acceptance Criteria

1. WHEN running saidata-gen generate THEN the --directory-structure and --comprehensive options SHALL be removed as the command always generates the structured directory format
2. WHEN running saidata-gen generate THEN the deprecated --use-rag and --rag-provider options SHALL be removed
3. WHEN users attempt to use removed options THEN the system SHALL provide clear error messages indicating the options have been removed

### Requirement 6

**User Story:** As a system administrator running saidata-gen, I want fetcher operations to be resilient to network failures and SSL certificate issues, so that metadata generation doesn't fail due to temporary connectivity problems.

#### Acceptance Criteria

1. WHEN a fetcher encounters SSL certificate verification errors THEN it SHALL implement appropriate fallback mechanisms or certificate handling
2. WHEN network requests fail with HTTP errors THEN the system SHALL implement exponential backoff retry logic with configurable limits
3. WHEN repository endpoints are temporarily unavailable THEN the fetcher SHALL gracefully degrade and continue with available sources

### Requirement 7

**User Story:** As a developer using saidata-gen, I want fetchers to handle missing system dependencies gracefully, so that the tool works even when optional package managers are not installed.

#### Acceptance Criteria

1. WHEN a fetcher requires a system command that is not installed (like emerge, guix, nix, spack) THEN it SHALL log a warning and continue without failing
2. WHEN system commands return non-zero exit codes THEN the fetcher SHALL handle these gracefully with appropriate error messages
3. WHEN optional dependencies are missing THEN the system SHALL provide clear guidance on what needs to be installed

### Requirement 8

**User Story:** As a user generating metadata, I want fetchers to handle malformed or corrupted repository data gracefully, so that one bad data source doesn't break the entire generation process.

#### Acceptance Criteria

1. WHEN repository data contains invalid JSON, YAML, or XML THEN the fetcher SHALL log the error and skip that source
2. WHEN package manifest files are corrupted or have encoding issues THEN the system SHALL handle these gracefully
3. WHEN repository indexes are incomplete or malformed THEN the fetcher SHALL attempt alternative approaches or fallback sources