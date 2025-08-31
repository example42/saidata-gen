#!/usr/bin/env python3
"""
Script to list packages from package manager metadata in ~/.saidata-gen/cache

Usage: python list_packages.py <package_manager_name>
"""

import json
import os
import sys
import glob
from pathlib import Path


def get_cache_dir():
    """Get the cache directory path"""
    return Path.home() / ".saidata-gen" / "cache"


def list_packages_from_json(json_file_path, package_manager):
    """Extract package names from a JSON metadata file"""
    packages = set()
    
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if package_manager in ['brew']:
            # For brew, package names are top-level keys
            packages.update(data.keys())
        
        elif package_manager in ['npm']:
            # For npm, packages are in objects array
            if 'objects' in data:
                for obj in data['objects']:
                    if 'package' in obj and 'name' in obj['package']:
                        packages.add(obj['package']['name'])
        
        elif package_manager in ['pypi']:
            # For PyPI, check if it's a list or dict structure
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and 'name' in item:
                        packages.add(item['name'])
            elif isinstance(data, dict):
                if 'packages' in data:
                    packages.update(data['packages'])
                else:
                    packages.update(data.keys())
        
        elif package_manager in ['apt', 'dnf', 'yum', 'pacman', 'zypper']:
            # For system package managers, try common structures
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        # Try common package name fields
                        for field in ['name', 'package', 'Package']:
                            if field in item:
                                packages.add(item[field])
                                break
                    elif isinstance(item, str):
                        packages.add(item)
            elif isinstance(data, dict):
                if 'packages' in data:
                    if isinstance(data['packages'], list):
                        packages.update(data['packages'])
                    elif isinstance(data['packages'], dict):
                        packages.update(data['packages'].keys())
                else:
                    packages.update(data.keys())
        
        else:
            # Generic fallback - try to extract package names from common structures
            if isinstance(data, dict):
                # If it's a dict, try keys first
                if all(isinstance(k, str) for k in data.keys()):
                    packages.update(data.keys())
                # Try common package list fields
                for field in ['packages', 'items', 'objects', 'results']:
                    if field in data:
                        if isinstance(data[field], list):
                            for item in data[field]:
                                if isinstance(item, dict):
                                    for name_field in ['name', 'package', 'title']:
                                        if name_field in item:
                                            packages.add(item[name_field])
                                            break
                                elif isinstance(item, str):
                                    packages.add(item)
                        break
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        for name_field in ['name', 'package', 'title']:
                            if name_field in item:
                                packages.add(item[name_field])
                                break
                    elif isinstance(item, str):
                        packages.add(item)
    
    except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
        print(f"Error processing {json_file_path}: {e}", file=sys.stderr)
    
    return packages


def main():
    if len(sys.argv) != 2:
        print("Usage: python list_packages.py <package_manager_name>", file=sys.stderr)
        sys.exit(1)
    
    package_manager = sys.argv[1].lower()
    cache_dir = get_cache_dir()
    
    # Check if the package manager directory exists
    pm_dir = cache_dir / package_manager
    if not pm_dir.exists():
        print(f"Package manager '{package_manager}' not found in cache", file=sys.stderr)
        print(f"Available package managers:", file=sys.stderr)
        for item in cache_dir.iterdir():
            if item.is_dir():
                print(f"  {item.name}", file=sys.stderr)
        sys.exit(1)
    
    # Find all JSON files in the package manager directory
    json_files = list(pm_dir.glob("*.json"))
    if not json_files:
        print(f"No JSON metadata files found for '{package_manager}'", file=sys.stderr)
        sys.exit(1)
    
    # Collect all packages from all JSON files
    all_packages = set()
    for json_file in json_files:
        packages = list_packages_from_json(json_file, package_manager)
        all_packages.update(packages)
    
    # Output packages, one per line, sorted
    for package in sorted(all_packages):
        print(package)


if __name__ == "__main__":
    main()
