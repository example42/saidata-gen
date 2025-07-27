#!/usr/bin/env python3
"""
Provider template migration tool.

This script migrates existing provider templates from the old full-configuration
format to the new override-only format.
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from saidata_gen.validation.config_validator import ConfigurationValidator


class ProviderTemplateMigrator:
    """
    Tool for migrating provider templates to override-only format.
    """
    
    def __init__(self, templates_dir: Optional[str] = None):
        """
        Initialize the migrator.
        
        Args:
            templates_dir: Directory containing template files
        """
        if templates_dir is None:
            self.templates_dir = project_root / "saidata_gen" / "templates"
        else:
            self.templates_dir = Path(templates_dir)
        
        self.validator = ConfigurationValidator(str(self.templates_dir))
        self.providers_dir = self.templates_dir / "providers"
        
        # Load defaults for comparison
        self.defaults = self._load_defaults()
    
    def _load_defaults(self) -> Dict[str, Any]:
        """Load the defaults template."""
        defaults_path = self.templates_dir / "defaults.yaml"
        
        try:
            with open(defaults_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            print(f"Warning: Defaults template not found at {defaults_path}")
            return {}
        except Exception as e:
            print(f"Warning: Failed to load defaults template: {e}")
            return {}
    
    def detect_migration_candidates(self) -> Dict[str, Any]:
        """
        Detect provider templates that need migration.
        
        Returns:
            Dictionary with migration candidates and analysis
        """
        candidates = {
            'needs_migration': [],
            'already_optimized': [],
            'unsupported_providers': [],
            'errors': [],
            'summary': {
                'total_providers': 0,
                'migration_candidates': 0,
                'optimization_potential': 0.0
            }
        }
        
        if not self.providers_dir.exists():
            return candidates
        
        # Check flat provider files
        for provider_file in self.providers_dir.glob("*.yaml"):
            provider_name = provider_file.stem
            candidates['summary']['total_providers'] += 1
            
            try:
                with open(provider_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                
                # Analyze the configuration
                analysis = self._analyze_provider_config(provider_name, config)
                
                if analysis['needs_migration']:
                    candidates['needs_migration'].append({
                        'provider': provider_name,
                        'file': str(provider_file),
                        'analysis': analysis
                    })
                    candidates['summary']['migration_candidates'] += 1
                    candidates['summary']['optimization_potential'] += analysis['optimization_potential']
                elif analysis['is_unsupported']:
                    candidates['unsupported_providers'].append({
                        'provider': provider_name,
                        'file': str(provider_file)
                    })
                else:
                    candidates['already_optimized'].append({
                        'provider': provider_name,
                        'file': str(provider_file)
                    })
                
            except Exception as e:
                candidates['errors'].append({
                    'provider': provider_name,
                    'file': str(provider_file),
                    'error': str(e)
                })
        
        # Check hierarchical provider directories
        for provider_dir in self.providers_dir.iterdir():
            if provider_dir.is_dir():
                self._analyze_hierarchical_provider(provider_dir, candidates)
        
        # Calculate average optimization potential
        if candidates['summary']['migration_candidates'] > 0:
            candidates['summary']['average_optimization_potential'] = (
                candidates['summary']['optimization_potential'] / 
                candidates['summary']['migration_candidates']
            )
        
        return candidates
    
    def _analyze_hierarchical_provider(self, provider_dir: Path, candidates: Dict[str, Any]):
        """
        Analyze hierarchical provider configurations.
        
        Args:
            provider_dir: Provider directory
            candidates: Candidates dictionary to update
        """
        # Analyze YAML files in the provider directory
        for config_file in provider_dir.glob("*.yaml"):
            provider_name = f"{provider_dir.name}/{config_file.stem}"
            candidates['summary']['total_providers'] += 1
            
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                
                analysis = self._analyze_provider_config(provider_name, config)
                
                if analysis['needs_migration']:
                    candidates['needs_migration'].append({
                        'provider': provider_name,
                        'file': str(config_file),
                        'analysis': analysis
                    })
                    candidates['summary']['migration_candidates'] += 1
                    candidates['summary']['optimization_potential'] += analysis['optimization_potential']
                elif analysis['is_unsupported']:
                    candidates['unsupported_providers'].append({
                        'provider': provider_name,
                        'file': str(config_file)
                    })
                else:
                    candidates['already_optimized'].append({
                        'provider': provider_name,
                        'file': str(config_file)
                    })
                
            except Exception as e:
                candidates['errors'].append({
                    'provider': provider_name,
                    'file': str(config_file),
                    'error': str(e)
                })
        
        # Analyze subdirectories (version-specific configs)
        for subdir in provider_dir.iterdir():
            if subdir.is_dir():
                for config_file in subdir.glob("*.yaml"):
                    provider_name = f"{provider_dir.name}/{subdir.name}/{config_file.stem}"
                    candidates['summary']['total_providers'] += 1
                    
                    try:
                        with open(config_file, 'r', encoding='utf-8') as f:
                            config = yaml.safe_load(f) or {}
                        
                        analysis = self._analyze_provider_config(provider_name, config)
                        
                        if analysis['needs_migration']:
                            candidates['needs_migration'].append({
                                'provider': provider_name,
                                'file': str(config_file),
                                'analysis': analysis
                            })
                            candidates['summary']['migration_candidates'] += 1
                            candidates['summary']['optimization_potential'] += analysis['optimization_potential']
                        elif analysis['is_unsupported']:
                            candidates['unsupported_providers'].append({
                                'provider': provider_name,
                                'file': str(config_file)
                            })
                        else:
                            candidates['already_optimized'].append({
                                'provider': provider_name,
                                'file': str(config_file)
                            })
                        
                    except Exception as e:
                        candidates['errors'].append({
                            'provider': provider_name,
                            'file': str(config_file),
                            'error': str(e)
                        })
    
    def _analyze_provider_config(self, provider: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a provider configuration to determine if it needs migration.
        
        Args:
            provider: Provider name
            config: Provider configuration
            
        Returns:
            Analysis results
        """
        # Check if it's an unsupported provider
        is_unsupported = config.get('supported') is False
        
        if is_unsupported:
            # For unsupported providers, check if it has unnecessary keys
            allowed_keys = {'version', 'supported'}
            extra_keys = set(config.keys()) - allowed_keys
            
            return {
                'needs_migration': len(extra_keys) > 0,
                'is_unsupported': True,
                'optimization_potential': len(extra_keys) / len(config) if config else 0,
                'redundant_keys': list(extra_keys),
                'migration_type': 'unsupported_cleanup'
            }
        
        # For supported providers, validate against defaults
        validation_result = self.validator.validate_provider_override(provider, config)
        
        needs_migration = (
            len(validation_result.redundant_keys) > 0 or
            validation_result.optimization_potential > 0.1
        )
        
        return {
            'needs_migration': needs_migration,
            'is_unsupported': False,
            'optimization_potential': validation_result.optimization_potential,
            'redundant_keys': validation_result.redundant_keys,
            'necessary_overrides': validation_result.necessary_overrides,
            'quality_score': validation_result.quality_score,
            'migration_type': 'override_optimization'
        }
    
    def migrate_provider_template(
        self, 
        provider_file: Path, 
        backup: bool = True,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Migrate a single provider template to override-only format.
        
        Args:
            provider_file: Path to provider template file
            backup: Whether to create a backup
            dry_run: Whether to perform a dry run
            
        Returns:
            Migration results
        """
        provider_name = self._extract_provider_name(provider_file)
        
        try:
            # Load original configuration
            with open(provider_file, 'r', encoding='utf-8') as f:
                original_config = yaml.safe_load(f) or {}
            
            # Analyze the configuration
            analysis = self._analyze_provider_config(provider_name, original_config)
            
            if not analysis['needs_migration']:
                return {
                    'provider': provider_name,
                    'file': str(provider_file),
                    'success': True,
                    'migrated': False,
                    'reason': 'No migration needed'
                }
            
            # Create migrated configuration
            if analysis['migration_type'] == 'unsupported_cleanup':
                # For unsupported providers, keep only version and supported
                migrated_config = {}
                if 'version' in original_config:
                    migrated_config['version'] = original_config['version']
                migrated_config['supported'] = False
            else:
                # For supported providers, create override-only configuration
                migrated_config = {}
                if 'version' in original_config:
                    migrated_config['version'] = original_config['version']
                migrated_config.update(analysis['necessary_overrides'])
            
            # Create backup if requested and not dry run
            backup_created = False
            if backup and not dry_run and original_config != migrated_config:
                backup_file = provider_file.with_suffix('.yaml.bak')
                shutil.copy2(provider_file, backup_file)
                backup_created = True
            
            # Write migrated configuration if not dry run
            if not dry_run and original_config != migrated_config:
                with open(provider_file, 'w', encoding='utf-8') as f:
                    yaml.dump(migrated_config, f, default_flow_style=False, sort_keys=False)
            
            return {
                'provider': provider_name,
                'file': str(provider_file),
                'success': True,
                'migrated': True,
                'migration_type': analysis['migration_type'],
                'original_keys': len(original_config),
                'migrated_keys': len(migrated_config),
                'removed_keys': analysis['redundant_keys'],
                'optimization_achieved': analysis['optimization_potential'],
                'backup_created': backup_created,
                'dry_run': dry_run
            }
            
        except Exception as e:
            return {
                'provider': provider_name,
                'file': str(provider_file),
                'success': False,
                'error': str(e)
            }
    
    def _extract_provider_name(self, provider_file: Path) -> str:
        """
        Extract provider name from file path, handling hierarchical structures.
        
        Args:
            provider_file: Path to provider file
            
        Returns:
            Provider name
        """
        # Get relative path from providers directory
        try:
            rel_path = provider_file.relative_to(self.providers_dir)
            parts = list(rel_path.parts)
            
            # Remove .yaml extension from the last part
            parts[-1] = parts[-1].replace('.yaml', '')
            
            return '/'.join(parts)
        except ValueError:
            # File is not under providers directory
            return provider_file.stem
    
    def migrate_all_templates(
        self, 
        backup: bool = True, 
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Migrate all provider templates that need migration.
        
        Args:
            backup: Whether to create backups
            dry_run: Whether to perform a dry run
            
        Returns:
            Migration summary
        """
        # First, detect migration candidates
        candidates = self.detect_migration_candidates()
        
        results = {
            'migrated': [],
            'skipped': [],
            'errors': [],
            'summary': {
                'total_candidates': len(candidates['needs_migration']),
                'successful_migrations': 0,
                'failed_migrations': 0,
                'total_keys_removed': 0,
                'backups_created': 0
            }
        }
        
        # Migrate each candidate
        for candidate in candidates['needs_migration']:
            provider_file = Path(candidate['file'])
            result = self.migrate_provider_template(provider_file, backup, dry_run)
            
            if result['success']:
                if result['migrated']:
                    results['migrated'].append(result)
                    results['summary']['successful_migrations'] += 1
                    results['summary']['total_keys_removed'] += len(result['removed_keys'])
                    
                    if result.get('backup_created', False):
                        results['summary']['backups_created'] += 1
                else:
                    results['skipped'].append(result)
            else:
                results['errors'].append(result)
                results['summary']['failed_migrations'] += 1
        
        return results
    
    def create_migration_report(self, results: Dict[str, Any]) -> str:
        """
        Create a detailed migration report.
        
        Args:
            results: Migration results
            
        Returns:
            Formatted migration report
        """
        report_lines = [
            "=== Provider Template Migration Report ===",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "Summary:",
            f"  Total migration candidates: {results['summary']['total_candidates']}",
            f"  Successful migrations: {results['summary']['successful_migrations']}",
            f"  Failed migrations: {results['summary']['failed_migrations']}",
            f"  Total keys removed: {results['summary']['total_keys_removed']}",
            f"  Backups created: {results['summary']['backups_created']}",
            ""
        ]
        
        if results['migrated']:
            report_lines.extend([
                "Migrated Templates:",
                ""
            ])
            
            for result in results['migrated']:
                report_lines.extend([
                    f"  {result['provider']}:",
                    f"    File: {result['file']}",
                    f"    Migration type: {result['migration_type']}",
                    f"    Keys: {result['original_keys']} → {result['migrated_keys']}",
                    f"    Removed keys: {result['removed_keys']}",
                    f"    Optimization: {result['optimization_achieved']:.1%}",
                    ""
                ])
        
        if results['errors']:
            report_lines.extend([
                "Migration Errors:",
                ""
            ])
            
            for error in results['errors']:
                report_lines.extend([
                    f"  {error['provider']}:",
                    f"    File: {error['file']}",
                    f"    Error: {error['error']}",
                    ""
                ])
        
        return "\n".join(report_lines)
    
    def rollback_migration(self, backup_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Rollback migration by restoring from backup files.
        
        Args:
            backup_dir: Directory containing backup files. If None, looks for .bak files.
            
        Returns:
            Rollback results
        """
        results = {
            'restored': [],
            'errors': [],
            'summary': {
                'backups_found': 0,
                'successful_restores': 0,
                'failed_restores': 0
            }
        }
        
        if backup_dir:
            # Restore from backup directory
            backup_path = Path(backup_dir)
            if not backup_path.exists():
                results['errors'].append({
                    'error': f"Backup directory {backup_dir} does not exist"
                })
                return results
            
            for backup_file in backup_path.glob("**/*.yaml"):
                results['summary']['backups_found'] += 1
                
                # Determine original file path
                original_file = self.providers_dir / backup_file.name
                
                try:
                    shutil.copy2(backup_file, original_file)
                    results['restored'].append({
                        'file': str(original_file),
                        'backup': str(backup_file),
                        'success': True
                    })
                    results['summary']['successful_restores'] += 1
                except Exception as e:
                    results['errors'].append({
                        'file': str(original_file),
                        'backup': str(backup_file),
                        'error': str(e)
                    })
                    results['summary']['failed_restores'] += 1
        else:
            # Restore from .bak files
            for backup_file in self.providers_dir.glob("**/*.yaml.bak"):
                results['summary']['backups_found'] += 1
                
                # Determine original file path
                original_file = backup_file.with_suffix('')
                
                try:
                    shutil.copy2(backup_file, original_file)
                    os.remove(backup_file)  # Remove backup file after successful restore
                    
                    results['restored'].append({
                        'file': str(original_file),
                        'backup': str(backup_file),
                        'success': True
                    })
                    results['summary']['successful_restores'] += 1
                except Exception as e:
                    results['errors'].append({
                        'file': str(original_file),
                        'backup': str(backup_file),
                        'error': str(e)
                    })
                    results['summary']['failed_restores'] += 1
        
        return results


def main():
    """Main function for the template migrator."""
    parser = argparse.ArgumentParser(
        description="Migrate provider templates to override-only format"
    )
    parser.add_argument(
        '--templates-dir',
        help='Directory containing template files'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Do not create backup files'
    )
    parser.add_argument(
        '--detect-only',
        action='store_true',
        help='Only detect migration candidates without migrating'
    )
    parser.add_argument(
        '--rollback',
        action='store_true',
        help='Rollback migration by restoring from backup files'
    )
    parser.add_argument(
        '--backup-dir',
        help='Directory containing backup files for rollback'
    )
    parser.add_argument(
        '--report-file',
        help='Save migration report to file'
    )
    parser.add_argument(
        '--format',
        choices=['text', 'json', 'yaml'],
        default='text',
        help='Output format'
    )
    
    args = parser.parse_args()
    
    # Initialize migrator
    migrator = ProviderTemplateMigrator(args.templates_dir)
    
    # Handle rollback
    if args.rollback:
        print("Rolling back migration...")
        results = migrator.rollback_migration(args.backup_dir)
        
        print(f"Backups found: {results['summary']['backups_found']}")
        print(f"Successful restores: {results['summary']['successful_restores']}")
        print(f"Failed restores: {results['summary']['failed_restores']}")
        
        if results['errors']:
            print("\nErrors:")
            for error in results['errors']:
                print(f"  {error.get('file', 'Unknown')}: {error['error']}")
        
        return
    
    # Detect migration candidates
    print("Detecting migration candidates...")
    candidates = migrator.detect_migration_candidates()
    
    if args.format == 'json':
        print(json.dumps(candidates, indent=2))
    elif args.format == 'yaml':
        print(yaml.dump(candidates, default_flow_style=False))
    else:
        print(f"Total providers: {candidates['summary']['total_providers']}")
        print(f"Migration candidates: {candidates['summary']['migration_candidates']}")
        print(f"Already optimized: {len(candidates['already_optimized'])}")
        print(f"Unsupported providers: {len(candidates['unsupported_providers'])}")
        
        if 'average_optimization_potential' in candidates['summary']:
            print(f"Average optimization potential: {candidates['summary']['average_optimization_potential']:.1%}")
        
        if candidates['needs_migration']:
            print(f"\nProviders needing migration ({len(candidates['needs_migration'])}):")
            for candidate in candidates['needs_migration']:
                analysis = candidate['analysis']
                print(f"  {candidate['provider']}: {analysis['optimization_potential']:.1%} optimization potential")
    
    # Stop here if only detecting
    if args.detect_only:
        return
    
    # Perform migration
    if candidates['summary']['migration_candidates'] > 0:
        print(f"\n{'Analyzing' if args.dry_run else 'Migrating'} {candidates['summary']['migration_candidates']} templates...")
        
        results = migrator.migrate_all_templates(not args.no_backup, args.dry_run)
        
        # Create and display report
        report = migrator.create_migration_report(results)
        print(report)
        
        # Save report to file if requested
        if args.report_file:
            with open(args.report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"\nReport saved to: {args.report_file}")
    else:
        print("\nNo templates need migration.")


if __name__ == '__main__':
    main()