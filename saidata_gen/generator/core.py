"""
Core metadata generator for saidata.

This module provides the core functionality for generating saidata metadata
from multiple sources.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import yaml

from saidata_gen.ai.enhancer import AIMetadataEnhancer, AIEnhancementResult
from saidata_gen.core.aggregation import DataAggregator
from saidata_gen.core.interfaces import (
    GeneratorConfig, MetadataResult, PackageInfo, SaidataMetadata, ValidationResult
)
from saidata_gen.core.models import EnhancedSaidataMetadata
from saidata_gen.generator.templates import TemplateEngine


logger = logging.getLogger(__name__)


class MetadataGenerator:
    """
    Core metadata generator for saidata.
    
    This class provides methods for generating saidata metadata from multiple sources,
    applying templates, and merging data.
    """
    
    def __init__(
        self,
        config: Optional[GeneratorConfig] = None,
        template_engine: Optional[TemplateEngine] = None,
        schema_validator: Optional[Any] = None,
        schema_path: Optional[str] = None,
        data_aggregator: Optional[DataAggregator] = None,
        ai_enhancer: Optional[AIMetadataEnhancer] = None
    ):
        """
        Initialize the metadata generator.
        
        Args:
            config: Generator configuration (for backward compatibility)
            template_engine: Template engine to use. If None, creates a new one.
            schema_validator: Schema validator (for backward compatibility)
            schema_path: Path to the saidata schema. If None, uses the default schema.
            data_aggregator: Data aggregator to use. If None, creates a new one.
            ai_enhancer: AI metadata enhancer to use. If None, creates a new one when needed.
        """
        self.config = config or GeneratorConfig()
        self.template_engine = template_engine or TemplateEngine()
        self.schema_validator = schema_validator  # For backward compatibility
        self.data_aggregator = data_aggregator or DataAggregator()
        self.ai_enhancer = ai_enhancer
        
        if schema_path is None:
            # Use the default schema path
            package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.schema_path = os.path.join(package_dir, "schemas", "saidata-0.1.schema.json")
        else:
            self.schema_path = os.path.expanduser(schema_path)
    
    def generate_from_sources(
        self,
        software_name: str,
        sources: List[PackageInfo],
        providers: Optional[List[str]] = None
    ) -> MetadataResult:
        """
        Generate metadata from multiple sources.
        
        Args:
            software_name: Name of the software.
            sources: List of package information from different sources.
            providers: List of providers to include in the metadata. If None, includes all providers.
            
        Returns:
            MetadataResult with the generated metadata and validation result.
        """
        # Start with an empty metadata object
        metadata = {}
        
        # Apply templates
        metadata = self.template_engine.apply_template(software_name, metadata, providers)
        
        # Use the new aggregation system to merge data from sources
        aggregated_data, confidence_scores = self.data_aggregator.aggregate_package_data(
            software_name, sources
        )
        
        # Merge the aggregated data with the template data
        metadata = self._deep_merge(metadata, aggregated_data)
        
        # Create the enhanced metadata object
        enhanced_metadata = EnhancedSaidataMetadata.from_dict(metadata)
        
        # Validate the metadata
        validation_result = enhanced_metadata.validate()
        
        return MetadataResult(
            metadata=enhanced_metadata,
            validation_result=validation_result,
            confidence_scores=confidence_scores
        )
    
    def generate_with_ai_enhancement(
        self,
        software_name: str,
        sources: List[PackageInfo],
        providers: Optional[List[str]] = None,
        ai_provider: str = "openai",
        enhancement_types: Optional[List[str]] = None
    ) -> MetadataResult:
        """
        Generate metadata with AI enhancement for missing fields.
        
        Args:
            software_name: Name of the software
            sources: List of package information from repositories
            providers: List of providers to include
            ai_provider: AI provider to use (openai, anthropic, local)
            enhancement_types: Types of AI enhancement to apply
            
        Returns:
            MetadataResult with AI-enhanced metadata
        """
        logger.info(f"Generating AI-enhanced metadata for {software_name} using {ai_provider}")
        
        # First generate base metadata from repository sources
        base_result = self.generate_from_sources(software_name, sources, providers)
        base_metadata = base_result.metadata.to_dict()
        
        # Initialize AI enhancer if not provided
        if self.ai_enhancer is None or self.ai_enhancer.provider != ai_provider:
            self.ai_enhancer = AIMetadataEnhancer(provider=ai_provider)
        
        # Check if AI enhancement is available
        if not self.ai_enhancer.is_available():
            logger.warning(f"AI provider {ai_provider} is not available, returning base metadata")
            return base_result
        
        try:
            # Perform AI enhancement
            ai_result = self.ai_enhancer.enhance_metadata(
                software_name=software_name,
                base_metadata=base_metadata,
                enhancement_types=enhancement_types
            )
            
            if ai_result.success:
                # Merge AI-enhanced data with repository data (repository takes precedence)
                merged_metadata = self.merge_ai_with_repository_data(
                    repository_data=base_metadata,
                    ai_data=ai_result.enhanced_metadata
                )
                
                # Create enhanced metadata object
                enhanced_metadata = EnhancedSaidataMetadata.from_dict(merged_metadata)
                
                # Validate the enhanced metadata
                validation_result = enhanced_metadata.validate()
                
                # Merge confidence scores (repository data gets higher confidence)
                merged_confidence_scores = self._merge_confidence_scores(
                    base_result.confidence_scores,
                    ai_result.confidence_scores
                )
                
                logger.info(
                    f"Successfully enhanced metadata for {software_name} "
                    f"(processing time: {ai_result.processing_time:.2f}s)"
                )
                
                return MetadataResult(
                    metadata=enhanced_metadata,
                    validation_result=validation_result,
                    confidence_scores=merged_confidence_scores
                )
            else:
                logger.warning(f"AI enhancement failed: {ai_result.error_message}")
                return base_result
                
        except Exception as e:
            logger.error(f"Error during AI enhancement for {software_name}: {e}")
            return base_result
    
    def merge_ai_with_repository_data(
        self,
        repository_data: Dict[str, Any],
        ai_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge AI-generated data with repository data, prioritizing repository data.
        
        Args:
            repository_data: Data from package repositories (authoritative)
            ai_data: Data from AI/LLM (supplementary)
            
        Returns:
            Merged data with repository data taking precedence
        """
        # Start with AI data as base
        merged = ai_data.copy()
        
        # Override with repository data (repository data takes precedence)
        merged = self._deep_merge_with_precedence(merged, repository_data, repository_precedence=True)
        
        logger.debug(f"Merged AI and repository data, repository data took precedence")
        return merged
    
    def _deep_merge_with_precedence(
        self, 
        base: Dict[str, Any], 
        overlay: Dict[str, Any], 
        repository_precedence: bool = True
    ) -> Dict[str, Any]:
        """
        Deep merge two dictionaries with precedence rules.
        
        Args:
            base: Base dictionary
            overlay: Dictionary to merge into base
            repository_precedence: If True, overlay (repository) data takes precedence
            
        Returns:
            Merged dictionary
        """
        result = base.copy()
        
        for key, value in overlay.items():
            if key in result:
                if isinstance(result[key], dict) and isinstance(value, dict):
                    # Recursively merge nested dictionaries
                    result[key] = self._deep_merge_with_precedence(
                        result[key], value, repository_precedence
                    )
                elif isinstance(result[key], list) and isinstance(value, list):
                    # Merge lists, avoiding duplicates
                    if repository_precedence:
                        # Repository data first, then AI data
                        merged_list = value.copy()
                        for item in result[key]:
                            if item not in merged_list:
                                merged_list.append(item)
                    else:
                        # AI data first, then repository data
                        merged_list = result[key].copy()
                        for item in value:
                            if item not in merged_list:
                                merged_list.append(item)
                    result[key] = merged_list
                else:
                    # For primitive values, repository data takes precedence if available
                    if repository_precedence and value is not None and value != "":
                        result[key] = value
                    elif not repository_precedence and result[key] is None or result[key] == "":
                        result[key] = value
            else:
                # Key doesn't exist in result, add it
                result[key] = value
        
        return result
    
    def _merge_confidence_scores(
        self,
        repository_scores: Dict[str, float],
        ai_scores: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Merge confidence scores from repository and AI sources.
        
        Args:
            repository_scores: Confidence scores from repository data
            ai_scores: Confidence scores from AI enhancement
            
        Returns:
            Merged confidence scores
        """
        merged_scores = {}
        
        # Repository scores get higher base confidence
        for field, score in repository_scores.items():
            merged_scores[field] = min(1.0, score * 1.2)  # Boost repository confidence
        
        # AI scores for fields not in repository data
        for field, score in ai_scores.items():
            if field not in merged_scores:
                merged_scores[field] = score * 0.8  # Reduce AI-only confidence
        
        # Calculate overall confidence
        if merged_scores:
            merged_scores["overall"] = sum(merged_scores.values()) / len(merged_scores)
        
        return merged_scores
    
    def _merge_sources(self, base: Dict[str, Any], sources: List[PackageInfo]) -> Dict[str, Any]:
        """
        Merge data from multiple sources into the base metadata.
        
        Args:
            base: Base metadata to merge into.
            sources: List of package information from different sources.
            
        Returns:
            Merged metadata.
        """
        result = base.copy()
        
        # Group sources by provider
        provider_sources: Dict[str, List[PackageInfo]] = {}
        for source in sources:
            if source.provider not in provider_sources:
                provider_sources[source.provider] = []
            provider_sources[source.provider].append(source)
        
        # Process each provider
        for provider, provider_sources_list in provider_sources.items():
            # Merge package information
            if "packages" not in result:
                result["packages"] = {}
            
            # Add provider-specific package configuration
            for source in provider_sources_list:
                package_config = {
                    "name": source.name,
                    "version": source.version or "latest"
                }
                
                # Add provider-specific package configuration
                result["packages"][provider] = package_config
            
            # Merge description if available
            for source in provider_sources_list:
                if source.description and (not result.get("description") or len(source.description) > len(result.get("description", ""))):
                    result["description"] = source.description
            
            # Merge URLs if available
            if "urls" not in result:
                result["urls"] = {}
            
            # Use the first source for URLs to ensure consistency in tests
            source = provider_sources_list[0]
            if "homepage" in source.details and source.details["homepage"]:
                result["urls"]["website"] = source.details["homepage"]
            
            if "source_url" in source.details and source.details["source_url"]:
                result["urls"]["source"] = source.details["source_url"]
            
            if "download_url" in source.details and source.details["download_url"]:
                result["urls"]["download"] = source.details["download_url"]
            
            if "license_url" in source.details and source.details["license_url"]:
                result["urls"]["license"] = source.details["license_url"]
            
            # Merge license if available
            for source in provider_sources_list:
                if "license" in source.details and source.details["license"]:
                    result["license"] = source.details["license"]
            
            # Merge platforms if available
            if "platforms" not in result:
                result["platforms"] = []
            
            for source in provider_sources_list:
                if "platforms" in source.details and source.details["platforms"]:
                    for platform in source.details["platforms"]:
                        if platform not in result["platforms"]:
                            result["platforms"].append(platform)
        
        return result
    
    def _deep_merge(self, base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries.
        
        Args:
            base: Base dictionary.
            overlay: Dictionary to merge into base.
            
        Returns:
            Merged dictionary.
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
    
    def get_conflict_report(
        self,
        software_name: str,
        sources: List[PackageInfo]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate a conflict report showing disagreements between sources.
        
        Args:
            software_name: Name of the software package.
            sources: List of package information from different sources.
            
        Returns:
            Dictionary mapping field paths to lists of conflicting values.
        """
        return self.data_aggregator.get_conflict_report(software_name, sources)
    
    def _calculate_confidence_scores(
        self,
        metadata: EnhancedSaidataMetadata,
        sources: List[PackageInfo]
    ) -> Dict[str, float]:
        """
        Calculate confidence scores for metadata fields.
        
        Args:
            metadata: Generated metadata.
            sources: List of package information from different sources.
            
        Returns:
            Dictionary mapping field paths to confidence scores.
        """
        confidence_scores = {}
        
        # Calculate confidence for description
        if metadata.description:
            # Count sources with matching descriptions
            matching_sources = sum(1 for source in sources if source.description == metadata.description)
            confidence_scores["description"] = matching_sources / len(sources) if sources else 0.5
        
        # Calculate confidence for license
        if metadata.license:
            # Count sources with matching licenses
            matching_sources = sum(1 for source in sources if source.details.get("license") == metadata.license)
            confidence_scores["license"] = matching_sources / len(sources) if sources else 0.5
        
        # Calculate confidence for URLs
        if metadata.urls:
            for url_type, url in metadata.urls.__dict__.items():
                if url:
                    # Count sources with matching URLs
                    matching_sources = 0
                    for source in sources:
                        if url_type == "website" and source.details.get("homepage") == url:
                            matching_sources += 1
                        elif url_type == "source" and source.details.get("source_url") == url:
                            matching_sources += 1
                        elif url_type == "download" and source.details.get("download_url") == url:
                            matching_sources += 1
                        elif url_type == "license" and source.details.get("license_url") == url:
                            matching_sources += 1
                    
                    confidence_scores[f"urls.{url_type}"] = matching_sources / len(sources) if sources else 0.5
        
        # Calculate confidence for platforms
        if metadata.platforms:
            for platform in metadata.platforms:
                # Count sources with matching platforms
                matching_sources = sum(1 for source in sources if "platforms" in source.details and platform in source.details["platforms"])
                confidence_scores[f"platforms.{platform}"] = matching_sources / len(sources) if sources else 0.5
        
        # Calculate overall confidence
        if confidence_scores:
            confidence_scores["overall"] = sum(confidence_scores.values()) / len(confidence_scores)
        else:
            confidence_scores["overall"] = 0.5
        
        return confidence_scores
    
    def apply_defaults(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply default values to metadata.
        
        Args:
            metadata: Metadata to apply defaults to.
            
        Returns:
            Metadata with defaults applied.
        """
        # Extract the software name from the metadata
        software_name = None
        if "packages" in metadata and "default" in metadata["packages"]:
            software_name = metadata["packages"]["default"].get("name")
        
        if not software_name:
            # Try to find a software name from any package
            for provider, package in metadata.get("packages", {}).items():
                if "name" in package:
                    software_name = package["name"]
                    break
        
        if not software_name:
            logger.warning("Could not determine software name from metadata")
            return metadata
        
        # Apply templates with the software name
        return self.template_engine.apply_template(software_name, metadata)
    
    def merge_provider_data(
        self,
        base: Dict[str, Any],
        provider_data: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Merge provider-specific data into the base metadata.
        
        Args:
            base: Base metadata to merge into.
            provider_data: Dictionary mapping provider names to their data.
            
        Returns:
            Merged metadata.
        """
        result = base.copy()
        
        # Ensure packages exist
        if "packages" not in result:
            result["packages"] = {}
        
        # Merge provider-specific package data
        for provider, data in provider_data.items():
            # Add provider-specific package configuration
            if "package" in data:
                result["packages"][provider] = data["package"]
            
            # Merge description if available
            if "description" in data and (not result.get("description") or len(data["description"]) > len(result.get("description", ""))):
                result["description"] = data["description"]
            
            # Merge URLs if available
            if "urls" in data:
                if "urls" not in result:
                    result["urls"] = {}
                
                for url_type, url in data["urls"].items():
                    if url and (url_type not in result["urls"] or not result["urls"][url_type]):
                        result["urls"][url_type] = url
            
            # Merge license if available
            if "license" in data and not result.get("license"):
                result["license"] = data["license"]
            
            # Merge platforms if available
            if "platforms" in data:
                if "platforms" not in result:
                    result["platforms"] = []
                
                for platform in data["platforms"]:
                    if platform not in result["platforms"]:
                        result["platforms"].append(platform)
            
            # Merge services if available
            if "services" in data:
                if "services" not in result:
                    result["services"] = {}
                
                for service_name, service_config in data["services"].items():
                    if service_name not in result["services"]:
                        result["services"][service_name] = service_config
            
            # Merge directories if available
            if "directories" in data:
                if "directories" not in result:
                    result["directories"] = {}
                
                for dir_name, dir_config in data["directories"].items():
                    if dir_name not in result["directories"]:
                        result["directories"][dir_name] = dir_config
            
            # Merge processes if available
            if "processes" in data:
                if "processes" not in result:
                    result["processes"] = {}
                
                for process_name, process_config in data["processes"].items():
                    if process_name not in result["processes"]:
                        result["processes"][process_name] = process_config
            
            # Merge ports if available
            if "ports" in data:
                if "ports" not in result:
                    result["ports"] = {}
                
                for port_name, port_config in data["ports"].items():
                    if port_name not in result["ports"]:
                        result["ports"][port_name] = port_config
            
            # Merge containers if available
            if "containers" in data:
                if "containers" not in result:
                    result["containers"] = {}
                
                for container_name, container_config in data["containers"].items():
                    if container_name not in result["containers"]:
                        result["containers"][container_name] = container_config
        
        return result
    
    def enhance_with_rag(
        self,
        metadata: Dict[str, Any],
        rag_engine: Any
    ) -> Dict[str, Any]:
        """
        Enhance metadata using RAG.
        
        Args:
            metadata: Metadata to enhance.
            rag_engine: RAG engine to use for enhancement.
            
        Returns:
            Enhanced metadata.
        """
        logger.warning("enhance_with_rag is deprecated, use generate_with_ai_enhancement instead")
        return metadata
    
    def get_ai_enhancement_statistics(
        self,
        results: List[AIEnhancementResult]
    ) -> Dict[str, Any]:
        """
        Generate statistics from AI enhancement results.
        
        Args:
            results: List of AI enhancement results
            
        Returns:
            Dictionary with enhancement statistics
        """
        if self.ai_enhancer is None:
            return {}
        
        return self.ai_enhancer.get_enhancement_statistics(results)
    
    def validate_ai_configuration(self, ai_provider: str) -> Tuple[bool, Optional[str]]:
        """
        Validate AI provider configuration.
        
        Args:
            ai_provider: AI provider to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Create temporary enhancer to validate configuration
            temp_enhancer = AIMetadataEnhancer(provider=ai_provider)
            return temp_enhancer.validate_configuration()
        except Exception as e:
            return False, str(e)
    
    def generate_software_directory_structure(
        self,
        software_name: str,
        sources: List[PackageInfo],
        output_dir: Union[str, Path],
        providers: Optional[List[str]] = None,
        ai_provider: Optional[str] = None,
        enhancement_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate software-specific directory structure with defaults.yaml and provider overrides.
        
        This method creates a directory structure following the pattern:
        <software_name>/
        ├── defaults.yaml (merged defaults + provider data + AI enhancements)
        └── providers/
            ├── apt.yaml (provider-specific overrides only)
            ├── brew.yaml (provider-specific overrides only)
            ├── winget.yaml (provider-specific overrides only)
            └── ... (other providers)
        
        Args:
            software_name: Name of the software
            sources: List of package information from repositories
            output_dir: Directory where to create the software directory
            providers: List of providers to include
            ai_provider: AI provider to use for enhancement
            enhancement_types: Types of AI enhancement to apply
            
        Returns:
            Dictionary with information about generated files
        """
        logger.info(f"Generating directory structure for {software_name}")
        
        # Create output directory path
        output_path = Path(output_dir)
        software_dir = output_path / software_name
        providers_dir = software_dir / "providers"
        
        # Create directories
        software_dir.mkdir(parents=True, exist_ok=True)
        providers_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate base metadata (with or without AI enhancement)
        if ai_provider:
            base_result = self.generate_with_ai_enhancement(
                software_name=software_name,
                sources=sources,
                providers=providers,
                ai_provider=ai_provider,
                enhancement_types=enhancement_types
            )
        else:
            base_result = self.generate_from_sources(
                software_name=software_name,
                sources=sources,
                providers=providers
            )
        
        # Get the merged metadata for defaults.yaml
        merged_metadata = base_result.metadata.to_dict()
        
        # Create defaults.yaml with merged configuration
        defaults_path = software_dir / "defaults.yaml"
        with open(defaults_path, 'w', encoding='utf-8') as f:
            yaml.dump(merged_metadata, f, default_flow_style=False, sort_keys=False)
        
        # Generate provider override files
        generated_files = {
            "defaults": str(defaults_path),
            "providers": {},
            "skipped_providers": {}
        }
        
        # Determine which providers to generate files for
        all_providers = providers or self._get_all_available_providers()
        
        for provider in all_providers:
            try:
                # Generate provider-specific overrides
                provider_overrides = self.template_engine.apply_provider_overrides_only(
                    software_name=software_name,
                    provider=provider,
                    repository_data=self._get_repository_data_for_provider(sources, provider)
                )
                
                # Skip generating provider files when supported: false
                if provider_overrides.get("supported") is False:
                    generated_files["skipped_providers"][provider] = "unsupported"
                    logger.debug(f"Skipped provider {provider} - marked as unsupported")
                    continue
                
                # Only create provider file if it contains meaningful overrides
                if self._has_meaningful_overrides(provider_overrides):
                    # Use proper file naming convention: provider.yaml
                    provider_filename = self._get_provider_filename(provider)
                    provider_path = providers_dir / provider_filename
                    
                    # Write provider override file with proper formatting
                    self._write_provider_file(provider_path, provider_overrides)
                    
                    generated_files["providers"][provider] = str(provider_path)
                    logger.debug(f"Generated provider override file: {provider_path}")
                else:
                    generated_files["skipped_providers"][provider] = "no_overrides"
                    logger.debug(f"Skipped provider {provider} - no meaningful overrides")
                    
            except Exception as e:
                logger.warning(f"Error generating provider override for {provider}: {e}")
                generated_files["skipped_providers"][provider] = f"error: {str(e)}"
                continue
        
        logger.info(f"Generated directory structure for {software_name} with {len(generated_files['providers'])} provider files")
        
        return {
            "software_name": software_name,
            "software_dir": str(software_dir),
            "defaults_file": generated_files["defaults"],
            "provider_files": generated_files["providers"],
            "skipped_providers": generated_files["skipped_providers"],
            "validation_result": base_result.validation_result,
            "confidence_scores": base_result.confidence_scores
        }
    
    def _get_all_available_providers(self) -> List[str]:
        """
        Get list of all available providers from template engine.
        
        Returns:
            List of available provider names
        """
        return list(self.template_engine.provider_templates.keys())
    
    def _get_repository_data_for_provider(
        self, 
        sources: List[PackageInfo], 
        provider: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get repository data for a specific provider from sources.
        
        Args:
            sources: List of package information from repositories
            provider: Provider name to get data for
            
        Returns:
            Repository data for the provider, or None if not found
        """
        for source in sources:
            if source.provider == provider:
                return {
                    "name": source.name,
                    "version": source.version,
                    "description": source.description,
                    **source.details
                }
        return None
    
    def _has_meaningful_overrides(self, provider_overrides: Dict[str, Any]) -> bool:
        """
        Check if provider overrides contain meaningful configuration beyond basic metadata.
        
        Args:
            provider_overrides: Provider override configuration
            
        Returns:
            True if overrides contain meaningful configuration, False otherwise
        """
        # Always skip if explicitly marked as unsupported
        if provider_overrides.get("supported") is False:
            return False
        
        # Check if there are any keys beyond version and supported
        meaningful_keys = set(provider_overrides.keys()) - {"version", "supported"}
        
        # If there are meaningful keys, check if they have non-empty values
        if meaningful_keys:
            for key in meaningful_keys:
                value = provider_overrides[key]
                if value is not None and value != {} and value != []:
                    return True
        
        return False
    
    def _get_provider_filename(self, provider: str) -> str:
        """
        Get the proper filename for a provider override file.
        
        Args:
            provider: Provider name
            
        Returns:
            Filename for the provider override file
        """
        # Sanitize provider name for filename
        safe_provider = provider.replace('/', '_').replace('\\', '_').replace(':', '_')
        return f"{safe_provider}.yaml"
    
    def _write_provider_file(self, file_path: Path, provider_overrides: Dict[str, Any]) -> None:
        """
        Write provider override file with proper formatting and style consistency.
        
        Args:
            file_path: Path to write the file to
            provider_overrides: Provider override configuration to write
        """
        # Clean up the configuration before writing
        cleaned_overrides = self._clean_provider_overrides(provider_overrides)
        
        # Write with consistent formatting
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(
                cleaned_overrides, 
                f, 
                default_flow_style=False, 
                sort_keys=False,
                allow_unicode=True,
                width=120,
                indent=2
            )
    
    def _clean_provider_overrides(self, provider_overrides: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean provider overrides by removing null values and empty structures.
        
        Args:
            provider_overrides: Provider override configuration
            
        Returns:
            Cleaned provider override configuration
        """
        def clean_dict(d):
            if not isinstance(d, dict):
                return d
            
            cleaned = {}
            for key, value in d.items():
                if value is None:
                    continue
                elif isinstance(value, dict):
                    cleaned_value = clean_dict(value)
                    if cleaned_value:  # Only include non-empty dicts
                        cleaned[key] = cleaned_value
                elif isinstance(value, list):
                    cleaned_value = [clean_dict(item) if isinstance(item, dict) else item 
                                   for item in value if item is not None]
                    if cleaned_value:  # Only include non-empty lists
                        cleaned[key] = cleaned_value
                elif value != "" and value != []:  # Exclude empty strings and lists
                    cleaned[key] = value
            
            return cleaned
        
        return clean_dict(provider_overrides)
    
    def create_comprehensive_metadata_file(
        self,
        software_name: str,
        sources: List[PackageInfo],
        output_path: Union[str, Path],
        providers: Optional[List[str]] = None,
        ai_provider: Optional[str] = None,
        enhancement_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create comprehensive metadata file with all provider information merged.
        
        This method creates a single comprehensive metadata file that includes
        all provider information merged together, suitable for cases where
        a single file is preferred over the directory structure.
        
        Args:
            software_name: Name of the software
            sources: List of package information from repositories
            output_path: Path where to create the comprehensive metadata file
            providers: List of providers to include
            ai_provider: AI provider to use for enhancement
            enhancement_types: Types of AI enhancement to apply
            
        Returns:
            Dictionary with information about the generated file
        """
        logger.info(f"Creating comprehensive metadata file for {software_name}")
        
        # Generate base metadata (with or without AI enhancement)
        if ai_provider:
            base_result = self.generate_with_ai_enhancement(
                software_name=software_name,
                sources=sources,
                providers=providers,
                ai_provider=ai_provider,
                enhancement_types=enhancement_types
            )
        else:
            base_result = self.generate_from_sources(
                software_name=software_name,
                sources=sources,
                providers=providers
            )
        
        # Get the merged metadata
        comprehensive_metadata = base_result.metadata.to_dict()
        
        # Add provider-specific information section
        provider_info = {}
        all_providers = providers or self._get_all_available_providers()
        
        for provider in all_providers:
            try:
                provider_overrides = self.template_engine.apply_provider_overrides_only(
                    software_name=software_name,
                    provider=provider,
                    repository_data=self._get_repository_data_for_provider(sources, provider)
                )
                
                if provider_overrides.get("supported") is False:
                    provider_info[provider] = {"supported": False}
                elif self._has_meaningful_overrides(provider_overrides):
                    provider_info[provider] = self._clean_provider_overrides(provider_overrides)
                else:
                    provider_info[provider] = {"supported": True, "overrides": "none"}
                    
            except Exception as e:
                logger.warning(f"Error processing provider {provider}: {e}")
                provider_info[provider] = {"error": str(e)}
        
        # Add provider information to the comprehensive metadata
        comprehensive_metadata["provider_overrides"] = provider_info
        
        # Write the comprehensive metadata file
        output_file_path = Path(output_path)
        output_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file_path, 'w', encoding='utf-8') as f:
            yaml.dump(
                comprehensive_metadata, 
                f, 
                default_flow_style=False, 
                sort_keys=False,
                allow_unicode=True,
                width=120,
                indent=2
            )
        
        logger.info(f"Created comprehensive metadata file: {output_file_path}")
        
        return {
            "software_name": software_name,
            "comprehensive_file": str(output_file_path),
            "provider_count": len(provider_info),
            "validation_result": base_result.validation_result,
            "confidence_scores": base_result.confidence_scores
        }
    
    def validate_generated_directory_structure(
        self,
        software_dir: Union[str, Path]
    ) -> Dict[str, Any]:
        """
        Validate the generated directory structure for correctness and consistency.
        
        Args:
            software_dir: Path to the software directory to validate
            
        Returns:
            Dictionary with validation results and any issues found
        """
        logger.info(f"Validating directory structure: {software_dir}")
        
        software_path = Path(software_dir)
        validation_result = {
            "valid": True,
            "issues": [],
            "warnings": [],
            "structure_valid": True,
            "files_valid": True,
            "consistency_valid": True
        }
        
        # Check if software directory exists
        if not software_path.exists():
            validation_result["valid"] = False
            validation_result["structure_valid"] = False
            validation_result["issues"].append(f"Software directory does not exist: {software_path}")
            return validation_result
        
        # Check for required files
        defaults_path = software_path / "defaults.yaml"
        providers_dir = software_path / "providers"
        
        if not defaults_path.exists():
            validation_result["valid"] = False
            validation_result["structure_valid"] = False
            validation_result["issues"].append("defaults.yaml file is missing")
        
        if not providers_dir.exists():
            validation_result["warnings"].append("providers directory is missing")
        elif not providers_dir.is_dir():
            validation_result["valid"] = False
            validation_result["structure_valid"] = False
            validation_result["issues"].append("providers path exists but is not a directory")
        
        # Validate defaults.yaml file
        if defaults_path.exists():
            try:
                with open(defaults_path, 'r', encoding='utf-8') as f:
                    defaults_content = yaml.safe_load(f)
                
                if not isinstance(defaults_content, dict):
                    validation_result["valid"] = False
                    validation_result["files_valid"] = False
                    validation_result["issues"].append("defaults.yaml does not contain a valid YAML dictionary")
                elif "version" not in defaults_content:
                    validation_result["warnings"].append("defaults.yaml is missing version field")
                
            except yaml.YAMLError as e:
                validation_result["valid"] = False
                validation_result["files_valid"] = False
                validation_result["issues"].append(f"defaults.yaml contains invalid YAML: {e}")
            except Exception as e:
                validation_result["valid"] = False
                validation_result["files_valid"] = False
                validation_result["issues"].append(f"Error reading defaults.yaml: {e}")
        
        # Validate provider files
        if providers_dir.exists() and providers_dir.is_dir():
            provider_files = list(providers_dir.glob("*.yaml"))
            
            if not provider_files:
                validation_result["warnings"].append("No provider files found in providers directory")
            
            for provider_file in provider_files:
                try:
                    with open(provider_file, 'r', encoding='utf-8') as f:
                        provider_content = yaml.safe_load(f)
                    
                    if not isinstance(provider_content, dict):
                        validation_result["valid"] = False
                        validation_result["files_valid"] = False
                        validation_result["issues"].append(f"{provider_file.name} does not contain a valid YAML dictionary")
                    elif "version" not in provider_content:
                        validation_result["warnings"].append(f"{provider_file.name} is missing version field")
                    
                    # Check for consistency with defaults
                    if defaults_path.exists() and isinstance(provider_content, dict):
                        consistency_issues = self._check_provider_consistency(
                            provider_file.stem, provider_content, defaults_content
                        )
                        if consistency_issues:
                            validation_result["consistency_valid"] = False
                            validation_result["issues"].extend(consistency_issues)
                
                except yaml.YAMLError as e:
                    validation_result["valid"] = False
                    validation_result["files_valid"] = False
                    validation_result["issues"].append(f"{provider_file.name} contains invalid YAML: {e}")
                except Exception as e:
                    validation_result["valid"] = False
                    validation_result["files_valid"] = False
                    validation_result["issues"].append(f"Error reading {provider_file.name}: {e}")
        
        logger.info(f"Directory structure validation completed: {'valid' if validation_result['valid'] else 'invalid'}")
        return validation_result
    
    def _check_provider_consistency(
        self,
        provider_name: str,
        provider_content: Dict[str, Any],
        defaults_content: Dict[str, Any]
    ) -> List[str]:
        """
        Check consistency between provider overrides and defaults.
        
        Args:
            provider_name: Name of the provider
            provider_content: Provider override content
            defaults_content: Defaults content
            
        Returns:
            List of consistency issues found
        """
        issues = []
        
        # Check version consistency
        provider_version = provider_content.get("version")
        defaults_version = defaults_content.get("version")
        
        if provider_version and defaults_version and provider_version != defaults_version:
            issues.append(f"Provider {provider_name} version ({provider_version}) differs from defaults version ({defaults_version})")
        
        # Check for conflicting overrides (this is a basic check - could be enhanced)
        if provider_content.get("supported") is False:
            # If provider is unsupported, it shouldn't have other configuration
            meaningful_keys = set(provider_content.keys()) - {"version", "supported"}
            if meaningful_keys:
                issues.append(f"Provider {provider_name} is marked as unsupported but contains configuration: {meaningful_keys}")
        
        return issues
    
    def _is_empty_provider_file(self, provider_content: Dict[str, Any]) -> bool:
        """
        Check if a provider file is effectively empty.
        
        Args:
            provider_content: Provider file content
            
        Returns:
            True if the file is empty or contains only basic metadata
        """
        if not provider_content:
            return True
        
        # Check if it only contains version and/or supported fields
        meaningful_keys = set(provider_content.keys()) - {"version", "supported"}
        
        if not meaningful_keys:
            # Only has version/supported, check if supported is False
            return provider_content.get("supported") is False
        
        # Check if all meaningful keys have empty values
        for key in meaningful_keys:
            value = provider_content[key]
            if value is not None and value != {} and value != []:
                return False
        
        return True
    
    def _is_redundant_provider_file(
        self,
        provider_content: Dict[str, Any],
        defaults_content: Dict[str, Any]
    ) -> bool:
        """
        Check if a provider file is redundant (contains only data that matches defaults).
        
        Args:
            provider_content: Provider file content
            defaults_content: Defaults content
            
        Returns:
            True if the provider file is redundant
        """
        if not provider_content or not defaults_content:
            return False
        
        # Skip version field for comparison
        provider_data = {k: v for k, v in provider_content.items() if k != "version"}
        
        # If provider is explicitly unsupported, it's not redundant
        if provider_data.get("supported") is False:
            return False
        
        # Check if all provider data matches defaults
        for key, value in provider_data.items():
            if key == "supported":
                continue  # Skip supported field
            
            default_value = defaults_content.get(key)
            if not self._values_equal_for_redundancy_check(value, default_value):
                return False
        
        return True
    
    def _values_equal_for_redundancy_check(self, value1: Any, value2: Any) -> bool:
        """
        Check if two values are equal for redundancy checking purposes.
        
        Args:
            value1: First value
            value2: Second value
            
        Returns:
            True if values are considered equal for redundancy purposes
        """
        # Handle None values
        if value1 is None and value2 is None:
            return True
        if value1 is None or value2 is None:
            return False
        
        # Handle different types
        if type(value1) != type(value2):
            return False
        
        # Handle dictionaries
        if isinstance(value1, dict):
            if set(value1.keys()) != set(value2.keys()):
                return False
            return all(self._values_equal_for_redundancy_check(value1[k], value2[k]) for k in value1.keys())
        
        # Handle lists
        if isinstance(value1, list):
            if len(value1) != len(value2):
                return False
            return all(self._values_equal_for_redundancy_check(v1, v2) for v1, v2 in zip(value1, value2))
        
        # Handle primitive types
        return value1 == value2
    
    def cleanup_generated_files(
        self,
        software_dir: Union[str, Path],
        remove_empty: bool = True,
        remove_redundant: bool = True
    ) -> Dict[str, Any]:
        """
        Clean up generated files by removing empty or redundant provider files.
        
        Args:
            software_dir: Path to the software directory to clean up
            remove_empty: Whether to remove empty provider files
            remove_redundant: Whether to remove redundant provider files
            
        Returns:
            Dictionary with cleanup results
        """
        logger.info(f"Cleaning up generated files in: {software_dir}")
        
        software_path = Path(software_dir)
        cleanup_result = {
            "removed_files": [],
            "kept_files": [],
            "errors": []
        }
        
        providers_dir = software_path / "providers"
        if not providers_dir.exists():
            return cleanup_result
        
        # Load defaults for comparison
        defaults_path = software_path / "defaults.yaml"
        defaults_content = {}
        if defaults_path.exists():
            try:
                with open(defaults_path, 'r', encoding='utf-8') as f:
                    defaults_content = yaml.safe_load(f) or {}
            except Exception as e:
                cleanup_result["errors"].append(f"Error reading defaults.yaml: {e}")
        
        # Process each provider file
        for provider_file in providers_dir.glob("*.yaml"):
            try:
                with open(provider_file, 'r', encoding='utf-8') as f:
                    provider_content = yaml.safe_load(f) or {}
                
                should_remove = False
                
                # Check if file is empty or contains only basic metadata
                if remove_empty and self._is_empty_provider_file(provider_content):
                    should_remove = True
                    logger.debug(f"Marking {provider_file.name} for removal: empty file")
                
                # Check if file is redundant (contains only data that matches defaults)
                elif remove_redundant and self._is_redundant_provider_file(provider_content, defaults_content):
                    should_remove = True
                    logger.debug(f"Marking {provider_file.name} for removal: redundant file")
                
                if should_remove:
                    provider_file.unlink()
                    cleanup_result["removed_files"].append(str(provider_file))
                    logger.debug(f"Removed redundant/empty provider file: {provider_file}")
                else:
                    cleanup_result["kept_files"].append(str(provider_file))
            
            except Exception as e:
                cleanup_result["errors"].append(f"Error processing {provider_file.name}: {e}")
        
        logger.info(f"Cleanup completed: removed {len(cleanup_result['removed_files'])} files, kept {len(cleanup_result['kept_files'])} files")
        return cleanup_result
    
    def ensure_formatting_consistency(
        self,
        software_dir: Union[str, Path]
    ) -> Dict[str, Any]:
        """
        Ensure formatting and style consistency for all generated files.
        
        Args:
            software_dir: Path to the software directory to format
            
        Returns:
            Dictionary with formatting results
        """
        logger.info(f"Ensuring formatting consistency in: {software_dir}")
        
        software_path = Path(software_dir)
        formatting_result = {
            "formatted_files": [],
            "errors": []
        }
        
        # Format defaults.yaml
        defaults_path = software_path / "defaults.yaml"
        if defaults_path.exists():
            try:
                with open(defaults_path, 'r', encoding='utf-8') as f:
                    content = yaml.safe_load(f)
                
                if content:
                    self._write_formatted_yaml(defaults_path, content)
                    formatting_result["formatted_files"].append(str(defaults_path))
            
            except Exception as e:
                formatting_result["errors"].append(f"Error formatting defaults.yaml: {e}")
        
        # Format provider files
        providers_dir = software_path / "providers"
        if providers_dir.exists():
            for provider_file in providers_dir.glob("*.yaml"):
                try:
                    with open(provider_file, 'r', encoding='utf-8') as f:
                        content = yaml.safe_load(f)
                    
                    if content:
                        self._write_formatted_yaml(provider_file, content)
                        formatting_result["formatted_files"].append(str(provider_file))
                
                except Exception as e:
                    formatting_result["errors"].append(f"Error formatting {provider_file.name}: {e}")
        
        logger.info(f"Formatting completed: formatted {len(formatting_result['formatted_files'])} files")
        return formatting_result
    
    def _write_formatted_yaml(self, file_path: Path, content: Dict[str, Any]) -> None:
        """
        Write YAML content with consistent formatting.
        
        Args:
            file_path: Path to write the file to
            content: Content to write
        """
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(
                content,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                width=120,
                indent=2,
                line_break='\n'
            )