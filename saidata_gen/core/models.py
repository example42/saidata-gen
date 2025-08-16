"""
Core data models for saidata-gen with YAML serialization/deserialization.

This module extends the core interfaces with YAML serialization/deserialization
capabilities and additional validation methods.
"""

import json
import os
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, cast

import yaml

from saidata_gen.core.interfaces import (
    BatchOptions, BatchResult, CategoryConfig, ContainerConfig, DirectoryConfig,
    FetchResult, FetcherConfig, GenerationOptions, MetadataResult, PackageConfig,
    PackageDetails, PackageInfo, PortConfig, ProcessConfig, RAGConfig,
    RepositoryData, SaidataMetadata, ServiceConfig, SoftwareMatch, URLConfig,
    ValidationIssue, ValidationLevel, ValidationResult
)

T = TypeVar('T')


class YAMLSerializable:
    """Mixin for YAML serialization/deserialization."""

    @classmethod
    def from_yaml(cls: Type[T], yaml_str: str) -> T:
        """
        Create an instance from a YAML string.
        
        Args:
            yaml_str: YAML string to parse
            
        Returns:
            Instance of the class
        """
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)
    
    @classmethod
    def from_yaml_file(cls: Type[T], file_path: Union[str, Path]) -> T:
        """
        Create an instance from a YAML file.
        
        Args:
            file_path: Path to the YAML file
            
        Returns:
            Instance of the class
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            return cls.from_yaml(f.read())
    
    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """
        Create an instance from a dictionary.
        
        Args:
            data: Dictionary to convert
            
        Returns:
            Instance of the class
        """
        if data is None:
            return cls()
        
        # Filter out keys that are not in the dataclass fields
        if is_dataclass(cls):
            field_names = {f.name for f in fields(cls)}
            filtered_data = {k: v for k, v in data.items() if k in field_names}
            return cls(**filtered_data)
        
        return cls(**data)
    
    def to_yaml(self) -> str:
        """
        Convert the instance to a YAML string.
        
        Returns:
            YAML string representation
        """
        return yaml.dump(self.to_dict(), sort_keys=False)
    
    def to_yaml_file(self, file_path: Union[str, Path]) -> None:
        """
        Write the instance to a YAML file.
        
        Args:
            file_path: Path to the output file
        """
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(self.to_yaml())
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the instance to a dictionary.
        
        Returns:
            Dictionary representation
        """
        if is_dataclass(self):
            return asdict(self)
        
        return self.__dict__


@dataclass
class EnhancedSaidataMetadata(SaidataMetadata, YAMLSerializable):
    """
    Enhanced SaidataMetadata with YAML serialization/deserialization and validation.
    """
    
    def validate(self) -> ValidationResult:
        """
        Validate the metadata for integrity.
        
        Returns:
            ValidationResult with validation issues
        """
        issues = []
        
        # Basic validation checks
        if not self.version:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                message="Version is required",
                path="version"
            ))
        
        # Check if at least one package is defined
        if not self.packages:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                message="No packages defined",
                path="packages"
            ))
        
        # Check if description is provided
        if not self.description:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                message="Description is missing",
                path="description"
            ))
        
        # Check if category is provided
        if not self.category.default:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                message="Default category is missing",
                path="category.default"
            ))
        
        # Check if license is provided
        if not self.license:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                message="License is missing",
                path="license"
            ))
        
        # Check if platforms are provided
        if not self.platforms:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                message="No platforms defined",
                path="platforms"
            ))
        
        return ValidationResult(
            valid=not any(issue.level == ValidationLevel.ERROR for issue in issues),
            issues=issues
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EnhancedSaidataMetadata':
        """
        Create an instance from a dictionary with proper nested object handling.
        
        Args:
            data: Dictionary to convert
            
        Returns:
            Instance of EnhancedSaidataMetadata
        """
        if data is None:
            return cls()
        
        # Create a copy to avoid modifying the original
        data_copy = data.copy()
        
        # Handle nested objects
        if 'packages' in data_copy and data_copy['packages']:
            packages = {}
            for key, value in data_copy['packages'].items():
                packages[key] = EnhancedPackageConfig.from_dict(value)
            data_copy['packages'] = packages
        
        if 'services' in data_copy and data_copy['services']:
            services = {}
            for key, value in data_copy['services'].items():
                services[key] = EnhancedServiceConfig.from_dict(value)
            data_copy['services'] = services
        
        if 'directories' in data_copy and data_copy['directories']:
            directories = {}
            for key, value in data_copy['directories'].items():
                directories[key] = EnhancedDirectoryConfig.from_dict(value)
            data_copy['directories'] = directories
        
        if 'processes' in data_copy and data_copy['processes']:
            processes = {}
            for key, value in data_copy['processes'].items():
                processes[key] = EnhancedProcessConfig.from_dict(value)
            data_copy['processes'] = processes
        
        if 'ports' in data_copy and data_copy['ports']:
            ports = {}
            for key, value in data_copy['ports'].items():
                ports[key] = EnhancedPortConfig.from_dict(value)
            data_copy['ports'] = ports
        
        if 'containers' in data_copy and data_copy['containers']:
            containers = {}
            for key, value in data_copy['containers'].items():
                containers[key] = EnhancedContainerConfig.from_dict(value)
            data_copy['containers'] = containers
        
        if 'urls' in data_copy:
            data_copy['urls'] = EnhancedURLConfig.from_dict(data_copy['urls'])
        
        if 'category' in data_copy:
            data_copy['category'] = EnhancedCategoryConfig.from_dict(data_copy['category'])
        
        # Filter out keys that are not in the dataclass fields
        field_names = {f.name for f in fields(cls)}
        filtered_data = {k: v for k, v in data_copy.items() if k in field_names}
        
        return cls(**filtered_data)


@dataclass
class EnhancedPackageConfig(PackageConfig, YAMLSerializable):
    """
    Enhanced PackageConfig with YAML serialization/deserialization and validation.
    """
    
    def validate(self) -> ValidationResult:
        """
        Validate the package configuration.
        
        Returns:
            ValidationResult with validation issues
        """
        issues = []
        
        if not self.name:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                message="Package name is required",
                path="name"
            ))
        
        return ValidationResult(
            valid=not any(issue.level == ValidationLevel.ERROR for issue in issues),
            issues=issues
        )


