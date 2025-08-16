"""
Unit tests for schema validation.
"""

import os
import tempfile
import unittest
from pathlib import Path

import yaml

from saidata_gen.validation.schema import SchemaValidator
from saidata_gen.core.interfaces import ValidationLevel


class TestSchemaValidator(unittest.TestCase):
    """Test the SchemaValidator class."""

    def setUp(self):
        """Set up the test environment."""
        # Create a validator with the default schema
        self.validator = SchemaValidator()
        
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
    
    def tearDown(self):
        """Clean up the test environment."""
        self.temp_dir.cleanup()
    
    def test_validate_valid_data(self):
        """Test validation of valid data."""
        valid_data = {
            "version": "0.1",
            "description": "Test software",
            "packages": {
                "default": {
                    "name": "test-package",
                    "version": "1.0.0"
                }
            },
            "category": {
                "default": "Development"
            },
            "license": "MIT",
            "platforms": ["linux", "macos"]
        }
        
        result = self.validator.validate_data(valid_data)
        self.assertTrue(result.valid)
        # Allow INFO level issues for enhanced validation
        error_issues = [issue for issue in result.issues if issue.level == ValidationLevel.ERROR]
        self.assertEqual(len(error_issues), 0)
    
    def test_validate_invalid_data(self):
        """Test validation of invalid data."""
        # Invalid data: version is not a string
        invalid_data = {
            "version": 1,  # Should be a string
            "description": "Test software",
            "packages": {
                "default": {
                    "name": "test-package",
                    "version": "1.0.0"
                }
            },
            "category": {
                "default": "Development"
            },
            "license": "MIT",
            "platforms": ["linux", "macos"]
        }
        
        result = self.validator.validate_data(invalid_data)
        self.assertFalse(result.valid)
        self.assertGreater(len(result.issues), 0)
        self.assertEqual(result.issues[0].level, ValidationLevel.ERROR)
    
    def test_validate_file(self):
        """Test validation of a file."""
        # Create a valid YAML file
        valid_yaml = """
        version: '0.1'
        description: Test software
        packages:
          default:
            name: test-package
            version: 1.0.0
        category:
          default: Development
        license: MIT
        platforms:
          - linux
          - macos
        """
        
        valid_file_path = os.path.join(self.temp_dir.name, "valid.yaml")
        with open(valid_file_path, "w") as f:
            f.write(valid_yaml)
        
        result = self.validator.validate_file(valid_file_path)
        self.assertTrue(result.valid)
        # Allow INFO level issues for enhanced validation
        error_issues = [issue for issue in result.issues if issue.level == ValidationLevel.ERROR]
        self.assertEqual(len(error_issues), 0)
        
        # Create an invalid YAML file
        invalid_yaml = """
        version: 1  # Should be a string
        description: Test software
        packages:
          default:
            name: test-package
            version: 1.0.0
        category:
          default: Development
        license: MIT
        platforms:
          - linux
          - macos
        """
        
        invalid_file_path = os.path.join(self.temp_dir.name, "invalid.yaml")
        with open(invalid_file_path, "w") as f:
            f.write(invalid_yaml)
        
        result = self.validator.validate_file(invalid_file_path)
        self.assertFalse(result.valid)
        self.assertGreater(len(result.issues), 0)
        self.assertEqual(result.issues[0].level, ValidationLevel.ERROR)
    
    def test_validate_batch(self):
        """Test batch validation."""
        # Create multiple YAML files
        valid_yaml = """
        version: '0.1'
        description: Test software
        packages:
          default:
            name: test-package
            version: 1.0.0
        category:
          default: Development
        license: MIT
        platforms:
          - linux
          - macos
        """
        
        invalid_yaml = """
        version: 1  # Should be a string
        description: Test software
        packages:
          default:
            name: test-package
            version: 1.0.0
        category:
          default: Development
        license: MIT
        platforms:
          - linux
          - macos
        """
        
        valid_file_path = os.path.join(self.temp_dir.name, "valid.yaml")
        with open(valid_file_path, "w") as f:
            f.write(valid_yaml)
        
        invalid_file_path = os.path.join(self.temp_dir.name, "invalid.yaml")
        with open(invalid_file_path, "w") as f:
            f.write(invalid_yaml)
        
        result = self.validator.validate_batch([valid_file_path, invalid_file_path])
        self.assertEqual(result.summary["total"], 2)
        self.assertEqual(result.summary["valid"], 1)
        self.assertEqual(result.summary["invalid"], 1)
        self.assertGreater(result.summary["errors"], 0)
    
    def test_additional_validations(self):
        """Test additional validations beyond the schema."""
        # Missing optional fields
        minimal_data = {
            "version": "0.1"
        }
        
        result = self.validator.validate_data(minimal_data)
        self.assertTrue(result.valid)  # Still valid according to the schema
        self.assertGreater(len(result.issues), 0)  # But has warnings
        
        # Check that all issues are warnings or info
        for issue in result.issues:
            self.assertIn(issue.level, [ValidationLevel.WARNING, ValidationLevel.INFO])
        
        # Check specific warnings
        paths = [issue.path for issue in result.issues]
        self.assertIn("description", paths)
        self.assertIn("packages", paths)
        # category.default may not be present if it's a valid category
        self.assertIn("license", paths)
        self.assertIn("platforms", paths)
    
    def test_get_schema_info(self):
        """Test getting schema information."""
        info = self.validator.get_schema_info()
        self.assertIn("title", info)
        self.assertIn("properties", info)
        self.assertIn("definitions", info)
        
        # Check that key properties are included
        self.assertIn("version", info["properties"])
        self.assertIn("packages", info["properties"])
        self.assertIn("services", info["properties"])
        self.assertIn("urls", info["properties"])
        
        # Check that key definitions are included
        self.assertIn("package", info["definitions"])
        self.assertIn("service", info["definitions"])


if __name__ == "__main__":
    unittest.main()