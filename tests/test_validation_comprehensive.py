"""
Comprehensive unit tests for validation system.

This module provides comprehensive test coverage for the validation
components including schema validation, quality assessment, and validation utilities.
"""

import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from saidata_gen.validation.schema import SchemaValidator
from saidata_gen.validation.quality import QualityAssessment
from saidata_gen.core.interfaces import (
    ValidationResult, ValidationIssue, ValidationLevel,
    BatchValidationResult, SaidataMetadata
)


class TestSchemaValidator:
    """Test SchemaValidator functionality."""
    
    @pytest.fixture
    def sample_schema(self):
        """Provide a sample JSON schema for testing."""
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "version": {
                    "type": "string",
                    "enum": ["0.1"]
                },
                "description": {
                    "type": "string",
                    "minLength": 1
                },
                "packages": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "version": {"type": "string"}
                        }
                    }
                },
                "urls": {
                    "type": "object",
                    "properties": {
                        "website": {"type": "string", "format": "uri"},
                        "documentation": {"type": "string", "format": "uri"}
                    }
                }
            },
            "required": ["version"]
        }
    
    @pytest.fixture
    def schema_file(self, sample_schema, temp_dir):
        """Create a temporary schema file."""
        schema_path = os.path.join(temp_dir, "test_schema.json")
        with open(schema_path, "w") as f:
            json.dump(sample_schema, f)
        return schema_path
    
    @pytest.fixture
    def validator(self, schema_file):
        """Create a SchemaValidator instance."""
        return SchemaValidator(schema_file)
    
    def test_initialization(self, schema_file):
        """Test SchemaValidator initialization."""
        validator = SchemaValidator(schema_file)
        assert validator.schema_path == schema_file
        assert validator.schema is not None
        assert isinstance(validator.schema, dict)
    
    def test_initialization_with_invalid_schema_file(self):
        """Test initialization with invalid schema file."""
        with pytest.raises(FileNotFoundError):
            SchemaValidator("nonexistent_schema.json")
    
    def test_initialization_with_invalid_json(self, temp_dir):
        """Test initialization with invalid JSON schema."""
        invalid_schema_path = os.path.join(temp_dir, "invalid_schema.json")
        with open(invalid_schema_path, "w") as f:
            f.write("invalid json content")
        
        with pytest.raises(json.JSONDecodeError):
            SchemaValidator(invalid_schema_path)
    
    def test_validate_data_valid(self, validator):
        """Test validation with valid data."""
        valid_data = {
            "version": "0.1",
            "description": "Test software",
            "packages": {
                "apt": {
                    "name": "nginx",
                    "version": "1.18.0"
                }
            },
            "urls": {
                "website": "https://nginx.org"
            }
        }
        
        result = validator.validate_data(valid_data)
        
        assert isinstance(result, ValidationResult)
        assert result.valid is True
        assert len(result.issues) == 0
    
    def test_validate_data_missing_required_field(self, validator):
        """Test validation with missing required field."""
        invalid_data = {
            "description": "Test software"
            # Missing required "version" field
        }
        
        result = validator.validate_data(invalid_data)
        
        assert isinstance(result, ValidationResult)
        assert result.valid is False
        assert len(result.issues) > 0
        
        # Should have an error about missing version
        error_messages = [issue.message for issue in result.issues]
        assert any("version" in msg.lower() for msg in error_messages)
    
    def test_validate_data_invalid_type(self, validator):
        """Test validation with invalid data type."""
        invalid_data = {
            "version": "0.1",
            "description": 123  # Should be string, not number
        }
        
        result = validator.validate_data(invalid_data)
        
        assert isinstance(result, ValidationResult)
        assert result.valid is False
        assert len(result.issues) > 0
    
    def test_validate_data_invalid_enum_value(self, validator):
        """Test validation with invalid enum value."""
        invalid_data = {
            "version": "1.0",  # Invalid version, should be "0.1"
            "description": "Test software"
        }
        
        result = validator.validate_data(invalid_data)
        
        assert isinstance(result, ValidationResult)
        assert result.valid is False
        assert len(result.issues) > 0
    
    def test_validate_data_invalid_url_format(self, validator):
        """Test validation with invalid URL format."""
        invalid_data = {
            "version": "0.1",
            "urls": {
                "website": "not-a-valid-url"
            }
        }
        
        result = validator.validate_data(invalid_data)
        
        assert isinstance(result, ValidationResult)
        assert result.valid is False
        assert len(result.issues) > 0
    
    def test_validate_file_valid(self, validator, temp_dir):
        """Test file validation with valid YAML file."""
        valid_data = {
            "version": "0.1",
            "description": "Test software"
        }
        
        yaml_file = os.path.join(temp_dir, "valid.yaml")
        with open(yaml_file, "w") as f:
            import yaml
            yaml.dump(valid_data, f)
        
        result = validator.validate_file(yaml_file)
        
        assert isinstance(result, ValidationResult)
        assert result.valid is True
        assert result.file_path == yaml_file
    
    def test_validate_file_invalid_yaml(self, validator, temp_dir):
        """Test file validation with invalid YAML file."""
        invalid_yaml_file = os.path.join(temp_dir, "invalid.yaml")
        with open(invalid_yaml_file, "w") as f:
            f.write("invalid: yaml: content: [")
        
        result = validator.validate_file(invalid_yaml_file)
        
        assert isinstance(result, ValidationResult)
        assert result.valid is False
        assert len(result.issues) > 0
        assert result.file_path == invalid_yaml_file
    
    def test_validate_file_nonexistent(self, validator):
        """Test file validation with nonexistent file."""
        result = validator.validate_file("nonexistent.yaml")
        
        assert isinstance(result, ValidationResult)
        assert result.valid is False
        assert len(result.issues) > 0
        assert result.file_path == "nonexistent.yaml"
    
    def test_validate_batch_mixed_results(self, validator, temp_dir):
        """Test batch validation with mixed results."""
        # Create valid file
        valid_data = {"version": "0.1", "description": "Valid software"}
        valid_file = os.path.join(temp_dir, "valid.yaml")
        with open(valid_file, "w") as f:
            import yaml
            yaml.dump(valid_data, f)
        
        # Create invalid file
        invalid_data = {"description": "Missing version"}
        invalid_file = os.path.join(temp_dir, "invalid.yaml")
        with open(invalid_file, "w") as f:
            import yaml
            yaml.dump(invalid_data, f)
        
        # Create nonexistent file reference
        nonexistent_file = os.path.join(temp_dir, "nonexistent.yaml")
        
        file_paths = [valid_file, invalid_file, nonexistent_file]
        result = validator.validate_batch(file_paths)
        
        assert isinstance(result, BatchValidationResult)
        assert len(result.results) == 3
        
        # Check individual results
        assert result.results[valid_file].valid is True
        assert result.results[invalid_file].valid is False
        assert result.results[nonexistent_file].valid is False
        
        # Check summary
        assert "valid" in result.summary
        assert "invalid" in result.summary
        assert result.summary["valid"] == 1
        assert result.summary["invalid"] == 2
    
    def test_get_schema_info(self, validator):
        """Test getting schema information."""
        info = validator.get_schema_info()
        
        assert isinstance(info, dict)
        assert "schema_path" in info
        assert "properties" in info
        assert "required" in info
        
        assert info["schema_path"] == validator.schema_path
        assert isinstance(info["properties"], list)
        assert isinstance(info["required"], list)
        assert "version" in info["required"]


