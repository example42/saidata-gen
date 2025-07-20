"""
Template engine for saidata metadata generation.

This module provides a template engine for applying defaults and provider-specific
configurations to saidata metadata.
"""

import os
import re
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from saidata_gen.core.interfaces import SaidataMetadata


logger = logging.getLogger(__name__)


class TemplateEngine:
    """
    Template engine for applying defaults and provider-specific configurations.
    
    This class provides methods for loading templates, applying variable substitution,
    and merging templates with metadata.
    """
    
    def __init__(self, templates_dir: Optional[str] = None):
        """
        Initialize the template engine.
        
        Args:
            templates_dir: Directory containing template files. If None, uses the default
                templates directory in the package.
        """
        if templates_dir is None:
            # Use the default templates directory in the package
            package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.templates_dir = os.path.join(package_dir, "templates")
        else:
            self.templates_dir = os.path.expanduser(templates_dir)
        
        # Create the templates directory if it doesn't exist
        os.makedirs(self.templates_dir, exist_ok=True)
        
        # Load the default template
        self.default_template = self._load_default_template()
        
        # Load provider-specific templates
        self.provider_templates = self._load_provider_templates()
    
    def _load_default_template(self) -> Dict[str, Any]:
        """
        Load the default template.
        
        Returns:
            Default template as a dictionary.
        """
        default_path = os.path.join(self.templates_dir, "defaults.yaml")
        
        # If the default template doesn't exist, create it with basic structure
        if not os.path.exists(default_path):
            self._create_default_template(default_path)
        
        try:
            with open(default_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load default template: {e}")
            return {}
    
    def _create_default_template(self, path: str) -> None:
        """
        Create a default template file.
        
        Args:
            path: Path to create the template at.
        """
        # Create a basic default template
        default_template = {
            "version": "0.1",
            "packages": {
                "default": {
                    "name": "$software_name",
                    "version": "latest"
                }
            },
            "services": {
                "default": {
                    "name": "$software_name"
                }
            },
            "directories": {
                "config": {
                    "path": "/etc/$software_name",
                    "owner": "root",
                    "group": "root",
                    "mode": "0755"
                }
            },
            "urls": {},
            "category": {
                "default": None,
                "sub": None,
                "tags": []
            },
            "platforms": []
        }
        
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Write the template to the file
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(default_template, f, default_flow_style=False)
    
    def _load_provider_templates(self) -> Dict[str, Dict[str, Any]]:
        """
        Load provider-specific templates.
        
        Returns:
            Dictionary mapping provider names to their templates.
        """
        provider_templates = {}
        providers_dir = os.path.join(self.templates_dir, "providers")
        
        # Create the providers directory if it doesn't exist
        os.makedirs(providers_dir, exist_ok=True)
        
        # Load templates from the providers directory
        if os.path.exists(providers_dir):
            for filename in os.listdir(providers_dir):
                if filename.endswith(".yaml") or filename.endswith(".yml"):
                    provider_name = os.path.splitext(filename)[0]
                    try:
                        with open(os.path.join(providers_dir, filename), 'r', encoding='utf-8') as f:
                            provider_templates[provider_name] = yaml.safe_load(f) or {}
                    except Exception as e:
                        logger.error(f"Failed to load provider template {filename}: {e}")
        
        return provider_templates
    
    def apply_template(
        self,
        software_name: str,
        metadata: Optional[Dict[str, Any]] = None,
        providers: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Apply templates to metadata.
        
        Args:
            software_name: Name of the software.
            metadata: Existing metadata to apply templates to. If None, starts with an empty dict.
            providers: List of providers to apply templates for. If None, applies all available provider templates.
            
        Returns:
            Metadata with templates applied.
        """
        # Start with the default template
        result = self._deep_copy(self.default_template)
        
        # Apply variable substitution to the default template
        result = self._substitute_variables(result, {"software_name": software_name})
        
        # Apply provider-specific templates
        if providers:
            for provider in providers:
                if provider in self.provider_templates:
                    provider_template = self._deep_copy(self.provider_templates[provider])
                    provider_template = self._substitute_variables(provider_template, {"software_name": software_name})
                    result = self._deep_merge(result, provider_template)
        
        # Apply the existing metadata on top
        if metadata:
            result = self._deep_merge(result, metadata)
        
        return result
    
    def _substitute_variables(self, data: Any, variables: Dict[str, str]) -> Any:
        """
        Substitute variables in data.
        
        Args:
            data: Data to substitute variables in.
            variables: Dictionary mapping variable names to their values.
            
        Returns:
            Data with variables substituted.
        """
        if isinstance(data, str):
            # Substitute variables in strings
            for var_name, var_value in variables.items():
                data = data.replace(f"${var_name}", var_value)
            return data
        elif isinstance(data, dict):
            # Recursively substitute variables in dictionaries
            return {k: self._substitute_variables(v, variables) for k, v in data.items()}
        elif isinstance(data, list):
            # Recursively substitute variables in lists
            return [self._substitute_variables(item, variables) for item in data]
        else:
            # Return other types as-is
            return data
    
    def _deep_merge(self, base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries.
        
        Args:
            base: Base dictionary.
            overlay: Dictionary to overlay on top of the base.
            
        Returns:
            Merged dictionary.
        """
        result = self._deep_copy(base)
        
        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge dictionaries
                result[key] = self._deep_merge(result[key], value)
            else:
                # Replace or add the value
                result[key] = self._deep_copy(value)
        
        return result
    
    def _deep_copy(self, data: Any) -> Any:
        """
        Deep copy data.
        
        Args:
            data: Data to copy.
            
        Returns:
            Deep copy of the data.
        """
        if isinstance(data, dict):
            return {k: self._deep_copy(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._deep_copy(item) for item in data]
        else:
            return data
    
    def evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """
        Evaluate a condition in the context.
        
        Args:
            condition: Condition to evaluate.
            context: Context to evaluate the condition in.
            
        Returns:
            Result of the condition evaluation.
        """
        # Simple condition evaluation for now
        # Format: "variable == value" or "variable != value"
        condition = condition.strip()
        
        if "==" in condition:
            var_name, value = condition.split("==", 1)
            var_name = var_name.strip()
            value = value.strip()
            
            # Get the variable value from the context
            var_value = self._get_nested_value(context, var_name)
            
            # Compare as strings
            return str(var_value) == value
        elif "!=" in condition:
            var_name, value = condition.split("!=", 1)
            var_name = var_name.strip()
            value = value.strip()
            
            # Get the variable value from the context
            var_value = self._get_nested_value(context, var_name)
            
            # Compare as strings
            return str(var_value) != value
        elif "in" in condition:
            var_name, value = condition.split("in", 1)
            var_name = var_name.strip()
            value = value.strip()
            
            # Get the variable value from the context
            var_value = self._get_nested_value(context, var_name)
            
            # Check if the value is in the list
            try:
                value_list = eval(value)
                return var_value in value_list
            except:
                return False
        else:
            # Unknown condition format
            logger.warning(f"Unknown condition format: {condition}")
            return False
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """
        Get a nested value from a dictionary using a dot-separated path.
        
        Args:
            data: Dictionary to get the value from.
            path: Dot-separated path to the value.
            
        Returns:
            Value at the path, or None if not found.
        """
        parts = path.split(".")
        current = data
        
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        return current