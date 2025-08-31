"""
Unit tests for the core data models.
"""

import os
import tempfile
import unittest
from pathlib import Path

import yaml

from saidata_gen.core.models import (
    EnhancedCategoryConfig, EnhancedContainerConfig, EnhancedDirectoryConfig,
    EnhancedPackageConfig, EnhancedPortConfig, EnhancedProcessConfig,
    EnhancedSaidataMetadata, EnhancedServiceConfig, EnhancedURLConfig,
    ValidationLevel
)


class TestEnhancedSaidataMetadata(unittest.TestCase):
    """Test the EnhancedSaidataMetadata class."""

    def test_initialization(self):
        """Test initialization with default values."""
        metadata = EnhancedSaidataMetadata()
        self.assertEqual(metadata.version, "0.1")
        self.assertEqual(metadata.packages, {})
        self.assertEqual(metadata.services, {})
        self.assertEqual(metadata.directories, {})
        self.assertEqual(metadata.processes, {})
        self.assertEqual(metadata.ports, {})
        self.assertEqual(metadata.containers, {})
        self.assertEqual(metadata.charts, {})
        self.assertEqual(metadata.repos, {})
        self.assertIsInstance(metadata.urls, EnhancedURLConfig)
        self.assertIsNone(metadata.language)
        self.assertIsNone(metadata.description)
        self.assertIsInstance(metadata.category, EnhancedCategoryConfig)
        self.assertIsNone(metadata.license)
        self.assertEqual(metadata.platforms, [])

    def test_to_yaml(self):
        """Test conversion to YAML."""
        metadata = EnhancedSaidataMetadata(
            version="0.1",
            description="Test metadata",
            language="python",
            license="MIT",
            platforms=["linux", "macos"]
        )
        yaml_str = metadata.to_yaml()
        self.assertIn("version: '0.1'", yaml_str)
        self.assertIn("description: Test metadata", yaml_str)
        self.assertIn("language: python", yaml_str)
        self.assertIn("license: MIT", yaml_str)
        self.assertIn("- linux", yaml_str)
        self.assertIn("- macos", yaml_str)

    def test_from_yaml(self):
        """Test creation from YAML."""
        yaml_str = """
        version: '0.1'
        description: Test metadata
        language: python
        license: MIT
        platforms:
          - linux
          - macos
        """
        metadata = EnhancedSaidataMetadata.from_yaml(yaml_str)
        self.assertEqual(metadata.version, "0.1")
        self.assertEqual(metadata.description, "Test metadata")
        self.assertEqual(metadata.language, "python")
        self.assertEqual(metadata.license, "MIT")
        self.assertEqual(metadata.platforms, ["linux", "macos"])

    def test_to_yaml_file(self):
        """Test writing to a YAML file."""
        metadata = EnhancedSaidataMetadata(
            version="0.1",
            description="Test metadata",
            language="python",
            license="MIT",
            platforms=["linux", "macos"]
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "metadata.yaml")
            metadata.to_yaml_file(file_path)
            
            # Check if the file exists
            self.assertTrue(os.path.exists(file_path))
            
            # Read the file and check its contents
            with open(file_path, "r") as f:
                content = f.read()
                self.assertIn("version: '0.1'", content)
                self.assertIn("description: Test metadata", content)
                self.assertIn("language: python", content)
                self.assertIn("license: MIT", content)
                self.assertIn("- linux", content)
                self.assertIn("- macos", content)

    def test_from_yaml_file(self):
        """Test reading from a YAML file."""
        yaml_content = """
        version: '0.1'
        description: Test metadata
        language: python
        license: MIT
        platforms:
          - linux
          - macos
        """
        
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "metadata.yaml")
            with open(file_path, "w") as f:
                f.write(yaml_content)
            
            metadata = EnhancedSaidataMetadata.from_yaml_file(file_path)
            self.assertEqual(metadata.version, "0.1")
            self.assertEqual(metadata.description, "Test metadata")
            self.assertEqual(metadata.language, "python")
            self.assertEqual(metadata.license, "MIT")
            self.assertEqual(metadata.platforms, ["linux", "macos"])

    def test_validation(self):
        """Test validation of metadata."""
        # Create a minimal valid metadata
        metadata = EnhancedSaidataMetadata(
            version="0.1",
            description="Test metadata",
            license="MIT",
            platforms=["linux"]
        )
        metadata.category.default = "Development"
        metadata.packages = {"default": EnhancedPackageConfig(name="test")}
        
        result = metadata.validate()
        self.assertTrue(result.valid)
        self.assertEqual(len(result.issues), 0)
        
        # Test with missing fields
        metadata = EnhancedSaidataMetadata()
        result = metadata.validate()
        self.assertTrue(result.valid)  # Still valid because no ERROR level issues
        self.assertGreater(len(result.issues), 0)  # But has warnings
        
        # Check that all issues are warnings
        for issue in result.issues:
            self.assertEqual(issue.level, ValidationLevel.WARNING)

    def test_nested_objects(self):
        """Test handling of nested objects."""
        yaml_str = """
        version: '0.1'
        description: Test metadata
        packages:
          default:
            name: test-package
            version: 1.0.0
          nginx:
            name: nginx
            version: 1.18.0
        services:
          default:
            name: test-service
            enabled: true
        urls:
          website: https://example.com
          documentation: https://docs.example.com
        category:
          default: Web
          sub: Server
          tags:
            - http
            - server
        """
        
        metadata = EnhancedSaidataMetadata.from_yaml(yaml_str)
        
        # Check packages
        self.assertEqual(len(metadata.packages), 2)
        self.assertIn("default", metadata.packages)
        self.assertIn("nginx", metadata.packages)
        self.assertIsInstance(metadata.packages["default"], EnhancedPackageConfig)
        self.assertEqual(metadata.packages["default"].name, "test-package")
        self.assertEqual(metadata.packages["default"].version, "1.0.0")
        self.assertEqual(metadata.packages["nginx"].name, "nginx")
        self.assertEqual(metadata.packages["nginx"].version, "1.18.0")
        
        # Check services
        self.assertEqual(len(metadata.services), 1)
        self.assertIn("default", metadata.services)
        self.assertIsInstance(metadata.services["default"], EnhancedServiceConfig)
        self.assertEqual(metadata.services["default"].name, "test-service")
        self.assertTrue(metadata.services["default"].enabled)
        
        # Check URLs
        self.assertIsInstance(metadata.urls, EnhancedURLConfig)
        self.assertEqual(metadata.urls.website, "https://example.com")
        self.assertEqual(metadata.urls.documentation, "https://docs.example.com")
        
        # Check category
        self.assertIsInstance(metadata.category, EnhancedCategoryConfig)
        self.assertEqual(metadata.category.default, "Web")
        self.assertEqual(metadata.category.sub, "Server")
        self.assertEqual(metadata.category.tags, ["http", "server"])