class TestQualityAssessment:
    """Test QualityAssessment functionality."""
    
    @pytest.fixture
    def quality_assessor(self):
        """Create a QualityAssessment instance."""
        return QualityAssessment()
    
    def test_initialization(self, quality_assessor):
        """Test QualityAssessment initialization."""
        assert quality_assessor is not None
        assert hasattr(quality_assessor, 'assess_metadata_quality')
        assert hasattr(quality_assessor, 'calculate_confidence_score')
    
    def test_assess_metadata_quality_complete(self, quality_assessor):
        """Test quality assessment with complete metadata."""
        complete_metadata = {
            "version": "0.1",
            "description": "A comprehensive web server and reverse proxy",
            "language": "c",
            "license": "BSD-2-Clause",
            "platforms": ["linux", "macos", "windows"],
            "packages": {
                "apt": {"name": "nginx", "version": "1.18.0"},
                "brew": {"name": "nginx", "version": "1.25.3"}
            },
            "urls": {
                "website": "https://nginx.org",
                "documentation": "https://nginx.org/docs",
                "source": "https://github.com/nginx/nginx"
            },
            "category": {
                "default": "Web",
                "sub": "Server",
                "tags": ["http", "proxy", "server"]
            }
        }
        
        assessment = quality_assessor.assess_metadata_quality(complete_metadata)
        
        assert isinstance(assessment, dict)
        assert "overall_score" in assessment
        assert "completeness_score" in assessment
        assert "accuracy_score" in assessment
        assert "consistency_score" in assessment
        assert "issues" in assessment
        
        # Complete metadata should have high scores
        assert assessment["overall_score"] >= 0.8
        assert assessment["completeness_score"] >= 0.8
    
    def test_assess_metadata_quality_minimal(self, quality_assessor):
        """Test quality assessment with minimal metadata."""
        minimal_metadata = {
            "version": "0.1",
            "description": "Software"
        }
        
        assessment = quality_assessor.assess_metadata_quality(minimal_metadata)
        
        assert isinstance(assessment, dict)
        assert "overall_score" in assessment
        assert "completeness_score" in assessment
        
        # Minimal metadata should have lower scores
        assert assessment["overall_score"] < 0.8
        assert assessment["completeness_score"] < 0.5
        assert len(assessment["issues"]) > 0
    
    def test_assess_metadata_quality_with_issues(self, quality_assessor):
        """Test quality assessment with problematic metadata."""
        problematic_metadata = {
            "version": "0.1",
            "description": "",  # Empty description
            "urls": {
                "website": "not-a-url"  # Invalid URL
            },
            "packages": {}  # Empty packages
        }
        
        assessment = quality_assessor.assess_metadata_quality(problematic_metadata)
        
        assert isinstance(assessment, dict)
        assert assessment["overall_score"] < 0.5
        assert len(assessment["issues"]) > 0
        
        # Should identify specific issues
        issue_types = [issue["type"] for issue in assessment["issues"]]
        assert "empty_description" in issue_types or "invalid_url" in issue_types
    
    def test_calculate_confidence_score_high_quality(self, quality_assessor):
        """Test confidence score calculation for high-quality data."""
        high_quality_sources = [
            {"provider": "apt", "confidence": 0.9, "data_completeness": 0.8},
            {"provider": "brew", "confidence": 0.85, "data_completeness": 0.9},
            {"provider": "official", "confidence": 0.95, "data_completeness": 0.95}
        ]
        
        confidence = quality_assessor.calculate_confidence_score(high_quality_sources)
        
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0
        assert confidence >= 0.8  # High-quality sources should yield high confidence
    
    def test_calculate_confidence_score_low_quality(self, quality_assessor):
        """Test confidence score calculation for low-quality data."""
        low_quality_sources = [
            {"provider": "unknown", "confidence": 0.3, "data_completeness": 0.4},
            {"provider": "unreliable", "confidence": 0.2, "data_completeness": 0.3}
        ]
        
        confidence = quality_assessor.calculate_confidence_score(low_quality_sources)
        
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0
        assert confidence < 0.5  # Low-quality sources should yield low confidence
    
    def test_calculate_confidence_score_empty_sources(self, quality_assessor):
        """Test confidence score calculation with no sources."""
        confidence = quality_assessor.calculate_confidence_score([])
        
        assert isinstance(confidence, float)
        assert confidence == 0.0  # No sources should yield zero confidence
    
    def test_identify_missing_fields(self, quality_assessor):
        """Test identification of missing fields."""
        incomplete_metadata = {
            "version": "0.1",
            "description": "Test software"
            # Missing: license, platforms, packages, urls, category
        }
        
        missing_fields = quality_assessor.identify_missing_fields(incomplete_metadata)
        
        assert isinstance(missing_fields, list)
        assert len(missing_fields) > 0
        
        expected_missing = ["license", "platforms", "packages", "urls", "category"]
        for field in expected_missing:
            assert field in missing_fields
    
    def test_validate_urls(self, quality_assessor):
        """Test URL validation."""
        urls = {
            "website": "https://nginx.org",
            "documentation": "https://nginx.org/docs",
            "invalid": "not-a-url",
            "empty": ""
        }
        
        url_issues = quality_assessor.validate_urls(urls)
        
        assert isinstance(url_issues, list)
        assert len(url_issues) >= 2  # Should find issues with "invalid" and "empty"
        
        issue_fields = [issue["field"] for issue in url_issues]
        assert "invalid" in issue_fields
        assert "empty" in issue_fields
    
    def test_check_consistency(self, quality_assessor):
        """Test consistency checking."""
        consistent_metadata = {
            "description": "Nginx web server",
            "packages": {
                "apt": {"name": "nginx"},
                "brew": {"name": "nginx"}
            },
            "category": {
                "default": "Web",
                "tags": ["web", "server", "http"]
            }
        }
        
        inconsistencies = quality_assessor.check_consistency(consistent_metadata)
        
        assert isinstance(inconsistencies, list)
        # Should have few or no inconsistencies for well-structured data
        assert len(inconsistencies) <= 1
    
    def test_check_consistency_with_issues(self, quality_assessor):
        """Test consistency checking with inconsistent data."""
        inconsistent_metadata = {
            "description": "Database server",  # Inconsistent with category
            "packages": {
                "apt": {"name": "nginx"},
                "brew": {"name": "apache"}  # Different package names
            },
            "category": {
                "default": "Web",
                "tags": ["database", "storage"]  # Inconsistent tags
            }
        }
        
        inconsistencies = quality_assessor.check_consistency(inconsistent_metadata)
        
        assert isinstance(inconsistencies, list)
        assert len(inconsistencies) > 0  # Should find multiple inconsistencies


