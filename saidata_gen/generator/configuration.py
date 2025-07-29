"""
Configuration manager for saidata metadata generation.

This module provides the ConfigurationManager class that handles loading and merging
of base defaults and provider-specific configurations.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml

from saidata_gen.core.interfaces import PackageInfo


logger = logging.getLogger(__name__)


class ConfigurationManager:
    """
    Manages configuration loading and merging for saidata metadata generation.
    
    This class handles:
    - Loading base defaults from defaults.yaml
    - Loading provider defaults from provider_defaults.yaml
    - Merging configurations with software-specific overrides
    - Determining when provider files should be created
    """
    
    def __init__(self, templates_dir: Optional[str] = None):
        """
        Initialize the configuration manager.
        
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
        
        # Validate templates directory path for security
        self.templates_dir = os.path.abspath(self.templates_dir)
        
        # Create the templates directory if it doesn't exist
        os.makedirs(self.templates_dir, exist_ok=True)
        
        # Cache for loaded configurations
        self._base_defaults = None
        self._provider_defaults = None
        self._provider_templates = {}
    
    def load_base_defaults(self) -> Dict[str, Any]:
        """
        Load the base defaults from defaults.yaml.
        
        Returns:
            Dictionary containing the base default configuration.
        """
        if self._base_defaults is not None:
            return self._base_defaults
        
        defaults_path = os.path.join(self.templates_dir, "defaults.yaml")
        
        # If the default template doesn't exist, create it with basic structure
        if not os.path.exists(defaults_path):
            self._create_default_template(defaults_path)
        
        try:
            with open(defaults_path, 'r', encoding='utf-8') as f:
                self._base_defaults = yaml.safe_load(f) or {}
                logger.debug(f"Loaded base defaults from {defaults_path}")
                return self._base_defaults
        except Exception as e:
            logger.error(f"Failed to load base defaults from {defaults_path}: {e}")
            self._base_defaults = {}
            return self._base_defaults
    
    def load_provider_defaults(self) -> Dict[str, Dict[str, Any]]:
        """
        Load provider defaults from provider_defaults.yaml.
        
        Returns:
            Dictionary mapping provider names to their default configurations.
        """
        if self._provider_defaults is not None:
            return self._provider_defaults
        
        provider_defaults_path = os.path.join(self.templates_dir, "provider_defaults.yaml")
        
        if not os.path.exists(provider_defaults_path):
            logger.warning(f"Provider defaults file not found: {provider_defaults_path}")
            self._provider_defaults = {}
            return self._provider_defaults
        
        try:
            with open(provider_defaults_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
                # Extract provider configurations (skip metadata like 'version')
                self._provider_defaults = {
                    key: value for key, value in data.items() 
                    if key not in ['version'] and isinstance(value, dict)
                }
                logger.debug(f"Loaded provider defaults for {len(self._provider_defaults)} providers")
                return self._provider_defaults
        except Exception as e:
            logger.error(f"Failed to load provider defaults from {provider_defaults_path}: {e}")
            self._provider_defaults = {}
            return self._provider_defaults
    
    def get_provider_config(
        self, 
        provider: str, 
        software_name: str,
        repository_data: Optional[PackageInfo] = None
    ) -> Dict[str, Any]:
        """
        Get merged configuration for a specific provider.
        
        This method merges configurations in the following order (later overrides earlier):
        1. Base defaults from defaults.yaml
        2. Provider defaults from provider_defaults.yaml
        3. Software-specific provider overrides (if they exist)
        4. Repository data (if provided)
        
        Args:
            provider: Name of the provider (e.g., 'apt', 'brew')
            software_name: Name of the software package
            repository_data: Optional repository data to merge
            
        Returns:
            Merged configuration dictionary for the provider.
        """
        # Start with base defaults
        config = self.load_base_defaults().copy()
        
        # Apply provider defaults
        provider_defaults = self.load_provider_defaults()
        if provider in provider_defaults:
            config = self._deep_merge(config, provider_defaults[provider])
        
        # Apply software-specific provider overrides
        provider_override = self._load_provider_template(provider, software_name)
        if provider_override:
            config = self._deep_merge(config, provider_override)
        
        # Apply repository data if provided
        if repository_data:
            repo_config = self._convert_repository_data_to_config(repository_data)
            config = self._deep_merge(config, repo_config)
        
        # Apply variable substitution
        config = self._substitute_variables(config, {
            'software_name': software_name,
            'provider': provider
        })
        
        return config
    
    def should_create_provider_file(
        self, 
        provider: str, 
        software_name: str,
        repository_data: Optional[PackageInfo] = None
    ) -> bool:
        """
        Determine whether a provider-specific file should be created.
        
        A provider file should be created if:
        1. There are software-specific overrides that differ from provider defaults
        2. Repository data provides additional configuration
        3. The provider is marked as supported for this software
        
        Args:
            provider: Name of the provider
            software_name: Name of the software package
            repository_data: Optional repository data
            
        Returns:
            True if a provider file should be created, False otherwise.
        """
        # Get provider defaults
        provider_defaults = self.load_provider_defaults()
        if provider not in provider_defaults:
            # If no provider defaults exist, create file if we have any data
            return repository_data is not None
        
        # Check if there are software-specific overrides
        provider_override = self._load_provider_template(provider, software_name)
        if provider_override:
            return True
        
        # Check if repository data provides meaningful configuration
        if repository_data:
            repo_config = self._convert_repository_data_to_config(repository_data)
            # Create file if repository data adds meaningful information
            return bool(repo_config)
        
        # Check if the provider is explicitly supported
        provider_config = self.get_provider_config(provider, software_name, repository_data)
        supported = provider_config.get('supported', True)
        
        # Don't create files for unsupported providers
        return supported is not False
    
    def _load_provider_template(self, provider: str, software_name: str) -> Optional[Dict[str, Any]]:
        """
        Load software-specific provider template if it exists.
        
        Args:
            provider: Name of the provider
            software_name: Name of the software package
            
        Returns:
            Provider template dictionary or None if not found.
        """
        cache_key = f"{software_name}:{provider}"
        if cache_key in self._provider_templates:
            return self._provider_templates[cache_key]
        
        # Try hierarchical structure first (software/providers/provider.yaml)
        hierarchical_path = os.path.join(
            self.templates_dir, "software", software_name, "providers", f"{provider}.yaml"
        )
        
        # Try flat structure (providers/provider/software.yaml)
        flat_path = os.path.join(
            self.templates_dir, "providers", provider, f"{software_name}.yaml"
        )
        
        # Try legacy flat structure (providers/provider.yaml with software-specific sections)
        legacy_path = os.path.join(self.templates_dir, "providers", f"{provider}.yaml")
        
        template = None
        
        # Check hierarchical structure first
        if os.path.exists(hierarchical_path):
            try:
                with open(hierarchical_path, 'r', encoding='utf-8') as f:
                    template = yaml.safe_load(f) or {}
                    logger.debug(f"Loaded hierarchical provider template: {hierarchical_path}")
            except Exception as e:
                logger.error(f"Failed to load hierarchical provider template {hierarchical_path}: {e}")
        
        # Check flat structure
        elif os.path.exists(flat_path):
            try:
                with open(flat_path, 'r', encoding='utf-8') as f:
                    template = yaml.safe_load(f) or {}
                    logger.debug(f"Loaded flat provider template: {flat_path}")
            except Exception as e:
                logger.error(f"Failed to load flat provider template {flat_path}: {e}")
        
        # Check legacy structure
        elif os.path.exists(legacy_path):
            try:
                with open(legacy_path, 'r', encoding='utf-8') as f:
                    legacy_template = yaml.safe_load(f) or {}
                    # Extract software-specific section if it exists
                    if software_name in legacy_template:
                        template = legacy_template[software_name]
                        logger.debug(f"Loaded legacy provider template section: {legacy_path}[{software_name}]")
            except Exception as e:
                logger.error(f"Failed to load legacy provider template {legacy_path}: {e}")
        
        # Cache the result (even if None)
        self._provider_templates[cache_key] = template
        return template
    
    def _convert_repository_data_to_config(self, repository_data: PackageInfo) -> Dict[str, Any]:
        """
        Convert repository data to configuration format.
        
        Args:
            repository_data: Package information from repository
            
        Returns:
            Configuration dictionary extracted from repository data.
        """
        config = {}
        
        # Add package information
        if repository_data.name or repository_data.version:
            config['packages'] = {
                'default': {}
            }
            if repository_data.name:
                config['packages']['default']['name'] = repository_data.name
            if repository_data.version:
                config['packages']['default']['version'] = repository_data.version
        
        # Add description
        if repository_data.description:
            config['description'] = repository_data.description
        
        # Add URLs from details
        if repository_data.details:
            urls = {}
            if 'homepage' in repository_data.details:
                urls['website'] = repository_data.details['homepage']
            if 'source_url' in repository_data.details:
                urls['source'] = repository_data.details['source_url']
            if 'download_url' in repository_data.details:
                urls['download'] = repository_data.details['download_url']
            if 'license_url' in repository_data.details:
                urls['license'] = repository_data.details['license_url']
            
            if urls:
                config['urls'] = urls
            
            # Add license
            if 'license' in repository_data.details:
                config['license'] = repository_data.details['license']
            
            # Add platforms
            if 'platforms' in repository_data.details:
                config['platforms'] = repository_data.details['platforms']
        
        return config
    
    def _deep_merge(self, base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries.
        
        Args:
            base: Base dictionary
            overlay: Dictionary to merge into base
            
        Returns:
            Merged dictionary
        """
        result = base.copy()
        
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
    
    def _substitute_variables(self, data: Any, context: Dict[str, Any]) -> Any:
        """
        Substitute variables in data using simple string replacement.
        
        Args:
            data: Data to substitute variables in
            context: Dictionary with variables for substitution
            
        Returns:
            Data with variables substituted
        """
        if isinstance(data, str):
            result = data
            # Substitute simple variables like $variable_name and {{ variable_name }}
            for var_name, var_value in context.items():
                if isinstance(var_value, (str, int, float, bool)):
                    # Handle $variable_name format
                    var_placeholder = f"${var_name}"
                    if var_placeholder in result:
                        result = result.replace(var_placeholder, str(var_value))
                    
                    # Handle {{ variable_name }} format
                    jinja_placeholder = f"{{{{ {var_name} }}}}"
                    if jinja_placeholder in result:
                        result = result.replace(jinja_placeholder, str(var_value))
            
            return result
        elif isinstance(data, dict):
            return {key: self._substitute_variables(value, context) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._substitute_variables(item, context) for item in data]
        else:
            return data
    
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
        
        logger.info(f"Created default template at {path}")