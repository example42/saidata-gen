"""
Schema validation module for saidata-gen.

This module provides functionality to validate saidata YAML files against
the saidata-0.1.schema.json schema.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import jsonschema
import yaml

from saidata_gen.core.interfaces import (
    ValidationIssue, ValidationLevel, ValidationResult, BatchValidationResult
)


class SchemaValidator:
    """
    Validator for saidata YAML files against the saidata-0.1.schema.json schema.
    """
    
    def __init__(self, schema_path: Optional[str] = None):
        """
        Initialize the schema validator.
        
        Args:
            schema_path: Path to the schema file. If None, uses the default schema.
        """
        if schema_path is None:
            # Use the default schema
            module_dir = os.path.dirname(os.path.abspath(__file__))
            schema_path = os.path.join(
                os.path.dirname(os.path.dirname(module_dir)),
                "schemas",
                "saidata-0.1.schema.json"
            )
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            self.schema = json.load(f)
        
        self.validator = jsonschema.Draft7Validator(self.schema)
    
    def validate_file(self, file_path: Union[str, Path]) -> ValidationResult:
        """
        Validate a YAML file against the schema.
        
        Args:
            file_path: Path to the YAML file
            
        Returns:
            ValidationResult with validation issues
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            return self.validate_data(data, file_path=str(file_path))
        except Exception as e:
            return ValidationResult(
                valid=False,
                issues=[
                    ValidationIssue(
                        level=ValidationLevel.ERROR,
                        message=f"Failed to load YAML file: {str(e)}",
                        path="",
                        schema_path=""
                    )
                ],
                file_path=str(file_path)
            )
    
    def validate_data(self, data: Dict[str, Any], file_path: Optional[str] = None) -> ValidationResult:
        """
        Validate data against the schema.
        
        Args:
            data: Data to validate
            file_path: Optional file path for reference
            
        Returns:
            ValidationResult with validation issues
        """
        issues = []
        
        for error in self.validator.iter_errors(data):
            # Convert jsonschema error to ValidationIssue
            path = "/".join(str(p) for p in error.path) if error.path else ""
            schema_path = "/".join(str(p) for p in error.schema_path) if error.schema_path else ""
            
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                message=error.message,
                path=path,
                schema_path=schema_path
            ))
        
        # Add additional validation checks beyond the schema
        self._add_additional_validations(data, issues)
        
        return ValidationResult(
            valid=len([i for i in issues if i.level == ValidationLevel.ERROR]) == 0,
            issues=issues,
            file_path=file_path
        )
    
    def validate_batch(self, file_paths: List[Union[str, Path]]) -> BatchValidationResult:
        """
        Validate multiple YAML files against the schema.
        
        Args:
            file_paths: List of paths to YAML files
            
        Returns:
            BatchValidationResult with validation results for each file
        """
        results = {}
        summary = {
            "total": len(file_paths),
            "valid": 0,
            "invalid": 0,
            "errors": 0,
            "warnings": 0
        }
        
        for file_path in file_paths:
            result = self.validate_file(file_path)
            results[str(file_path)] = result
            
            if result.valid:
                summary["valid"] += 1
            else:
                summary["invalid"] += 1
            
            summary["errors"] += len([i for i in result.issues if i.level == ValidationLevel.ERROR])
            summary["warnings"] += len([i for i in result.issues if i.level == ValidationLevel.WARNING])
        
        return BatchValidationResult(
            results=results,
            summary=summary
        )
    
    def get_schema_info(self) -> Dict[str, Any]:
        """
        Get information about the schema.
        
        Returns:
            Dictionary with schema information
        """
        return {
            "title": self.schema.get("title", ""),
            "version": self.schema.get("version", ""),
            "properties": list(self.schema.get("properties", {}).keys()),
            "definitions": list(self.schema.get("definitions", {}).keys())
        }
    
    def _add_additional_validations(self, data: Dict[str, Any], issues: List[ValidationIssue]) -> None:
        """
        Add additional validation checks beyond the schema.
        
        Args:
            data: Data to validate
            issues: List of validation issues to append to
        """
        # Check if version is specified
        if "version" not in data or not data["version"]:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                message="Version is not specified",
                path="version",
                schema_path=""
            ))
        
        # Check if description is provided
        if "description" not in data or not data["description"]:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                message="Description is not provided",
                path="description",
                schema_path=""
            ))
        
        # Check if at least one package is defined
        if "packages" not in data or not data["packages"]:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                message="No packages defined",
                path="packages",
                schema_path=""
            ))
        
        # Check if category is provided
        if "category" not in data or not data["category"] or "default" not in data["category"] or not data["category"]["default"]:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                message="Default category is not provided",
                path="category.default",
                schema_path=""
            ))
        
        # Check if license is provided
        if "license" not in data or not data["license"]:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                message="License is not provided",
                path="license",
                schema_path=""
            ))
        
        # Check if platforms are provided
        if "platforms" not in data or not data["platforms"]:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                message="No platforms defined",
                path="platforms",
                schema_path=""
            ))
        
        # Check URLs
        if "urls" in data and data["urls"]:
            if "website" not in data["urls"] or not data["urls"]["website"]:
                issues.append(ValidationIssue(
                    level=ValidationLevel.WARNING,
                    message="Website URL is not provided",
                    path="urls.website",
                    schema_path=""
                ))