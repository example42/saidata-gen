"""
Configuration management for saidata-gen.

This module provides the ConfigurationManager class for handling loading of base defaults
and provider defaults, merging configurations with software-specific overrides, and
determining when provider files are needed.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

from saidata_gen.core.exceptions import ConfigurationError


logger = logging.getLogger(__name__)


class ConfigurationManager:
    """
    Manages loading and merging of configuration files for saidata-gen.
    
    This class handles:
    - Loading base defaults from defaults.yaml
    - Loading provider defaults from provider_defaults.yaml
    - Merging configurations with software-specific overrides
    - Determining when provider files need to be created
    """
    
    def __init__(self, templates_dir: Optional[Union[str, Path]] = None):
        """
        Initialize the configuration manager.
        
        Args:
            templates_dir: Directory containing template files. If None, uses the default
                templates directory in the package.
        """
        if templates_dir is None:
            # Use the default templates directory in the package
            package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.templates_dir = Path(package_dir) / "templates"
        else:
            self.templates_dir = Path(templates_dir).expanduser().resolve()
        
        # Validate templates directory exists
        if not self.templates_dir.exists():
            raise ConfigurationError(f"Templates directory does not exist: {self.templates_dir}")
        
        # Cache for loaded configurations
        self._base_defaults_cache: Optional[Dict[str, Any]] = None
        self._provider_defaults_cache: Optional[Dict[str, Dict[str, Any]]] = None
        
        logger.debug(f"ConfigurationManager initialized with templates_dir: {self.templates_dir}")
    
    def load_base_defaults(self) -> Dict[str, Any]:
        """
        Load the base defaults from defaults.yaml.
        
        Returns:
            Dictionary containing the base default configuration.
            
        Raises:
            ConfigurationError: If the defaults.yaml file cannot be loaded.
        """
        if self._base_defaults_cache is not None:
            return self._base_defaults_cache
        
        defaults_path = self.templates_dir / "defaults.yaml"
        
        if not defaults_path.exists():
            raise ConfigurationError(f"Base defaults file not found: {defaults_path}")
        
        try:
            with open(defaults_path, 'r', encoding='utf-8') as f:
                self._base_defaults_cache = yaml.safe_load(f) or {}
            
            logger.debug(f"Loaded base defaults from {defaults_path}")
            return self._base_defaults_cache
            
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Error parsing base defaults YAML: {e}")
        except IOError as e:
            raise ConfigurationError(f"Error reading base defaults file: {e}")
    
    def load_provider_defaults(self) -> Dict[str, Dict[str, Any]]:
        """
        Load provider defaults from provider_defaults.yaml.
        
        Returns:
            Dictionary mapping provider names to their default configurations.
            
        Raises:
            ConfigurationError: If the provider_defaults.yaml file cannot be loaded.
        """
        if self._provider_defaults_cache is not None:
            return self._provider_defaults_cache
        
        provider_defaults_path = self.templates_dir / "provider_defaults.yaml"
        
        if not provider_defaults_path.exists():
            raise ConfigurationError(f"Provider defaults file not found: {provider_defaults_path}")
        
        try:
            with open(provider_defaults_path, 'r', encoding='utf-8') as f:
                raw_data = yaml.safe_load(f) or {}
            
            # Filter out the version key and any other non-provider keys
            self._provider_defaults_cache = {}
            for key, value in raw_data.items():
                if key != "version" and isinstance(value, dict):
                    self._provider_defaults_cache[key] = value
            
            logger.debug(f"Loaded provider defaults for {len(self._provider_defaults_cache)} providers from {provider_defaults_path}")
            return self._provider_defaults_cache
            
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Error parsing provider defaults YAML: {e}")
        except IOError as e:
            raise ConfigurationError(f"Error reading provider defaults file: {e}")
    
    def get_provider_config(
        self, 
        provider: str, 
        software_name: str, 
        software_overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get the merged configuration for a specific provider.
        
        This method merges provider defaults with software-specific overrides,
        applying variable substitution for the software name.
        
        Args:
            provider: Name of the provider (e.g., 'apt', 'brew', 'winget').
            software_name: Name of the software package.
            software_overrides: Optional software-specific configuration overrides.
            
        Returns:
            Dictionary containing the merged provider configuration.
            
        Raises:
            ConfigurationError: If the provider is not found in defaults.
        """
        provider_defaults = self.load_provider_defaults()
        
        if provider not in provider_defaults:
            raise ConfigurationError(f"Provider '{provider}' not found in provider defaults")
        
        # Start with provider defaults
        config = self._deep_copy(provider_defaults[provider])
        
        # Apply software-specific overrides if provided
        if software_overrides:
            config = self._deep_merge(config, software_overrides)
        
        # Apply variable substitution
        config = self._substitute_variables(config, software_name)
        
        logger.debug(f"Generated config for provider '{provider}' and software '{software_name}'")
        return config
    
    def should_create_provider_file(
        self, 
        provider: str, 
        software_config: Dict[str, Any], 
        software_name: str
    ) -> bool:
        """
        Determine whether a provider-specific file should be created.
        
        A provider file should only be created if the software-specific configuration
        differs from the provider defaults after variable substitution.
        
        Args:
            provider: Name of the provider.
            software_config: Software-specific configuration for the provider.
            software_name: Name of the software package.
            
        Returns:
            True if a provider file should be created, False otherwise.
        """
        try:
            # Get the default configuration for this provider
            default_config = self.get_provider_config(provider, software_name)
            
            # Compare the software config with the default config
            return not self._configs_equal(software_config, default_config)
            
        except ConfigurationError:
            # If we can't get the default config, create the file to be safe
            logger.warning(f"Could not get default config for provider '{provider}', creating file")
            return True
    
    def get_all_provider_names(self) -> list[str]:
        """
        Get a list of all available provider names.
        
        Returns:
            List of provider names from the provider defaults.
        """
        provider_defaults = self.load_provider_defaults()
        return list(provider_defaults.keys())
    
    def clear_cache(self) -> None:
        """Clear the configuration cache to force reloading from files."""
        self._base_defaults_cache = None
        self._provider_defaults_cache = None
        logger.debug("Configuration cache cleared")
    
    def _deep_copy(self, obj: Any) -> Any:
        """
        Create a deep copy of an object.
        
        Args:
            obj: Object to copy.
            
        Returns:
            Deep copy of the object.
        """
        if isinstance(obj, dict):
            return {key: self._deep_copy(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        else:
            return obj
    
    def _deep_merge(self, base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries.
        
        Args:
            base: Base dictionary.
            overlay: Dictionary to merge into base.
            
        Returns:
            Merged dictionary.
        """
        result = self._deep_copy(base)
        
        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            elif key in result and isinstance(result[key], list) and isinstance(value, list):
                # Merge lists, avoiding duplicates
                merged_list = result[key].copy()
                for item in value:
                    if item not in merged_list:
                        merged_list.append(item)
                result[key] = merged_list
            else:
                result[key] = value
        
        return result
    
    def _substitute_variables(self, obj: Any, software_name: str) -> Any:
        """
        Substitute variables in configuration values.
        
        Replaces {{ software_name }} with the actual software name.
        
        Args:
            obj: Object to process for variable substitution.
            software_name: Name of the software to substitute.
            
        Returns:
            Object with variables substituted.
        """
        if isinstance(obj, str):
            return obj.replace("{{ software_name }}", software_name)
        elif isinstance(obj, dict):
            return {key: self._substitute_variables(value, software_name) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute_variables(item, software_name) for item in obj]
        else:
            return obj
    
    def _configs_equal(self, config1: Dict[str, Any], config2: Dict[str, Any]) -> bool:
        """
        Compare two configurations for equality.
        
        Args:
            config1: First configuration.
            config2: Second configuration.
            
        Returns:
            True if configurations are equal, False otherwise.
        """
        if set(config1.keys()) != set(config2.keys()):
            return False
        
        for key in config1:
            if isinstance(config1[key], dict) and isinstance(config2[key], dict):
                if not self._configs_equal(config1[key], config2[key]):
                    return False
            elif isinstance(config1[key], list) and isinstance(config2[key], list):
                if len(config1[key]) != len(config2[key]):
                    return False
                for item1, item2 in zip(config1[key], config2[key]):
                    if isinstance(item1, dict) and isinstance(item2, dict):
                        if not self._configs_equal(item1, item2):
                            return False
                    elif item1 != item2:
                        return False
            elif config1[key] != config2[key]:
                return False
        
        return True