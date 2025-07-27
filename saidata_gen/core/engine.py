"""
Core engine for saidata-gen.

This module contains the central orchestrator that coordinates all operations
and provides the main API.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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
        providers = options.providers if options.providers else self.get_default_providers()
        
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
    
    def generate_metadata_with_directory_structure(
        self, 
        software_name: str, 
        output_dir: str,
        options: GenerationOptions
    ) -> Dict[str, Any]:
        """
        Generate metadata with software-specific directory structure.
        
        This method creates a directory structure following the pattern:
        <software_name>/
        ├── defaults.yaml (merged defaults + provider data + AI enhancements)
        └── providers/
            ├── apt.yaml (provider-specific overrides only)
            ├── brew.yaml (provider-specific overrides only)
            └── ... (other providers)
        
        Args:
            software_name: Name of the software package
            output_dir: Directory where to create the software directory
            options: Options for metadata generation
            
        Returns:
            Dictionary with information about generated files and validation results
        """
        logger.info(f"Generating directory structure for {software_name}")
        
        # Determine which providers to use
        providers = options.providers if options.providers else self.get_default_providers()
        
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
        
        # Generate directory structure using the metadata generator
        ai_provider = getattr(options, 'rag_provider', None) if getattr(options, 'use_rag', False) else None
        
        result = self.metadata_generator.generate_software_directory_structure(
            software_name=software_name,
            sources=package_sources,
            output_dir=output_dir,
            providers=providers,
            ai_provider=ai_provider
        )
        
        logger.info(f"Generated directory structure for {software_name} with {len(result['provider_files'])} provider files")
        return result
    
    def generate_comprehensive_metadata_file(
        self,
        software_name: str,
        output_path: str,
        options: GenerationOptions
    ) -> Dict[str, Any]:
        """
        Generate comprehensive metadata file with all provider information merged.
        
        Args:
            software_name: Name of the software package
            output_path: Path where to create the comprehensive metadata file
            options: Options for metadata generation
            
        Returns:
            Dictionary with information about the generated file
        """
        logger.info(f"Generating comprehensive metadata file for {software_name}")
        
        # Determine which providers to use
        providers = options.providers if options.providers else self.get_default_providers()
        
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
        
        # Generate comprehensive metadata file using the metadata generator
        ai_provider = getattr(options, 'rag_provider', None) if getattr(options, 'use_rag', False) else None
        
        result = self.metadata_generator.create_comprehensive_metadata_file(
            software_name=software_name,
            sources=package_sources,
            output_path=output_path,
            providers=providers,
            ai_provider=ai_provider
        )
        
        logger.info(f"Generated comprehensive metadata file for {software_name}")
        return result
    
    def validate_and_cleanup_directory_structure(
        self,
        software_dir: str,
        cleanup: bool = True,
        format_files: bool = True
    ) -> Dict[str, Any]:
        """
        Validate and optionally cleanup/format a generated directory structure.
        
        Args:
            software_dir: Path to the software directory to validate
            cleanup: Whether to perform cleanup of empty/redundant files
            format_files: Whether to ensure formatting consistency
            
        Returns:
            Dictionary with validation, cleanup, and formatting results
        """
        logger.info(f"Validating and cleaning up directory structure: {software_dir}")
        
        result = {
            "validation": {},
            "cleanup": {},
            "formatting": {}
        }
        
        # Validate directory structure
        result["validation"] = self.metadata_generator.validate_generated_directory_structure(software_dir)
        
        # Cleanup if requested and validation passed
        if cleanup and result["validation"]["valid"]:
            result["cleanup"] = self.metadata_generator.cleanup_generated_files(software_dir)
        
        # Format files if requested
        if format_files:
            result["formatting"] = self.metadata_generator.ensure_formatting_consistency(software_dir)
        
        logger.info(f"Directory structure processing completed for {software_dir}")
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
        errors = []
        
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
                    error_msg = f"Generated metadata for {software_name} has validation issues"
                    logger.warning(error_msg)
                    if result.error_message:
                        errors.append(f"{software_name}: {result.error_message}")
                    else:
                        errors.append(f"{software_name}: validation failed")
                    
            except Exception as e:
                failed += 1
                error_msg = f"Failed to process {software_name}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                results[software_name] = None
        
        logger.info(f"Batch processing completed: {successful} successful, {failed} failed")
        
        return BatchResult(
            results=results,
            summary={
                "total": len(software_list),
                "successful": successful,
                "failed": failed
            },
            total_processed=len(software_list),
            successful=successful,
            failed=failed,
            errors=errors
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

    def get_available_providers(self) -> Dict[str, Dict[str, any]]:
        """
        Get information about all available providers.

        Returns:
            Dict[str, Dict[str, any]]: Dictionary mapping provider names to their information.
        """
        logger.debug("Getting available providers information")
        
        # Get registered fetchers from factory
        registered_fetchers = fetcher_factory.get_registered_fetchers()
        
        # Check for available templates
        from pathlib import Path
        templates_dir = Path(__file__).parent.parent / "templates" / "providers"
        available_templates = set()
        
        if templates_dir.exists():
            for template_file in templates_dir.glob("*.yaml"):
                available_templates.add(template_file.stem)
            
            # Also check for hierarchical templates (directories)
            for template_dir in templates_dir.iterdir():
                if template_dir.is_dir():
                    available_templates.add(template_dir.name)
        
        # Provider type mapping
        provider_types = {
            'apt': 'Linux Package Manager',
            'brew': 'macOS/Linux Package Manager', 
            'dnf': 'Linux Package Manager (RPM)',
            'yum': 'Linux Package Manager (RPM)',
            'zypper': 'Linux Package Manager (RPM)',
            'pacman': 'Linux Package Manager (Arch)',
            'apk': 'Linux Package Manager (Alpine)',
            'snap': 'Universal Package Manager',
            'flatpak': 'Universal Package Manager',
            'winget': 'Windows Package Manager',
            'choco': 'Windows Package Manager',
            'scoop': 'Windows Package Manager',
            'npm': 'JavaScript Package Manager',
            'pypi': 'Python Package Manager',
            'cargo': 'Rust Package Manager',
            'gem': 'Ruby Package Manager',
            'composer': 'PHP Package Manager',
            'nuget': '.NET Package Manager',
            'maven': 'Java Package Manager',
            'gradle': 'Java Build Tool',
            'go': 'Go Module Manager',
            'docker': 'Container Registry',
            'helm': 'Kubernetes Package Manager',
            'nix': 'Nix Package Manager',
            'nixpkgs': 'Nix Package Collection',
            'guix': 'GNU Guix Package Manager',
            'spack': 'HPC Package Manager',
            'portage': 'Gentoo Package Manager',
            'emerge': 'Gentoo Package Manager',
            'xbps': 'Void Linux Package Manager',
            'slackpkg': 'Slackware Package Manager',
            'opkg': 'Embedded Linux Package Manager',
            'pkg': 'FreeBSD Package Manager'
        }
        
        # Provider descriptions
        provider_descriptions = {
            'apt': 'Debian/Ubuntu APT package manager',
            'brew': 'Homebrew package manager for macOS and Linux',
            'dnf': 'DNF package manager for Fedora/RHEL 8+',
            'yum': 'YUM package manager for RHEL/CentOS 7 and earlier',
            'zypper': 'Zypper package manager for openSUSE/SLES',
            'pacman': 'Pacman package manager for Arch Linux',
            'apk': 'APK package manager for Alpine Linux',
            'snap': 'Snap universal package manager',
            'flatpak': 'Flatpak universal application distribution',
            'winget': 'Windows Package Manager',
            'choco': 'Chocolatey package manager for Windows',
            'scoop': 'Scoop command-line installer for Windows',
            'npm': 'Node.js package manager',
            'pypi': 'Python Package Index',
            'cargo': 'Rust package manager and build system',
            'gem': 'Ruby package manager',
            'composer': 'PHP dependency manager',
            'nuget': '.NET package manager',
            'maven': 'Apache Maven build automation tool',
            'gradle': 'Gradle build automation tool',
            'go': 'Go module system',
            'docker': 'Docker container registry',
            'helm': 'Kubernetes package manager',
            'nix': 'Nix package manager',
            'nixpkgs': 'Nix package collection',
            'guix': 'GNU Guix functional package manager',
            'spack': 'Package manager for supercomputers',
            'portage': 'Gentoo Portage package manager',
            'emerge': 'Gentoo emerge package management tool',
            'xbps': 'X Binary Package System for Void Linux',
            'slackpkg': 'Slackware package management tool',
            'opkg': 'Lightweight package manager for embedded systems',
            'pkg': 'FreeBSD package manager'
        }
        
        # Combine all known providers
        all_providers = set(registered_fetchers.keys()) | available_templates
        
        provider_info = {}
        for provider in sorted(all_providers):
            provider_info[provider] = {
                'type': provider_types.get(provider, 'Unknown'),
                'description': provider_descriptions.get(provider, 'No description available'),
                'has_fetcher': provider in registered_fetchers,
                'has_template': provider in available_templates
            }
        
        logger.debug(f"Found {len(provider_info)} available providers")
        return provider_info

    def get_default_providers(self) -> List[str]:
        """
        Get list of default providers that should be used when none are specified.
        
        Returns:
            List[str]: List of default provider names.
        """
        available_providers = self.get_available_providers()
        
        # Filter to providers that have both fetchers and templates
        default_providers = []
        for provider, info in available_providers.items():
            if info.get('has_fetcher', False) and info.get('has_template', False):
                default_providers.append(provider)
        
        # If no providers have both, fall back to providers with templates only
        if not default_providers:
            for provider, info in available_providers.items():
                if info.get('has_template', False):
                    default_providers.append(provider)
        
        logger.debug(f"Default providers: {default_providers}")
        return sorted(default_providers)