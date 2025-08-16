"""
Directory structure generator for saidata-gen.

This module provides the DirectoryStructureGenerator class for creating structured
output directories with software-specific defaults.yaml and provider-specific YAML files.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from saidata_gen.core.configuration import ConfigurationManager
from saidata_gen.core.exceptions import ConfigurationError


logger = logging.getLogger(__name__)


class DirectoryStructureGenerator:
    """
    Generates structured directory output for software metadata.
    
    This class creates a directory structure following the pattern:
    $software/
    ├── defaults.yaml              # Software-specific base configuration
    └── providers/                 # Provider-specific overrides (only if different from defaults)
        ├── apt.yaml              # Only created if apt config differs from provider_defaults.yaml
        ├── brew.yaml             # Only created if brew config differs from provider_defaults.yaml
        └── ...
    """
    
    def __init__(self, config_manager: Optional[ConfigurationManager] = None):
        """
        Initialize the directory structure generator.
        
        Args:
            config_manager: Configuration manager to use. If None, creates a new one.
        """
        self.config_manager = config_manager or ConfigurationManager()
        logger.debug("DirectoryStructureGenerator initialized")
    
    def create_software_directory(self, software_name: str, output_path: Union[str, Path]) -> Path:
        """
        Create the software directory structure.
        
        Creates the main software directory and the providers subdirectory.
        
        Args:
            software_name: Name of the software package.
            output_path: Base path where the software directory should be created.
            
        Returns:
            Path to the created software directory.
            
        Raises:
            OSError: If directory creation fails.
        """
        try:
            # Convert to Path object and resolve
            base_path = Path(output_path).expanduser().resolve()
            software_dir = base_path / software_name
            providers_dir = software_dir / "providers"
            
            # Create directories
            software_dir.mkdir(parents=True, exist_ok=True)
            providers_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Created software directory structure at {software_dir}")
            return software_dir
            
        except OSError as e:
            logger.error(f"Failed to create software directory for {software_name}: {e}")
            raise
    
    def write_defaults_file(
        self, 
        software_config: Dict[str, Any], 
        output_path: Path,
        software_name: Optional[str] = None
    ) -> Path:
        """
        Write the software-specific defaults.yaml file.
        
        Args:
            software_config: Complete software configuration dictionary.
            output_path: Path to the software directory.
            software_name: Name of the software (for logging purposes).
            
        Returns:
            Path to the created defaults.yaml file.
            
        Raises:
            IOError: If file writing fails.
            yaml.YAMLError: If YAML serialization fails.
        """
        defaults_path = output_path / "defaults.yaml"
        
        try:
            with open(defaults_path, 'w', encoding='utf-8') as f:
                yaml.dump(
                    software_config, 
                    f, 
                    default_flow_style=False, 
                    sort_keys=False,
                    allow_unicode=True,
                    indent=2
                )
            
            logger.info(f"Created defaults.yaml for {software_name or 'software'} at {defaults_path}")
            return defaults_path
            
        except (IOError, yaml.YAMLError) as e:
            logger.error(f"Failed to write defaults.yaml for {software_name or 'software'}: {e}")
            raise
    
    def write_provider_files(
        self, 
        provider_configs: Dict[str, Dict[str, Any]], 
        output_path: Path,
        software_name: str
    ) -> Dict[str, Path]:
        """
        Write provider-specific YAML files only when they differ from defaults.
        
        This method compares each provider configuration with the provider defaults
        and only creates files for providers that have different configurations.
        
        Args:
            provider_configs: Dictionary mapping provider names to their configurations.
            output_path: Path to the software directory.
            software_name: Name of the software package.
            
        Returns:
            Dictionary mapping provider names to their file paths (only for created files).
            
        Raises:
            IOError: If file writing fails.
            yaml.YAMLError: If YAML serialization fails.
        """
        providers_dir = output_path / "providers"
        created_files = {}
        
        for provider, config in provider_configs.items():
            try:
                # Check if this provider file should be created
                if self.config_manager.should_create_provider_file(provider, config, software_name):
                    provider_path = providers_dir / f"{provider}.yaml"
                    
                    with open(provider_path, 'w', encoding='utf-8') as f:
                        yaml.dump(
                            config, 
                            f, 
                            default_flow_style=False, 
                            sort_keys=False,
                            allow_unicode=True,
                            indent=2
                        )
                    
                    created_files[provider] = provider_path
                    logger.debug(f"Created provider file for {provider} at {provider_path}")
                else:
                    logger.debug(f"Skipped provider file for {provider} (matches defaults)")
                    
            except (IOError, yaml.YAMLError) as e:
                logger.error(f"Failed to write provider file for {provider}: {e}")
                raise
            except ConfigurationError as e:
                logger.warning(f"Configuration error for provider {provider}: {e}")
                # Continue with other providers
                continue
        
        logger.info(f"Created {len(created_files)} provider files for {software_name}")
        return created_files
    
    def cleanup_empty_provider_directory(self, output_path: Path) -> bool:
        """
        Remove the providers directory if it's empty.
        
        This method checks if the providers directory contains any files and removes
        it if it's empty to avoid cluttering the output structure.
        
        Args:
            output_path: Path to the software directory.
            
        Returns:
            True if the directory was removed, False if it wasn't empty or doesn't exist.
        """
        providers_dir = output_path / "providers"
        
        try:
            if not providers_dir.exists():
                logger.debug("Providers directory doesn't exist, nothing to cleanup")
                return False
            
            # Check if directory is empty
            if not any(providers_dir.iterdir()):
                providers_dir.rmdir()
                logger.info(f"Removed empty providers directory at {providers_dir}")
                return True
            else:
                logger.debug(f"Providers directory at {providers_dir} is not empty, keeping it")
                return False
                
        except OSError as e:
            logger.warning(f"Failed to cleanup providers directory at {providers_dir}: {e}")
            return False
    
    def generate_complete_structure(
        self,
        software_name: str,
        software_config: Dict[str, Any],
        provider_configs: Dict[str, Dict[str, Any]],
        output_path: Union[str, Path]
    ) -> Dict[str, Any]:
        """
        Generate the complete directory structure with all files.
        
        This is a convenience method that combines all the individual operations
        to create a complete software directory structure.
        
        Args:
            software_name: Name of the software package.
            software_config: Complete software configuration dictionary.
            provider_configs: Dictionary mapping provider names to their configurations.
            output_path: Base path where the software directory should be created.
            
        Returns:
            Dictionary with information about the generated structure:
            {
                "software_directory": Path,
                "defaults_file": Path,
                "provider_files": Dict[str, Path],
                "providers_directory_removed": bool
            }
        """
        logger.info(f"Generating complete directory structure for {software_name}")
        
        # Create the software directory structure
        software_dir = self.create_software_directory(software_name, output_path)
        
        # Write the defaults file
        defaults_file = self.write_defaults_file(software_config, software_dir, software_name)
        
        # Write provider files (only those that differ from defaults)
        provider_files = self.write_provider_files(provider_configs, software_dir, software_name)
        
        # Cleanup empty providers directory if no provider files were created
        providers_directory_removed = False
        if not provider_files:
            providers_directory_removed = self.cleanup_empty_provider_directory(software_dir)
        
        result = {
            "software_directory": software_dir,
            "defaults_file": defaults_file,
            "provider_files": provider_files,
            "providers_directory_removed": providers_directory_removed
        }
        
        logger.info(
            f"Generated structure for {software_name}: "
            f"defaults file, {len(provider_files)} provider files, "
            f"providers dir removed: {providers_directory_removed}"
        )
        
        return result
    
    def validate_output_path(self, output_path: Union[str, Path]) -> Path:
        """
        Validate and normalize the output path.
        
        Args:
            output_path: Path to validate.
            
        Returns:
            Normalized Path object.
            
        Raises:
            ValueError: If the path is invalid.
            OSError: If the path cannot be created or accessed.
        """
        try:
            path = Path(output_path).expanduser().resolve()
            
            # Create parent directories if they don't exist
            path.mkdir(parents=True, exist_ok=True)
            
            # Check if we can write to the directory
            if not os.access(path, os.W_OK):
                raise OSError(f"No write permission for directory: {path}")
            
            return path
            
        except (ValueError, OSError) as e:
            logger.error(f"Invalid output path {output_path}: {e}")
            raise
    
    def get_structure_info(self, software_dir: Path) -> Dict[str, Any]:
        """
        Get information about an existing software directory structure.
        
        Args:
            software_dir: Path to the software directory.
            
        Returns:
            Dictionary with structure information:
            {
                "exists": bool,
                "has_defaults": bool,
                "has_providers_dir": bool,
                "provider_files": List[str],
                "total_files": int
            }
        """
        info = {
            "exists": software_dir.exists(),
            "has_defaults": False,
            "has_providers_dir": False,
            "provider_files": [],
            "total_files": 0
        }
        
        if not info["exists"]:
            return info
        
        # Check for defaults.yaml
        defaults_path = software_dir / "defaults.yaml"
        info["has_defaults"] = defaults_path.exists()
        if info["has_defaults"]:
            info["total_files"] += 1
        
        # Check for providers directory
        providers_dir = software_dir / "providers"
        info["has_providers_dir"] = providers_dir.exists()
        
        if info["has_providers_dir"]:
            # List provider files
            try:
                for file_path in providers_dir.glob("*.yaml"):
                    provider_name = file_path.stem
                    info["provider_files"].append(provider_name)
                    info["total_files"] += 1
            except OSError as e:
                logger.warning(f"Error reading providers directory {providers_dir}: {e}")
        
        return info