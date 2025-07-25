#!/usr/bin/env python3
"""
Test Docker configuration without building.
"""

from pathlib import Path


def test_dockerfile():
    """Test Dockerfile exists and has basic structure."""
    dockerfile = Path("Dockerfile")
    if not dockerfile.exists():
        print("❌ Dockerfile not found")
        return False
    
    content = dockerfile.read_text()
    required_elements = [
        "FROM python:",
        "WORKDIR",
        "COPY",
        "RUN pip install",
        "ENTRYPOINT",
        "LABEL"
    ]
    
    missing = []
    for element in required_elements:
        if element not in content:
            missing.append(element)
    
    if missing:
        print(f"❌ Dockerfile missing elements: {missing}")
        return False
    
    print("✅ Dockerfile structure looks good")
    return True


def test_dockerignore():
    """Test .dockerignore exists and has basic patterns."""
    dockerignore = Path(".dockerignore")
    if not dockerignore.exists():
        print("❌ .dockerignore not found")
        return False
    
    content = dockerignore.read_text()
    required_patterns = [
        ".git",
        "__pycache__",
        "*.pyc",
        ".venv",
        "build/",
        "dist/"
    ]
    
    missing = []
    for pattern in required_patterns:
        if pattern not in content:
            missing.append(pattern)
    
    if missing:
        print(f"❌ .dockerignore missing patterns: {missing}")
        return False
    
    print("✅ .dockerignore looks good")
    return True


def test_build_script():
    """Test Docker build script exists."""
    build_script = Path("scripts/build_docker.py")
    if not build_script.exists():
        print("❌ Docker build script not found")
        return False
    
    print("✅ Docker build script exists")
    return True


def main():
    """Run all Docker configuration tests."""
    print("Testing Docker configuration...")
    
    tests = [
        test_dockerfile,
        test_dockerignore,
        test_build_script
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    if all(results):
        print("\n✅ All Docker configuration tests passed!")
        return True
    else:
        print("\n❌ Some Docker configuration tests failed!")
        return False


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)