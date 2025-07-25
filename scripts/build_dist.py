#!/usr/bin/env python3
"""
Build script for creating PyPI distributions.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def run_command(cmd, check=True):
    """Run a shell command and return the result."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error running command: {cmd}")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        sys.exit(1)
    return result


def clean_build_dirs():
    """Clean up build directories."""
    dirs_to_clean = ["build", "dist", "*.egg-info"]
    for pattern in dirs_to_clean:
        for path in Path(".").glob(pattern):
            if path.is_dir():
                print(f"Removing directory: {path}")
                shutil.rmtree(path)
            elif path.is_file():
                print(f"Removing file: {path}")
                path.unlink()


def check_dependencies():
    """Check if required build dependencies are installed."""
    required_packages = ["build", "twine"]
    for package in required_packages:
        result = run_command(f"python -m pip show {package}", check=False)
        if result.returncode != 0:
            print(f"Installing {package}...")
            run_command(f"python -m pip install {package}")


def build_distributions():
    """Build wheel and source distributions."""
    print("Building distributions...")
    run_command("python -m build")
    
    # List built files
    dist_dir = Path("dist")
    if dist_dir.exists():
        print("\nBuilt distributions:")
        for file in dist_dir.iterdir():
            print(f"  {file.name} ({file.stat().st_size} bytes)")


def check_distributions():
    """Check the built distributions."""
    print("\nChecking distributions...")
    run_command("python -m twine check dist/*")


def main():
    """Main build process."""
    print("Starting build process for saidata-gen...")
    
    # Change to project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    os.chdir(project_root)
    
    # Clean previous builds
    clean_build_dirs()
    
    # Check dependencies
    check_dependencies()
    
    # Build distributions
    build_distributions()
    
    # Check distributions
    check_distributions()
    
    print("\nBuild process completed successfully!")
    print("To upload to PyPI:")
    print("  Test PyPI: python -m twine upload --repository testpypi dist/*")
    print("  Production: python -m twine upload dist/*")


if __name__ == "__main__":
    main()