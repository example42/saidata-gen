"""
Validation module for saidata-gen.

This module provides functionality to validate saidata YAML files against
the saidata-0.1.schema.json schema.
"""

from saidata_gen.validation.schema import SchemaValidator

__all__ = ["SchemaValidator"]