#!/usr/bin/env python3
"""
Version management script for saidata-gen.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Tuple


def get_current_version() -> str:
    """Get the current version from pyproject.toml."""
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        raise FileNotFoundError("pyproject.toml not found")
    
    content = pyproject_path.read_text()
    match = re.search(r'version = "([^"]+)"', content)
    if not match:
        raise ValueError("Version not found in pyproject.toml")
    
    return match.group(1)


def update_version(new_version: str) -> None:
    """Update version in pyproject.toml."""
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()
    
    # Update version in pyproject.toml
    updated_content = re.sub(
        r'version = "[^"]+"',
        f'version = "{new_version}"',
        content
    )
    pyproject_path.write_text(updated_content)
    
    # Update version in __init__.py
    init_path = Path("saidata_gen/__init__.py")
    if init_path.exists():
        init_content = init_path.read_text()
        updated_init = re.sub(
            r'__version__ = "[^"]+"',
            f'__version__ = "{new_version}"',
            init_content
        )
        init_path.write_text(updated_init)


def parse_version(version: str) -> Tuple[int, int, int]:
    """Parse a semantic version string."""
    match = re.match(r'^(\d+)\.(\d+)\.(\d+)(?:-.*)?$', version)
    if not match:
        raise ValueError(f"Invalid version format: {version}")
    
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def bump_version(current_version: str, bump_type: str) -> str:
    """Bump version based on type (major, minor, patch)."""
    major, minor, patch = parse_version(current_version)
    
    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")


def main():
    """Main version management function."""
    parser = argparse.ArgumentParser(description="Manage saidata-gen version")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Show current version
    subparsers.add_parser("show", help="Show current version")
    
    # Set specific version
    set_parser = subparsers.add_parser("set", help="Set specific version")
    set_parser.add_argument("version", help="Version to set (e.g., 1.0.0)")
    
    # Bump version
    bump_parser = subparsers.add_parser("bump", help="Bump version")
    bump_parser.add_argument(
        "type", 
        choices=["major", "minor", "patch"],
        help="Type of version bump"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        current_version = get_current_version()
        
        if args.command == "show":
            print(f"Current version: {current_version}")
        
        elif args.command == "set":
            # Validate version format
            parse_version(args.version)
            update_version(args.version)
            print(f"Version updated from {current_version} to {args.version}")
        
        elif args.command == "bump":
            new_version = bump_version(current_version, args.type)
            update_version(new_version)
            print(f"Version bumped from {current_version} to {new_version}")
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()