"""
Factory for creating repository fetchers.

This module provides a factory for creating repository fetchers for different
package managers.
"""

import logging
from typing import Dict, List, Optional, Type

from saidata_gen.core.interfaces import FetcherConfig
from saidata_gen.fetcher.base import RepositoryFetcher


logger = logging.getLogger(__name__)


class FetcherFactory:
    """
    Factory for creating repository fetchers.
    
    This class provides methods for creating and managing repository fetchers
    for different package managers.
    """
    
    def __init__(self):
        """Initialize the fetcher factory."""
        self._fetcher_classes: Dict[str, Type[RepositoryFetcher]] = {}
    
    def register_fetcher(self, name: str, fetcher_class: Type[RepositoryFetcher]) -> None:
        """
        Register a fetcher class.
        
        Args:
            name: Name of the fetcher.
            fetcher_class: Fetcher class to register.
        """
        self._fetcher_classes[name] = fetcher_class
        logger.debug(f"Registered fetcher: {name}")
    
    def create_fetcher(
        self,
        name: str,
        config: Optional[FetcherConfig] = None,
        **kwargs
    ) -> Optional[RepositoryFetcher]:
        """
        Create a fetcher instance.
        
        Args:
            name: Name of the fetcher to create.
            config: Configuration for the fetcher.
            **kwargs: Additional arguments to pass to the fetcher constructor.
            
        Returns:
            Fetcher instance if the fetcher is registered, None otherwise.
        """
        if name not in self._fetcher_classes:
            logger.warning(f"Fetcher not registered: {name}")
            return None
        
        try:
            fetcher_class = self._fetcher_classes[name]
            return fetcher_class(config=config, **kwargs)
        except Exception as e:
            logger.error(f"Failed to create fetcher {name}: {e}")
            return None
    
    def get_available_fetchers(self) -> List[str]:
        """
        Get a list of available fetcher names.
        
        Returns:
            List of available fetcher names.
        """
        return list(self._fetcher_classes.keys())
    
    def is_fetcher_available(self, name: str) -> bool:
        """
        Check if a fetcher is available.
        
        Args:
            name: Name of the fetcher to check.
            
        Returns:
            True if the fetcher is available, False otherwise.
        """
        return name in self._fetcher_classes
    
    def get_registered_fetchers(self) -> Dict[str, Type[RepositoryFetcher]]:
        """
        Get all registered fetcher classes.
        
        Returns:
            Dictionary mapping fetcher names to their classes.
        """
        return self._fetcher_classes.copy()


# Create a singleton instance
fetcher_factory = FetcherFactory()