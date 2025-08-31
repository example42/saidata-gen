"""
Validation module for saidata-gen.

This module provides functionality to validate saidata YAML files against
the saidata-0.1.schema.json schema, as well as comprehensive quality assessment
and verification capabilities.
"""

from saidata_gen.validation.schema import SchemaValidator
from saidata_gen.validation.quality import (
    QualityAssessment, QualityReport, FieldQuality, SourceAttribution,
    CrossReferenceResult
)
from saidata_gen.validation.config_validator import (
    ConfigurationValidator, ConfigurationSuggestion, ProviderOverrideValidationResult,
    ConfigurationValidationReport
)

__all__ = [
    "SchemaValidator",
    "QualityAssessment", 
    "QualityReport",
    "FieldQuality",
    "SourceAttribution",
    "CrossReferenceResult",
    "ConfigurationValidator",
    "ConfigurationSuggestion",
    "ProviderOverrideValidationResult",
    "ConfigurationValidationReport"
]