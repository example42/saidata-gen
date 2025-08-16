# Requirements Document

## Introduction

This feature involves refactoring the current saidata provider template structure to follow a more efficient and maintainable pattern. The current provider files contain redundant information that duplicates the general defaults, making them harder to maintain and understand. The new structure should only include provider-specific overrides and differences from the general defaults, following the pattern established in the examples directory.

When generating saidata for a given software, a directory with the software name is created, and inside that directory there's a structure similar to the one in examples/saidata/example, including a defaults.yaml file and a providers subdirectory with individual provider files.

## Requirements

### Requirement 1

**User Story:** As a developer maintaining saidata provider configurations, I want provider files to only contain settings that differ from the general defaults, so that the configuration is cleaner and easier to maintain.

#### Acceptance Criteria

1. WHEN a provider file is created or updated THEN it SHALL only contain settings that are different from the general defaults
2. WHEN a setting has the same value as the general default THEN it SHALL NOT be included in the provider file
3. WHEN a provider file is processed THEN the system SHALL merge provider-specific settings with general defaults correctly
4. WHEN reviewing provider configurations THEN developers SHALL be able to quickly identify provider-specific customizations

### Requirement 2

**User Story:** As a developer working with unsupported providers, I want a clear way to indicate when a provider doesn't support a particular package, so that the system can handle these cases appropriately.

#### Acceptance Criteria

1. WHEN a provider does not support a package THEN the provider file SHALL contain `supported: false`
2. WHEN `supported: false` is set THEN no other configuration keys SHALL be required in the provider file
3. WHEN the system processes a provider with `supported: false` THEN it SHALL skip that provider for the given package
4. WHEN generating metadata THEN unsupported providers SHALL be excluded from the output

### Requirement 3

**User Story:** As a developer maintaining provider configurations, I want to avoid null or undefined values in provider files, so that the configuration is cleaner and more readable.

#### Acceptance Criteria

1. WHEN a provider doesn't have a known value for a configuration key THEN the key SHALL NOT be included in the provider file
2. WHEN a key is not present in a provider file THEN the system SHALL use the default value from the general defaults
3. WHEN processing provider configurations THEN null values SHALL NOT be explicitly written to provider files
4. WHEN merging configurations THEN missing keys SHALL be treated as using the default value

### Requirement 4

**User Story:** As a developer working with the saidata generation system, I want the refactored provider structure to be backward compatible, so that existing functionality continues to work without breaking changes.

#### Acceptance Criteria

1. WHEN the new provider structure is implemented THEN existing metadata generation workflows SHALL continue to work
2. WHEN provider files are refactored THEN the output metadata SHALL remain functionally equivalent
3. WHEN the system processes both old and new provider file formats THEN it SHALL handle both correctly during a transition period
4. WHEN tests are run after refactoring THEN all existing tests SHALL pass without modification

### Requirement 5

**User Story:** As a developer maintaining the saidata system, I want automated tools to help with the refactoring process, so that the migration can be done efficiently and accurately.

#### Acceptance Criteria

1. WHEN refactoring provider files THEN there SHALL be automated tools to identify redundant settings
2. WHEN migrating to the new structure THEN there SHALL be validation tools to ensure correctness
3. WHEN processing provider files THEN there SHALL be tools to detect and report configuration inconsistencies
4. WHEN updating provider files THEN there SHALL be automated formatting to ensure consistency

### Requirement 6

**User Story:** As a developer working with multiple providers, I want templates for all supported providers and comprehensive provider coverage, so that the system can generate complete saidata configurations.

#### Acceptance Criteria

1. WHEN generating saidata THEN there SHALL be templates available for all supported package managers and providers
2. WHEN running example scripts THEN they SHALL use all available providers by default to demonstrate comprehensive coverage
3. WHEN a new provider is added to the system THEN there SHALL be a corresponding template file created
4. WHEN processing software metadata THEN all relevant providers SHALL be considered unless explicitly excluded

### Requirement 7