class TestValidationUtilities:
    """Test validation utility functions."""
    
    def test_create_validation_issue(self):
        """Test creating validation issues."""
        issue = ValidationIssue(
            level=ValidationLevel.ERROR,
            message="Test error message",
            path="test.field",
            schema_path="properties.test.properties.field"
        )
        
        assert issue.level == ValidationLevel.ERROR
        assert issue.message == "Test error message"
        assert issue.path == "test.field"
        assert issue.schema_path == "properties.test.properties.field"
    
    def test_validation_result_aggregation(self):
        """Test aggregating validation results."""
        issues = [
            ValidationIssue(ValidationLevel.ERROR, "Error 1", "field1"),
            ValidationIssue(ValidationLevel.WARNING, "Warning 1", "field2"),
            ValidationIssue(ValidationLevel.INFO, "Info 1", "field3")
        ]
        
        result = ValidationResult(valid=False, issues=issues)
        
        # Count issues by level
        error_count = sum(1 for issue in result.issues if issue.level == ValidationLevel.ERROR)
        warning_count = sum(1 for issue in result.issues if issue.level == ValidationLevel.WARNING)
        info_count = sum(1 for issue in result.issues if issue.level == ValidationLevel.INFO)
        
        assert error_count == 1
        assert warning_count == 1
        assert info_count == 1
    
    def test_batch_validation_result_summary(self):
        """Test batch validation result summary."""
        results = {
            "file1.yaml": ValidationResult(valid=True),
            "file2.yaml": ValidationResult(valid=False, issues=[
                ValidationIssue(ValidationLevel.ERROR, "Error", "field")
            ]),
            "file3.yaml": ValidationResult(valid=True)
        }
        
        batch_result = BatchValidationResult(
            results=results,
            summary={
                "valid": 2,
                "invalid": 1,
                "total": 3
            }
        )
        
        assert len(batch_result.results) == 3
        assert batch_result.summary["valid"] == 2
        assert batch_result.summary["invalid"] == 1
        assert batch_result.summary["total"] == 3


