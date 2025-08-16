#!/usr/bin/env python3
"""
Script to migrate fetchers to use the centralized repository URL manager.

This script helps identify hardcoded URLs in fetchers and provides guidance
on migrating them to use the repository URL manager.
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def find_hardcoded_urls(file_path: Path) -> List[Tuple[int, str, str]]:
    """
    Find hardcoded URLs in a Python file.
    
    Args:
        file_path: Path to the Python file.
    
    Returns:
        List of tuples (line_number, line_content, url).
    """
    url_pattern = re.compile(r'https?://[a-zA-Z0-9.-]+[^\s\'"]*')
    hardcoded_urls = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                # Skip comments and docstrings
                if line.strip().startswith('#') or '"""' in line or "'''" in line:
                    continue
                
                matches = url_pattern.findall(line)
                for match in matches:
                    # Clean up the URL (remove trailing punctuation)
                    url = match.rstrip('",\')')
                    hardcoded_urls.append((line_num, line.strip(), url))
    
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    
    return hardcoded_urls


def analyze_fetcher_files() -> Dict[str, List[Tuple[int, str, str]]]:
    """
    Analyze all fetcher files for hardcoded URLs.
    
    Returns:
        Dictionary mapping file paths to lists of hardcoded URLs.
    """
    fetcher_dir = project_root / "saidata_gen" / "fetcher"
    results = {}
    
    for file_path in fetcher_dir.glob("*.py"):
        if file_path.name in ["__init__.py", "base.py", "error_handler.py", "rpm_utils.py"]:
            continue
        
        hardcoded_urls = find_hardcoded_urls(file_path)
        if hardcoded_urls:
            results[str(file_path)] = hardcoded_urls
    
    return results


def generate_migration_report():
    """Generate a migration report for fetchers."""
    print("=" * 80)
    print("FETCHER URL MIGRATION REPORT")
    print("=" * 80)
    print()
    
    results = analyze_fetcher_files()
    
    if not results:
        print("✅ No hardcoded URLs found in fetcher files!")
        return
    
    total_urls = sum(len(urls) for urls in results.values())
    print(f"Found {total_urls} hardcoded URLs in {len(results)} fetcher files:")
    print()
    
    for file_path, urls in results.items():
        file_name = Path(file_path).name
        provider_name = file_name.replace('.py', '')
        
        print(f"📁 {file_name} ({provider_name} provider)")
        print("-" * 60)
        
        for line_num, line_content, url in urls:
            print(f"  Line {line_num:3d}: {url}")
            print(f"           {line_content[:70]}{'...' if len(line_content) > 70 else ''}")
        
        print()
        print(f"  🔧 Migration steps for {provider_name}:")
        print(f"     1. Add import: from saidata_gen.core.repository_url_manager import get_repository_url_manager")
        print(f"     2. Initialize URL manager in __init__: self.url_manager = get_repository_url_manager()")
        print(f"     3. Replace hardcoded URLs with: self.url_manager.get_primary_url('{provider_name}', ...)")
        print(f"     4. Add fallback handling with: self.url_manager.get_fallback_urls('{provider_name}', ...)")
        print(f"     5. Update repository_urls.yaml with {provider_name} configuration")
        print()
        print("-" * 60)
        print()


def check_url_manager_coverage():
    """Check which providers are covered in the repository_urls.yaml file."""
    print("=" * 80)
    print("URL MANAGER COVERAGE REPORT")
    print("=" * 80)
    print()
    
    # Load the repository URLs configuration
    try:
        import yaml
        url_config_path = project_root / "saidata_gen" / "templates" / "repository_urls.yaml"
        
        with open(url_config_path, 'r', encoding='utf-8') as f:
            url_config = yaml.safe_load(f)
        
        configured_providers = set(url_config.keys()) - {'version'}
        
        # Find all fetcher files
        fetcher_dir = project_root / "saidata_gen" / "fetcher"
        fetcher_files = [f.stem for f in fetcher_dir.glob("*.py") 
                        if f.name not in ["__init__.py", "base.py", "error_handler.py", "rpm_utils.py"]]
        
        print(f"📊 Configured providers in repository_urls.yaml: {len(configured_providers)}")
        print(f"📊 Fetcher files found: {len(fetcher_files)}")
        print()
        
        # Check coverage
        missing_providers = set(fetcher_files) - configured_providers
        extra_providers = configured_providers - set(fetcher_files)
        
        if missing_providers:
            print("❌ Providers missing from repository_urls.yaml:")
            for provider in sorted(missing_providers):
                print(f"   - {provider}")
            print()
        
        if extra_providers:
            print("ℹ️  Providers in repository_urls.yaml without fetcher files:")
            for provider in sorted(extra_providers):
                print(f"   - {provider}")
            print()
        
        covered_providers = configured_providers & set(fetcher_files)
        if covered_providers:
            print(f"✅ Providers with URL configuration ({len(covered_providers)}):")
            for provider in sorted(covered_providers):
                print(f"   - {provider}")
            print()
        
        coverage_percentage = (len(covered_providers) / len(fetcher_files)) * 100
        print(f"📈 Coverage: {coverage_percentage:.1f}% ({len(covered_providers)}/{len(fetcher_files)})")
        
    except Exception as e:
        print(f"❌ Error checking URL manager coverage: {e}")


def generate_template_for_provider(provider_name: str):
    """Generate a template configuration for a provider."""
    print(f"=" * 80)
    print(f"TEMPLATE CONFIGURATION FOR {provider_name.upper()}")
    print(f"=" * 80)
    print()
    
    template = f"""# {provider_name.title()} - Add to repository_urls.yaml
{provider_name}:
  default:
    primary_url: "https://example.com/api/v1"
    fallback_urls:
      - "https://backup.example.com/api/v1"
  
  # OS-specific overrides (if needed)
  os:
    linux:
      primary_url: "https://linux.example.com/api/v1"
    
    macos:
      primary_url: "https://macos.example.com/api/v1"
    
    windows:
      primary_url: "https://windows.example.com/api/v1"
      
      # Version-specific overrides (if needed)
      versions:
        "10":
          primary_url: "https://win10.example.com/api/v1"
        "11":
          primary_url: "https://win11.example.com/api/v1"
"""
    
    print(template)


def main():
    """Main function."""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "analyze":
            generate_migration_report()
        elif command == "coverage":
            check_url_manager_coverage()
        elif command == "template":
            if len(sys.argv) > 2:
                generate_template_for_provider(sys.argv[2])
            else:
                print("Usage: python migrate_fetchers_to_url_manager.py template <provider_name>")
        else:
            print(f"Unknown command: {command}")
            print("Available commands: analyze, coverage, template")
    else:
        print("Fetcher URL Migration Tool")
        print("=" * 40)
        print()
        print("Commands:")
        print("  analyze   - Find hardcoded URLs in fetcher files")
        print("  coverage  - Check URL manager coverage")
        print("  template  - Generate template for a provider")
        print()
        print("Usage:")
        print("  python migrate_fetchers_to_url_manager.py analyze")
        print("  python migrate_fetchers_to_url_manager.py coverage")
        print("  python migrate_fetchers_to_url_manager.py template <provider_name>")


if __name__ == "__main__":
    main()