"""
Core engine for saidata-gen.

This module contains the central orchestrator that coordinates all operations
and provides the main API.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from saidata_gen.core.interfaces import (
    BatchOptions,
    BatchResult,
    FetchResult,
    GenerationOptions,
    MetadataResult,
    SoftwareMatch,
    ValidationResult,
    FetcherConfig,
    PackageInfo,
)
from saidata_gen.generator.core import MetadataGenerator
from saidata_gen.search.engine import SoftwareSearchEngine
from saidata_gen.validation.schema import SchemaValidator
from saidata_gen.fetcher.factory import fetcher_factory
from saidata_gen.fetcher.apt import APTFetcher
from saidata_gen.fetcher.brew import BrewFetcher
from saidata_gen.fetcher.dnf import DNFFetcher
from saidata_gen.fetcher.winget import WingetFetcher
from saidata_gen.fetcher.scoop import ScoopFetcher
from saidata_gen.fetcher.npm import NPMFetcher
from saidata_gen.fetcher.pypi import PyPIFetcher
from saidata_gen.fetcher.docker import DockerFetcher


logger = logging.getLogger(__name__)


class SaidataEngine:
    """
    Central orchestrator that coordinates all operations and provides the main API.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the SaidataEngine.

        Args:
            config_path: Path to the configuration file. If None, default configuration is used.
        """
        self.config_path = config_path
        
        # Initialize core components
        self.metadata_generator = MetadataGenerator()
        self.schema_validator = SchemaValidator()
        self.search_engine = SoftwareSearchEngine()
        
        # Register available fetchers
        self._register_fetchers()
        
        # Default fetcher configuration
        self.fetcher_config = FetcherConfig()
    
    def _register_fetchers(self):
        """Register all available fetchers with the factory."""
        fetcher_factory.register_fetcher("apt", APTFetcher)
        fetcher_factory.register_fetcher("brew", BrewFetcher)
        fetcher_factory.register_fetcher("dnf", DNFFetcher)
        fetcher_factory.register_fetcher("winget", WingetFetcher)
        fetcher_factory.register_fetcher("scoop", ScoopFetcher)
        fetcher_factory.register_fetcher("npm", NPMFetcher)
        fetcher_factory.register_fetcher("pypi", PyPIFetcher)
        fetcher_factory.register_fetcher("docker", DockerFetcher)

    def generate_metadata(self, software_name: str, options: GenerationOptions) -> MetadataResult:
        """
        Generate metadata for a software package.

        Args:
            software_name: Name of the software package.
            options: Options for metadata generation.

        Returns:
            MetadataResult: Result of the metadata generation.
        """
        logger.info(f"Generating metadata for {software_name}")
        
        # Determine which providers to use
        providers = options.providers if options.providers else ["apt", "brew", "dnf", "npm", "pypi", "docker"]
        
        # Collect package information from all providers
        package_sources = []
        for provider in providers:
            try:
                fetcher = fetcher_factory.create_fetcher(provider, self.fetcher_config)
                if fetcher:
                    logger.debug(f"Searching for {software_name} in {provider}")
                    packages = fetcher.search_packages(software_name)
                    if packages:
                        # Take the first (best) match
                        package_info = packages[0]
                        package_sources.append(package_info)
                        logger.debug(f"Found {software_name} in {provider}: {package_info.name}")
                    else:
                        logger.debug(f"No packages found for {software_name} in {provider}")
                else:
                    logger.warning(f"Could not create fetcher for provider: {provider}")
            except Exception as e:
                logger.warning(f"Error fetching from {provider}: {e}")
                continue
        
        if not package_sources:
            logger.warning(f"No package information found for {software_name}")
            # Create a minimal package info for template generation
            package_sources = [PackageInfo(
                name=software_name,
                version="latest",
                description=f"Software package: {software_name}",
                provider="default",
                details={}
            )]
        
        # Generate metadata using the metadata generator
        result = self.metadata_generator.generate_from_sources(
            software_name=software_name,
            sources=package_sources,
            providers=providers
        )
        
        logger.info(f"Generated metadata for {software_name} with {len(package_sources)} sources")
        return result

    def validate_metadata(self, file_path: str) -> ValidationResult:
        """
        Validate a metadata file against the schema.

        Args:
            file_path: Path to the metadata file.

        Returns:
            ValidationResult: Result of the validation.
        """
        logger.info(f"Validating metadata file: {file_path}")
        
        try:
            result = self.schema_validator.validate_file(file_path)
            logger.info(f"Validation completed for {file_path}: {'valid' if result.valid else 'invalid'}")
            return result
        except Exception as e:
            logger.error(f"Error validating {file_path}: {e}")
            return ValidationResult(
                valid=False,
                issues=[],
                file_path=file_path
            )

    def batch_process(self, software_list: List[str], options: BatchOptions) -> BatchResult:
        """
        Process multiple software packages in batch.

        Args:
            software_list: List of software package names.
            options: Options for batch processing.

        Returns:
            BatchResult: Result of the batch processing.
        """
        logger.info(f"Starting batch processing for {len(software_list)} packages")
        
        results = {}
        successful = 0
        failed = 0
        
        for software_name in software_list:
            try:
                # Convert BatchOptions to GenerationOptions
                gen_options = GenerationOptions(
                    providers=getattr(options, 'providers', []),
                    use_rag=getattr(options, 'use_rag', False),
                    confidence_threshold=getattr(options, 'confidence_threshold', 0.7)
                )
                
                result = self.generate_metadata(software_name, gen_options)
                results[software_name] = result
                
                if result.validation_result.valid:
                    successful += 1
                    logger.debug(f"Successfully processed {software_name}")
                else:
                    failed += 1
                    logger.warning(f"Generated metadata for {software_name} has validation issues")
                    
            except Exception as e:
                failed += 1
                logger.error(f"Failed to process {software_name}: {e}")
                results[software_name] = None
        
        logger.info(f"Batch processing completed: {successful} successful, {failed} failed")
        
        return BatchResult(
            results=results,
            summary={
                "total": len(software_list),
                "successful": successful,
                "failed": failed
            }
        )

    def search_software(self, query: str) -> List[SoftwareMatch]:
        """
        Search for software packages across multiple repositories.

        Args:
            query: Search query.

        Returns:
            List[SoftwareMatch]: List of matching software packages.
        """
        logger.info(f"Searching for software: {query}")
        
        try:
            results = self.search_engine.search(query)
            logger.info(f"Found {len(results)} matches for '{query}'")
            return results
        except Exception as e:
            logger.error(f"Error searching for {query}: {e}")
            return []

    def fetch_repository_data(self, providers: List[str]) -> FetchResult:
        """
        Fetch data from package repositories.

        Args:
            providers: List of provider names.

        Returns:
            FetchResult: Result of the repository data fetching.
        """
        logger.info(f"Fetching repository data for providers: {providers}")
        
        results = {}
        successful = 0
        failed = 0
        
        for provider in providers:
            try:
                fetcher = fetcher_factory.create_fetcher(provider, self.fetcher_config)
                if fetcher:
                    # Fetch repository data (this would typically cache repository metadata)
                    repository_data = fetcher.fetch_repository_data()
                    results[provider] = repository_data
                    successful += 1
                    logger.debug(f"Successfully fetched data from {provider}")
                else:
                    failed += 1
                    logger.warning(f"Could not create fetcher for provider: {provider}")
                    results[provider] = None
            except Exception as e:
                failed += 1
                logger.error(f"Failed to fetch data from {provider}: {e}")
                results[provider] = None
        
        logger.info(f"Repository data fetching completed: {successful} successful, {failed} failed")
        
        return FetchResult(
            results=results,
            summary={
                "total": len(providers),
                "successful": successful,
                "failed": failed
            }
        )