class TestEnhancedPackageConfig(unittest.TestCase):
    """Test the EnhancedPackageConfig class."""

    def test_initialization(self):
        """Test initialization with default values."""
        package = EnhancedPackageConfig()
        self.assertIsNone(package.name)
        self.assertIsNone(package.version)
        self.assertIsNone(package.install_options)

    def test_to_yaml(self):
        """Test conversion to YAML."""
        package = EnhancedPackageConfig(
            name="test-package",
            version="1.0.0",
            install_options="--no-deps"
        )
        yaml_str = package.to_yaml()
        self.assertIn("name: test-package", yaml_str)
        self.assertIn("version: 1.0.0", yaml_str)
        self.assertIn("install_options: --no-deps", yaml_str)

    def test_from_yaml(self):
        """Test creation from YAML."""
        yaml_str = """
        name: test-package
        version: 1.0.0
        install_options: --no-deps
        """
        package = EnhancedPackageConfig.from_yaml(yaml_str)
        self.assertEqual(package.name, "test-package")
        self.assertEqual(package.version, "1.0.0")
        self.assertEqual(package.install_options, "--no-deps")

    def test_validation(self):
        """Test validation of package configuration."""
        # Valid package
        package = EnhancedPackageConfig(name="test-package")
        result = package.validate()
        self.assertTrue(result.valid)
        self.assertEqual(len(result.issues), 0)
        
        # Invalid package (missing name)
        package = EnhancedPackageConfig()
        result = package.validate()
        self.assertFalse(result.valid)
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0].level, ValidationLevel.ERROR)
        self.assertEqual(result.issues[0].path, "name")


