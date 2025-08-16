"""
Repository URL Manager for saidata-gen.

This module provides centralized management of repository URLs with support for
OS and version-specific overrides, eliminating hardcoded URLs in fetchers.
"""

import logging
import os
import platform
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import yaml

from saidata_gen.core.interfaces import FetcherConfig

logger = logging.getLogger(__name__)


class RepositoryUrlManager:
    """
    Manages repository URLs with OS and version-specific overrides.
    
    This class loads repository URL configurations from YAML files and provides
    methods to resolve the appropriate URLs based on context (OS, version, architecture).
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the repository URL manager.
        
        Args:
            config_path: Optional path to custom repository URLs configuration file.
                        If None, uses the default configuration.
        """
        self.config_path = config_path
        self._url_config: Dict[str, Any] = {}
        self._load_configuration()
    
    def _load_configuration(self):
        """Load repository URL configuration from YAML file."""
        if self.config_path and os.path.exists(self.config_path):
            config_file = self.config_path
        elif self.config_path:
            # Custom config path specified but doesn't exist
            logger.warning(f"Configuration file not found: {self.config_path}")
            self._url_config = {}
            return
        else:
            # Use default configuration file
            config_file = Path(__file__).parent.parent / "templates" / "repository_urls.yaml"
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                self._url_config = yaml.safe_load(f) or {}
            logger.debug(f"Loaded repository URL configuration from {config_file}")
        except Exception as e:
            logger.error(f"Failed to load repository URL configuration: {e}")
            self._url_config = {}
    
    def get_urls(
        self,
        provider: str,
        os_name: Optional[str] = None,
        os_version: Optional[str] = None,
        architecture: Optional[str] = None,
        context: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Get repository URLs for a provider with OS and version-specific overrides.
        
        Args:
            provider: Provider name (e.g., 'apt', 'dnf', 'brew').
            os_name: Operating system name (e.g., 'ubuntu', 'fedora', 'macos').
            os_version: OS version (e.g., 'jammy', '38', '10.15').
            architecture: Architecture (e.g., 'x86_64', 'aarch64').
            context: Additional context variables for URL template substitution.
        
        Returns:
            Dictionary of resolved URLs for the provider.
        """
        if provider not in self._url_config:
            logger.warning(f"No URL configuration found for provider: {provider}")
            return {}
        
        provider_config = self._url_config[provider]
        
        # Start with default configuration
        urls = provider_config.get('default', {}).copy()
        
        # Apply OS-specific overrides
        if os_name and 'os' in provider_config and os_name in provider_config['os']:
            os_config = provider_config['os'][os_name]
            urls.update(os_config)
            
            # Apply version-specific overrides
            if (os_version and 'versions' in os_config and 
                os_version in os_config['versions']):
                version_config = os_config['versions'][os_version]
                urls.update(version_config)
        
        # Apply template variable substitution
        resolved_urls = self._resolve_template_variables(
            urls, provider, os_name, os_version, architecture, context
        )
        
        return resolved_urls
    
    def get_primary_url(
        self,
        provider: str,
        os_name: Optional[str] = None,
        os_version: Optional[str] = None,
        architecture: Optional[str] = None,
        context: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        Get the primary URL for a provider.
        
        Args:
            provider: Provider name.
            os_name: Operating system name.
            os_version: OS version.
            architecture: Architecture.
            context: Additional context variables.
        
        Returns:
            Primary URL string or None if not found.
        """
        urls = self.get_urls(provider, os_name, os_version, architecture, context)
        return urls.get('primary_url') or urls.get('api_url') or urls.get('registry_url')
    
    def get_fallback_urls(
        self,
        provider: str,
        os_name: Optional[str] = None,
        os_version: Optional[str] = None,
        architecture: Optional[str] = None,
        context: Optional[Dict[str, str]] = None
    ) -> List[str]:
        """
        Get fallback URLs for a provider.
        
        Args:
            provider: Provider name.
            os_name: Operating system name.
            os_version: OS version.
            architecture: Architecture.
            context: Additional context variables.
        
        Returns:
            List of fallback URL strings.
        """
        urls = self.get_urls(provider, os_name, os_version, architecture, context)
        fallback_urls = urls.get('fallback_urls', [])
        
        # Ensure fallback_urls is a list
        if isinstance(fallback_urls, str):
            fallback_urls = [fallback_urls]
        
        return fallback_urls
    
    def get_search_url(
        self,
        provider: str,
        software_name: str,
        os_name: Optional[str] = None,
        os_version: Optional[str] = None,
        architecture: Optional[str] = None,
        context: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        Get the search URL for a provider with software name substitution.
        
        Args:
            provider: Provider name.
            software_name: Name of the software to search for.
            os_name: Operating system name.
            os_version: OS version.
            architecture: Architecture.
            context: Additional context variables.
        
        Returns:
            Search URL string or None if not found.
        """
        # Add software_name to context
        search_context = (context or {}).copy()
        search_context['software_name'] = software_name
        
        urls = self.get_urls(provider, os_name, os_version, architecture, search_context)
        return urls.get('search_url')
    
    def get_package_url(
        self,
        provider: str,
        software_name: str,
        os_name: Optional[str] = None,
        os_version: Optional[str] = None,
        architecture: Optional[str] = None,
        context: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        Get the package-specific URL for a provider.
        
        Args:
            provider: Provider name.
            software_name: Name of the software package.
            os_name: Operating system name.
            os_version: OS version.
            architecture: Architecture.
            context: Additional context variables.
        
        Returns:
            Package URL string or None if not found.
        """
        # Add software_name to context
        package_context = (context or {}).copy()
        package_context['software_name'] = software_name
        
        urls = self.get_urls(provider, os_name, os_version, architecture, package_context)
        return urls.get('package_url')
    
    def _resolve_template_variables(
        self,
        urls: Dict[str, Any],
        provider: str,
        os_name: Optional[str],
        os_version: Optional[str],
        architecture: Optional[str],
        context: Optional[Dict[str, str]]
    ) -> Dict[str, str]:
        """
        Resolve template variables in URL strings.
        
        Args:
            urls: Dictionary of URLs with potential template variables.
            provider: Provider name.
            os_name: Operating system name.
            os_version: OS version.
            architecture: Architecture.
            context: Additional context variables.
        
        Returns:
            Dictionary of URLs with resolved template variables.
        """
        # Build template context
        template_context = {
            'provider': provider,
            'os': os_name or self._detect_os(),
            'version': os_version or self._detect_os_version(),
            'arch': architecture or self._detect_architecture(),
        }
        
        # Add custom context variables
        if context:
            template_context.update(context)
        
        resolved_urls = {}
        
        for key, value in urls.items():
            if isinstance(value, str):
                resolved_urls[key] = self._substitute_template_variables(value, template_context)
            elif isinstance(value, list):
                resolved_urls[key] = [
                    self._substitute_template_variables(url, template_context)
                    if isinstance(url, str) else url
                    for url in value
                ]
            else:
                resolved_urls[key] = value
        
        return resolved_urls
    
    def _substitute_template_variables(self, url_template: str, context: Dict[str, str]) -> str:
        """
        Substitute template variables in a URL string.
        
        Args:
            url_template: URL string with template variables.
            context: Context variables for substitution.
        
        Returns:
            URL string with substituted variables.
        """
        try:
            # Handle both {{ variable }} and { variable } formats
            import re
            
            # Replace {{ variable }} format
            def replace_double_braces(match):
                var_name = match.group(1).strip()
                return context.get(var_name, match.group(0))
            
            url = re.sub(r'\{\{\s*([^}]+)\s*\}\}', replace_double_braces, url_template)
            
            # Replace { variable } format (for simple cases)
            def replace_single_braces(match):
                var_name = match.group(1).strip()
                return context.get(var_name, match.group(0))
            
            url = re.sub(r'\{\s*([^}]+)\s*\}', replace_single_braces, url)
            
            return url
            
        except Exception as e:
            logger.warning(f"Failed to substitute template variables in URL: {url_template}, error: {e}")
            return url_template
    
    def _detect_os(self) -> str:
        """
        Detect the current operating system.
        
        Returns:
            Operating system name.
        """
        system = platform.system().lower()
        
        if system == 'linux':
            # Try to detect specific Linux distribution
            try:
                with open('/etc/os-release', 'r') as f:
                    for line in f:
                        if line.startswith('ID='):
                            return line.split('=')[1].strip().strip('"')
            except FileNotFoundError:
                pass
            return 'linux'
        elif system == 'darwin':
            return 'macos'
        elif system == 'windows':
            return 'windows'
        else:
            return system
    
    def _detect_os_version(self) -> str:
        """
        Detect the current operating system version.
        
        Returns:
            Operating system version.
        """
        system = platform.system().lower()
        
        if system == 'linux':
            # Try to detect specific Linux distribution version
            try:
                with open('/etc/os-release', 'r') as f:
                    for line in f:
                        if line.startswith('VERSION_CODENAME='):
                            return line.split('=')[1].strip().strip('"')
                        elif line.startswith('VERSION_ID='):
                            return line.split('=')[1].strip().strip('"')
            except FileNotFoundError:
                pass
        elif system == 'darwin':
            return platform.mac_ver()[0]
        elif system == 'windows':
            return platform.version()
        
        return platform.release()
    
    def _detect_architecture(self) -> str:
        """
        Detect the current system architecture.
        
        Returns:
            System architecture.
        """
        arch = platform.machine().lower()
        
        # Normalize architecture names
        arch_mapping = {
            'x86_64': 'x86_64',
            'amd64': 'x86_64',
            'aarch64': 'aarch64',
            'arm64': 'aarch64',
            'armv7l': 'armv7',
            'i386': 'i386',
            'i686': 'i386',
        }
        
        return arch_mapping.get(arch, arch)
    
    def list_providers(self) -> List[str]:
        """
        Get a list of all configured providers.
        
        Returns:
            List of provider names.
        """
        return list(self._url_config.keys())
    
    def has_provider(self, provider: str) -> bool:
        """
        Check if a provider is configured.
        
        Args:
            provider: Provider name to check.
        
        Returns:
            True if provider is configured, False otherwise.
        """
        return provider in self._url_config
    
    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """
        Get the full configuration for a provider.
        
        Args:
            provider: Provider name.
        
        Returns:
            Provider configuration dictionary.
        """
        return self._url_config.get(provider, {})
    
    def reload_configuration(self):
        """Reload the repository URL configuration from file."""
        self._load_configuration()
        logger.info("Repository URL configuration reloaded")


# Global instance for easy access
_url_manager_instance: Optional[RepositoryUrlManager] = None


def get_repository_url_manager(config_path: Optional[str] = None) -> RepositoryUrlManager:
    """
    Get the global repository URL manager instance.
    
    Args:
        config_path: Optional path to custom configuration file.
    
    Returns:
        RepositoryUrlManager instance.
    """
    global _url_manager_instance
    
    if _url_manager_instance is None or config_path:
        _url_manager_instance = RepositoryUrlManager(config_path)
    
    return _url_manager_instance


def reset_repository_url_manager():
    """Reset the global repository URL manager instance."""
    global _url_manager_instance
    _url_manager_instance = None