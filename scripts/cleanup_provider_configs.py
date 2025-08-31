#!/usr/bin/env python3
"""
Provider configuration cleanup tool.

This script automatically removes redundant keys from provider configurations
and converts them to the override-only format.
"""

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from saidata_gen.validation.config_validator import ConfigurationValidator


class ProviderConfigCleaner:
    """
    Tool for cleaning up provider configurations by removing redundant keys.
    """
    
    def __init__(self, templates_dir: Optional[str] = None):
        """
        Initialize the cleaner.
        
        Args:
            templates_dir: Directory containing template files
        """
        if templates_dir is None:
            self.templates_dir = project_root / "saidata_gen" / "templates"
        else:
            self.templates_dir = Path(templates_dir)
        
        self.validator = ConfigurationValidator(str(self.templates_dir))
        self.providers_dir = self.templates_dir / "providers"
    
    def cleanup_provider_file(self, provider_file: Path, backup: bool = True) -> Dict[str, Any]:
        """
        Clean up a single provider configuration file.
        
        Args:
            provider_file: Path to provider configuration file
            backup: Whether to create a backup before modifying
            
        Returns:
            Dictionary with cleanup results
        """
        provider_name = provider_file.stem
        
        try:
            # Load original configuration
            with open(provider_file, 'r', encoding='utf-8') as f:
                original_config = yaml.safe_load(f) or {}
            
            # Validate and get suggestions
            result = self.validator.validate_provider_override(provider_name, original_config)
            
            # Create cleaned configuration
            cleaned_config = {}
            
            # Always keep version if present
            if 'version' in original_config:
                cleaned_config['version'] = original_config['version']
            
            # Add necessary overrides
            cleaned_config.update(result.necessary_overrides)
            
            # Create backup if requested
            if backup and original_config != cleaned_config:
                backup_file = provider_file.with_suffix('.yaml.bak')
                shutil.copy2(provider_file, backup_file)
            
            # Write cleaned configuration
            if original_config != cleaned_config:
                with open(provider_file, 'w', encoding='utf-8') as f:
                    yaml.dump(cleaned_config, f, default_flow_style=False, sort_keys=False)
            
            return {
                'provider': provider_name,
                'file': str(provider_file),
                'success': True,
                'changes_made': original_config != cleaned_config,
                'original_keys': len(original_config),
                'cleaned_keys': len(cleaned_config),
                'removed_keys': result.redundant_keys,
                'backup_created': backup and original_config != cleaned_config
            }
            
        except Exception as e:
            return {
                'provider': provider_name,
                'file': str(provider_file),
                'success': False,
                'error': str(e)
            }
    
    def cleanup_all_providers(self, backup: bool = True, dry_run: bool = False) -> Dict[str, Any]:
        """
        Clean up all provider configuration files.
        
        Args:
            backup: Whether to create backups before modifying
            dry_run: If True, only show what would be done
            
        Returns:
            Summary of cleanup results
        """
        results = {
            'processed': [],
            'errors': [],
            'summary': {
                'total_files': 0,
                'files_changed': 0,
                'total_keys_removed': 0,
                'backups_created': 0
            }
        }
        
        # Process flat provider files
        if self.providers_dir.exists():
            for provider_file in self.providers_dir.glob("*.yaml"):
                results['summary']['total_files'] += 1
                
                if dry_run:
                    # Just analyze without making changes
                    provider_name = provider_file.stem
                    try:
                        with open(provider_file, 'r', encoding='utf-8') as f:
                            config = yaml.safe_load(f) or {}
                        
                        validation_result = self.validator.validate_provider_override(provider_name, config)
                        
                        result = {
                            'provider': provider_name,
                            'file': str(provider_file),
                            'success': True,
                            'changes_made': len(validation_result.redundant_keys) > 0,
                            'original_keys': len(config),
                            'cleaned_keys': len(validation_result.necessary_overrides) + (1 if 'version' in config else 0),
                            'removed_keys': validation_result.redundant_keys,
                            'dry_run': True
                        }
                        
                        results['processed'].append(result)
                        
                        if result['changes_made']:
                            results['summary']['files_changed'] += 1
                            results['summary']['total_keys_removed'] += len(result['removed_keys'])
                        
                    except Exception as e:
                        results['errors'].append({
                            'provider': provider_name,
                            'file': str(provider_file),
                            'error': str(e)
                        })
                else:
                    # Actually clean up the file
                    result = self.cleanup_provider_file(provider_file, backup)
                    
                    if result['success']:
                        results['processed'].append(result)
                        
                        if result['changes_made']:
                            results['summary']['files_changed'] += 1
                            results['summary']['total_keys_removed'] += len(result['removed_keys'])
                        
                        if result.get('backup_created', False):
                            results['summary']['backups_created'] += 1
                    else:
                        results['errors'].append(result)
            
            # Process hierarchical provider directories
            for provider_dir in self.providers_dir.iterdir():
                if provider_dir.is_dir():
                    self._cleanup_hierarchical_provider(provider_dir, results, backup, dry_run)
        
        return results
    
    def _cleanup_hierarchical_provider(
        self, 
        provider_dir: Path, 
        results: Dict[str, Any], 
        backup: bool, 
        dry_run: bool
    ):
        """
        Clean up hierarchical provider configurations.
        
        Args:
            provider_dir: Provider directory
            results: Results dictionary to update
            backup: Whether to create backups
            dry_run: Whether this is a dry run
        """
        # Process YAML files in the provider directory
        for config_file in provider_dir.glob("*.yaml"):
            results['summary']['total_files'] += 1
            
            if dry_run:
                # Analyze without changes
                provider_name = f"{provider_dir.name}/{config_file.stem}"
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f) or {}
                    
                    validation_result = self.validator.validate_provider_override(provider_name, config)
                    
                    result = {
                        'provider': provider_name,
                        'file': str(config_file),
                        'success': True,
                        'changes_made': len(validation_result.redundant_keys) > 0,
                        'original_keys': len(config),
                        'cleaned_keys': len(validation_result.necessary_overrides) + (1 if 'version' in config else 0),
                        'removed_keys': validation_result.redundant_keys,
                        'dry_run': True
                    }
                    
                    results['processed'].append(result)
                    
                    if result['changes_made']:
                        results['summary']['files_changed'] += 1
                        results['summary']['total_keys_removed'] += len(result['removed_keys'])
                
                except Exception as e:
                    results['errors'].append({
                        'provider': provider_name,
                        'file': str(config_file),
                        'error': str(e)
                    })
            else:
                # Actually clean up
                result = self.cleanup_provider_file(config_file, backup)
                result['provider'] = f"{provider_dir.name}/{config_file.stem}"
                
                if result['success']:
                    results['processed'].append(result)
                    
                    if result['changes_made']:
                        results['summary']['files_changed'] += 1
                        results['summary']['total_keys_removed'] += len(result['removed_keys'])
                    
                    if result.get('backup_created', False):
                        results['summary']['backups_created'] += 1
                else:
                    results['errors'].append(result)
        
        # Process subdirectories (version-specific configs)
        for subdir in provider_dir.iterdir():
            if subdir.is_dir():
                for config_file in subdir.glob("*.yaml"):
                    results['summary']['total_files'] += 1
                    
                    if dry_run:
                        # Analyze without changes
                        provider_name = f"{provider_dir.name}/{subdir.name}/{config_file.stem}"
                        try:
                            with open(config_file, 'r', encoding='utf-8') as f:
                                config = yaml.safe_load(f) or {}
                            
                            validation_result = self.validator.validate_provider_override(provider_name, config)
                            
                            result = {
                                'provider': provider_name,
                                'file': str(config_file),
                                'success': True,
                                'changes_made': len(validation_result.redundant_keys) > 0,
                                'original_keys': len(config),
                                'cleaned_keys': len(validation_result.necessary_overrides) + (1 if 'version' in config else 0),
                                'removed_keys': validation_result.redundant_keys,
                                'dry_run': True
                            }
                            
                            results['processed'].append(result)
                            
                            if result['changes_made']:
                                results['summary']['files_changed'] += 1
                                results['summary']['total_keys_removed'] += len(result['removed_keys'])
                        
                        except Exception as e:
                            results['errors'].append({
                                'provider': provider_name,
                                'file': str(config_file),
                                'error': str(e)
                            })
                    else:
                        # Actually clean up
                        result = self.cleanup_provider_file(config_file, backup)
                        result['provider'] = f"{provider_dir.name}/{subdir.name}/{config_file.stem}"
                        
                        if result['success']:
                            results['processed'].append(result)
                            
                            if result['changes_made']:
                                results['summary']['files_changed'] += 1
                                results['summary']['total_keys_removed'] += len(result['removed_keys'])
                            
                            if result.get('backup_created', False):
                                results['summary']['backups_created'] += 1
                        else:
                            results['errors'].append(result)
    
    def validate_all_templates_exist(self) -> Dict[str, Any]:
        """
        Validate that all supported providers have necessary templates.
        
        Returns:
            Validation results
        """
        # List of expected providers based on the fetcher module
        expected_providers = [
            'apt', 'brew', 'winget', 'choco', 'scoop', 'yum', 'dnf', 'zypper',
            'pacman', 'apk', 'snap', 'flatpak', 'docker', 'helm', 'npm', 'pypi',
            'cargo', 'gem', 'composer', 'nuget', 'maven', 'gradle', 'go',
            'nix', 'nixpkgs', 'guix', 'spack', 'portage', 'emerge', 'xbps',
            'slackpkg', 'opkg', 'pkg'
        ]
        
        results = {
            'missing_templates': [],
            'existing_templates': [],
            'hierarchical_templates': [],
            'summary': {
                'expected_providers': len(expected_providers),
                'missing_count': 0,
                'existing_count': 0,
                'hierarchical_count': 0
            }
        }
        
        for provider in expected_providers:
            # Check for flat template
            flat_template = self.providers_dir / f"{provider}.yaml"
            
            # Check for hierarchical template
            hierarchical_dir = self.providers_dir / provider
            
            if flat_template.exists():
                results['existing_templates'].append(provider)
                results['summary']['existing_count'] += 1
            elif hierarchical_dir.exists() and hierarchical_dir.is_dir():
                results['hierarchical_templates'].append(provider)
                results['summary']['hierarchical_count'] += 1
            else:
                results['missing_templates'].append(provider)
                results['summary']['missing_count'] += 1
        
        return results


