"""
Tests for enhanced schema validation functionality.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from saidata_gen.core.interfaces import ValidationLevel
from saidata_gen.validation.schema import (
    SchemaValidator, EnhancedValidationResult, EnhancedValidationIssue, 
    ValidationSuggestion
)


class TestEnhancedSchemaValidation(unittest.TestCase):
    """Test enhanced schema validation functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.validator = SchemaValidator()
        
        # Sample valid data
        self.valid_data = {
            "version": "0.1",
            "description": "A comprehensive web server",
            "license": "MIT",
            "platforms": ["linux", "windows"],
            "category": {
                "default": "web",
                "tags": ["server", "http"]
            },
            "urls": {
                "website": "https://example.com",
                "source": "https://github.com/example/project"
            },
            "packages": {
                "default": {
                    "name": "example-server",
                    "version": "1.0.0"
                }
            }
        }
        
        # Sample data with issues
        self.data_with_issues = {
            "description": "Short",  # Too short
            "license": "Custom License",  # Non-standard
            "platforms": ["linux", "win32"],  # Non-standard platform
            "category": {
                "default": "webserver"  # Non-standard category
            },
            "urls": {
                "website": "invalid-url",  # Invalid URL
                "source": "github.com/example"  # Missing protocol
            },
            "packages": {
                "default": {
                    # Missing name
                    "version": "1.0.0"
                }
            }
        }
    
    def test_validate_valid_data(self):
        """Test validation of valid data."""
        result = self.validator.validate_data(self.valid_data)
        
        self.assertIsInstance(result, EnhancedValidationResult)
        self.assertTrue(result.valid)
        self.assertGreater(result.quality_score, 0.8)
        self.assertGreater(result.completeness_score, 0.8)
        
        # Should have minimal issues (maybe some info-level suggestions)
        error_issues = [i for i in result.issues if i.level == ValidationLevel.ERROR]
        self.assertEqual(len(error_issues), 0)
    
    def test_validate_data_with_issues(self):
        """Test validation of data with various issues."""
        result = self.validator.validate_data(self.data_with_issues)
        
        self.assertIsInstance(result, EnhancedValidationResult)
        self.assertFalse(result.valid)  # Should be invalid due to missing version
        
        # Check for specific issues
        issue_messages = [issue.message for issue in result.issues]
        
        # Should detect missing version
        self.assertTrue(any("Version is not specified" in msg for msg in issue_messages))
        
        # Should detect short description
        self.assertTrue(any("Description is very short" in msg for msg in issue_messages))
        
        # Should detect invalid URLs
        self.assertTrue(any("Invalid URL format" in msg for msg in issue_messages))
        
        # Should detect missing package name
        self.assertTrue(any("has no name specified" in msg for msg in issue_messages))
    
    def test_validation_suggestions(self):
        """Test that validation provides helpful suggestions."""
        result = self.validator.validate_data(self.data_with_issues)
        
        # Should have suggestions
        self.assertGreater(len(result.suggestions), 0)
        
        # Check for specific suggestion types
        suggestion_types = [s.type for s in result.suggestions]
        self.assertIn('add', suggestion_types)  # Add missing fields
        self.assertIn('modify', suggestion_types)  # Fix existing fields
        
        # Check for auto-fixable suggestions
        auto_fixable_suggestions = [s for s in result.suggestions if s.confidence >= 0.7]
        self.assertGreater(len(auto_fixable_suggestions), 0)
    
    def test_auto_fix_functionality(self):
        """Test auto-fix functionality."""
        result = self.validator.validate_data(self.data_with_issues)
        
        # Apply auto-fixes
        fixed_data = self.validator.apply_auto_fixes(self.data_with_issues, result.suggestions)
        
        # Validate fixed data
        fixed_result = self.validator.validate_data(fixed_data)
        
        # Should have fewer issues after auto-fix
        original_error_count = len([i for i in result.issues if i.level == ValidationLevel.ERROR])
        fixed_error_count = len([i for i in fixed_result.issues if i.level == ValidationLevel.ERROR])
        
        self.assertLessEqual(fixed_error_count, original_error_count)
    
    def test_quality_scoring(self):
        """Test quality scoring functionality."""
        # Test with high-quality data
        high_quality_result = self.validator.validate_data(self.valid_data)
        
        # Test with low-quality data
        low_quality_data = {"description": ""}  # Minimal data
        low_quality_result = self.validator.validate_data(low_quality_data)
        
        # High-quality data should have better scores
        self.assertGreater(high_quality_result.quality_score, low_quality_result.quality_score)
        self.assertGreater(high_quality_result.completeness_score, low_quality_result.completeness_score)
    
    def test_field_coverage_calculation(self):
        """Test field coverage calculation."""
        result = self.validator.validate_data(self.valid_data)
        
        # Should have good field coverage
        self.assertIn('version', result.field_coverage)
        self.assertIn('description', result.field_coverage)
        self.assertIn('license', result.field_coverage)
        self.assertIn('platforms', result.field_coverage)
        self.assertIn('category', result.field_coverage)
        self.assertIn('urls', result.field_coverage)
        self.assertIn('packages', result.field_coverage)
        
        # Most fields should be present
        present_fields = sum(1 for present in result.field_coverage.values() if present)
        self.assertGreater(present_fields, len(result.field_coverage) * 0.7)
    
    def test_url_validation(self):
        """Test URL validation functionality."""
        data_with_urls = {
            "urls": {
                "website": "https://example.com",  # Valid
                "source": "invalid-url",  # Invalid
                "documentation": "github.com/docs",  # Missing protocol
                "issues": "https://github.com/example/issues"  # Valid
            }
        }
        
        result = self.validator.validate_data(data_with_urls)
        
        # Should detect invalid URLs
        url_issues = [i for i in result.issues if "Invalid URL format" in i.message]
        self.assertGreater(len(url_issues), 0)
        
        # Should provide URL fix suggestions
        url_suggestions = [s for s in result.suggestions if s.path.startswith('urls.')]
        self.assertGreater(len(url_suggestions), 0)
    
    def test_license_validation(self):
        """Test license validation functionality."""
        data_with_license = {
            "license": "Custom License"  # Non-standard license
        }
        
        result = self.validator.validate_data(data_with_license)
        
        # Should suggest standard license
        license_issues = [i for i in result.issues if "not a common SPDX identifier" in i.message]
        self.assertGreater(len(license_issues), 0)
    
    def test_platform_validation(self):
        """Test platform validation functionality."""
        data_with_platforms = {
            "platforms": ["linux", "win32", "osx"]  # Mix of standard and non-standard
        }
        
        result = self.validator.validate_data(data_with_platforms)
        
        # Should suggest standard platform names
        platform_issues = [i for i in result.issues if "might not be standard" in i.message]
        self.assertGreater(len(platform_issues), 0)
    
    def test_category_validation(self):
        """Test category validation functionality."""
        data_with_category = {
            "category": {
                "default": "webserver"  # Non-standard category
            }
        }
        
        result = self.validator.validate_data(data_with_category)
        
        # Should suggest standard category
        category_issues = [i for i in result.issues if "not a common category" in i.message]
        self.assertGreater(len(category_issues), 0)
    
    def test_file_validation(self):
        """Test file validation functionality."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.valid_data, f)
            temp_file = f.name
        
        try:
            result = self.validator.validate_file(temp_file)
            
            self.assertIsInstance(result, EnhancedValidationResult)
            self.assertEqual(result.file_path, temp_file)
            self.assertTrue(result.valid)
        finally:
            os.unlink(temp_file)
    
    def test_invalid_yaml_file(self):
        """Test validation of invalid YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")  # Invalid YAML
            temp_file = f.name
        
        try:
            result = self.validator.validate_file(temp_file)
            
            self.assertIsInstance(result, EnhancedValidationResult)
            self.assertFalse(result.valid)
            self.assertEqual(result.quality_score, 0.0)
            
            # Should have YAML parsing error
            yaml_errors = [i for i in result.issues if "YAML parsing error" in i.message]
            self.assertGreater(len(yaml_errors), 0)
        finally:
            os.unlink(temp_file)
    
    def test_batch_validation(self):
        """Test batch validation functionality."""
        # Create temporary files
        temp_files = []
        
        try:
            # Valid file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(self.valid_data, f)
                temp_files.append(f.name)
            
            # Invalid file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(self.data_with_issues, f)
                temp_files.append(f.name)
            
            result = self.validator.validate_batch(temp_files)
            
            self.assertEqual(result.summary['total'], 2)
            self.assertEqual(result.summary['valid'], 1)
            self.assertEqual(result.summary['invalid'], 1)
            self.assertGreater(result.summary['avg_quality_score'], 0.0)
            self.assertGreater(result.summary['avg_completeness_score'], 0.0)
            
        finally:
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
    
    def test_validation_report_generation(self):
        """Test validation report generation."""
        result = self.validator.validate_data(self.data_with_issues)
        report = self.validator.generate_validation_report(result)
        
        self.assertIsInstance(report, str)
        self.assertIn("Validation Report", report)
        self.assertIn("Status:", report)
        self.assertIn("Quality Score:", report)
        self.assertIn("Issues Summary:", report)
        self.assertIn("Field Coverage:", report)
        
        # Should contain issue details
        self.assertIn("ERROR", report)
        self.assertIn("WARNING", report)
    
    def test_schema_info(self):
        """Test schema information retrieval."""
        info = self.validator.get_schema_info()
        
        self.assertIn('title', info)
        self.assertIn('properties', info)
        self.assertIn('expected_fields', info)
        self.assertIn('common_licenses', info)
        self.assertIn('common_platforms', info)
        self.assertIn('common_categories', info)
        
        # Should contain expected properties
        self.assertIn('version', info['properties'])
        self.assertIn('description', info['properties'])
        self.assertIn('packages', info['properties'])
    
    def test_path_utilities(self):
        """Test path utility functions."""
        data = {
            "category": {"default": "web"},
            "platforms": ["linux", "windows"]
        }
        
        # Test getting values
        self.assertEqual(self.validator._get_value_at_path(data, "category.default"), "web")
        self.assertEqual(self.validator._get_value_at_path(data, "platforms[0]"), "linux")
        self.assertIsNone(self.validator._get_value_at_path(data, "nonexistent.path"))
        
        # Test setting values
        self.validator._set_value_at_path(data, "new.field", "value")
        self.assertEqual(data["new"]["field"], "value")
        
        self.validator._set_value_at_path(data, "platforms[2]", "macos")
        self.assertEqual(data["platforms"][2], "macos")
    
    def test_close_matches_finding(self):
        """Test close matches finding functionality."""
        candidates = {"linux", "windows", "macos", "freebsd"}
        
        matches = self.validator._find_close_matches("win32", candidates)
        self.assertIn("windows", matches)
        
        matches = self.validator._find_close_matches("osx", candidates)
        self.assertIn("macos", matches)
    
    def test_url_fixing(self):
        """Test URL fixing functionality."""
        self.assertTrue(self.validator._is_valid_url("https://example.com"))
        self.assertFalse(self.validator._is_valid_url("invalid-url"))
        
        fixed_url = self.validator._fix_url("example.com")
        self.assertEqual(fixed_url, "https://example.com")
        
        fixed_url = self.validator._fix_url("https://example.com")
        self.assertEqual(fixed_url, "https://example.com")


if __name__ == '__main__':
    unittest.main()