# Integration tests for validation system
class TestValidationIntegration:
    """Integration tests for the validation system."""
    
    def test_end_to_end_validation_workflow(self, temp_dir):
        """Test complete validation workflow."""
        # Create schema
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "version": {"type": "string", "enum": ["0.1"]},
                "description": {"type": "string"}
            },
            "required": ["version"]
        }
        
        schema_path = os.path.join(temp_dir, "schema.json")
        with open(schema_path, "w") as f:
            json.dump(schema, f)
        
        # Create test data files
        valid_data = {"version": "0.1", "description": "Valid software"}
        invalid_data = {"description": "Missing version"}
        
        valid_file = os.path.join(temp_dir, "valid.yaml")
        invalid_file = os.path.join(temp_dir, "invalid.yaml")
        
        import yaml
        with open(valid_file, "w") as f:
            yaml.dump(valid_data, f)
        with open(invalid_file, "w") as f:
            yaml.dump(invalid_data, f)
        
        # Run validation workflow
        validator = SchemaValidator(schema_path)
        quality_assessor = QualityAssessment()
        
        # Validate individual files
        valid_result = validator.validate_file(valid_file)
        invalid_result = validator.validate_file(invalid_file)
        
        assert valid_result.valid is True
        assert invalid_result.valid is False
        
        # Assess quality
        valid_quality = quality_assessor.assess_metadata_quality(valid_data)
        invalid_quality = quality_assessor.assess_metadata_quality(invalid_data)
        
        assert valid_quality["overall_score"] > invalid_quality["overall_score"]
        
        # Batch validation
        batch_result = validator.validate_batch([valid_file, invalid_file])
        assert len(batch_result.results) == 2
        assert batch_result.summary["valid"] == 1
        assert batch_result.summary["invalid"] == 1
    
    def test_validation_with_real_saidata_structure(self):
        """Test validation with realistic saidata structure."""
        realistic_data = {
            "version": "0.1",
            "description": "Nginx HTTP server and reverse proxy",
            "language": "c",
            "license": "BSD-2-Clause",
            "platforms": ["linux", "macos", "windows"],
            "packages": {
                "apt": {
                    "name": "nginx",
                    "version": "1.18.0"
                },
                "brew": {
                    "name": "nginx",
                    "version": "1.25.3"
                }
            },
            "services": {
                "default": {
                    "name": "nginx",
                    "enabled": True
                }
            },
            "urls": {
                "website": "https://nginx.org",
                "documentation": "https://nginx.org/docs",
                "source": "https://github.com/nginx/nginx"
            },
            "category": {
                "default": "Web",
                "sub": "Server",
                "tags": ["http", "proxy", "server"]
            },
            "ports": {
                "http": {
                    "number": 80,
                    "protocol": "tcp"
                },
                "https": {
                    "number": 443,
                    "protocol": "tcp"
                }
            }
        }
        
        # Test quality assessment
        quality_assessor = QualityAssessment()
        assessment = quality_assessor.assess_metadata_quality(realistic_data)
        
        # Realistic, complete data should score well
        assert assessment["overall_score"] >= 0.8
        assert assessment["completeness_score"] >= 0.8
        assert len(assessment["issues"]) <= 2  # Should have minimal issues