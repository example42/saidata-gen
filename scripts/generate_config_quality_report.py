#!/usr/bin/env python3
"""
Configuration quality reporting tool.

This script generates comprehensive reports on provider configuration quality,
coverage statistics, consistency analysis, and performance metrics.
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from saidata_gen.validation.config_validator import (
    ConfigurationValidator, ConfigurationValidationReport
)
from saidata_gen.generator.templates import TemplateEngine


class ConfigurationQualityReporter:
    """
    Comprehensive reporter for configuration quality and coverage analysis.
    """
    
    def __init__(self, templates_dir: Optional[str] = None):
        """
        Initialize the quality reporter.
        
        Args:
            templates_dir: Directory containing template files
        """
        if templates_dir is None:
            self.templates_dir = project_root / "saidata_gen" / "templates"
        else:
            self.templates_dir = Path(templates_dir)
        
        self.validator = ConfigurationValidator(str(self.templates_dir))
        self.template_engine = TemplateEngine(str(self.templates_dir))
        self.providers_dir = self.templates_dir / "providers"
        
        # Define expected providers based on fetcher capabilities
        self.expected_providers = [
            'apt', 'brew', 'winget', 'choco', 'scoop', 'yum', 'dnf', 'zypper',
            'pacman', 'apk', 'snap', 'flatpak', 'docker', 'helm', 'npm', 'pypi',
            'cargo', 'gem', 'composer', 'nuget', 'maven', 'gradle', 'go',
            'nix', 'nixpkgs', 'guix', 'spack', 'portage', 'emerge', 'xbps',
            'slackpkg', 'opkg', 'pkg'
        ]
    
    def generate_comprehensive_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive quality report.
        
        Returns:
            Complete quality report
        """
        report = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'templates_dir': str(self.templates_dir),
                'total_expected_providers': len(self.expected_providers)
            },
            'coverage_analysis': self._analyze_provider_coverage(),
            'quality_analysis': self._analyze_configuration_quality(),
            'consistency_analysis': self._analyze_configuration_consistency(),
            'performance_metrics': self._measure_performance_metrics(),
            'recommendations': [],
            'summary': {}
        }
        
        # Generate summary and recommendations
        report['summary'] = self._generate_summary(report)
        report['recommendations'] = self._generate_recommendations(report)
        
        return report
    
    def _analyze_provider_coverage(self) -> Dict[str, Any]:
        """
        Analyze provider template coverage.
        
        Returns:
            Coverage analysis results
        """
        coverage = {
            'existing_providers': [],
            'missing_providers': [],
            'hierarchical_providers': {},
            'coverage_statistics': {
                'total_expected': len(self.expected_providers),
                'total_existing': 0,
                'total_missing': 0,
                'coverage_percentage': 0.0,
                'hierarchical_count': 0
            }
        }
        
        for provider in self.expected_providers:
            # Check for flat template
            flat_template = self.providers_dir / f"{provider}.yaml"
            
            # Check for hierarchical template
            hierarchical_dir = self.providers_dir / provider
            
            if flat_template.exists():
                coverage['existing_providers'].append({
                    'provider': provider,
                    'type': 'flat',
                    'file': str(flat_template)
                })
                coverage['coverage_statistics']['total_existing'] += 1
                
            elif hierarchical_dir.exists() and hierarchical_dir.is_dir():
                # Analyze hierarchical structure
                hierarchical_info = self._analyze_hierarchical_provider(hierarchical_dir)
                coverage['hierarchical_providers'][provider] = hierarchical_info
                coverage['coverage_statistics']['total_existing'] += 1
                coverage['coverage_statistics']['hierarchical_count'] += 1
                
            else:
                coverage['missing_providers'].append(provider)
                coverage['coverage_statistics']['total_missing'] += 1
        
        # Calculate coverage percentage
        coverage['coverage_statistics']['coverage_percentage'] = (
            coverage['coverage_statistics']['total_existing'] / 
            coverage['coverage_statistics']['total_expected'] * 100
        )
        
        return coverage
    
    def _analyze_hierarchical_provider(self, provider_dir: Path) -> Dict[str, Any]:
        """
        Analyze hierarchical provider structure.
        
        Args:
            provider_dir: Provider directory
            
        Returns:
            Hierarchical provider analysis
        """
        info = {
            'provider': provider_dir.name,
            'type': 'hierarchical',
            'base_dir': str(provider_dir),
            'configurations': [],
            'structure': {
                'os_specific': [],
                'version_specific': {},
                'total_configs': 0
            }
        }
        
        # Analyze YAML files in the provider directory
        for config_file in provider_dir.glob("*.yaml"):
            config_info = {
                'name': config_file.stem,
                'file': str(config_file),
                'level': 'os' if config_file.stem != 'default' else 'base'
            }
            info['configurations'].append(config_info)
            info['structure']['total_configs'] += 1
            
            if config_file.stem != 'default':
                info['structure']['os_specific'].append(config_file.stem)
        
        # Analyze subdirectories (version-specific configs)
        for subdir in provider_dir.iterdir():
            if subdir.is_dir():
                version_configs = []
                for config_file in subdir.glob("*.yaml"):
                    config_info = {
                        'name': f"{subdir.name}/{config_file.stem}",
                        'file': str(config_file),
                        'level': 'version'
                    }
                    info['configurations'].append(config_info)
                    version_configs.append(config_file.stem)
                    info['structure']['total_configs'] += 1
                
                info['structure']['version_specific'][subdir.name] = version_configs
        
        return info
    
    def _analyze_configuration_quality(self) -> Dict[str, Any]:
        """
        Analyze configuration quality across all providers.
        
        Returns:
            Quality analysis results
        """
        # Load all provider configurations
        provider_configs = {}
        
        # Load flat providers
        if self.providers_dir.exists():
            for provider_file in self.providers_dir.glob("*.yaml"):
                provider_name = provider_file.stem
                try:
                    with open(provider_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f) or {}
                    provider_configs[provider_name] = config
                except Exception as e:
                    print(f"Warning: Failed to load {provider_file}: {e}")
            
            # Load hierarchical providers
            for provider_dir in self.providers_dir.iterdir():
                if provider_dir.is_dir():
                    self._load_hierarchical_configs(provider_dir, provider_configs)
        
        # Validate configurations
        validation_report = self.validator.validate_configuration_consistency(provider_configs)
        
        # Analyze quality distribution
        quality_distribution = self._analyze_quality_distribution(validation_report)
        
        return {
            'validation_report': validation_report,
            'quality_distribution': quality_distribution,
            'provider_rankings': self._rank_providers_by_quality(validation_report),
            'common_issues': self._identify_common_issues(validation_report)
        }
    
    def _load_hierarchical_configs(self, provider_dir: Path, provider_configs: Dict[str, Dict[str, Any]]):
        """
        Load hierarchical provider configurations.
        
        Args:
            provider_dir: Provider directory
            provider_configs: Dictionary to populate
        """
        provider_name = provider_dir.name
        
        # Load configurations from the directory
        for config_file in provider_dir.glob("*.yaml"):
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
    
    def _analyze_quality_distribution(self, validation_report: ConfigurationValidationReport) -> Dict[str, Any]:
        """
        Analyze quality score distribution.
        
        Args:
            validation_report: Validation report
            
        Returns:
            Quality distribution analysis
        """
        quality_scores = [
            result.quality_score for result in validation_report.provider_results.values()
        ]
        
        if not quality_scores:
            return {
                'average': 0.0,
                'median': 0.0,
                'min': 0.0,
                'max': 0.0,
                'distribution': {}
            }
        
        quality_scores.sort()
        
        # Calculate distribution buckets
        distribution = {
            'excellent (0.9-1.0)': len([s for s in quality_scores if s >= 0.9]),
            'good (0.75-0.89)': len([s for s in quality_scores if 0.75 <= s < 0.9]),
            'fair (0.6-0.74)': len([s for s in quality_scores if 0.6 <= s < 0.75]),
            'poor (0.4-0.59)': len([s for s in quality_scores if 0.4 <= s < 0.6]),
            'very poor (<0.4)': len([s for s in quality_scores if s < 0.4])
        }
        
        return {
            'average': sum(quality_scores) / len(quality_scores),
            'median': quality_scores[len(quality_scores) // 2],
            'min': min(quality_scores),
            'max': max(quality_scores),
            'distribution': distribution
        }
    
    def _rank_providers_by_quality(self, validation_report: ConfigurationValidationReport) -> List[Dict[str, Any]]:
        """
        Rank providers by quality score.
        
        Args:
            validation_report: Validation report
            
        Returns:
            List of providers ranked by quality
        """
        rankings = []
        
        for provider, result in validation_report.provider_results.items():
            rankings.append({
                'provider': provider,
                'quality_score': result.quality_score,
                'optimization_potential': result.optimization_potential,
                'redundant_keys_count': len(result.redundant_keys),
                'issues_count': len(result.issues)
            })
        
        # Sort by quality score (descending)
        rankings.sort(key=lambda x: x['quality_score'], reverse=True)
        
        return rankings
    
    def _identify_common_issues(self, validation_report: ConfigurationValidationReport) -> Dict[str, Any]:
        """
        Identify common issues across providers.
        
        Args:
            validation_report: Validation report
            
        Returns:
            Common issues analysis
        """
        issue_counts = defaultdict(int)
        redundant_key_counts = defaultdict(int)
        
        for result in validation_report.provider_results.values():
            # Count issue types
            for issue in result.issues:
                issue_counts[issue.message] += 1
            
            # Count redundant keys
            for key in result.redundant_keys:
                redundant_key_counts[key] += 1
        
        return {
            'most_common_issues': dict(sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            'most_common_redundant_keys': dict(sorted(redundant_key_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            'total_unique_issues': len(issue_counts),
            'total_unique_redundant_keys': len(redundant_key_counts)
        }
    
    def _analyze_configuration_consistency(self) -> Dict[str, Any]:
        """
        Analyze configuration consistency across providers.
        
        Returns:
            Consistency analysis results
        """
        consistency = {
            'version_consistency': self._analyze_version_consistency(),
            'structure_consistency': self._analyze_structure_consistency(),
            'naming_consistency': self._analyze_naming_consistency(),
            'platform_consistency': self._analyze_platform_consistency()
        }
        
        return consistency
    
    def _analyze_version_consistency(self) -> Dict[str, Any]:
        """Analyze version specification consistency."""
        version_usage = defaultdict(list)
        
        # Collect version information from all providers
        if self.providers_dir.exists():
            for provider_file in self.providers_dir.glob("**/*.yaml"):
                try:
                    with open(provider_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f) or {}
                    
                    version = config.get('version', 'not_specified')
                    provider_name = self._extract_provider_name_from_path(provider_file)
                    version_usage[version].append(provider_name)
                    
                except Exception:
                    continue
        
        return {
            'version_distribution': dict(version_usage),
            'most_common_version': max(version_usage.keys(), key=lambda k: len(version_usage[k])) if version_usage else None,
            'inconsistent_versions': len(version_usage) > 1
        }
    
    def _analyze_structure_consistency(self) -> Dict[str, Any]:
        """Analyze configuration structure consistency."""
        structure_patterns = defaultdict(int)
        
        if self.providers_dir.exists():
            for provider_file in self.providers_dir.glob("**/*.yaml"):
                try:
                    with open(provider_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f) or {}
                    
                    # Create structure signature
                    structure_sig = self._create_structure_signature(config)
                    structure_patterns[structure_sig] += 1
                    
                except Exception:
                    continue
        
        return {
            'unique_structures': len(structure_patterns),
            'most_common_structure': max(structure_patterns.keys(), key=structure_patterns.get) if structure_patterns else None,
            'structure_distribution': dict(structure_patterns)
        }
    
    def _analyze_naming_consistency(self) -> Dict[str, Any]:
        """Analyze naming convention consistency."""
        naming_patterns = {
            'package_name_patterns': defaultdict(int),
            'key_naming_patterns': defaultdict(int)
        }
        
        if self.providers_dir.exists():
            for provider_file in self.providers_dir.glob("**/*.yaml"):
                try:
                    with open(provider_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f) or {}
                    
                    # Analyze package naming patterns
                    if 'packages' in config and 'default' in config['packages']:
                        pkg_config = config['packages']['default']
                        if 'name' in pkg_config:
                            name_pattern = self._classify_name_pattern(pkg_config['name'])
                            naming_patterns['package_name_patterns'][name_pattern] += 1
                    
                    # Analyze key naming patterns
                    for key in config.keys():
                        key_pattern = self._classify_key_pattern(key)
                        naming_patterns['key_naming_patterns'][key_pattern] += 1
                    
                except Exception:
                    continue
        
        return naming_patterns
    
    def _analyze_platform_consistency(self) -> Dict[str, Any]:
        """Analyze platform specification consistency."""
        platform_usage = defaultdict(list)
        
        if self.providers_dir.exists():
            for provider_file in self.providers_dir.glob("**/*.yaml"):
                try:
                    with open(provider_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f) or {}
                    
                    platforms = config.get('platforms', [])
                    provider_name = self._extract_provider_name_from_path(provider_file)
                    
                    if platforms:
                        platform_key = ','.join(sorted(platforms))
                        platform_usage[platform_key].append(provider_name)
                    else:
                        platform_usage['not_specified'].append(provider_name)
                    
                except Exception:
                    continue
        
        return {
            'platform_distribution': dict(platform_usage),
            'providers_without_platforms': len(platform_usage.get('not_specified', [])),
            'unique_platform_combinations': len([k for k in platform_usage.keys() if k != 'not_specified'])
        }
    
    def _measure_performance_metrics(self) -> Dict[str, Any]:
        """
        Measure template processing and merging performance.
        
        Returns:
            Performance metrics
        """
        metrics = {
            'template_loading_time': 0.0,
            'validation_time': 0.0,
            'merge_operation_time': 0.0,
            'total_processing_time': 0.0,
            'memory_usage_estimate': 0,
            'file_sizes': {}
        }
        
        start_time = time.time()
        
        # Measure template loading time
        load_start = time.time()
        provider_configs = {}
        
        if self.providers_dir.exists():
            for provider_file in self.providers_dir.glob("**/*.yaml"):
                try:
                    with open(provider_file, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f) or {}
                    
                    provider_name = self._extract_provider_name_from_path(provider_file)
                    provider_configs[provider_name] = config
                    
                    # Record file size
                    metrics['file_sizes'][provider_name] = provider_file.stat().st_size
                    
                except Exception:
                    continue
        
        metrics['template_loading_time'] = time.time() - load_start
        
        # Measure validation time
        validation_start = time.time()
        validation_report = self.validator.validate_configuration_consistency(provider_configs)
        metrics['validation_time'] = time.time() - validation_start
        
        # Measure merge operation time (simulate)
        merge_start = time.time()
        for provider, config in list(provider_configs.items())[:5]:  # Sample 5 providers
            try:
                # Simulate merge operation
                self.template_engine._deep_merge(self.validator.defaults, config)
            except Exception:
                continue
        metrics['merge_operation_time'] = time.time() - merge_start
        
        metrics['total_processing_time'] = time.time() - start_time
        
        # Estimate memory usage
        metrics['memory_usage_estimate'] = sum(
            len(str(config)) for config in provider_configs.values()
        )
        
        return metrics
    
    def _extract_provider_name_from_path(self, provider_file: Path) -> str:
        """Extract provider name from file path."""
        try:
            rel_path = provider_file.relative_to(self.providers_dir)
            parts = list(rel_path.parts)
            parts[-1] = parts[-1].replace('.yaml', '')
            return '/'.join(parts)
        except ValueError:
            return provider_file.stem
    
    def _create_structure_signature(self, config: Dict[str, Any]) -> str:
        """Create a signature representing the configuration structure."""
        def get_structure(obj, depth=0):
            if depth > 3:  # Limit depth to avoid infinite recursion
                return "..."
            
            if isinstance(obj, dict):
                return "{" + ",".join(sorted(f"{k}:{get_structure(v, depth+1)}" for k, v in obj.items())) + "}"
            elif isinstance(obj, list):
                return f"[{len(obj)}]"
            else:
                return type(obj).__name__
        
        return get_structure(config)
    
    def _classify_name_pattern(self, name: str) -> str:
        """Classify package name pattern."""
        if '{{' in name and '}}' in name:
            return 'templated'
        elif '-' in name:
            return 'hyphenated'
        elif '_' in name:
            return 'underscored'
        elif name.islower():
            return 'lowercase'
        elif name.isupper():
            return 'uppercase'
        else:
            return 'mixed_case'
    
    def _classify_key_pattern(self, key: str) -> str:
        """Classify configuration key pattern."""
        if '_' in key:
            return 'snake_case'
        elif key.islower():
            return 'lowercase'
        elif any(c.isupper() for c in key):
            return 'camelCase'
        else:
            return 'other'
    
    def _generate_summary(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """Generate report summary."""
        coverage = report['coverage_analysis']['coverage_statistics']
        quality = report['quality_analysis']['quality_distribution']
        
        return {
            'provider_coverage': f"{coverage['coverage_percentage']:.1f}%",
            'missing_providers': coverage['total_missing'],
            'average_quality_score': f"{quality['average']:.2f}",
            'providers_needing_attention': len([
                p for p in report['quality_analysis']['provider_rankings']
                if p['quality_score'] < 0.7
            ]),
            'total_redundant_keys': sum(
                p['redundant_keys_count'] for p in report['quality_analysis']['provider_rankings']
            ),
            'performance_summary': {
                'total_processing_time': f"{report['performance_metrics']['total_processing_time']:.2f}s",
                'average_file_size': f"{sum(report['performance_metrics']['file_sizes'].values()) / max(1, len(report['performance_metrics']['file_sizes'])):.0f} bytes"
            }
        }
    
    def _generate_recommendations(self, report: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        # Coverage recommendations
        coverage = report['coverage_analysis']['coverage_statistics']
        if coverage['total_missing'] > 0:
            recommendations.append(
                f"Create templates for {coverage['total_missing']} missing providers to achieve 100% coverage"
            )
        
        # Quality recommendations
        quality = report['quality_analysis']['quality_distribution']
        if quality['average'] < 0.8:
            recommendations.append(
                f"Improve overall quality score from {quality['average']:.2f} by addressing redundant configurations"
            )
        
        poor_quality_count = quality['distribution'].get('poor (0.4-0.59)', 0) + quality['distribution'].get('very poor (<0.4)', 0)
        if poor_quality_count > 0:
            recommendations.append(
                f"Prioritize refactoring {poor_quality_count} providers with poor quality scores"
            )
        
        # Consistency recommendations
        version_consistency = report['consistency_analysis']['version_consistency']
        if version_consistency['inconsistent_versions']:
            recommendations.append(
                "Standardize version specifications across all provider templates"
            )
        
        # Performance recommendations
        performance = report['performance_metrics']
        if performance['total_processing_time'] > 5.0:
            recommendations.append(
                "Consider optimizing template processing for better performance"
            )
        
        return recommendations
    
    def format_report(self, report: Dict[str, Any], format_type: str = 'text') -> str:
        """
        Format the report for display.
        
        Args:
            report: Report data
            format_type: Format type ('text', 'json', 'yaml')
            
        Returns:
            Formatted report string
        """
        if format_type == 'json':
            return json.dumps(report, indent=2, default=str)
        elif format_type == 'yaml':
            return yaml.dump(report, default_flow_style=False)
        else:
            return self._format_text_report(report)
    
    def _format_text_report(self, report: Dict[str, Any]) -> str:
        """Format report as human-readable text."""
        lines = [
            "=== Configuration Quality Report ===",
            f"Generated: {report['metadata']['generated_at']}",
            f"Templates Directory: {report['metadata']['templates_dir']}",
            ""
        ]
        
        # Summary section (always included)
        if 'summary' in report:
            lines.extend([
                "SUMMARY",
                "-------",
                f"Provider Coverage: {report['summary']['provider_coverage']}",
                f"Missing Providers: {report['summary']['missing_providers']}",
                f"Average Quality Score: {report['summary']['average_quality_score']}",
                f"Providers Needing Attention: {report['summary']['providers_needing_attention']}",
                f"Total Redundant Keys: {report['summary']['total_redundant_keys']}",
                ""
            ])
        
        # Coverage analysis section
        if 'coverage_analysis' in report:
            lines.extend([
                "COVERAGE ANALYSIS",
                "----------------"
            ])
            
            coverage = report['coverage_analysis']
            lines.extend([
                f"Total Expected Providers: {coverage['coverage_statistics']['total_expected']}",
                f"Existing Providers: {coverage['coverage_statistics']['total_existing']}",
                f"Missing Providers: {coverage['coverage_statistics']['total_missing']}",
                f"Hierarchical Providers: {coverage['coverage_statistics']['hierarchical_count']}"
            ])
            
            if coverage['missing_providers']:
                lines.extend([
                    "",
                    "Missing Providers:",
                    "  " + ", ".join(coverage['missing_providers'])
                ])
            
            lines.append("")
        
        # Quality analysis section
        if 'quality_analysis' in report:
            lines.extend([
                "QUALITY ANALYSIS",
                "---------------"
            ])
            
            quality = report['quality_analysis']['quality_distribution']
            lines.extend([
                f"Average Quality Score: {quality['average']:.2f}",
                f"Quality Range: {quality['min']:.2f} - {quality['max']:.2f}",
                "",
                "Quality Distribution:"
            ])
            
            for category, count in quality['distribution'].items():
                lines.append(f"  {category}: {count}")
            
            # Top and bottom performers
            rankings = report['quality_analysis']['provider_rankings']
            if rankings:
                lines.extend([
                    "",
                    "Top 5 Performers:"
                ])
                for provider in rankings[:5]:
                    lines.append(f"  {provider['provider']}: {provider['quality_score']:.2f}")
                
                if len(rankings) > 5:
                    lines.extend([
                        "",
                        "Bottom 5 Performers:"
                    ])
                    for provider in rankings[-5:]:
                        lines.append(f"  {provider['provider']}: {provider['quality_score']:.2f}")
            
            # Common issues
            common_issues = report['quality_analysis']['common_issues']
            if common_issues['most_common_issues']:
                lines.extend([
                    "",
                    "Most Common Issues:"
                ])
                for issue, count in list(common_issues['most_common_issues'].items())[:5]:
                    lines.append(f"  {issue}: {count} providers")
            
            lines.append("")
        
        # Consistency analysis section
        if 'consistency_analysis' in report:
            lines.extend([
                "CONSISTENCY ANALYSIS",
                "-------------------"
            ])
            
            consistency = report['consistency_analysis']
            
            # Version consistency
            version_info = consistency['version_consistency']
            lines.extend([
                f"Version Consistency: {'✓' if not version_info['inconsistent_versions'] else '✗'}",
                f"Most Common Version: {version_info['most_common_version']}"
            ])
            
            # Structure consistency
            structure_info = consistency['structure_consistency']
            lines.extend([
                f"Unique Structures: {structure_info['unique_structures']}"
            ])
            
            # Platform consistency
            platform_info = consistency['platform_consistency']
            lines.extend([
                f"Providers Without Platforms: {platform_info['providers_without_platforms']}",
                f"Unique Platform Combinations: {platform_info['unique_platform_combinations']}"
            ])
            
            lines.append("")
        
        # Performance metrics section
        if 'performance_metrics' in report:
            performance = report['performance_metrics']
            lines.extend([
                "PERFORMANCE METRICS",
                "------------------",
                f"Template Loading Time: {performance['template_loading_time']:.2f}s",
                f"Validation Time: {performance['validation_time']:.2f}s",
                f"Total Processing Time: {performance['total_processing_time']:.2f}s",
                ""
            ])
        
        # Recommendations section (always included if present)
        if 'recommendations' in report and report['recommendations']:
            lines.extend([
                "RECOMMENDATIONS",
                "--------------"
            ])
            for i, rec in enumerate(report['recommendations'], 1):
                lines.append(f"{i}. {rec}")
        
        return "\n".join(lines)


def main():
    """Main function for the quality reporter."""
    parser = argparse.ArgumentParser(
        description="Generate configuration quality reports"
    )
    parser.add_argument(
        '--templates-dir',
        help='Directory containing template files'
    )
    parser.add_argument(
        '--format',
        choices=['text', 'json', 'yaml'],
        default='text',
        help='Output format'
    )
    parser.add_argument(
        '--output-file',
        help='Save report to file'
    )
    parser.add_argument(
        '--section',
        choices=['coverage', 'quality', 'consistency', 'performance', 'all'],
        default='all',
        help='Report section to generate'
    )
    
    args = parser.parse_args()
    
    # Initialize reporter
    reporter = ConfigurationQualityReporter(args.templates_dir)
    
    # Generate report
    print("Generating configuration quality report...")
    report = reporter.generate_comprehensive_report()
    
    # Filter report sections if requested
    if args.section != 'all':
        filtered_report = {
            'metadata': report['metadata'],
            'summary': report['summary'],
            'recommendations': report['recommendations']
        }
        
        if args.section == 'coverage':
            filtered_report['coverage_analysis'] = report['coverage_analysis']
        elif args.section == 'quality':
            filtered_report['quality_analysis'] = report['quality_analysis']
        elif args.section == 'consistency':
            filtered_report['consistency_analysis'] = report['consistency_analysis']
        elif args.section == 'performance':
            filtered_report['performance_metrics'] = report['performance_metrics']
        
        report = filtered_report
    
    # Format and output report
    formatted_report = reporter.format_report(report, args.format)
    
    if args.output_file:
        with open(args.output_file, 'w', encoding='utf-8') as f:
            f.write(formatted_report)
        print(f"Report saved to: {args.output_file}")
    else:
        print(formatted_report)


if __name__ == '__main__':
    main()