def main():
    """Main function for the configuration cleaner."""
    parser = argparse.ArgumentParser(
        description="Clean up provider configurations by removing redundant keys"
    )
    parser.add_argument(
        '--templates-dir',
        help='Directory containing template files'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Do not create backup files'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--validate-templates',
        action='store_true',
        help='Validate that all expected provider templates exist'
    )
    parser.add_argument(
        '--provider',
        help='Clean up only the specified provider'
    )
    
    args = parser.parse_args()
    
    # Initialize cleaner
    cleaner = ProviderConfigCleaner(args.templates_dir)
    
    # Validate templates if requested
    if args.validate_templates:
        print("Validating provider template coverage...")
        validation_results = cleaner.validate_all_templates_exist()
        
        print(f"Expected providers: {validation_results['summary']['expected_providers']}")
        print(f"Existing flat templates: {validation_results['summary']['existing_count']}")
        print(f"Hierarchical templates: {validation_results['summary']['hierarchical_count']}")
        print(f"Missing templates: {validation_results['summary']['missing_count']}")
        
        if validation_results['missing_templates']:
            print("\nMissing templates:")
            for provider in validation_results['missing_templates']:
                print(f"  • {provider}")
        
        if validation_results['hierarchical_templates']:
            print("\nHierarchical templates:")
            for provider in validation_results['hierarchical_templates']:
                print(f"  • {provider}")
        
        return
    
    # Clean up configurations
    if args.provider:
        # Clean up specific provider
        provider_file = cleaner.providers_dir / f"{args.provider}.yaml"
        if not provider_file.exists():
            print(f"Error: Provider file {provider_file} not found")
            sys.exit(1)
        
        print(f"{'Analyzing' if args.dry_run else 'Cleaning up'} provider: {args.provider}")
        result = cleaner.cleanup_provider_file(provider_file, not args.no_backup)
        
        if result['success']:
            print(f"  Original keys: {result['original_keys']}")
            print(f"  Cleaned keys: {result['cleaned_keys']}")
            print(f"  Removed keys: {result['removed_keys']}")
            print(f"  Changes made: {result['changes_made']}")
            if result.get('backup_created'):
                print(f"  Backup created: {result['file']}.bak")
        else:
            print(f"  Error: {result['error']}")
    else:
        # Clean up all providers
        print(f"{'Analyzing' if args.dry_run else 'Cleaning up'} all provider configurations...")
        results = cleaner.cleanup_all_providers(not args.no_backup, args.dry_run)
        
        print(f"\nSummary:")
        print(f"  Total files processed: {results['summary']['total_files']}")
        print(f"  Files that would be changed: {results['summary']['files_changed']}")
        print(f"  Total keys that would be removed: {results['summary']['total_keys_removed']}")
        
        if not args.dry_run:
            print(f"  Backups created: {results['summary']['backups_created']}")
        
        if results['errors']:
            print(f"\nErrors ({len(results['errors'])}):")
            for error in results['errors']:
                print(f"  {error['provider']}: {error['error']}")
        
        # Show detailed results for files with changes
        changed_files = [r for r in results['processed'] if r['changes_made']]
        if changed_files:
            print(f"\nFiles with changes ({len(changed_files)}):")
            for result in changed_files:
                print(f"  {result['provider']}:")
                print(f"    Keys: {result['original_keys']} → {result['cleaned_keys']}")
                print(f"    Removed: {result['removed_keys']}")


if __name__ == '__main__':
    main()