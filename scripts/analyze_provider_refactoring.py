#!/usr/bin/env python3
"""
Provider template analysis and refactoring tool.

This script analyzes existing provider templates, identifies redundant configurations,
and suggests refactoring to the override-only format.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from saidata_gen.validation.config_validator import (
    ConfigurationValidator, ConfigurationValidationReport
)


class ProviderRefactoringAnalyzer:
    """
    Analyzer for provider template refactoring opportunities.
    """
    
    def __init__(self, templates_dir: Optional[str] = None):
        """
        Initialize the analyzer.
        
        Args:
            templates_dir: Directory containing template files
        """
        if templates_dir is None:
            self.templates_dir = project_root / "saidata_gen" / "templates"
        else:
            self.templates_dir = Path(templates_dir)
        
        self.validator = ConfigurationValidator(str(self.templates_dir))
        self.providers_dir = self.templates_dir / "providers"
    
    def analyze_all_providers(self) -> ConfigurationValidationReport:
        """
        Analyze all provider templates for refactoring opportunities.
        
        Returns:
            Comprehensive analysis report
        """
        provider_configs = {}
        
        # Load all provider configurations
        if self.providers_dir.exists():
            for provider_file in self.providers_dir.glob("*.yaml"):
                provider_name = provider_file.stem
                try:
                    with open(provider_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f) or {}
                    provider_configs[provider_name] = config
                except Exception as e:
                    print(f"Warning: Failed to load {provider_file}: {e}")
                    continue
            
            # Also check hierarchical providers
            for provider_dir in self.providers_dir.iterdir():
                if provider_dir.is_dir():
                    self._load_hierarchical_provider(provider_dir, provider_configs)
        
        # Validate configurations
        return self.validator.validate_configuration_consistency(provider_configs)
    
    def _load_hierarchical_provider(self, provider_dir: Path, provider_configs: Dict[str, Dict[str, Any]]):
        """
        Load hierarchical provider configurations.
        
        Args:
            provider_dir: Provider directory
            provider_configs: Dictionary to populate with configurations
        """
        provider_name = provider_dir.name
        
        # Load default configuration
        default_file = provider_dir / "default.yaml"
        if default_file.exists():
            try:
                with open(default_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                provider_configs[f"{provider_name}/default"] = config
            except Exception as e:
                print(f"Warning: Failed to load {default_file}: {e}")
        
        # Load OS-specific configurations
        for config_file in provider_dir.glob("*.yaml"):
            if config_file.name != "default.yaml":
                config_name = f"{provider_name}/{config_file.stem}"
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f) or {}
                    provider_configs[config_name] = config
                except Exception as e:
                    print(f"Warning: Failed to load {config_file}: {e}")
        
        # Load version-specific configurations
        for subdir in provider_dir.iterdir():
            if subdir.is_dir():
                for config_file in subdir.glob("*.yaml"):
                    config_name = f"{provider_name}/{subdir.name}/{config_file.stem}"
                    try:
                        with open(config_file, 'r', encoding='utf-8') as f:
                            config = yaml.safe_load(f) or {}
                        provider_configs[config_name] = config
                    except Exception as e:
                        print(f"Warning: Failed to load {config_file}: {e}")
    
    def generate_refactoring_suggestions(self, report: ConfigurationValidationReport) -> Dict[str, Any]:
        """
        Generate specific refactoring suggestions based on analysis.
        
        Args:
            report: Configuration validation report
            
        Returns:
            Dictionary of refactoring suggestions
        """
        suggestions = {
            'summary': {
                'total_providers': len(report.provider_results),
                'providers_needing_refactoring': 0,
                'total_redundant_keys': report.total_redundant_keys,
                'potential_savings': 0
            },
            'provider_suggestions': {},
            'global_recommendations': report.recommendations
        }
        
        for provider, result in report.provider_results.items():
            if result.redundant_keys or result.optimization_potential > 0.1:
                suggestions['summary']['providers_needing_refactoring'] += 1
                
                provider_suggestion = {
                    'current_quality_score': result.quality_score,
                    'optimization_potential': result.optimization_potential,
                    'redundant_keys': result.redundant_keys,
                    'actions': []
                }
                
                # Generate specific actions
                for suggestion in result.suggestions:
                    if suggestion.type == 'remove':
                        provider_suggestion['actions'].append({
                            'action': 'remove_key',
                            'key': suggestion.path,
                            'reason': suggestion.reason,
                            'confidence': suggestion.confidence
                        })
                
                # Calculate potential file size savings
                original_keys = len(result.necessary_overrides) + len(result.redundant_keys)
                optimized_keys = len(result.necessary_overrides)
                if original_keys > 0:
                    savings_percent = (len(result.redundant_keys) / original_keys) * 100
                    provider_suggestion['potential_savings_percent'] = savings_percent
                    suggestions['summary']['potential_savings'] += savings_percent
                
                suggestions['provider_suggestions'][provider] = provider_suggestion
        
        # Calculate average potential savings
        if suggestions['summary']['providers_needing_refactoring'] > 0:
            suggestions['summary']['average_potential_savings'] = (
                suggestions['summary']['potential_savings'] / 
                suggestions['summary']['providers_needing_refactoring']
            )
        
        return suggestions
    
    def create_refactored_template(self, provider: str, original_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a refactored template with only necessary overrides.
        
        Args:
            provider: Provider name
            original_config: Original provider configuration
            
        Returns:
            Refactored configuration with only necessary overrides
        """
        result = self.validator.validate_provider_override(provider, original_config)
        
        # Start with version if present
        refactored = {}
        if 'version' in original_config:
            refactored['version'] = original_config['version']
        
        # Add necessary overrides
        refactored.update(result.necessary_overrides)
        
        return refactored
    
    def save_refactored_templates(self, output_dir: str, dry_run: bool = True) -> Dict[str, Any]:
        """
        Save refactored templates to output directory.
        
        Args:
            output_dir: Output directory for refactored templates
            dry_run: If True, only show what would be done without saving
            
        Returns:
            Summary of refactoring actions
        """
        output_path = Path(output_dir)
        if not dry_run:
            output_path.mkdir(parents=True, exist_ok=True)
        
        report = self.analyze_all_providers()
        summary = {
            'refactored_files': [],
            'skipped_files': [],
            'errors': []
        }
        
        # Process each provider
        for provider, result in report.provider_results.items():
            try:
                # Skip if no optimization needed
                if result.optimization_potential < 0.1:
                    summary['skipped_files'].append({
                        'provider': provider,
                        'reason': 'No significant optimization potential'
                    })
                    continue
                
                # Load original configuration
                provider_file = self._find_provider_file(provider)
                if not provider_file:
                    summary['errors'].append({
                        'provider': provider,
                        'error': 'Provider file not found'
                    })
                    continue
                
                with open(provider_file, 'r', encoding='utf-8') as f:
                    original_config = yaml.safe_load(f) or {}
                
                # Create refactored configuration
                refactored_config = self.create_refactored_template(provider, original_config)
                
                # Save or show refactored configuration
                output_file = output_path / f"{provider.replace('/', '_')}.yaml"
                
                if dry_run:
                    print(f"\n--- Refactored {provider} ---")
                    print(yaml.dump(refactored_config, default_flow_style=False))
                else:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        yaml.dump(refactored_config, f, default_flow_style=False)
                
                summary['refactored_files'].append({
                    'provider': provider,
                    'original_keys': len(original_config),
                    'refactored_keys': len(refactored_config),
                    'removed_keys': result.redundant_keys,
                    'output_file': str(output_file) if not dry_run else None
                })
                
            except Exception as e:
                summary['errors'].append({
                    'provider': provider,
                    'error': str(e)
                })
        
        return summary
    
    def _find_provider_file(self, provider: str) -> Optional[Path]:
        """
        Find the file for a given provider.
        
        Args:
            provider: Provider name (may include hierarchy like 'apt/ubuntu')
            
        Returns:
            Path to provider file, or None if not found
        """
        # Handle hierarchical providers
        if '/' in provider:
            parts = provider.split('/')
            if len(parts) == 2:
                # provider/os format
                provider_dir = self.providers_dir / parts[0]
                return provider_dir / f"{parts[1]}.yaml"
            elif len(parts) == 3:
                # provider/os/version format
                provider_dir = self.providers_dir / parts[0] / parts[1]
                return provider_dir / f"{parts[2]}.yaml"
        else:
            # Simple provider
            return self.providers_dir / f"{provider}.yaml"
        
        return None


