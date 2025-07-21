"""
Schema validation module for saidata-gen.

This module provides comprehensive functionality to validate saidata YAML files against
the saidata-0.1.schema.json schema with detailed reporting, suggestions, and auto-fix
recommendations.
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple
from urllib.parse import urlparse

import jsonschema
import yaml

from saidata_gen.core.interfaces import (
    ValidationIssue, ValidationLevel, ValidationResult, BatchValidationResult
)


@dataclass
class ValidationSuggestion:
    """
    Suggestion for fixing a validation issue.
    """
    type: str  # 'fix', 'add', 'remove', 'modify'
    path: str
    current_value: Any
    suggested_value: Any
    reason: str
    confidence: float  # 0.0 to 1.0


@dataclass
class EnhancedValidationIssue(ValidationIssue):
    """
    Enhanced validation issue with suggestions and context.
    """
    suggestions: List[ValidationSuggestion] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    severity_score: float = 0.0  # 0.0 to 1.0, higher is more severe
    auto_fixable: bool = False


@dataclass
class EnhancedValidationResult(ValidationResult):
    """
    Enhanced validation result with detailed reporting.
    """
    issues: List[EnhancedValidationIssue] = field(default_factory=list)
    suggestions: List[ValidationSuggestion] = field(default_factory=list)
    quality_score: float = 0.0  # Overall quality score 0.0 to 1.0
    completeness_score: float = 0.0  # Completeness score 0.0 to 1.0
    field_coverage: Dict[str, bool] = field(default_factory=dict)
    auto_fix_available: bool = False


class SchemaValidator:
    """
    Enhanced validator for saidata YAML files against the saidata-0.1.schema.json schema.
    Provides comprehensive validation with detailed reporting, suggestions, and auto-fix capabilities.
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
        
        # Define expected fields for completeness checking
        self.expected_fields = {
            'version': {'required': False, 'weight': 0.1},
            'description': {'required': False, 'weight': 0.2},
            'license': {'required': False, 'weight': 0.15},
            'platforms': {'required': False, 'weight': 0.1},
            'category': {'required': False, 'weight': 0.1},
            'urls': {'required': False, 'weight': 0.15},
            'packages': {'required': False, 'weight': 0.2}
        }
        
        # Common license identifiers for validation
        self.common_licenses = {
            'MIT', 'Apache-2.0', 'GPL-3.0', 'GPL-2.0', 'BSD-3-Clause', 
            'BSD-2-Clause', 'ISC', 'MPL-2.0', 'LGPL-3.0', 'LGPL-2.1',
            'Unlicense', 'CC0-1.0', 'AGPL-3.0'
        }
        
        # Common platforms for validation
        self.common_platforms = {
            'linux', 'windows', 'macos', 'darwin', 'freebsd', 'openbsd',
            'netbsd', 'solaris', 'aix', 'android', 'ios'
        }
        
        # Common categories for validation
        self.common_categories = {
            'development', 'productivity', 'system', 'network', 'security',
            'multimedia', 'graphics', 'office', 'education', 'games',
            'science', 'database', 'web', 'communication', 'utilities'
        }
    
    def validate_file(self, file_path: Union[str, Path]) -> EnhancedValidationResult:
        """
        Validate a YAML file against the schema with comprehensive reporting.
        
        Args:
            file_path: Path to the YAML file
            
        Returns:
            EnhancedValidationResult with detailed validation information
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                data = yaml.safe_load(content)
            
            return self.validate_data(data, file_path=str(file_path), raw_content=content)
        except yaml.YAMLError as e:
            return EnhancedValidationResult(
                valid=False,
                issues=[
                    EnhancedValidationIssue(
                        level=ValidationLevel.ERROR,
                        message=f"YAML parsing error: {str(e)}",
                        path="",
                        schema_path="",
                        severity_score=1.0,
                        suggestions=[
                            ValidationSuggestion(
                                type='fix',
                                path='',
                                current_value=None,
                                suggested_value=None,
                                reason='Fix YAML syntax errors',
                                confidence=0.9
                            )
                        ]
                    )
                ],
                file_path=str(file_path),
                quality_score=0.0
            )
        except Exception as e:
            return EnhancedValidationResult(
                valid=False,
                issues=[
                    EnhancedValidationIssue(
                        level=ValidationLevel.ERROR,
                        message=f"Failed to load file: {str(e)}",
                        path="",
                        schema_path="",
                        severity_score=1.0
                    )
                ],
                file_path=str(file_path),
                quality_score=0.0
            )
    
    def validate_data(self, data: Dict[str, Any], file_path: Optional[str] = None, 
                     raw_content: Optional[str] = None) -> EnhancedValidationResult:
        """
        Validate data against the schema with comprehensive analysis.
        
        Args:
            data: Data to validate
            file_path: Optional file path for reference
            raw_content: Optional raw file content for context
            
        Returns:
            EnhancedValidationResult with detailed validation information
        """
        if data is None:
            data = {}
            
        issues = []
        suggestions = []
        
        # Schema validation
        for error in self.validator.iter_errors(data):
            path = "/".join(str(p) for p in error.path) if error.path else ""
            schema_path = "/".join(str(p) for p in error.schema_path) if error.schema_path else ""
            
            # Create enhanced issue with suggestions
            enhanced_issue = self._create_enhanced_issue(error, path, schema_path, data)
            issues.append(enhanced_issue)
            suggestions.extend(enhanced_issue.suggestions)
        
        # Additional comprehensive validations
        additional_issues, additional_suggestions = self._perform_comprehensive_validation(data)
        issues.extend(additional_issues)
        suggestions.extend(additional_suggestions)
        
        # Calculate quality and completeness scores
        quality_score = self._calculate_quality_score(data, issues)
        completeness_score = self._calculate_completeness_score(data)
        field_coverage = self._calculate_field_coverage(data)
        
        # Check if auto-fix is available
        auto_fix_available = any(issue.auto_fixable for issue in issues)
        
        return EnhancedValidationResult(
            valid=len([i for i in issues if i.level == ValidationLevel.ERROR]) == 0,
            issues=issues,
            suggestions=suggestions,
            file_path=file_path,
            quality_score=quality_score,
            completeness_score=completeness_score,
            field_coverage=field_coverage,
            auto_fix_available=auto_fix_available
        )
    
    def _create_enhanced_issue(self, error: jsonschema.ValidationError, path: str, 
                              schema_path: str, data: Dict[str, Any]) -> EnhancedValidationIssue:
        """
        Create an enhanced validation issue with suggestions.
        """
        suggestions = []
        severity_score = 0.5
        auto_fixable = False
        
        # Analyze the error and create suggestions
        if "is not of type" in error.message:
            # Type mismatch - suggest correct type
            expected_type = error.schema.get('type', 'unknown')
            current_value = self._get_value_at_path(data, path)
            
            if expected_type == 'string' and current_value is not None:
                suggestions.append(ValidationSuggestion(
                    type='modify',
                    path=path,
                    current_value=current_value,
                    suggested_value=str(current_value),
                    reason=f'Convert to string type',
                    confidence=0.8
                ))
                auto_fixable = True
            elif expected_type == 'array' and not isinstance(current_value, list):
                suggestions.append(ValidationSuggestion(
                    type='modify',
                    path=path,
                    current_value=current_value,
                    suggested_value=[current_value] if current_value is not None else [],
                    reason=f'Convert to array type',
                    confidence=0.7
                ))
                auto_fixable = True
                
        elif "is a required property" in error.message:
            # Missing required property
            missing_prop = error.message.split("'")[1]
            suggestions.append(ValidationSuggestion(
                type='add',
                path=f"{path}.{missing_prop}" if path else missing_prop,
                current_value=None,
                suggested_value=self._get_default_value_for_property(missing_prop),
                reason=f'Add required property {missing_prop}',
                confidence=0.9
            ))
            severity_score = 0.8
            auto_fixable = True
            
        elif "Additional properties are not allowed" in error.message:
            # Extra properties
            severity_score = 0.3
            suggestions.append(ValidationSuggestion(
                type='remove',
                path=path,
                current_value=self._get_value_at_path(data, path),
                suggested_value=None,
                reason='Remove additional property not allowed by schema',
                confidence=0.6
            ))
        
        return EnhancedValidationIssue(
            level=ValidationLevel.ERROR,
            message=error.message,
            path=path,
            schema_path=schema_path,
            suggestions=suggestions,
            severity_score=severity_score,
            auto_fixable=auto_fixable,
            context={'schema_constraint': error.schema}
        )
    
    def _perform_comprehensive_validation(self, data: Dict[str, Any]) -> Tuple[List[EnhancedValidationIssue], List[ValidationSuggestion]]:
        """
        Perform comprehensive validation beyond schema checking.
        """
        issues = []
        suggestions = []
        
        # Version validation
        if "version" not in data or not data["version"]:
            issues.append(EnhancedValidationIssue(
                level=ValidationLevel.WARNING,
                message="Version is not specified",
                path="version",
                schema_path="",
                suggestions=[ValidationSuggestion(
                    type='add',
                    path='version',
                    current_value=None,
                    suggested_value='0.1',
                    reason='Add schema version',
                    confidence=0.9
                )],
                severity_score=0.3,
                auto_fixable=True
            ))
        
        # Description validation
        if "description" not in data or not data["description"]:
            issues.append(EnhancedValidationIssue(
                level=ValidationLevel.WARNING,
                message="Description is not provided",
                path="description",
                schema_path="",
                suggestions=[ValidationSuggestion(
                    type='add',
                    path='description',
                    current_value=None,
                    suggested_value='[Add software description]',
                    reason='Add software description for better documentation',
                    confidence=0.7
                )],
                severity_score=0.4,
                auto_fixable=False
            ))
        elif len(data["description"]) < 10:
            issues.append(EnhancedValidationIssue(
                level=ValidationLevel.INFO,
                message="Description is very short",
                path="description",
                schema_path="",
                suggestions=[ValidationSuggestion(
                    type='modify',
                    path='description',
                    current_value=data["description"],
                    suggested_value=f"{data['description']} [Add more details]",
                    reason='Expand description for better clarity',
                    confidence=0.5
                )],
                severity_score=0.2,
                auto_fixable=False
            ))
        
        # License validation
        license_issues, license_suggestions = self._validate_license(data)
        issues.extend(license_issues)
        suggestions.extend(license_suggestions)
        
        # Platform validation
        platform_issues, platform_suggestions = self._validate_platforms(data)
        issues.extend(platform_issues)
        suggestions.extend(platform_suggestions)
        
        # URL validation
        url_issues, url_suggestions = self._validate_urls(data)
        issues.extend(url_issues)
        suggestions.extend(url_suggestions)
        
        # Category validation
        category_issues, category_suggestions = self._validate_category(data)
        issues.extend(category_issues)
        suggestions.extend(category_suggestions)
        
        # Package validation
        package_issues, package_suggestions = self._validate_packages(data)
        issues.extend(package_issues)
        suggestions.extend(package_suggestions)
        
        return issues, suggestions
    
    def _validate_license(self, data: Dict[str, Any]) -> Tuple[List[EnhancedValidationIssue], List[ValidationSuggestion]]:
        """Validate license field."""
        issues = []
        suggestions = []
        
        if "license" not in data or not data["license"]:
            issues.append(EnhancedValidationIssue(
                level=ValidationLevel.WARNING,
                message="License is not provided",
                path="license",
                schema_path="",
                suggestions=[ValidationSuggestion(
                    type='add',
                    path='license',
                    current_value=None,
                    suggested_value='MIT',
                    reason='Add license information (MIT is commonly used)',
                    confidence=0.6
                )],
                severity_score=0.4,
                auto_fixable=False
            ))
        elif data["license"] not in self.common_licenses:
            # Check if it's a close match to a common license
            close_matches = self._find_close_matches(data["license"], self.common_licenses)
            if close_matches:
                issues.append(EnhancedValidationIssue(
                    level=ValidationLevel.INFO,
                    message=f"License '{data['license']}' is not a common SPDX identifier",
                    path="license",
                    schema_path="",
                    suggestions=[ValidationSuggestion(
                        type='modify',
                        path='license',
                        current_value=data["license"],
                        suggested_value=close_matches[0],
                        reason=f'Use standard SPDX license identifier',
                        confidence=0.7
                    )],
                    severity_score=0.2,
                    auto_fixable=True
                ))
        
        return issues, suggestions
    
    def _validate_platforms(self, data: Dict[str, Any]) -> Tuple[List[EnhancedValidationIssue], List[ValidationSuggestion]]:
        """Validate platforms field."""
        issues = []
        suggestions = []
        
        if "platforms" not in data or not data["platforms"]:
            issues.append(EnhancedValidationIssue(
                level=ValidationLevel.WARNING,
                message="No platforms defined",
                path="platforms",
                schema_path="",
                suggestions=[ValidationSuggestion(
                    type='add',
                    path='platforms',
                    current_value=None,
                    suggested_value=['linux'],
                    reason='Add supported platforms',
                    confidence=0.7
                )],
                severity_score=0.3,
                auto_fixable=True
            ))
        elif isinstance(data["platforms"], list):
            for i, platform in enumerate(data["platforms"]):
                if platform.lower() not in self.common_platforms:
                    close_matches = self._find_close_matches(platform.lower(), self.common_platforms)
                    if close_matches:
                        issues.append(EnhancedValidationIssue(
                            level=ValidationLevel.INFO,
                            message=f"Platform '{platform}' might not be standard",
                            path=f"platforms[{i}]",
                            schema_path="",
                            suggestions=[ValidationSuggestion(
                                type='modify',
                                path=f'platforms[{i}]',
                                current_value=platform,
                                suggested_value=close_matches[0],
                                reason=f'Use standard platform name',
                                confidence=0.6
                            )],
                            severity_score=0.1,
                            auto_fixable=True
                        ))
        
        return issues, suggestions
    
    def _validate_urls(self, data: Dict[str, Any]) -> Tuple[List[EnhancedValidationIssue], List[ValidationSuggestion]]:
        """Validate URLs field."""
        issues = []
        suggestions = []
        
        if "urls" not in data or not data["urls"]:
            issues.append(EnhancedValidationIssue(
                level=ValidationLevel.WARNING,
                message="No URLs provided",
                path="urls",
                schema_path="",
                suggestions=[ValidationSuggestion(
                    type='add',
                    path='urls',
                    current_value=None,
                    suggested_value={'website': '[Add website URL]'},
                    reason='Add relevant URLs for the software',
                    confidence=0.6
                )],
                severity_score=0.3,
                auto_fixable=False
            ))
        elif isinstance(data["urls"], dict):
            # Validate individual URLs
            for url_type, url_value in data["urls"].items():
                if url_value and not self._is_valid_url(url_value):
                    issues.append(EnhancedValidationIssue(
                        level=ValidationLevel.ERROR,
                        message=f"Invalid URL format for {url_type}",
                        path=f"urls.{url_type}",
                        schema_path="",
                        suggestions=[ValidationSuggestion(
                            type='modify',
                            path=f'urls.{url_type}',
                            current_value=url_value,
                            suggested_value=self._fix_url(url_value),
                            reason='Fix URL format',
                            confidence=0.8
                        )],
                        severity_score=0.6,
                        auto_fixable=True
                    ))
            
            # Check for missing important URLs
            if "website" not in data["urls"] or not data["urls"]["website"]:
                issues.append(EnhancedValidationIssue(
                    level=ValidationLevel.INFO,
                    message="Website URL is not provided",
                    path="urls.website",
                    schema_path="",
                    suggestions=[ValidationSuggestion(
                        type='add',
                        path='urls.website',
                        current_value=None,
                        suggested_value='[Add website URL]',
                        reason='Add website URL for better documentation',
                        confidence=0.5
                    )],
                    severity_score=0.2,
                    auto_fixable=False
                ))
        
        return issues, suggestions
    
    def _validate_category(self, data: Dict[str, Any]) -> Tuple[List[EnhancedValidationIssue], List[ValidationSuggestion]]:
        """Validate category field."""
        issues = []
        suggestions = []
        
        if "category" not in data or not data["category"]:
            issues.append(EnhancedValidationIssue(
                level=ValidationLevel.WARNING,
                message="Category is not provided",
                path="category",
                schema_path="",
                suggestions=[ValidationSuggestion(
                    type='add',
                    path='category',
                    current_value=None,
                    suggested_value={'default': 'utilities'},
                    reason='Add category for better organization',
                    confidence=0.6
                )],
                severity_score=0.3,
                auto_fixable=True
            ))
        elif isinstance(data["category"], dict):
            if "default" not in data["category"] or not data["category"]["default"]:
                issues.append(EnhancedValidationIssue(
                    level=ValidationLevel.WARNING,
                    message="Default category is not provided",
                    path="category.default",
                    schema_path="",
                    suggestions=[ValidationSuggestion(
                        type='add',
                        path='category.default',
                        current_value=None,
                        suggested_value='utilities',
                        reason='Add default category',
                        confidence=0.7
                    )],
                    severity_score=0.3,
                    auto_fixable=True
                ))
            elif data["category"]["default"] not in self.common_categories:
                close_matches = self._find_close_matches(data["category"]["default"], self.common_categories)
                if close_matches:
                    issues.append(EnhancedValidationIssue(
                        level=ValidationLevel.INFO,
                        message=f"Category '{data['category']['default']}' is not a common category",
                        path="category.default",
                        schema_path="",
                        suggestions=[ValidationSuggestion(
                            type='modify',
                            path='category.default',
                            current_value=data["category"]["default"],
                            suggested_value=close_matches[0],
                            reason='Use common category name',
                            confidence=0.6
                        )],
                        severity_score=0.1,
                        auto_fixable=True
                    ))
        
        return issues, suggestions
    
    def _validate_packages(self, data: Dict[str, Any]) -> Tuple[List[EnhancedValidationIssue], List[ValidationSuggestion]]:
        """Validate packages field."""
        issues = []
        suggestions = []
        
        if "packages" not in data or not data["packages"]:
            issues.append(EnhancedValidationIssue(
                level=ValidationLevel.WARNING,
                message="No packages defined",
                path="packages",
                schema_path="",
                suggestions=[ValidationSuggestion(
                    type='add',
                    path='packages',
                    current_value=None,
                    suggested_value={'default': {'name': '[package-name]'}},
                    reason='Add package definitions',
                    confidence=0.6
                )],
                severity_score=0.4,
                auto_fixable=False
            ))
        elif isinstance(data["packages"], dict):
            for pkg_key, pkg_config in data["packages"].items():
                if isinstance(pkg_config, dict):
                    if "name" not in pkg_config or not pkg_config["name"]:
                        issues.append(EnhancedValidationIssue(
                            level=ValidationLevel.WARNING,
                            message=f"Package '{pkg_key}' has no name specified",
                            path=f"packages.{pkg_key}.name",
                            schema_path="",
                            suggestions=[ValidationSuggestion(
                                type='add',
                                path=f'packages.{pkg_key}.name',
                                current_value=None,
                                suggested_value=pkg_key if pkg_key != 'default' else '[package-name]',
                                reason='Add package name',
                                confidence=0.8
                            )],
                            severity_score=0.3,
                            auto_fixable=True
                        ))
        
        return issues, suggestions

    def validate_batch(self, file_paths: List[Union[str, Path]]) -> BatchValidationResult:
        """
        Validate multiple YAML files against the schema with enhanced reporting.
        
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
            "warnings": 0,
            "info": 0,
            "auto_fixable": 0,
            "avg_quality_score": 0.0,
            "avg_completeness_score": 0.0
        }
        
        total_quality = 0.0
        total_completeness = 0.0
        
        for file_path in file_paths:
            result = self.validate_file(file_path)
            results[str(file_path)] = result
            
            if result.valid:
                summary["valid"] += 1
            else:
                summary["invalid"] += 1
            
            summary["errors"] += len([i for i in result.issues if i.level == ValidationLevel.ERROR])
            summary["warnings"] += len([i for i in result.issues if i.level == ValidationLevel.WARNING])
            summary["info"] += len([i for i in result.issues if i.level == ValidationLevel.INFO])
            
            if hasattr(result, 'auto_fix_available') and result.auto_fix_available:
                summary["auto_fixable"] += 1
            
            if hasattr(result, 'quality_score'):
                total_quality += result.quality_score
            if hasattr(result, 'completeness_score'):
                total_completeness += result.completeness_score
        
        if len(file_paths) > 0:
            summary["avg_quality_score"] = total_quality / len(file_paths)
            summary["avg_completeness_score"] = total_completeness / len(file_paths)
        
        return BatchValidationResult(
            results=results,
            summary=summary
        )
    
    def get_schema_info(self) -> Dict[str, Any]:
        """
        Get comprehensive information about the schema.
        
        Returns:
            Dictionary with schema information
        """
        return {
            "title": self.schema.get("title", ""),
            "version": self.schema.get("version", ""),
            "properties": list(self.schema.get("properties", {}).keys()),
            "definitions": list(self.schema.get("definitions", {}).keys()),
            "expected_fields": list(self.expected_fields.keys()),
            "common_licenses": list(self.common_licenses),
            "common_platforms": list(self.common_platforms),
            "common_categories": list(self.common_categories)
        }
    
    def apply_auto_fixes(self, data: Dict[str, Any], suggestions: List[ValidationSuggestion]) -> Dict[str, Any]:
        """
        Apply auto-fixable suggestions to the data.
        
        Args:
            data: Original data
            suggestions: List of validation suggestions
            
        Returns:
            Fixed data
        """
        fixed_data = data.copy()
        
        for suggestion in suggestions:
            if suggestion.confidence >= 0.7:  # Only apply high-confidence fixes
                try:
                    if suggestion.type == 'add':
                        self._set_value_at_path(fixed_data, suggestion.path, suggestion.suggested_value)
                    elif suggestion.type == 'modify':
                        self._set_value_at_path(fixed_data, suggestion.path, suggestion.suggested_value)
                    elif suggestion.type == 'remove':
                        self._remove_value_at_path(fixed_data, suggestion.path)
                except Exception:
                    # Skip fixes that fail
                    continue
        
        return fixed_data
    
    def generate_validation_report(self, result: EnhancedValidationResult) -> str:
        """
        Generate a human-readable validation report.
        
        Args:
            result: Enhanced validation result
            
        Returns:
            Formatted validation report
        """
        report = []
        
        if result.file_path:
            report.append(f"Validation Report for: {result.file_path}")
        else:
            report.append("Validation Report")
        
        report.append("=" * 50)
        
        # Overall status
        status = "✅ VALID" if result.valid else "❌ INVALID"
        report.append(f"Status: {status}")
        
        if hasattr(result, 'quality_score'):
            report.append(f"Quality Score: {result.quality_score:.2f}/1.0")
        if hasattr(result, 'completeness_score'):
            report.append(f"Completeness Score: {result.completeness_score:.2f}/1.0")
        
        report.append("")
        
        # Issues summary
        errors = [i for i in result.issues if i.level == ValidationLevel.ERROR]
        warnings = [i for i in result.issues if i.level == ValidationLevel.WARNING]
        info = [i for i in result.issues if i.level == ValidationLevel.INFO]
        
        report.append(f"Issues Summary:")
        report.append(f"  Errors: {len(errors)}")
        report.append(f"  Warnings: {len(warnings)}")
        report.append(f"  Info: {len(info)}")
        
        if hasattr(result, 'auto_fix_available') and result.auto_fix_available:
            report.append(f"  Auto-fixable: Yes")
        
        report.append("")
        
        # Detailed issues
        if result.issues:
            report.append("Detailed Issues:")
            report.append("-" * 20)
            
            for issue in result.issues:
                level_icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(issue.level.value, "•")
                report.append(f"{level_icon} {issue.level.value.upper()}: {issue.message}")
                
                if issue.path:
                    report.append(f"   Path: {issue.path}")
                
                if hasattr(issue, 'suggestions') and issue.suggestions:
                    report.append(f"   Suggestions:")
                    for suggestion in issue.suggestions:
                        confidence_icon = "🔧" if suggestion.confidence >= 0.7 else "💡"
                        report.append(f"     {confidence_icon} {suggestion.reason}")
                        if suggestion.type == 'add':
                            report.append(f"        Add: {suggestion.suggested_value}")
                        elif suggestion.type == 'modify':
                            report.append(f"        Change '{suggestion.current_value}' to '{suggestion.suggested_value}'")
                        elif suggestion.type == 'remove':
                            report.append(f"        Remove: {suggestion.current_value}")
                
                report.append("")
        
        # Field coverage
        if hasattr(result, 'field_coverage') and result.field_coverage:
            report.append("Field Coverage:")
            report.append("-" * 15)
            for field, present in result.field_coverage.items():
                status_icon = "✅" if present else "❌"
                report.append(f"  {status_icon} {field}")
            report.append("")
        
        return "\n".join(report)
    
    def _get_value_at_path(self, data: Dict[str, Any], path: str) -> Any:
        """Get value at a given path in the data structure."""
        if not path:
            return data
        
        parts = path.split('.')
        current = data
        
        for part in parts:
            if '[' in part and ']' in part:
                # Handle array indices like "platforms[0]"
                key, index_str = part.split('[')
                index = int(index_str.rstrip(']'))
                if key in current and isinstance(current[key], list) and len(current[key]) > index:
                    current = current[key][index]
                else:
                    return None
            else:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return None
        
        return current
    
    def _set_value_at_path(self, data: Dict[str, Any], path: str, value: Any) -> None:
        """Set value at a given path in the data structure."""
        if not path:
            return
        
        parts = path.split('.')
        current = data
        
        for i, part in enumerate(parts[:-1]):
            if '[' in part and ']' in part:
                # Handle array indices
                key, index_str = part.split('[')
                index = int(index_str.rstrip(']'))
                if key not in current:
                    current[key] = []
                while len(current[key]) <= index:
                    current[key].append(None)
                if current[key][index] is None:
                    current[key][index] = {}
                current = current[key][index]
            else:
                if part not in current:
                    current[part] = {}
                current = current[part]
        
        # Set the final value
        final_part = parts[-1]
        if '[' in final_part and ']' in final_part:
            key, index_str = final_part.split('[')
            index = int(index_str.rstrip(']'))
            if key not in current:
                current[key] = []
            while len(current[key]) <= index:
                current[key].append(None)
            current[key][index] = value
        else:
            current[final_part] = value
    
    def _remove_value_at_path(self, data: Dict[str, Any], path: str) -> None:
        """Remove value at a given path in the data structure."""
        if not path:
            return
        
        parts = path.split('.')
        current = data
        
        for part in parts[:-1]:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return
        
        final_part = parts[-1]
        if isinstance(current, dict) and final_part in current:
            del current[final_part]
    
    def _get_default_value_for_property(self, property_name: str) -> Any:
        """Get a sensible default value for a property."""
        defaults = {
            'version': '0.1',
            'description': '[Add description]',
            'license': 'MIT',
            'platforms': ['linux'],
            'category': {'default': 'utilities'},
            'urls': {'website': '[Add website URL]'},
            'packages': {'default': {'name': '[package-name]'}}
        }
        return defaults.get(property_name, None)
    
    def _find_close_matches(self, value: str, candidates: set, threshold: float = 0.6) -> List[str]:
        """Find close matches for a value in a set of candidates."""
        import difflib
        matches = difflib.get_close_matches(value, candidates, n=3, cutoff=threshold)
        return matches
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if a URL is valid."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def _fix_url(self, url: str) -> str:
        """Attempt to fix a malformed URL."""
        if not url.startswith(('http://', 'https://')):
            return f'https://{url}'
        return url
    
    def _calculate_quality_score(self, data: Dict[str, Any], issues: List[EnhancedValidationIssue]) -> float:
        """Calculate overall quality score based on issues and data completeness."""
        if not data:
            return 0.0
        
        # Start with base score
        score = 1.0
        
        # Deduct points for issues
        for issue in issues:
            if hasattr(issue, 'severity_score'):
                if issue.level == ValidationLevel.ERROR:
                    score -= issue.severity_score * 0.3
                elif issue.level == ValidationLevel.WARNING:
                    score -= issue.severity_score * 0.1
                elif issue.level == ValidationLevel.INFO:
                    score -= issue.severity_score * 0.05
        
        return max(0.0, min(1.0, score))
    
    def _calculate_completeness_score(self, data: Dict[str, Any]) -> float:
        """Calculate completeness score based on expected fields."""
        if not data:
            return 0.0
        
        total_weight = sum(field_info['weight'] for field_info in self.expected_fields.values())
        achieved_weight = 0.0
        
        for field, field_info in self.expected_fields.items():
            if field in data and data[field]:
                # Additional checks for complex fields
                if field == 'urls' and isinstance(data[field], dict):
                    # Partial credit for URLs based on how many are provided
                    url_count = len([v for v in data[field].values() if v])
                    achieved_weight += field_info['weight'] * min(1.0, url_count / 3)
                elif field == 'category' and isinstance(data[field], dict):
                    # Check if default category is provided
                    if data[field].get('default'):
                        achieved_weight += field_info['weight']
                    else:
                        achieved_weight += field_info['weight'] * 0.5
                elif field == 'packages' and isinstance(data[field], dict):
                    # Check if packages have names
                    valid_packages = sum(1 for pkg in data[field].values() 
                                       if isinstance(pkg, dict) and pkg.get('name'))
                    if valid_packages > 0:
                        achieved_weight += field_info['weight']
                    else:
                        achieved_weight += field_info['weight'] * 0.5
                else:
                    achieved_weight += field_info['weight']
        
        return achieved_weight / total_weight if total_weight > 0 else 0.0
    
    def _calculate_field_coverage(self, data: Dict[str, Any]) -> Dict[str, bool]:
        """Calculate which expected fields are present."""
        coverage = {}
        
        for field in self.expected_fields:
            coverage[field] = field in data and data[field] is not None
            
            # Special handling for complex fields
            if field == 'category' and coverage[field]:
                coverage[field] = isinstance(data[field], dict) and bool(data[field].get('default'))
            elif field == 'urls' and coverage[field]:
                coverage[field] = isinstance(data[field], dict) and any(data[field].values())
            elif field == 'packages' and coverage[field]:
                coverage[field] = isinstance(data[field], dict) and bool(data[field])
        
        return coverage