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

from saidata_gen.core.interfaces import (
    MetadataResult, PackageInfo, SaidataMetadata, ValidationResult
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
        template_engine: Optional[TemplateEngine] = None,
        schema_path: Optional[str] = None
    ):
        """
        Initialize the metadata generator.
        
        Args:
            template_engine: Template engine to use. If None, creates a new one.
            schema_path: Path to the saidata schema. If None, uses the default schema.
        """
        self.template_engine = template_engine or TemplateEngine()
        
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
        
        # Merge data from sources
        metadata = self._merge_sources(metadata, sources)
        
        # Create the enhanced metadata object
        enhanced_metadata = EnhancedSaidataMetadata.from_dict(metadata)
        
        # Validate the metadata
        validation_result = enhanced_metadata.validate()
        
        # Calculate confidence scores
        confidence_scores = self._calculate_confidence_scores(enhanced_metadata, sources)
        
        return MetadataResult(
            metadata=enhanced_metadata,
            validation_result=validation_result,
            confidence_scores=confidence_scores
        )
    
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
        # This is a placeholder for RAG integration
        # The actual implementation will be done in task 6
        logger.info("RAG enhancement not implemented yet")
        return metadata