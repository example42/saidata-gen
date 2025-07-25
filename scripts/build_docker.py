#!/usr/bin/env python3
"""
Docker build script for saidata-gen.
"""

import argparse
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


def get_version():
    """Get version from pyproject.toml."""
    import re
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()
    match = re.search(r'version = "([^"]+)"', content)
    if not match:
        raise ValueError("Version not found in pyproject.toml")
    return match.group(1)


def build_docker_image(tag=None, platform=None, push=False, latest=False):
    """Build Docker image."""
    version = get_version()
    
    if not tag:
        tag = f"saidata/saidata-gen:{version}"
    
    # Build command
    cmd_parts = ["docker", "build"]
    
    if platform:
        cmd_parts.extend(["--platform", platform])
    
    cmd_parts.extend(["-t", tag])
    
    if latest:
        latest_tag = tag.split(':')[0] + ':latest'
        cmd_parts.extend(["-t", latest_tag])
    
    cmd_parts.append(".")
    
    cmd = " ".join(cmd_parts)
    run_command(cmd)
    
    if push:
        run_command(f"docker push {tag}")
        if latest:
            run_command(f"docker push {latest_tag}")
    
    return tag


def test_docker_image(tag):
    """Test the built Docker image."""
    print(f"Testing Docker image: {tag}")
    
    # Test basic functionality
    test_commands = [
        f"docker run --rm {tag} --version",
        f"docker run --rm {tag} --help",
        f"docker run --rm {tag} config init --help",
    ]
    
    for cmd in test_commands:
        print(f"Testing: {cmd}")
        result = run_command(cmd, check=False)
        if result.returncode != 0:
            print(f"Test failed: {cmd}")
            print(f"Output: {result.stdout}")
            print(f"Error: {result.stderr}")
            return False
    
    print("All Docker tests passed!")
    return True


def main():
    """Main Docker build function."""
    parser = argparse.ArgumentParser(description="Build Docker image for saidata-gen")
    parser.add_argument("--tag", help="Docker image tag")
    parser.add_argument("--platform", help="Target platform (e.g., linux/amd64,linux/arm64)")
    parser.add_argument("--push", action="store_true", help="Push image to registry")
    parser.add_argument("--latest", action="store_true", help="Also tag as latest")
    parser.add_argument("--test", action="store_true", help="Test the built image")
    parser.add_argument("--multi-arch", action="store_true", help="Build multi-architecture image")
    
    args = parser.parse_args()
    
    # Change to project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    os.chdir(project_root)
    
    try:
        if args.multi_arch:
            # Build multi-architecture image
            version = get_version()
            tag = args.tag or f"saidata/saidata-gen:{version}"
            
            # Create and use buildx builder
            run_command("docker buildx create --use --name saidata-builder", check=False)
            
            cmd_parts = [
                "docker", "buildx", "build",
                "--platform", "linux/amd64,linux/arm64",
                "-t", tag
            ]
            
            if args.latest:
                latest_tag = tag.split(':')[0] + ':latest'
                cmd_parts.extend(["-t", latest_tag])
            
            if args.push:
                cmd_parts.append("--push")
            else:
                cmd_parts.append("--load")
            
            cmd_parts.append(".")
            
            cmd = " ".join(cmd_parts)
            run_command(cmd)
            
        else:
            # Build single architecture image
            tag = build_docker_image(
                tag=args.tag,
                platform=args.platform,
                push=args.push,
                latest=args.latest
            )
        
        if args.test and not args.multi_arch:
            test_docker_image(tag)
        
        print(f"Docker build completed successfully!")
        if not args.push:
            print(f"To run the image: docker run --rm {tag} --help")
            print(f"To push the image: docker push {tag}")
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    import os
    main()