def main():
    """Main function for the refactoring analyzer."""
    parser = argparse.ArgumentParser(
        description="Analyze and refactor provider templates"
    )
    parser.add_argument(
        '--templates-dir',
        help='Directory containing template files'
    )
    parser.add_argument(
        '--output-dir',
        default='refactored_templates',
        help='Output directory for refactored templates'
    )
    parser.add_argument(
        '--format',
        choices=['json', 'yaml', 'text'],
        default='text',
        help='Output format for analysis report'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--save-refactored',
        action='store_true',
        help='Save refactored templates to output directory'
    )
    
    args = parser.parse_args()
    
    # Initialize analyzer
    analyzer = ProviderRefactoringAnalyzer(args.templates_dir)
    
    # Analyze providers
    print("Analyzing provider templates...")
    report = analyzer.analyze_all_providers()
    
    # Generate suggestions
    suggestions = analyzer.generate_refactoring_suggestions(report)
    
    # Output analysis report
    if args.format == 'json':
        print(json.dumps(suggestions, indent=2))
    elif args.format == 'yaml':
        print(yaml.dump(suggestions, default_flow_style=False))
    else:
        # Text format
        print("\n=== Provider Template Refactoring Analysis ===")
        print(f"Total providers analyzed: {suggestions['summary']['total_providers']}")
        print(f"Providers needing refactoring: {suggestions['summary']['providers_needing_refactoring']}")
        print(f"Total redundant keys found: {suggestions['summary']['total_redundant_keys']}")
        
        if 'average_potential_savings' in suggestions['summary']:
            print(f"Average potential savings: {suggestions['summary']['average_potential_savings']:.1f}%")
        
        print("\n--- Provider-Specific Suggestions ---")
        for provider, suggestion in suggestions['provider_suggestions'].items():
            print(f"\n{provider}:")
            print(f"  Quality score: {suggestion['current_quality_score']:.2f}")
            print(f"  Optimization potential: {suggestion['optimization_potential']:.1f}")
            print(f"  Redundant keys: {suggestion['redundant_keys']}")
            if 'potential_savings_percent' in suggestion:
                print(f"  Potential savings: {suggestion['potential_savings_percent']:.1f}%")
        
        print("\n--- Global Recommendations ---")
        for recommendation in suggestions['global_recommendations']:
            print(f"  • {recommendation}")
    
    # Save refactored templates if requested
    if args.save_refactored:
        print(f"\n{'=== Dry Run ===' if args.dry_run else '=== Saving Refactored Templates ==='}")
        summary = analyzer.save_refactored_templates(args.output_dir, args.dry_run)
        
        print(f"Refactored files: {len(summary['refactored_files'])}")
        print(f"Skipped files: {len(summary['skipped_files'])}")
        print(f"Errors: {len(summary['errors'])}")
        
        if summary['errors']:
            print("\nErrors:")
            for error in summary['errors']:
                print(f"  {error['provider']}: {error['error']}")


if __name__ == '__main__':
    main()