**User Story:** As a user generating saidata, I want an AI option that enhances the generated metadata with information from LLMs, so that I can get more complete and comprehensive package information.

#### Acceptance Criteria

1. WHEN using the generate command THEN there SHALL be an AI option that queries LLMs for additional package information
2. WHEN the AI option is enabled THEN the system SHALL merge data from provider repositories with LLM responses
3. WHEN merging AI and repository data THEN provider repository data SHALL be considered more authoritative and take precedence
4. WHEN LLM data is used THEN it SHALL primarily fill in missing information for URLs, ports, processes, and other metadata not available in provider repositories
5. WHEN AI enhancement is complete THEN the final saidata SHALL be a comprehensive merge of both data sources
6. WHEN the AI option is not specified THEN the system SHALL work with repository data only, maintaining backward compatibility

### Requirement 8

**User Story:** As a developer working with multiple providers, I want clear documentation and examples of the new provider structure, so that I can create and maintain provider configurations correctly.

#### Acceptance Criteria

1. WHEN the new structure is implemented THEN there SHALL be updated documentation explaining the provider override pattern
2. WHEN creating new provider files THEN there SHALL be clear examples showing the correct format
3. WHEN working with provider configurations THEN there SHALL be guidelines for determining what should be included in provider files
4. WHEN troubleshooting provider issues THEN there SHALL be documentation explaining the configuration merging process

### Requirement 9

**User Story:** As a developer working with different package managers, I want to be able to override package names when they differ between providers, so that the system can correctly identify packages across different ecosystems.

#### Acceptance Criteria

1. WHEN a package has different names across providers THEN provider files SHALL be able to override the package name
2. WHEN a package name override is specified THEN it SHALL use the `packages.default.name` configuration key
3. WHEN no package name override is provided THEN the system SHALL use the software name as the package name
4. WHEN processing package configurations THEN provider-specific package names SHALL take precedence over the default software name
5. WHEN documenting provider templates THEN there SHALL be clear examples of package name overrides (e.g., Apache HTTP Server as 'apache2' on APT vs 'httpd' on YUM)

### Requirement 10

**User Story:** As a developer maintaining saidata configurations, I want platform support to be defined only at the software level, so that platform information is not duplicated across provider templates.

#### Acceptance Criteria

1. WHEN defining platform support THEN it SHALL be specified only in the `defaults.yaml` file
2. WHEN platform support is defined THEN it SHALL indicate which platforms the software supports, not which platforms the provider supports
3. WHEN provider templates are created THEN they SHALL NOT include platform configuration
4. WHEN processing configurations THEN provider platform support SHALL be implicit from the provider type (e.g., APT implies Linux support, Winget implies Windows support)
5. WHEN documenting the system THEN there SHALL be clear guidance that platforms represent software support, not provider availability

### Requirement 11

**User Story:** As a developer working with diverse Linux distributions and OS versions, I want provider templates to support hierarchical configurations for handling OS/distro/version-specific differences, so that the same provider can have different configurations based on the target environment.

#### Acceptance Criteria

1. WHEN provider templates are organized THEN they SHALL support a hierarchical directory structure (e.g., `yum/rhel.yaml`, `yum/centos.yaml`)
2. WHEN configurations are processed THEN they SHALL be merged in hierarchical order: defaults → provider base → distro-specific → version-specific
3. WHEN a provider has distro-specific differences THEN each distro SHALL have its own template file within the provider directory
4. WHEN a provider has version-specific differences THEN version-specific templates SHALL be organized in subdirectories (e.g., `yum/rhel/8.yaml`)
5. WHEN the same provider is used across different environments THEN the system SHALL automatically select and merge the appropriate template hierarchy
6. WHEN analyzing templates THEN the analysis tools SHALL support both flat and hierarchical provider structures
7. WHEN documenting the system THEN there SHALL be clear examples showing how hierarchical templates handle real-world scenarios (e.g., Apache HTTP Server package names across different distros)