@dataclass
class EnhancedServiceConfig(ServiceConfig, YAMLSerializable):
    """
    Enhanced ServiceConfig with YAML serialization/deserialization and validation.
    """
    
    def validate(self) -> ValidationResult:
        """
        Validate the service configuration.
        
        Returns:
            ValidationResult with validation issues
        """
        issues = []
        
        if not self.name:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                message="Service name is required",
                path="name"
            ))
        
        return ValidationResult(
            valid=not any(issue.level == ValidationLevel.ERROR for issue in issues),
            issues=issues
        )


@dataclass
class EnhancedDirectoryConfig(DirectoryConfig, YAMLSerializable):
    """
    Enhanced DirectoryConfig with YAML serialization/deserialization and validation.
    """
    
    def validate(self) -> ValidationResult:
        """
        Validate the directory configuration.
        
        Returns:
            ValidationResult with validation issues
        """
        issues = []
        
        if not self.path:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                message="Directory path is required",
                path="path"
            ))
        
        return ValidationResult(
            valid=not any(issue.level == ValidationLevel.ERROR for issue in issues),
            issues=issues
        )


@dataclass
class EnhancedProcessConfig(ProcessConfig, YAMLSerializable):
    """
    Enhanced ProcessConfig with YAML serialization/deserialization and validation.
    """
    
    def validate(self) -> ValidationResult:
        """
        Validate the process configuration.
        
        Returns:
            ValidationResult with validation issues
        """
        issues = []
        
        if not self.name and not self.command:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                message="Process name or command is required",
                path="name/command"
            ))
        
        return ValidationResult(
            valid=not any(issue.level == ValidationLevel.ERROR for issue in issues),
            issues=issues
        )


@dataclass
class EnhancedPortConfig(PortConfig, YAMLSerializable):
    """
    Enhanced PortConfig with YAML serialization/deserialization and validation.
    """
    
    def validate(self) -> ValidationResult:
        """
        Validate the port configuration.
        
        Returns:
            ValidationResult with validation issues
        """
        issues = []
        
        if self.number is None:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                message="Port number is required",
                path="number"
            ))
        
        if self.number is not None and (self.number < 1 or self.number > 65535):
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                message="Port number must be between 1 and 65535",
                path="number"
            ))
        
        if not self.protocol:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                message="Port protocol is missing",
                path="protocol"
            ))
        
        return ValidationResult(
            valid=not any(issue.level == ValidationLevel.ERROR for issue in issues),
            issues=issues
        )


@dataclass
class EnhancedContainerConfig(ContainerConfig, YAMLSerializable):
    """
    Enhanced ContainerConfig with YAML serialization/deserialization and validation.
    """
    
    def validate(self) -> ValidationResult:
        """
        Validate the container configuration.
        
        Returns:
            ValidationResult with validation issues
        """
        issues = []
        
        if not self.image:
            issues.append(ValidationIssue(
                level=ValidationLevel.ERROR,
                message="Container image is required",
                path="image"
            ))
        
        return ValidationResult(
            valid=not any(issue.level == ValidationLevel.ERROR for issue in issues),
            issues=issues
        )


@dataclass
class EnhancedURLConfig(URLConfig, YAMLSerializable):
    """
    Enhanced URLConfig with YAML serialization/deserialization and validation.
    """
    
    def validate(self) -> ValidationResult:
        """
        Validate the URL configuration.
        
        Returns:
            ValidationResult with validation issues
        """
        issues = []
        
        # Check if at least one URL is provided
        if not any([
            self.website, self.sbom, self.issues, self.documentation,
            self.support, self.source, self.license, self.changelog,
            self.download, self.icon
        ]):
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                message="No URLs provided",
                path=""
            ))
        
        return ValidationResult(
            valid=True,  # URLs are optional, so always valid
            issues=issues
        )


@dataclass
class EnhancedCategoryConfig(CategoryConfig, YAMLSerializable):
    """
    Enhanced CategoryConfig with YAML serialization/deserialization and validation.
    """
    
    def validate(self) -> ValidationResult:
        """
        Validate the category configuration.
        
        Returns:
            ValidationResult with validation issues
        """
        issues = []
        
        if not self.default:
            issues.append(ValidationIssue(
                level=ValidationLevel.WARNING,
                message="Default category is missing",
                path="default"
            ))
        
        return ValidationResult(
            valid=True,  # Categories are optional, so always valid
            issues=issues
        )


# Helper function to get dataclass fields
def fields(cls):
    """Get fields of a dataclass."""
    return cls.__dataclass_fields__.values()