class TestEnhancedURLConfig(unittest.TestCase):
    """Test the EnhancedURLConfig class."""

    def test_initialization(self):
        """Test initialization with default values."""
        urls = EnhancedURLConfig()
        self.assertIsNone(urls.website)
        self.assertIsNone(urls.sbom)
        self.assertIsNone(urls.issues)
        self.assertIsNone(urls.documentation)
        self.assertIsNone(urls.support)
        self.assertIsNone(urls.source)
        self.assertIsNone(urls.license)
        self.assertIsNone(urls.changelog)
        self.assertIsNone(urls.download)
        self.assertIsNone(urls.icon)

    def test_to_yaml(self):
        """Test conversion to YAML."""
        urls = EnhancedURLConfig(
            website="https://example.com",
            documentation="https://docs.example.com",
            source="https://github.com/example/repo"
        )
        yaml_str = urls.to_yaml()
        self.assertIn("website: https://example.com", yaml_str)
        self.assertIn("documentation: https://docs.example.com", yaml_str)
        self.assertIn("source: https://github.com/example/repo", yaml_str)

    def test_from_yaml(self):
        """Test creation from YAML."""
        yaml_str = """
        website: https://example.com
        documentation: https://docs.example.com
        source: https://github.com/example/repo
        """
        urls = EnhancedURLConfig.from_yaml(yaml_str)
        self.assertEqual(urls.website, "https://example.com")
        self.assertEqual(urls.documentation, "https://docs.example.com")
        self.assertEqual(urls.source, "https://github.com/example/repo")

    def test_validation(self):
        """Test validation of URL configuration."""
        # Valid URLs (at least one URL is provided)
        urls = EnhancedURLConfig(website="https://example.com")
        result = urls.validate()
        self.assertTrue(result.valid)
        self.assertEqual(len(result.issues), 0)
        
        # Warning if no URLs are provided
        urls = EnhancedURLConfig()
        result = urls.validate()
        self.assertTrue(result.valid)  # Still valid because URLs are optional
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0].level, ValidationLevel.WARNING)


class TestEnhancedCategoryConfig(unittest.TestCase):
    """Test the EnhancedCategoryConfig class."""

    def test_initialization(self):
        """Test initialization with default values."""
        category = EnhancedCategoryConfig()
        self.assertIsNone(category.default)
        self.assertIsNone(category.sub)
        self.assertIsNone(category.tags)

    def test_to_yaml(self):
        """Test conversion to YAML."""
        category = EnhancedCategoryConfig(
            default="Web",
            sub="Server",
            tags=["http", "server"]
        )
        yaml_str = category.to_yaml()
        self.assertIn("default: Web", yaml_str)
        self.assertIn("sub: Server", yaml_str)
        self.assertIn("- http", yaml_str)
        self.assertIn("- server", yaml_str)

    def test_from_yaml(self):
        """Test creation from YAML."""
        yaml_str = """
        default: Web
        sub: Server
        tags:
          - http
          - server
        """
        category = EnhancedCategoryConfig.from_yaml(yaml_str)
        self.assertEqual(category.default, "Web")
        self.assertEqual(category.sub, "Server")
        self.assertEqual(category.tags, ["http", "server"])

    def test_validation(self):
        """Test validation of category configuration."""
        # Valid category
        category = EnhancedCategoryConfig(default="Web")
        result = category.validate()
        self.assertTrue(result.valid)
        self.assertEqual(len(result.issues), 0)
        
        # Warning if default category is missing
        category = EnhancedCategoryConfig()
        result = category.validate()
        self.assertTrue(result.valid)  # Still valid because categories are optional
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(result.issues[0].level, ValidationLevel.WARNING)
        self.assertEqual(result.issues[0].path, "default")


if __name__ == "__main__":
    unittest.main()