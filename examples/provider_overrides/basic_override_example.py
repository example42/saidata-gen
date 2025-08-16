#!/usr/bin/env python3
"""
Basic Override-Only Provider Configuration Example

This example demonstrates the new override-only provider template system
where provider configurations contain only settings that differ from defaults.
"""

import json
import os
import sys
from pathlib import Path

# Add the parent directory to the path so we can import saidata_gen
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from saidata_gen.generator.templates import TemplateEngine
from saidata_gen.validation.config_validator import ConfigurationValidator


def main():
    """Demonstrate override-only provider configuration."""
    print("=== Basic Override-Only Provider Configuration Example ===\n")
    
    # Initialize template engine
    template_engine = TemplateEngine()
    
    # Initialize configuration validator
    validator = ConfigurationValidator()
    
    print("1. Loading default template...")
    defaults = template_engine.default_template
    print(f"Default template loaded with {len(defaults)} top-level keys")
    print(f"Default package name template: {defaults.get('packages', {}).get('default', {}).get('name', 'N/A')}")
    print()
    
    # Example 1: APT provider with package name override
    print("2. Generating APT provider override (package name differs)...")
    apt_override = template_engine.apply_provider_overrides_only(
        software_name="nginx",
        provider="apt",
        repository_data={
            "name": "nginx-core",  # Different from default "nginx"
            "version": "1.18.0",
            "description": "High-performance web server"
        }
    )
    
    print("APT Override Configuration:")
    print(json.dumps(apt_override, indent=2))
    print()
    
    # Validate the APT override
    print("3. Validating APT override configuration...")
    apt_validation = validator.validate_provider_override("apt", apt_override)
    print(f"Valid: {apt_validation.valid}")
    print(f"Quality Score: {apt_validation.quality_score:.2f}")
    print(f"Necessary overrides: {len(apt_validation.necessary_overrides)}")
    print(f"Redundant keys: {apt_validation.redundant_keys}")
    print()
    
    # Example 2: Chocolatey provider (unsupported)
    print("4. Generating Chocolatey provider override (unsupported)...")
    choco_override = template_engine.apply_provider_overrides_only(
        software_name="nginx",
        provider="choco",
        repository_data=None  # No repository data = unsupported
    )
    
    print("Chocolatey Override Configuration:")
    print(json.dumps(choco_override, indent=2))
    print()
    
    # Example 3: Merge override with defaults
    print("5. Merging APT override with defaults...")
    merged_config = template_engine.merge_with_defaults(defaults, apt_override)
    
    print("Merged Configuration (showing key differences):")
    print(f"Package name: {merged_config['packages']['default']['name']}")  # From override
    print(f"Version: {merged_config.get('version')}")  # From defaults
    print(f"Service name: {merged_config.get('services', {}).get('default', {}).get('name')}")  # From defaults
    print()
    
    # Example 4: Provider support detection
    print("6. Testing provider support detection...")
    
    providers_to_test = ["apt", "brew", "winget", "choco", "nonexistent"]
    for provider in providers_to_test:
        is_supported = template_engine.is_provider_supported(
            software_name="nginx",
            provider=provider,
            repository_data={"name": "nginx"} if provider != "choco" else None
        )
        print(f"{provider:12}: {'✓ Supported' if is_supported else '✗ Not supported'}")
    print()
    
    # Example 5: Configuration validation across multiple providers
    print("7. Validating configuration consistency across providers...")
    
    provider_configs = {
        "apt": {
            "version": "0.1",
            "packages": {"default": {"name": "nginx-core"}}
        },
        "brew": {
            "version": "0.1", 
            "packages": {"default": {"name": "nginx"}}
        },
        "winget": {
            "version": "0.1",
            "packages": {"default": {"name": "nginx"}}
        },
        "choco": {
            "version": "0.1",
            "supported": False
        }
    }
    
    consistency_report = validator.validate_configuration_consistency(provider_configs)
    
    print(f"Overall quality score: {consistency_report.overall_quality_score:.2f}")
    print(f"Total redundant keys: {consistency_report.total_redundant_keys}")
    print(f"Providers with high optimization potential: {consistency_report.optimization_summary.get('high_optimization', 0)}")
    
    if consistency_report.recommendations:
        print("\nRecommendations:")
        for rec in consistency_report.recommendations:
            print(f"  - {rec}")
    print()
    
    # Example 6: Demonstrate removable keys suggestion
    print("8. Identifying removable keys in a redundant configuration...")
    
    redundant_config = {
        "version": "0.1",
        "packages": {"default": {"name": "nginx", "version": "latest"}},  # Matches defaults
        "services": {"default": {"name": "nginx"}},  # Matches defaults
        "directories": {"config": {"path": "/etc/nginx"}},  # Might match defaults
        "custom_setting": "unique_value"  # Actually needed
    }
    
    removable_keys = validator.suggest_removable_keys(redundant_config)
    print(f"Configuration has {len(redundant_config)} keys")
    print(f"Removable keys: {removable_keys}")
    print(f"Optimized configuration would have {len(redundant_config) - len(removable_keys)} keys")
    print()
    
    print("=== Example completed successfully! ===")
    print("\nKey takeaways:")
    print("1. Override-only templates contain only necessary differences")
    print("2. Unsupported providers use 'supported: false'")
    print("3. Configuration validation helps identify redundant settings")
    print("4. Provider support is automatically detected")
    print("5. Consistency validation ensures quality across providers")


if __name__ == "__main__":
    main()