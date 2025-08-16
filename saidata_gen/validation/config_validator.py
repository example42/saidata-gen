"""
Configuration validation and cleanup module for saidata-gen.

This module provides comprehensive functionality to validate provider configurations,
identify redundant settings, and suggest optimizations for the override-only template system.
"""

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import yaml

from saidata_gen.core.interfaces import ValidationIssue, ValidationLevel, ValidationResult
from saidata_gen.validation.schema import SchemaValidator


logger = logging.getLogger(__name__)


@dataclass
class ConfigurationSuggestion:
    """
    Suggestion for improving configuration.
    """
    type: str  # 'remove', 'modify', 'add', 'merge'
    path: str
    current_value: Any
    suggested_value: Any
    reason: str
    confidence: float  # 0.0 to 1.0
    impact: str  # 'low', 'medium', 'high'


@dataclass
class ProviderOverrideValidationResult:
    """
    Result of provider override validation.
    """
    provider: str
    valid: bool
    necessary_overrides: Dict[str, Any] = field(default_factory=dict)
    redundant_keys: List[str] = field(default_factory=list)
    missing_keys: List[str] = field(default_factory=list)
    suggestions: List[ConfigurationSuggestion] = field(default_factory=list)
    issues: List[ValidationIssue] = field(default_factory=list)
    quality_score: float = 0.0
    optimization_potential: float = 0.0


