#!/usr/bin/env python3
"""
Analysis script to compare provider templates with defaults and identify redundant configurations.
This script helps identify which keys in provider templates match defaults and can be removed.
Supports both flat and hierarchical provider template structures.
"""

import yaml
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Set
from dataclasses import dataclass


@dataclass
class AnalysisResult:
    """Results of template analysis"""
    provider: str
    redundant_keys: List[str]
    unique_keys: List[str]
    total_keys: int
    redundancy_percentage: float


def load_yaml_file(file_path: str) -> Dict[str, Any]:
    """Load and parse a YAML file"""
    try:
        # Resolve path to prevent directory traversal
        resolved_path = Path(file_path).resolve()
        with open(resolved_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"Warning: File not found: {file_path}")
        return {}
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file {file_path}: {e}")
        return {}
    except (OSError, IOError) as e:
        print(f"Error reading file {file_path}: {e}")
        return {}


def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
    """Flatten a nested dictionary for easier comparison"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def normalize_template_variables(value: Any) -> Any:
    """Normalize template variables for comparison"""
    if isinstance(value, str):
        # Normalize different template variable formats (more efficient with single pass)
        if '{{' in value:
            value = value.replace('{{ software_name }}', '$software_name').replace('{{software_name}}', '$software_name')
    return value


def is_valid_package_override(key: str, value: Any, flat_normalized_defaults: Dict[str, Any]) -> bool:
    """Check if a package configuration is a valid provider-specific override"""
    if not key.startswith('packages.default.'):
        return True  # Non-package configs are handled normally
    
    # Package name overrides are always valid (different package names per provider)
    if key == 'packages.default.name':
        return True
    
    # Other package configs should only be included if they differ from defaults
    normalized_value = normalize_template_variables(value)
    
    return key not in flat_normalized_defaults or flat_normalized_defaults[key] != normalized_value


def compare_configurations(defaults: Dict[str, Any], provider: Dict[str, Any]) -> tuple[List[str], List[str]]:
    """Compare provider configuration with defaults to find redundant and unique keys"""
    # Flatten both configurations for easier comparison
    flat_defaults = flatten_dict(defaults)
    flat_provider = flatten_dict(provider)
    
    # Normalize template variables (do this once for defaults)
    normalized_defaults = {k: normalize_template_variables(v) for k, v in flat_defaults.items()}
    normalized_provider = {k: normalize_template_variables(v) for k, v in flat_provider.items()}
    
    redundant_keys = []
    unique_keys = []
    
    for key, value in normalized_provider.items():
        # Check if this is a valid package override
        if not is_valid_package_override(key, value, normalized_defaults):
            if key in normalized_defaults and normalized_defaults[key] == value:
                redundant_keys.append(key)
            else:
                unique_keys.append(key)
        else:
            # For package name overrides, always consider them unique/valid
            if key == 'packages.default.name':
                unique_keys.append(key + " (package name override)")
            elif key in normalized_defaults:
                if normalized_defaults[key] == value:
                    redundant_keys.append(key)
                else:
                    unique_keys.append(key)
            else:
                unique_keys.append(key)
    
    return redundant_keys, unique_keys


def analyze_provider_template(defaults: Dict[str, Any], provider_file: str) -> AnalysisResult:
    """Analyze a single provider template against defaults"""
    provider_name = Path(provider_file).stem
    provider_config = load_yaml_file(provider_file)
    
    # Skip version field from analysis as it's always required
    if 'version' in provider_config:
        del provider_config['version']
    if 'version' in defaults:
        defaults_copy = defaults.copy()
        del defaults_copy['version']
    else:
        defaults_copy = defaults
    
    redundant_keys, unique_keys = compare_configurations(defaults_copy, provider_config)
    
    total_keys = len(redundant_keys) + len(unique_keys)
    redundancy_percentage = (len(redundant_keys) / total_keys * 100) if total_keys > 0 else 0
    
    return AnalysisResult(
        provider=provider_name,
        redundant_keys=redundant_keys,
        unique_keys=unique_keys,
        total_keys=total_keys,
        redundancy_percentage=redundancy_percentage
    )


def generate_report(results: List[AnalysisResult]) -> str:
    """Generate a comprehensive analysis report"""
    report = []
    report.append("=" * 80)
    report.append("PROVIDER TEMPLATE ANALYSIS REPORT")
    report.append("=" * 80)
    report.append("")
    
    # Summary statistics
    total_providers = len(results)
    avg_redundancy = sum(r.redundancy_percentage for r in results) / total_providers if total_providers > 0 else 0
    
    report.append("SUMMARY:")
    report.append(f"  Total providers analyzed: {total_providers}")
    report.append(f"  Average redundancy: {avg_redundancy:.1f}%")
    report.append("")
    
    # Individual provider analysis
    for result in sorted(results, key=lambda x: x.redundancy_percentage, reverse=True):
        report.append(f"PROVIDER: {result.provider.upper()}")
        report.append("-" * 40)
        report.append(f"  Total keys: {result.total_keys}")
        report.append(f"  Redundant keys: {len(result.redundant_keys)} ({result.redundancy_percentage:.1f}%)")
        report.append(f"  Unique keys: {len(result.unique_keys)}")
        report.append("")
        
        if result.redundant_keys:
            report.append("  REDUNDANT KEYS (can be removed):")
            for key in sorted(result.redundant_keys):
                report.append(f"    - {key}")
            report.append("")
        
        if result.unique_keys:
            report.append("  UNIQUE KEYS (provider-specific, keep):")
            for key in sorted(result.unique_keys):
                report.append(f"    - {key}")
            report.append("")
        
        report.append("")
    
    # Recommendations
    report.append("RECOMMENDATIONS:")
    report.append("-" * 40)
    
    high_redundancy = [r for r in results if r.redundancy_percentage > 50]
    if high_redundancy:
        report.append("  High redundancy providers (>50% redundant keys):")
        for result in high_redundancy:
            report.append(f"    - {result.provider}: {result.redundancy_percentage:.1f}% redundant")
        report.append("")
    
    report.append("  Actions to take:")
    report.append("    1. Remove redundant keys from provider templates")
    report.append("    2. Keep only provider-specific overrides")
    report.append("    3. Ensure 'version' field is always present")
    report.append("    4. Add 'supported: false' for unsupported providers")
    report.append("")
    
    return "\n".join(report)


def find_provider_templates(providers_dir: Path) -> List[Path]:
    """Find all provider template files in both flat and hierarchical structure"""
    provider_files = []
    
    # Find flat provider files (legacy)
    flat_files = list(providers_dir.glob("*.yaml"))
    provider_files.extend(flat_files)
    
    # Find hierarchical provider files
    for provider_dir in providers_dir.iterdir():
        if provider_dir.is_dir():
            # Find all YAML files in provider subdirectories
            hierarchical_files = list(provider_dir.rglob("*.yaml"))
            provider_files.extend(hierarchical_files)
    
    return provider_files


def main():
    """Main analysis function"""
    # Get the project root directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Load defaults template
    defaults_file = project_root / "saidata_gen" / "templates" / "defaults.yaml"
    defaults = load_yaml_file(str(defaults_file))
    
    if not defaults:
        print("Error: Could not load defaults template")
        sys.exit(1)
    
    # Find all provider template files (both flat and hierarchical)
    providers_dir = project_root / "saidata_gen" / "templates" / "providers"
    provider_files = find_provider_templates(providers_dir)
    
    if not provider_files:
        print("Error: No provider template files found")
        sys.exit(1)
    
    print(f"Analyzing {len(provider_files)} provider templates...")
    print(f"Defaults file: {defaults_file}")
    print(f"Providers directory: {providers_dir}")
    print("")
    
    # Analyze each provider template
    results = []
    for provider_file in provider_files:
        # Create a more descriptive name for hierarchical files
        relative_path = provider_file.relative_to(providers_dir)
        display_name = str(relative_path).replace(os.sep, '_')
        
        print(f"Analyzing {display_name}...")
        result = analyze_provider_template(defaults, str(provider_file))
        # Update the provider name to include the path
        result.provider = display_name.replace('.yaml', '')
        results.append(result)
    
    # Generate and display report
    report = generate_report(results)
    print(report)
    
    # Save report to file
    report_file = project_root / "provider_template_analysis_report.txt"
    with open(report_file, 'w') as f:
        f.write(report)
    
    print(f"Report saved to: {report_file}")


if __name__ == "__main__":
    main()