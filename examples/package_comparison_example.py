#!/usr/bin/env python3
"""
Package Comparison Example
Demonstrates how to compare software packages across different providers and repositories
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict
import argparse

@dataclass
class PackageInfo:
    """Represents package information from a specific provider"""
    name: str
    provider: str
    version: Optional[str] = None
    description: Optional[str] = None
    license: Optional[str] = None
    homepage: Optional[str] = None
    install_command: Optional[str] = None
    size: Optional[str] = None
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []

@dataclass
class ComparisonResult:
    """Results of comparing packages across providers"""
    software_name: str
    providers: List[str]
    common_fields: Dict[str, Any]
    differences: Dict[str, Dict[str, Any]]
    recommendations: List[str]
    confidence_score: float

class PackageComparator:
    """Compares software packages across different providers"""
    
    def __init__(self):
        self.provider_priorities = {
            'apt': 10,
            'brew': 9,
            'pypi': 8,
            'npm': 8,
            'docker': 7,
            'snap': 6,
            'flatpak': 6,
            'winget': 8,
            'scoop': 7,
            'choco': 6
        }
    
    def load_metadata_file(self, file_path: Path) -> Dict[str, Any]:
        """Load a saidata YAML metadata file"""
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    
    def extract_package_info(self, metadata: Dict[str, Any]) -> List[PackageInfo]:
        """Extract package information from metadata"""
        packages = []
        
        if 'packages' not in metadata:
            return packages
        
        for provider, config in metadata['packages'].items():
            if not isinstance(config, dict):
                continue
            
            package_info = PackageInfo(
                name=config.get('name', ''),
                provider=provider,
                version=config.get('version'),
                description=metadata.get('description'),
                license=metadata.get('license'),
                homepage=metadata.get('urls', {}).get('website'),
                install_command=self._generate_install_command(provider, config),
                size=config.get('size'),
                dependencies=config.get('dependencies', [])
            )
            packages.append(package_info)
        
        return packages
    
    def _generate_install_command(self, provider: str, config: Dict[str, Any]) -> str:
        """Generate installation command for a package"""
        package_name = config.get('name', '')
        install_options = config.get('install_options', '')
        
        commands = {
            'apt': f"sudo apt install {package_name} {install_options}".strip(),
            'brew': f"brew install {package_name} {install_options}".strip(),
            'pypi': f"pip install {package_name} {install_options}".strip(),
            'npm': f"npm install {package_name} {install_options}".strip(),
            'docker': f"docker pull {package_name}",
            'snap': f"sudo snap install {package_name} {install_options}".strip(),
            'flatpak': f"flatpak install {package_name}",
            'winget': f"winget install {package_name}",
            'scoop': f"scoop install {package_name}",
            'choco': f"choco install {package_name} {install_options}".strip()
        }
        
        return commands.get(provider, f"{provider} install {package_name}")
    
    def compare_packages(self, packages: List[PackageInfo]) -> ComparisonResult:
        """Compare packages across providers"""
        if not packages:
            return ComparisonResult("unknown", [], {}, {}, [], 0.0)
        
        software_name = packages[0].name
        providers = [pkg.provider for pkg in packages]
        
        # Find common fields
        common_fields = self._find_common_fields(packages)
        
        # Find differences
        differences = self._find_differences(packages)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(packages)
        
        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(packages)
        
        return ComparisonResult(
            software_name=software_name,
            providers=providers,
            common_fields=common_fields,
            differences=differences,
            recommendations=recommendations,
            confidence_score=confidence_score
        )
    
    def _find_common_fields(self, packages: List[PackageInfo]) -> Dict[str, Any]:
        """Find fields that are common across all packages"""
        common_fields = {}
        
        if not packages:
            return common_fields
        
        # Check each field
        fields_to_check = ['description', 'license', 'homepage']
        
        for field in fields_to_check:
            values = [getattr(pkg, field) for pkg in packages if getattr(pkg, field)]
            if values and len(set(values)) == 1:
                common_fields[field] = values[0]
        
        return common_fields
    
    def _find_differences(self, packages: List[PackageInfo]) -> Dict[str, Dict[str, Any]]:
        """Find differences between packages"""
        differences = defaultdict(dict)
        
        fields_to_compare = ['name', 'version', 'size', 'install_command']
        
        for field in fields_to_compare:
            values = {}
            for pkg in packages:
                value = getattr(pkg, field)
                if value:
                    values[pkg.provider] = value
            
            if len(set(values.values())) > 1:  # Different values exist
                differences[field] = values
        
        return dict(differences)
    
    def _generate_recommendations(self, packages: List[PackageInfo]) -> List[str]:
        """Generate recommendations based on package comparison"""
        recommendations = []
        
        if not packages:
            return recommendations
        
        # Recommend based on provider priority
        sorted_packages = sorted(packages, 
                                key=lambda p: self.provider_priorities.get(p.provider, 0), 
                                reverse=True)
        
        best_provider = sorted_packages[0].provider
        recommendations.append(f"Recommended provider: {best_provider}")
        
        # Check for version differences
        versions = [pkg.version for pkg in packages if pkg.version]
        if len(set(versions)) > 1:
            recommendations.append("Version differences detected - verify compatibility requirements")
        
        # Check for size differences
        sizes = [pkg.size for pkg in packages if pkg.size]
        if len(set(sizes)) > 1:
            recommendations.append("Package sizes vary across providers - consider storage constraints")
        
        # Platform-specific recommendations
        platform_providers = {
            'linux': ['apt', 'snap', 'flatpak'],
            'macos': ['brew'],
            'windows': ['winget', 'scoop', 'choco'],
            'cross_platform': ['docker', 'pypi', 'npm']
        }
        
        available_platforms = []
        for platform, providers in platform_providers.items():
            if any(pkg.provider in providers for pkg in packages):
                available_platforms.append(platform)
        
        if available_platforms:
            recommendations.append(f"Available on platforms: {', '.join(available_platforms)}")
        
        return recommendations
    
    def _calculate_confidence_score(self, packages: List[PackageInfo]) -> float:
        """Calculate confidence score for the comparison"""
        if not packages:
            return 0.0
        
        score = 0.0
        
        # Base score for having packages
        score += 0.3
        
        # Bonus for multiple providers
        score += min(len(packages) * 0.1, 0.3)
        
        # Bonus for having common fields
        common_count = sum(1 for pkg in packages if pkg.description and pkg.license)
        score += min(common_count * 0.1, 0.2)
        
        # Bonus for high-priority providers
        high_priority_count = sum(1 for pkg in packages 
                                 if self.provider_priorities.get(pkg.provider, 0) >= 8)
        score += min(high_priority_count * 0.1, 0.2)
        
        return min(score, 1.0)
    
    def export_comparison_report(self, comparison: ComparisonResult, output_file: Path):
        """Export comparison report to JSON"""
        report = {
            'software_name': comparison.software_name,
            'comparison_summary': {
                'providers_count': len(comparison.providers),
                'providers': comparison.providers,
                'confidence_score': comparison.confidence_score
            },
            'common_fields': comparison.common_fields,
            'differences': comparison.differences,
            'recommendations': comparison.recommendations,
            'detailed_comparison': asdict(comparison)
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
    
    def generate_comparison_table(self, packages: List[PackageInfo]) -> str:
        """Generate a comparison table in markdown format"""
        if not packages:
            return "No packages to compare"
        
        # Table headers
        headers = ['Provider', 'Package Name', 'Version', 'Install Command', 'Size']
        
        # Create table rows
        rows = []
        for pkg in packages:
            row = [
                pkg.provider,
                pkg.name or 'N/A',
                pkg.version or 'N/A',
                pkg.install_command or 'N/A',
                pkg.size or 'N/A'
            ]
            rows.append(row)
        
        # Format as markdown table
        table_lines = []
        
        # Header row
        table_lines.append('| ' + ' | '.join(headers) + ' |')
        table_lines.append('|' + '|'.join(['---'] * len(headers)) + '|')
        
        # Data rows
        for row in rows:
            table_lines.append('| ' + ' | '.join(row) + ' |')
        
        return '\n'.join(table_lines)

def main():
    parser = argparse.ArgumentParser(description="Compare software packages across providers")
    parser.add_argument("--metadata-dir", required=True, help="Directory containing metadata files")
    parser.add_argument("--software", help="Specific software to compare (optional)")
    parser.add_argument("--output-dir", default="./comparison-output", help="Output directory")
    parser.add_argument("--format", choices=["json", "markdown", "both"], default="both", help="Output format")
    
    args = parser.parse_args()
    
    metadata_dir = Path(args.metadata_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    comparator = PackageComparator()
    
    # Find metadata files
    if args.software:
        metadata_files = [metadata_dir / f"{args.software}.yaml"]
    else:
        metadata_files = list(metadata_dir.glob("*.yaml"))
    
    print(f"Found {len(metadata_files)} metadata files to process")
    
    # Process each metadata file
    for metadata_file in metadata_files:
        if not metadata_file.exists():
            print(f"Warning: {metadata_file} not found")
            continue
        
        print(f"Processing: {metadata_file.name}")
        
        try:
            # Load metadata
            metadata = comparator.load_metadata_file(metadata_file)
            
            # Extract package information
            packages = comparator.extract_package_info(metadata)
            
            if not packages:
                print(f"  No package information found in {metadata_file.name}")
                continue
            
            print(f"  Found {len(packages)} packages across {len(set(pkg.provider for pkg in packages))} providers")
            
            # Compare packages
            comparison = comparator.compare_packages(packages)
            
            # Generate outputs
            software_name = metadata_file.stem
            
            if args.format in ["json", "both"]:
                json_output = output_dir / f"{software_name}_comparison.json"
                comparator.export_comparison_report(comparison, json_output)
                print(f"  JSON report: {json_output}")
            
            if args.format in ["markdown", "both"]:
                markdown_output = output_dir / f"{software_name}_comparison.md"
                
                with open(markdown_output, 'w') as f:
                    f.write(f"# Package Comparison: {software_name}\n\n")
                    f.write(f"**Confidence Score:** {comparison.confidence_score:.2f}\n\n")
                    
                    f.write("## Provider Comparison\n\n")
                    f.write(comparator.generate_comparison_table(packages))
                    f.write("\n\n")
                    
                    if comparison.common_fields:
                        f.write("## Common Fields\n\n")
                        for field, value in comparison.common_fields.items():
                            f.write(f"- **{field.title()}:** {value}\n")
                        f.write("\n")
                    
                    if comparison.differences:
                        f.write("## Differences\n\n")
                        for field, values in comparison.differences.items():
                            f.write(f"### {field.title()}\n\n")
                            for provider, value in values.items():
                                f.write(f"- **{provider}:** {value}\n")
                            f.write("\n")
                    
                    if comparison.recommendations:
                        f.write("## Recommendations\n\n")
                        for rec in comparison.recommendations:
                            f.write(f"- {rec}\n")
                
                print(f"  Markdown report: {markdown_output}")
            
            print(f"  Confidence score: {comparison.confidence_score:.2f}")
            
        except Exception as e:
            print(f"  Error processing {metadata_file.name}: {e}")
    
    print("Package comparison completed!")

if __name__ == "__main__":
    main()