"""
Generator module for saidata-gen.

This module provides functionality for generating saidata metadata from multiple sources.
"""

from saidata_gen.generator.core import MetadataGenerator
from saidata_gen.generator.templates import TemplateEngine

__all__ = ["MetadataGenerator", "TemplateEngine"]