@dataclass
class ConfigurationValidationReport:
    """
    Comprehensive configuration validation report.
    """
    provider_results: Dict[str, ProviderOverrideValidationResult] = field(default_factory=dict)
    overall_quality_score: float = 0.0
    total_redundant_keys: int = 0
    total_suggestions: int = 0
    optimization_summary: Dict[str, int] = field(default_factory=dict)
    consistency_issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class ConfigurationValidator:
    """
    Comprehensive validator for saidata provider configurations.
    
    This class provides functionality to validate provider override configurations,
    identify redundant settings, suggest optimizations, and ensure consistency
    across the provider template system.
    """
    
    def __init__(self, templates_dir: Optional[str] = None):
        """
        Initialize the configuration validator.
        
        Args:
            templates_dir: Directory containing template files. If None, uses the default.
        """
        if templates_dir is None:
            # Use the default templates directory in the package
            package_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.templates_dir = os.path.join(package_dir, "saidata_gen", "templates")
        else:
            self.templates_dir = os.path.expanduser(templates_dir)
        
        # Load defaults template
        self.defaults = self._load_defaults_template()
        
        # Initialize schema validator for additional validation
        self.schema_validator = SchemaValidator()
        
        # Define provider-specific validation rules
        self.provider_rules = self._initialize_provider_rules()
        
        # Define common redundant patterns
        self.redundant_patterns = self._initialize_redundant_patterns()
    
    def validate_provider_override(
        self,
        provider: str,
        override_config: Dict[str, Any],
        defaults: Optional[Dict[str, Any]] = None
    ) -> ProviderOverrideValidationResult:
        """
        Validate that provider override only contains necessary overrides.
        
        Args:
            provider: Provider name (e.g., 'apt', 'brew', 'winget')
            override_config: Provider override configuration
            defaults: Default configuration to compare against. If None, uses loaded defaults.
            
        Returns:
            ProviderOverrideValidationResult with validation details
        """
        if defaults is None:
            defaults = self.defaults
        
        result = ProviderOverrideValidationResult(
            provider=provider,
            valid=True
        )
        
        # Check if provider is supported (has 'supported: false')
        if override_config.get('supported') is False:
            # For unsupported providers, only 'version' and 'supported' should be present
            allowed_keys = {'version', 'supported'}
            extra_keys = set(override_config.keys()) - allowed_keys
            
            if extra_keys:
                result.valid = False
                result.issues.append(ValidationIssue(
                    level=ValidationLevel.WARNING,
                    message=f"Unsupported provider should only contain 'version' and 'supported' keys",
                    path=f"provider.{provider}",
                    schema_path=""
                ))
                
                for key in extra_keys:
                    result.redundant_keys.append(key)
                    result.suggestions.append(ConfigurationSuggestion(
                        type='remove',
                        path=key,
                        current_value=override_config[key],
                        suggested_value=None,
                        reason=f"Unnecessary key for unsupported provider",
                        confidence=0.9,
                        impact='medium'
                    ))
            
            result.quality_score = 0.8 if not extra_keys else 0.5
            return result
        
        # Validate override necessity
        necessary_overrides = {}
        redundant_keys = []
        
        for key, value in override_config.items():
            if key == 'version':
                # Version is always allowed
                necessary_overrides[key] = value
                continue
            
            # Check if this key-value pair differs from defaults
            if self._is_override_necessary(key, value, defaults):
                necessary_overrides[key] = value
            else:
                redundant_keys.append(key)
                result.suggestions.append(ConfigurationSuggestion(
                    type='remove',
                    path=key,
                    current_value=value,
                    suggested_value=None,
                    reason=f"Value matches default configuration",
                    confidence=0.8,
                    impact='low'
                ))
        
        # Check for missing provider-specific keys
        missing_keys = self._identify_missing_provider_keys(provider, override_config, defaults)
        
        # Apply provider-specific validation rules
        provider_issues = self._apply_provider_rules(provider, override_config)
        
        # Calculate quality and optimization scores
        quality_score = self._calculate_quality_score(
            len(necessary_overrides), 
            len(redundant_keys), 
            len(missing_keys),
            len(provider_issues)
        )
        
        optimization_potential = len(redundant_keys) / max(1, len(override_config))
        
        # Populate result
        result.necessary_overrides = necessary_overrides
        result.redundant_keys = redundant_keys
        result.missing_keys = missing_keys
        result.issues.extend(provider_issues)
        result.quality_score = quality_score
        result.optimization_potential = optimization_potential
        
        # Determine if configuration is valid
        error_count = len([issue for issue in result.issues if issue.level == ValidationLevel.ERROR])
        result.valid = error_count == 0
        
        return result
    
    def suggest_removable_keys(
        self,
        provider_config: Dict[str, Any],
        defaults: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Suggest keys that can be removed from provider config.
        
        Args:
            provider_config: Provider configuration
            defaults: Default configuration to compare against
            
        Returns:
            List of keys that match defaults and can be removed
        """
        if defaults is None:
            defaults = self.defaults
        
        removable_keys = []
        
        for key, value in provider_config.items():
            if key == 'version':
                # Version is always kept
                continue
            
            if not self._is_override_necessary(key, value, defaults):
                removable_keys.append(key)
        
        return removable_keys
    
    def validate_configuration_consistency(
        self,
        provider_configs: Dict[str, Dict[str, Any]]
    ) -> ConfigurationValidationReport:
        """
        Validate consistency across multiple provider configurations.
        
        Args:
            provider_configs: Dictionary of provider name -> configuration
            
        Returns:
            ConfigurationValidationReport with comprehensive analysis
        """
        report = ConfigurationValidationReport()
        
        # Validate each provider configuration
        for provider, config in provider_configs.items():
            result = self.validate_provider_override(provider, config)
            report.provider_results[provider] = result
        
        # Calculate overall metrics
        total_configs = len(provider_configs)
        valid_configs = len([r for r in report.provider_results.values() if r.valid])
        
        report.overall_quality_score = sum(
            r.quality_score for r in report.provider_results.values()
        ) / max(1, total_configs)
        
        report.total_redundant_keys = sum(
            len(r.redundant_keys) for r in report.provider_results.values()
        )
        
        report.total_suggestions = sum(
            len(r.suggestions) for r in report.provider_results.values()
        )
        
        # Analyze optimization opportunities
        report.optimization_summary = {
            'high_optimization': len([
                r for r in report.provider_results.values() 
                if r.optimization_potential > 0.5
            ]),
            'medium_optimization': len([
                r for r in report.provider_results.values() 
                if 0.2 < r.optimization_potential <= 0.5
            ]),
            'low_optimization': len([
                r for r in report.provider_results.values() 
                if r.optimization_potential <= 0.2
            ])
        }
        
        # Identify consistency issues
        report.consistency_issues = self._identify_consistency_issues(provider_configs)
        
        # Generate recommendations
        report.recommendations = self._generate_configuration_recommendations(report)
        
        return report
    
    def validate_provider_template_file(self, file_path: Union[str, Path]) -> ProviderOverrideValidationResult:
        """
        Validate a provider template file.
        
        Args:
            file_path: Path to the provider template file
            
        Returns:
            ProviderOverrideValidationResult for the template file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Extract provider name from file path
            provider = Path(file_path).stem
            
            return self.validate_provider_override(provider, config or {})
            
        except yaml.YAMLError as e:
            return ProviderOverrideValidationResult(
                provider=Path(file_path).stem,
                valid=False,
                issues=[ValidationIssue(
                    level=ValidationLevel.ERROR,
                    message=f"YAML parsing error: {str(e)}",
                    path=str(file_path),
                    schema_path=""
                )]
            )
        except Exception as e:
            return ProviderOverrideValidationResult(
                provider=Path(file_path).stem,
                valid=False,
                issues=[ValidationIssue(
                    level=ValidationLevel.ERROR,
                    message=f"Failed to load file: {str(e)}",
                    path=str(file_path),
                    schema_path=""
                )]
            )
    
    def _load_defaults_template(self) -> Dict[str, Any]:
        """Load the defaults template."""
        defaults_path = os.path.join(self.templates_dir, "defaults.yaml")
        
        try:
            with open(defaults_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning(f"Defaults template not found at {defaults_path}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load defaults template: {e}")
            return {}
    
    def _is_override_necessary(self, key: str, value: Any, defaults: Dict[str, Any]) -> bool:
        """
        Check if an override is necessary by comparing with defaults.
        
        Args:
            key: Configuration key
            value: Override value
            defaults: Default configuration
            
        Returns:
            True if override is necessary, False if it matches defaults
        """
        # Navigate to the nested key in defaults
        default_value = self._get_nested_value(defaults, key)
        
        # If key doesn't exist in defaults, override is necessary
        if default_value is None and key not in self._flatten_dict(defaults):
            return True
        
        # Compare values
        return not self._values_equal(value, default_value)
    
    def _get_nested_value(self, data: Dict[str, Any], key_path: str) -> Any:
        """
        Get value from nested dictionary using dot notation.
        
        Args:
            data: Dictionary to search
            key_path: Key path (e.g., 'packages.default.name')
            
        Returns:
            Value at the key path, or None if not found
        """
        keys = key_path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current
    
    def _flatten_dict(self, data: Dict[str, Any], prefix: str = '') -> Dict[str, Any]:
        """
        Flatten nested dictionary with dot notation keys.
        
        Args:
            data: Dictionary to flatten
            prefix: Key prefix for recursion
            
        Returns:
            Flattened dictionary
        """
        result = {}
        
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                result.update(self._flatten_dict(value, full_key))
            else:
                result[full_key] = value
        
        return result
    
    def _values_equal(self, value1: Any, value2: Any) -> bool:
        """
        Compare two values for equality, handling different types appropriately.
        
        Args:
            value1: First value
            value2: Second value
            
        Returns:
            True if values are considered equal
        """
        # Handle None values
        if value1 is None and value2 is None:
            return True
        if value1 is None or value2 is None:
            return False
        
        # Handle lists
        if isinstance(value1, list) and isinstance(value2, list):
            if len(value1) != len(value2):
                return False
            return all(self._values_equal(v1, v2) for v1, v2 in zip(value1, value2))
        
        # Handle dictionaries
        if isinstance(value1, dict) and isinstance(value2, dict):
            if set(value1.keys()) != set(value2.keys()):
                return False
            return all(self._values_equal(value1[k], value2[k]) for k in value1.keys())
        
        # Handle primitive types
        return value1 == value2
    
    def _identify_missing_provider_keys(
        self,
        provider: str,
        config: Dict[str, Any],
        defaults: Dict[str, Any]
    ) -> List[str]:
        """
        Identify keys that should be present for a specific provider.
        
        Args:
            provider: Provider name
            config: Provider configuration
            defaults: Default configuration
            
        Returns:
            List of missing keys that should be present
        """
        missing_keys = []
        
        # Provider-specific required keys
        provider_required_keys = self.provider_rules.get(provider, {}).get('required_keys', [])
        
        for key in provider_required_keys:
            if key not in config and key not in self._flatten_dict(config):
                missing_keys.append(key)
        
        return missing_keys
    
    def _apply_provider_rules(
        self,
        provider: str,
        config: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """
        Apply provider-specific validation rules.
        
        Args:
            provider: Provider name
            config: Provider configuration
            
        Returns:
            List of validation issues
        """
        issues = []
        rules = self.provider_rules.get(provider, {})
        
        # Check forbidden keys
        forbidden_keys = rules.get('forbidden_keys', [])
        for key in forbidden_keys:
            if key in config:
                issues.append(ValidationIssue(
                    level=ValidationLevel.WARNING,
                    message=f"Key '{key}' should not be used for provider '{provider}'",
                    path=f"provider.{provider}.{key}",
                    schema_path=""
                ))
        
        # Check platform-specific rules
        platform_rules = rules.get('platform_rules', {})
        for platform, platform_config in platform_rules.items():
            if self._config_suggests_platform(config, platform):
                required_keys = platform_config.get('required_keys', [])
                for key in required_keys:
                    if key not in config:
                        issues.append(ValidationIssue(
                            level=ValidationLevel.INFO,
                            message=f"Consider adding '{key}' for {platform} platform",
                            path=f"provider.{provider}.{key}",
                            schema_path=""
                        ))
        
        return issues
    
    def _config_suggests_platform(self, config: Dict[str, Any], platform: str) -> bool:
        """
        Check if configuration suggests a specific platform.
        
        Args:
            config: Provider configuration
            platform: Platform name
            
        Returns:
            True if configuration suggests the platform
        """
        # Simple heuristics to detect platform-specific configurations
        platform_indicators = {
            'windows': ['winget', 'choco', 'scoop', '.exe', 'C:\\', 'Program Files'],
            'linux': ['apt', 'dnf', 'yum', 'pacman', '/usr/', '/etc/', 'systemd'],
            'macos': ['brew', '/usr/local/', '/Applications/', 'launchd']
        }
        
        indicators = platform_indicators.get(platform.lower(), [])
        config_str = str(config).lower()
        
        return any(indicator.lower() in config_str for indicator in indicators)
    
    def _calculate_quality_score(
        self,
        necessary_count: int,
        redundant_count: int,
        missing_count: int,
        issue_count: int
    ) -> float:
        """
        Calculate quality score for a provider configuration.
        
        Args:
            necessary_count: Number of necessary overrides
            redundant_count: Number of redundant keys
            missing_count: Number of missing keys
            issue_count: Number of validation issues
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        total_keys = necessary_count + redundant_count
        
        if total_keys == 0:
            return 0.5  # Empty configuration
        
        # Base score from necessity ratio
        necessity_score = necessary_count / total_keys
        
        # Penalty for missing keys
        missing_penalty = min(0.3, missing_count * 0.1)
        
        # Penalty for issues
        issue_penalty = min(0.2, issue_count * 0.05)
        
        quality_score = necessity_score - missing_penalty - issue_penalty
        
        return max(0.0, min(1.0, quality_score))
    
    def _identify_consistency_issues(
        self,
        provider_configs: Dict[str, Dict[str, Any]]
    ) -> List[str]:
        """
        Identify consistency issues across provider configurations.
        
        Args:
            provider_configs: Dictionary of provider configurations
            
        Returns:
            List of consistency issues
        """
        issues = []
        
        # Check for inconsistent version specifications
        versions = {}
        for provider, config in provider_configs.items():
            if 'version' in config:
                version = config['version']
                if version in versions:
                    versions[version].append(provider)
                else:
                    versions[version] = [provider]
        
        if len(versions) > 1:
            issues.append(f"Inconsistent version specifications across providers: {dict(versions)}")
        
        # Check for similar configurations that could be consolidated
        similar_configs = self._find_similar_configurations(provider_configs)
        if similar_configs:
            issues.append(f"Similar configurations found that could be consolidated: {similar_configs}")
        
        return issues
    
    def _find_similar_configurations(
        self,
        provider_configs: Dict[str, Dict[str, Any]]
    ) -> List[Tuple[str, str]]:
        """
        Find provider configurations that are very similar.
        
        Args:
            provider_configs: Dictionary of provider configurations
            
        Returns:
            List of tuples of similar provider pairs
        """
        similar_pairs = []
        providers = list(provider_configs.keys())
        
        for i, provider1 in enumerate(providers):
            for provider2 in providers[i+1:]:
                config1 = provider_configs[provider1]
                config2 = provider_configs[provider2]
                
                similarity = self._calculate_config_similarity(config1, config2)
                if similarity > 0.8:  # 80% similarity threshold
                    similar_pairs.append((provider1, provider2))
        
        return similar_pairs
    
    def _calculate_config_similarity(self, config1: Dict[str, Any], config2: Dict[str, Any]) -> float:
        """
        Calculate similarity between two configurations.
        
        Args:
            config1: First configuration
            config2: Second configuration
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        flat1 = self._flatten_dict(config1)
        flat2 = self._flatten_dict(config2)
        
        all_keys = set(flat1.keys()) | set(flat2.keys())
        if not all_keys:
            return 1.0
        
        matching_keys = 0
        for key in all_keys:
            if key in flat1 and key in flat2:
                if self._values_equal(flat1[key], flat2[key]):
                    matching_keys += 1
        
        return matching_keys / len(all_keys)
    
    def _generate_configuration_recommendations(
        self,
        report: ConfigurationValidationReport
    ) -> List[str]:
        """
        Generate recommendations based on validation report.
        
        Args:
            report: Configuration validation report
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Overall quality recommendations
        if report.overall_quality_score < 0.7:
            recommendations.append(
                f"Overall configuration quality is low ({report.overall_quality_score:.2f}). "
                "Consider reviewing and optimizing provider configurations."
            )
        
        # Redundancy recommendations
        if report.total_redundant_keys > 0:
            recommendations.append(
                f"Found {report.total_redundant_keys} redundant keys across all providers. "
                "Remove these keys to improve maintainability."
            )
        
        # High optimization potential recommendations
        high_opt_count = report.optimization_summary.get('high_optimization', 0)
        if high_opt_count > 0:
            recommendations.append(
                f"{high_opt_count} provider(s) have high optimization potential (>50% redundant keys). "
                "Prioritize optimizing these configurations."
            )
        
        # Consistency recommendations
        if report.consistency_issues:
            recommendations.append(
                "Consistency issues found across providers. "
                "Review and standardize configurations where appropriate."
            )
        
        return recommendations
    
    def _initialize_provider_rules(self) -> Dict[str, Dict[str, Any]]:
        """
        Initialize provider-specific validation rules.
        
        Returns:
            Dictionary of provider rules
        """
        return {
            'apt': {
                'required_keys': [],
                'forbidden_keys': ['supported'],  # Should be implicit for apt
                'platform_rules': {
                    'linux': {
                        'required_keys': ['packages.default.name']
                    }
                }
            },
            'brew': {
                'required_keys': [],
                'forbidden_keys': [],
                'platform_rules': {
                    'macos': {
                        'required_keys': ['packages.default.name']
                    },
                    'linux': {
                        'required_keys': ['packages.default.name']
                    }
                }
            },
            'winget': {
                'required_keys': [],
                'forbidden_keys': [],
                'platform_rules': {
                    'windows': {
                        'required_keys': ['packages.default.name']
                    }
                }
            },
            'choco': {
                'required_keys': [],
                'forbidden_keys': [],
                'platform_rules': {
                    'windows': {
                        'required_keys': ['packages.default.name']
                    }
                }
            },
            'scoop': {
                'required_keys': [],
                'forbidden_keys': [],
                'platform_rules': {
                    'windows': {
                        'required_keys': ['packages.default.name']
                    }
                }
            }
        }
    
    def _initialize_redundant_patterns(self) -> List[Dict[str, Any]]:
        """
        Initialize common redundant patterns to detect.
        
        Returns:
            List of redundant pattern definitions
        """
        return [
            {
                'name': 'default_package_name',
                'pattern': lambda config, software_name: (
                    config.get('packages', {}).get('default', {}).get('name') == software_name
                ),
                'message': 'Package name matches software name (default behavior)'
            },
            {
                'name': 'empty_directories',
                'pattern': lambda config, software_name: (
                    config.get('directories') == {}
                ),
                'message': 'Empty directories configuration'
            },
            {
                'name': 'empty_services',
                'pattern': lambda config, software_name: (
                    config.get('services') == {}
                ),
                'message': 'Empty services configuration'
            }
        ]