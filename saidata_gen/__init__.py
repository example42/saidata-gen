"""
Saidata Generator - A standalone tool for generating saidata YAML files.

This package provides functionality to generate, validate, and manage software metadata
in YAML format following the saidata-0.1.schema.json specification.
"""

__version__ = "0.1.0"
__author__ = "Saidata Generator Team"
__email__ = "contact@saidata.org"

from .core.engine import SaidataEngine
from .core.exceptions import SaidataGenError, ValidationError, FetchError, GenerationError

__all__ = [
    "SaidataEngine",
    "SaidataGenError", 
    "ValidationError",
    "FetchError", 
    "GenerationError"
]