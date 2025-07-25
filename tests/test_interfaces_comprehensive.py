"""
Comprehensive unit tests for core interfaces and models.

This module provides comprehensive test coverage for all interface classes
and data models in the saidata-gen system.
"""

import pytest
import tempfile
import os
from dataclasses import asdict
from typing import Dict, Any

from saidata_gen.core.interfaces import (
    SaidataMetadata, PackageConfig, ServiceConfig, DirectoryConfig,
    ProcessConfig, PortConfig, ContainerConfig, URLConfig, CategoryConfig,
    GenerationOptions, BatchOptions, RAGConfig, FetcherConfig, GeneratorConfig,
    SearchOptions, SearchResult, ValidationLevel, ValidationIssue, ValidationResult,
    BatchValidationResult, MetadataResult, BatchResult, SoftwareMatch,
    FetchResult, RepositoryData, PackageInfo, PackageDetails
)
from saidata_gen.core.models import (
    EnhancedSaidataMetadata, EnhancedPackageConfig, EnhancedServiceConfig,
    EnhancedDirectoryConfig, EnhancedProcessConfig, EnhancedPortConfig,
    EnhancedContainerConfig, EnhancedURLConfig, EnhancedCategoryConfig,
    YAMLSerializable
)


class TestSaidataMetadata:
    """Test SaidataMetadata data model."""
    
    def test_default_initialization(self):
        """Test default initialization of SaidataMetadata."""
        metadata = SaidataMetadata()
        
        assert metadata.version == "0.1"
        assert isinstance(metadata.packages, dict)
        assert isinstance(metadata.services, dict)
        assert isinstance(metadata.directories, dict)
        assert isinstance(metadata.processes, dict)
        assert isinstance(metadata.ports, dict)
        assert isinstance(metadata.containers, dict)
        assert isinstance(metadata.charts, dict)
        assert isinstance(metadata.repos, dict)
        assert isinstance(metadata.urls, URLConfig)
        assert isinstance(metadata.category, CategoryConfig)
        assert isinstance(metadata.platforms, list)
        assert metadata.language is None
        assert metadata.description is None
        assert metadata.license is None
    
    def test_custom_initialization(self):
        """Test custom initialization with values."""
        packages = {"apt": PackageConfig(name="nginx", version="1.18.0")}
        urls = URLConfig(website="https://nginx.org")
        category = CategoryConfig(default="Web", sub="Server")
        
        metadata = SaidataMetadata(
            description="Web server",
            language="c",
            license="BSD-2-Clause",
            platforms=["linux", "macos"],
            packages=packages,
            urls=urls,
            category=category
        )
        
        assert metadata.description == "Web server"
        assert metadata.language == "c"
        assert metadata.license == "BSD-2-Clause"
        assert metadata.platforms == ["linux", "macos"]
        assert metadata.packages == packages
        assert metadata.urls == urls
        assert metadata.category == category
    
    def test_serialization(self):
        """Test serialization to dictionary."""
        metadata = SaidataMetadata(
            description="Test software",
            platforms=["linux"]
        )
        
        data = asdict(metadata)
        assert isinstance(data, dict)
        assert data["version"] == "0.1"
        assert data["description"] == "Test software"
        assert data["platforms"] == ["linux"]


class TestPackageConfig:
    """Test PackageConfig data model."""
    
    def test_default_initialization(self):
        """Test default initialization."""
        config = PackageConfig()
        
        assert config.name is None
        assert config.version is None
        assert config.install_options is None
    
    def test_custom_initialization(self):
        """Test initialization with values."""
        config = PackageConfig(
            name="nginx",
            version="1.18.0",
            install_options="--with-ssl"
        )
        
        assert config.name == "nginx"
        assert config.version == "1.18.0"
        assert config.install_options == "--with-ssl"


class TestServiceConfig:
    """Test ServiceConfig data model."""
    
    def test_default_initialization(self):
        """Test default initialization."""
        config = ServiceConfig()
        
        assert config.name is None
        assert config.enabled is False
        assert config.status is None
    
    def test_custom_initialization(self):
        """Test initialization with values."""
        config = ServiceConfig(
            name="nginx",
            enabled=True,
            status="running"
        )
        
        assert config.name == "nginx"
        assert config.enabled is True
        assert config.status == "running"


class TestURLConfig:
    """Test URLConfig data model."""
    
    def test_default_initialization(self):
        """Test default initialization."""
        config = URLConfig()
        
        assert config.website is None
        assert config.sbom is None
        assert config.issues is None
        assert config.documentation is None
        assert config.support is None
        assert config.source is None
        assert config.license is None
        assert config.changelog is None
        assert config.download is None
        assert config.icon is None
    
    def test_custom_initialization(self):
        """Test initialization with values."""
        config = URLConfig(
            website="https://nginx.org",
            documentation="https://nginx.org/docs",
            source="https://github.com/nginx/nginx",
            issues="https://trac.nginx.org"
        )
        
        assert config.website == "https://nginx.org"
        assert config.documentation == "https://nginx.org/docs"
        assert config.source == "https://github.com/nginx/nginx"
        assert config.issues == "https://trac.nginx.org"


class TestCategoryConfig:
    """Test CategoryConfig data model."""
    
    def test_default_initialization(self):
        """Test default initialization."""
        config = CategoryConfig()
        
        assert config.default is None
        assert config.sub is None
        assert config.tags is None
    
    def test_custom_initialization(self):
        """Test initialization with values."""
        config = CategoryConfig(
            default="Web",
            sub="Server",
            tags=["http", "proxy", "server"]
        )
        
        assert config.default == "Web"
        assert config.sub == "Server"
        assert config.tags == ["http", "proxy", "server"]


class TestGenerationOptions:
    """Test GenerationOptions data model."""
    
    def test_default_initialization(self):
        """Test default initialization."""
        options = GenerationOptions()
        
        assert isinstance(options.providers, list)
        assert len(options.providers) == 0
        assert options.use_rag is False
        assert options.rag_provider == "openai"
        assert options.include_dev_packages is False
        assert options.confidence_threshold == 0.7
        assert options.output_format == "yaml"
        assert options.validate_schema is True
    
    def test_custom_initialization(self):
        """Test initialization with custom values."""
        options = GenerationOptions(
            providers=["apt", "brew"],
            use_rag=True,
            rag_provider="anthropic",
            confidence_threshold=0.8,
            output_format="json"
        )
        
        assert options.providers == ["apt", "brew"]
        assert options.use_rag is True
        assert options.rag_provider == "anthropic"
        assert options.confidence_threshold == 0.8
        assert options.output_format == "json"


class TestBatchOptions:
    """Test BatchOptions data model."""
    
    def test_default_initialization(self):
        """Test default initialization."""
        options = BatchOptions()
        
        assert options.output_dir == "."
        assert isinstance(options.providers, list)
        assert options.max_concurrent == 5
        assert options.continue_on_error is True
    
    def test_custom_initialization(self):
        """Test initialization with custom values."""
        options = BatchOptions(
            output_dir="/tmp/output",
            providers=["apt", "dnf"],
            max_concurrent=10,
            continue_on_error=False
        )
        
        assert options.output_dir == "/tmp/output"
        assert options.providers == ["apt", "dnf"]
        assert options.max_concurrent == 10
        assert options.continue_on_error is False


class TestRAGConfig:
    """Test RAGConfig data model."""
    
    def test_default_initialization(self):
        """Test default initialization."""
        config = RAGConfig()
        
        assert config.provider == "openai"
        assert config.model == "gpt-3.5-turbo"
        assert config.api_key is None
        assert config.base_url is None
        assert config.temperature == 0.1
        assert config.max_tokens == 1000
    
    def test_custom_initialization(self):
        """Test initialization with custom values."""
        config = RAGConfig(
            provider="anthropic",
            model="claude-3-sonnet",
            api_key="test-key",
            temperature=0.2,
            max_tokens=2000
        )
        
        assert config.provider == "anthropic"
        assert config.model == "claude-3-sonnet"
        assert config.api_key == "test-key"
        assert config.temperature == 0.2
        assert config.max_tokens == 2000


class TestFetcherConfig:
    """Test FetcherConfig data model."""
    
    def test_default_initialization(self):
        """Test default initialization."""
        config = FetcherConfig()
        
        assert config.cache_dir == "~/.saidata-gen/cache"
        assert config.cache_ttl == 3600
        assert config.concurrent_requests == 5
        assert config.request_timeout == 30
        assert config.retry_count == 3
    
    def test_custom_initialization(self):
        """Test initialization with custom values."""
        config = FetcherConfig(
            cache_dir="/tmp/cache",
            cache_ttl=7200,
            concurrent_requests=10,
            request_timeout=60,
            retry_count=5
        )
        
        assert config.cache_dir == "/tmp/cache"
        assert config.cache_ttl == 7200
        assert config.concurrent_requests == 10
        assert config.request_timeout == 60
        assert config.retry_count == 5


class TestGeneratorConfig:
    """Test GeneratorConfig data model."""
    
    def test_default_initialization(self):
        """Test default initialization."""
        config = GeneratorConfig()
        
        assert config.template_dir == "templates"
        assert config.defaults_file == "defaults.yaml"
        assert isinstance(config.provider_templates, dict)
        assert config.enable_rag is False
        assert config.rag_config is None
        assert config.confidence_threshold == 0.7
        assert config.merge_strategy == "weighted"
    
    def test_custom_initialization(self):
        """Test initialization with custom values."""
        rag_config = RAGConfig(provider="openai")
        config = GeneratorConfig(
            template_dir="/custom/templates",
            enable_rag=True,
            rag_config=rag_config,
            confidence_threshold=0.8,
            merge_strategy="priority"
        )
        
        assert config.template_dir == "/custom/templates"
        assert config.enable_rag is True
        assert config.rag_config == rag_config
        assert config.confidence_threshold == 0.8
        assert config.merge_strategy == "priority"


class TestSearchOptions:
    """Test SearchOptions data model."""
    
    def test_default_initialization(self):
        """Test default initialization."""
        options = SearchOptions()
        
        assert isinstance(options.providers, list)
        assert options.fuzzy_threshold == 0.6
        assert options.max_results == 50
        assert options.include_dev_packages is False
        assert options.exact_match_only is False
        assert options.case_sensitive is False
    
    def test_custom_initialization(self):
        """Test initialization with custom values."""
        options = SearchOptions(
            providers=["apt", "brew"],
            fuzzy_threshold=0.8,
            max_results=20,
            exact_match_only=True,
            case_sensitive=True
        )
        
        assert options.providers == ["apt", "brew"]
        assert options.fuzzy_threshold == 0.8
        assert options.max_results == 20
        assert options.exact_match_only is True
        assert options.case_sensitive is True


class TestValidationLevel:
    """Test ValidationLevel enum."""
    
    def test_enum_values(self):
        """Test enum values."""
        assert ValidationLevel.ERROR.value == "error"
        assert ValidationLevel.WARNING.value == "warning"
        assert ValidationLevel.INFO.value == "info"
    
    def test_enum_comparison(self):
        """Test enum comparison."""
        assert ValidationLevel.ERROR != ValidationLevel.WARNING
        assert ValidationLevel.WARNING != ValidationLevel.INFO
        assert ValidationLevel.ERROR == ValidationLevel.ERROR


class TestValidationIssue:
    """Test ValidationIssue data model."""
    
    def test_initialization(self):
        """Test initialization."""
        issue = ValidationIssue(
            level=ValidationLevel.ERROR,
            message="Invalid field",
            path="packages.apt.name",
            schema_path="properties.packages.properties.apt.properties.name"
        )
        
        assert issue.level == ValidationLevel.ERROR
        assert issue.message == "Invalid field"
        assert issue.path == "packages.apt.name"
        assert issue.schema_path == "properties.packages.properties.apt.properties.name"
    
    def test_optional_schema_path(self):
        """Test initialization without schema path."""
        issue = ValidationIssue(
            level=ValidationLevel.WARNING,
            message="Missing field",
            path="description"
        )
        
        assert issue.level == ValidationLevel.WARNING
        assert issue.message == "Missing field"
        assert issue.path == "description"
        assert issue.schema_path is None


class TestValidationResult:
    """Test ValidationResult data model."""
    
    def test_valid_result(self):
        """Test valid validation result."""
        result = ValidationResult(valid=True)
        
        assert result.valid is True
        assert isinstance(result.issues, list)
        assert len(result.issues) == 0
        assert result.file_path is None
    
    def test_invalid_result_with_issues(self):
        """Test invalid validation result with issues."""
        issues = [
            ValidationIssue(ValidationLevel.ERROR, "Missing version", "version"),
            ValidationIssue(ValidationLevel.WARNING, "Empty description", "description")
        ]
        
        result = ValidationResult(
            valid=False,
            issues=issues,
            file_path="/path/to/file.yaml"
        )
        
        assert result.valid is False
        assert len(result.issues) == 2
        assert result.file_path == "/path/to/file.yaml"


class TestMetadataResult:
    """Test MetadataResult data model."""
    
    def test_successful_result(self):
        """Test successful metadata result."""
        metadata = SaidataMetadata(description="Test software")
        result = MetadataResult(
            metadata=metadata,
            success=True,
            software_name="nginx"
        )
        
        assert result.metadata == metadata
        assert result.success is True
        assert result.software_name == "nginx"
        assert result.error_message is None
        assert isinstance(result.confidence_scores, dict)
    
    def test_failed_result(self):
        """Test failed metadata result."""
        result = MetadataResult(
            success=False,
            software_name="nonexistent",
            error_message="Package not found"
        )
        
        assert result.metadata is None
        assert result.success is False
        assert result.software_name == "nonexistent"
        assert result.error_message == "Package not found"


class TestBatchResult:
    """Test BatchResult data model."""
    
    def test_initialization(self):
        """Test batch result initialization."""
        result = BatchResult(
            total_processed=5,
            successful=4,
            failed=1,
            errors=["Package 'nonexistent' not found"]
        )
        
        assert result.total_processed == 5
        assert result.successful == 4
        assert result.failed == 1
        assert len(result.errors) == 1
        assert result.errors[0] == "Package 'nonexistent' not found"
        assert isinstance(result.results, dict)
        assert isinstance(result.summary, dict)


class TestSoftwareMatch:
    """Test SoftwareMatch data model."""
    
    def test_initialization(self):
        """Test software match initialization."""
        match = SoftwareMatch(
            name="nginx",
            provider="apt",
            version="1.18.0",
            description="Web server",
            score=0.95
        )
        
        assert match.name == "nginx"
        assert match.provider == "apt"
        assert match.version == "1.18.0"
        assert match.description == "Web server"
        assert match.score == 0.95
        assert isinstance(match.details, dict)
    
    def test_minimal_initialization(self):
        """Test minimal initialization."""
        match = SoftwareMatch(name="nginx", provider="apt")
        
        assert match.name == "nginx"
        assert match.provider == "apt"
        assert match.version is None
        assert match.description is None
        assert match.score == 0.0


class TestRepositoryData:
    """Test RepositoryData data model."""
    
    def test_initialization(self):
        """Test repository data initialization."""
        packages = {"nginx": {"version": "1.18.0", "description": "Web server"}}
        data = RepositoryData(
            provider="apt",
            packages=packages,
            timestamp=1640995200.0,
            source_url="http://archive.ubuntu.com/ubuntu"
        )
        
        assert data.provider == "apt"
        assert data.packages == packages
        assert data.timestamp == 1640995200.0
        assert data.source_url == "http://archive.ubuntu.com/ubuntu"


class TestPackageInfo:
    """Test PackageInfo data model."""
    
    def test_initialization(self):
        """Test package info initialization."""
        details = {"architecture": "amd64", "size": "3588"}
        info = PackageInfo(
            name="nginx",
            provider="apt",
            version="1.18.0",
            description="Web server",
            details=details
        )
        
        assert info.name == "nginx"
        assert info.provider == "apt"
        assert info.version == "1.18.0"
        assert info.description == "Web server"
        assert info.details == details


class TestPackageDetails:
    """Test PackageDetails data model."""
    
    def test_comprehensive_initialization(self):
        """Test comprehensive package details initialization."""
        raw_data = {"Package": "nginx", "Section": "httpd"}
        details = PackageDetails(
            name="nginx",
            provider="apt",
            version="1.18.0",
            description="Web server",
            license="BSD-2-Clause",
            homepage="https://nginx.org",
            dependencies=["libc6", "libssl1.1"],
            maintainer="Ubuntu Developers",
            source_url="https://github.com/nginx/nginx",
            download_url="http://archive.ubuntu.com/ubuntu/pool/main/n/nginx/",
            checksum="abc123def456",
            raw_data=raw_data
        )
        
        assert details.name == "nginx"
        assert details.provider == "apt"
        assert details.version == "1.18.0"
        assert details.description == "Web server"
        assert details.license == "BSD-2-Clause"
        assert details.homepage == "https://nginx.org"
        assert details.dependencies == ["libc6", "libssl1.1"]
        assert details.maintainer == "Ubuntu Developers"
        assert details.source_url == "https://github.com/nginx/nginx"
        assert details.download_url == "http://archive.ubuntu.com/ubuntu/pool/main/n/nginx/"
        assert details.checksum == "abc123def456"
        assert details.raw_data == raw_data


# Integration tests for interface compatibility
class TestInterfaceCompatibility:
    """Test interface compatibility and integration."""
    
    def test_metadata_with_all_configs(self):
        """Test SaidataMetadata with all config types."""
        metadata = SaidataMetadata(
            packages={"apt": PackageConfig(name="nginx")},
            services={"default": ServiceConfig(name="nginx", enabled=True)},
            directories={"config": DirectoryConfig(path="/etc/nginx")},
            processes={"main": ProcessConfig(name="nginx", command="/usr/sbin/nginx")},
            ports={"http": PortConfig(number=80, protocol="tcp")},
            containers={"web": ContainerConfig(name="nginx", image="nginx", tag="latest")},
            urls=URLConfig(website="https://nginx.org"),
            category=CategoryConfig(default="Web", sub="Server")
        )
        
        # Should be able to serialize without errors
        data = asdict(metadata)
        assert isinstance(data, dict)
        assert "packages" in data
        assert "services" in data
        assert "directories" in data
        assert "processes" in data
        assert "ports" in data
        assert "containers" in data
        assert "urls" in data
        assert "category" in data
    
    def test_result_objects_compatibility(self):
        """Test result objects work together."""
        # Create a validation result
        validation_result = ValidationResult(valid=True)
        
        # Create metadata result with validation
        metadata = SaidataMetadata(description="Test")
        metadata_result = MetadataResult(
            metadata=metadata,
            validation_result=validation_result,
            success=True,
            software_name="test"
        )
        
        # Create batch result with metadata results
        batch_result = BatchResult(
            results={"test": metadata_result},
            total_processed=1,
            successful=1,
            failed=0
        )
        
        assert batch_result.results["test"] == metadata_result
        assert batch_result.total_processed == 1
        assert batch_result.successful == 1


# Tests for Enhanced Models with YAML serialization
class TestYAMLSerializable:
    """Test YAMLSerializable mixin functionality."""
    
    def test_yaml_serialization_roundtrip(self):
        """Test YAML serialization and deserialization roundtrip."""
        original_data = {
            "version": "0.1",
            "description": "Test software",
            "platforms": ["linux", "macos"]
        }
        
        # Create enhanced metadata
        metadata = EnhancedSaidataMetadata.from_dict(original_data)
        
        # Convert to YAML and back
        yaml_str = metadata.to_yaml()
        restored_metadata = EnhancedSaidataMetadata.from_yaml(yaml_str)
        
        assert restored_metadata.version == original_data["version"]
        assert restored_metadata.description == original_data["description"]
        assert restored_metadata.platforms == original_data["platforms"]
    
    def test_yaml_file_operations(self):
        """Test YAML file read/write operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "test.yaml")
            
            # Create and save metadata
            metadata = EnhancedSaidataMetadata(
                version="0.1",
                description="Test software",
                platforms=["linux"]
            )
            metadata.to_yaml_file(file_path)
            
            # Load from file
            loaded_metadata = EnhancedSaidataMetadata.from_yaml_file(file_path)
            
            assert loaded_metadata.version == metadata.version
            assert loaded_metadata.description == metadata.description
            assert loaded_metadata.platforms == metadata.platforms


class TestEnhancedSaidataMetadata:
    """Test EnhancedSaidataMetadata functionality."""
    
    def test_validation_complete_metadata(self):
        """Test validation with complete metadata."""
        metadata = EnhancedSaidataMetadata(
            version="0.1",
            description="Complete test software",
            license="MIT",
            platforms=["linux", "macos"],
            packages={"apt": EnhancedPackageConfig(name="test-pkg")},
            category=EnhancedCategoryConfig(default="Development")
        )
        
        result = metadata.validate()
        
        assert isinstance(result, ValidationResult)
        assert result.valid is True
        # Should have minimal issues for complete metadata
        error_count = sum(1 for issue in result.issues if issue.level == ValidationLevel.ERROR)
        assert error_count == 0
    
    def test_validation_minimal_metadata(self):
        """Test validation with minimal metadata."""
        metadata = EnhancedSaidataMetadata()  # Default initialization
        
        result = metadata.validate()
        
        assert isinstance(result, ValidationResult)
        # Should have warnings but might still be valid
        warning_count = sum(1 for issue in result.issues if issue.level == ValidationLevel.WARNING)
        assert warning_count > 0
    
    def test_validation_missing_version(self):
        """Test validation with missing version."""
        metadata = EnhancedSaidataMetadata(version="")  # Empty version
        
        result = metadata.validate()
        
        assert isinstance(result, ValidationResult)
        assert result.valid is False
        
        # Should have error about missing version
        error_messages = [issue.message for issue in result.issues if issue.level == ValidationLevel.ERROR]
        assert any("version" in msg.lower() for msg in error_messages)
    
    def test_from_dict_with_nested_objects(self):
        """Test creating metadata from dictionary with nested objects."""
        data = {
            "version": "0.1",
            "description": "Test software",
            "packages": {
                "apt": {"name": "test-pkg", "version": "1.0.0"},
                "brew": {"name": "test-pkg", "version": "1.0.1"}
            },
            "services": {
                "main": {"name": "test-service", "enabled": True}
            },
            "urls": {
                "website": "https://example.com",
                "documentation": "https://docs.example.com"
            },
            "category": {
                "default": "Development",
                "sub": "Tools",
                "tags": ["testing", "development"]
            }
        }
        
        metadata = EnhancedSaidataMetadata.from_dict(data)
        
        assert metadata.version == "0.1"
        assert metadata.description == "Test software"
        
        # Check nested objects are properly converted
        assert isinstance(metadata.packages["apt"], EnhancedPackageConfig)
        assert metadata.packages["apt"].name == "test-pkg"
        assert metadata.packages["apt"].version == "1.0.0"
        
        assert isinstance(metadata.services["main"], EnhancedServiceConfig)
        assert metadata.services["main"].name == "test-service"
        assert metadata.services["main"].enabled is True
        
        assert isinstance(metadata.urls, EnhancedURLConfig)
        assert metadata.urls.website == "https://example.com"
        
        assert isinstance(metadata.category, EnhancedCategoryConfig)
        assert metadata.category.default == "Development"
        assert metadata.category.tags == ["testing", "development"]


class TestEnhancedPackageConfig:
    """Test EnhancedPackageConfig functionality."""
    
    def test_validation_valid_package(self):
        """Test validation with valid package configuration."""
        config = EnhancedPackageConfig(
            name="nginx",
            version="1.18.0",
            install_options="--with-ssl"
        )
        
        result = config.validate()
        
        assert isinstance(result, ValidationResult)
        assert result.valid is True
        assert len(result.issues) == 0
    
    def test_validation_missing_name(self):
        """Test validation with missing package name."""
        config = EnhancedPackageConfig(version="1.0.0")
        
        result = config.validate()
        
        assert isinstance(result, ValidationResult)
        assert result.valid is False
        
        error_messages = [issue.message for issue in result.issues]
        assert any("name" in msg.lower() for msg in error_messages)
    
    def test_yaml_serialization(self):
        """Test YAML serialization of package config."""
        config = EnhancedPackageConfig(
            name="nginx",
            version="1.18.0"
        )
        
        yaml_str = config.to_yaml()
        restored_config = EnhancedPackageConfig.from_yaml(yaml_str)
        
        assert restored_config.name == config.name
        assert restored_config.version == config.version


class TestEnhancedServiceConfig:
    """Test EnhancedServiceConfig functionality."""
    
    def test_validation_valid_service(self):
        """Test validation with valid service configuration."""
        config = EnhancedServiceConfig(
            name="nginx",
            enabled=True,
            status="running"
        )
        
        result = config.validate()
        
        assert isinstance(result, ValidationResult)
        assert result.valid is True
        assert len(result.issues) == 0
    
    def test_validation_missing_name(self):
        """Test validation with missing service name."""
        config = EnhancedServiceConfig(enabled=True)
        
        result = config.validate()
        
        assert isinstance(result, ValidationResult)
        assert result.valid is False


class TestEnhancedPortConfig:
    """Test EnhancedPortConfig functionality."""
    
    def test_validation_valid_port(self):
        """Test validation with valid port configuration."""
        config = EnhancedPortConfig(
            number=80,
            protocol="tcp",
            service="http"
        )
        
        result = config.validate()
        
        assert isinstance(result, ValidationResult)
        assert result.valid is True
    
    def test_validation_missing_port_number(self):
        """Test validation with missing port number."""
        config = EnhancedPortConfig(protocol="tcp")
        
        result = config.validate()
        
        assert isinstance(result, ValidationResult)
        assert result.valid is False
        
        error_messages = [issue.message for issue in result.issues]
        assert any("number" in msg.lower() for msg in error_messages)
    
    def test_validation_invalid_port_range(self):
        """Test validation with invalid port number range."""
        # Test port number too high
        config_high = EnhancedPortConfig(number=70000)
        result_high = config_high.validate()
        assert result_high.valid is False
        
        # Test port number too low
        config_low = EnhancedPortConfig(number=0)
        result_low = config_low.validate()
        assert result_low.valid is False
    
    def test_validation_missing_protocol_warning(self):
        """Test validation with missing protocol (should be warning)."""
        config = EnhancedPortConfig(number=80)
        
        result = config.validate()
        
        assert isinstance(result, ValidationResult)
        assert result.valid is True  # Should be valid despite warning
        
        warning_count = sum(1 for issue in result.issues if issue.level == ValidationLevel.WARNING)
        assert warning_count > 0


class TestEnhancedContainerConfig:
    """Test EnhancedContainerConfig functionality."""
    
    def test_validation_valid_container(self):
        """Test validation with valid container configuration."""
        config = EnhancedContainerConfig(
            name="nginx-container",
            image="nginx",
            tag="latest"
        )
        
        result = config.validate()
        
        assert isinstance(result, ValidationResult)
        assert result.valid is True
        assert len(result.issues) == 0
    
    def test_validation_missing_image(self):
        """Test validation with missing container image."""
        config = EnhancedContainerConfig(name="test-container")
        
        result = config.validate()
        
        assert isinstance(result, ValidationResult)
        assert result.valid is False
        
        error_messages = [issue.message for issue in result.issues]
        assert any("image" in msg.lower() for msg in error_messages)


class TestEnhancedURLConfig:
    """Test EnhancedURLConfig functionality."""
    
    def test_validation_with_urls(self):
        """Test validation with URLs provided."""
        config = EnhancedURLConfig(
            website="https://nginx.org",
            documentation="https://nginx.org/docs",
            source="https://github.com/nginx/nginx"
        )
        
        result = config.validate()
        
        assert isinstance(result, ValidationResult)
        assert result.valid is True
    
    def test_validation_no_urls(self):
        """Test validation with no URLs provided."""
        config = EnhancedURLConfig()
        
        result = config.validate()
        
        assert isinstance(result, ValidationResult)
        assert result.valid is True  # Should be valid despite warning
        
        warning_count = sum(1 for issue in result.issues if issue.level == ValidationLevel.WARNING)
        assert warning_count > 0


class TestEnhancedCategoryConfig:
    """Test EnhancedCategoryConfig functionality."""
    
    def test_validation_with_category(self):
        """Test validation with category provided."""
        config = EnhancedCategoryConfig(
            default="Web",
            sub="Server",
            tags=["http", "proxy", "server"]
        )
        
        result = config.validate()
        
        assert isinstance(result, ValidationResult)
        assert result.valid is True
    
    def test_validation_missing_default_category(self):
        """Test validation with missing default category."""
        config = EnhancedCategoryConfig(sub="Server")
        
        result = config.validate()
        
        assert isinstance(result, ValidationResult)
        assert result.valid is True  # Should be valid despite warning
        
        warning_count = sum(1 for issue in result.issues if issue.level == ValidationLevel.WARNING)
        assert warning_count > 0


# Integration tests for enhanced models
class TestEnhancedModelsIntegration:
    """Integration tests for enhanced models."""
    
    def test_complete_metadata_workflow(self):
        """Test complete workflow with enhanced metadata."""
        # Create comprehensive metadata
        metadata = EnhancedSaidataMetadata(
            version="0.1",
            description="Nginx HTTP server and reverse proxy",
            language="c",
            license="BSD-2-Clause",
            platforms=["linux", "macos", "windows"],
            packages={
                "apt": EnhancedPackageConfig(name="nginx", version="1.18.0"),
                "brew": EnhancedPackageConfig(name="nginx", version="1.25.3")
            },
            services={
                "default": EnhancedServiceConfig(name="nginx", enabled=True)
            },
            directories={
                "config": EnhancedDirectoryConfig(path="/etc/nginx", owner="root")
            },
            processes={
                "main": EnhancedProcessConfig(name="nginx", command="/usr/sbin/nginx")
            },
            ports={
                "http": EnhancedPortConfig(number=80, protocol="tcp"),
                "https": EnhancedPortConfig(number=443, protocol="tcp")
            },
            containers={
                "web": EnhancedContainerConfig(name="nginx", image="nginx", tag="latest")
            },
            urls=EnhancedURLConfig(
                website="https://nginx.org",
                documentation="https://nginx.org/docs",
                source="https://github.com/nginx/nginx"
            ),
            category=EnhancedCategoryConfig(
                default="Web",
                sub="Server",
                tags=["http", "proxy", "server"]
            )
        )
        
        # Validate metadata
        validation_result = metadata.validate()
        assert validation_result.valid is True
        
        # Test YAML serialization
        yaml_str = metadata.to_yaml()
        assert isinstance(yaml_str, str)
        assert "version: '0.1'" in yaml_str
        assert "nginx" in yaml_str
        
        # Test deserialization
        restored_metadata = EnhancedSaidataMetadata.from_yaml(yaml_str)
        assert restored_metadata.version == metadata.version
        assert restored_metadata.description == metadata.description
        assert len(restored_metadata.packages) == len(metadata.packages)
        assert len(restored_metadata.services) == len(metadata.services)
        
        # Test individual component validation
        for package_config in restored_metadata.packages.values():
            package_result = package_config.validate()
            assert package_result.valid is True
        
        for service_config in restored_metadata.services.values():
            service_result = service_config.validate()
            assert service_result.valid is True
    
    def test_yaml_file_roundtrip_with_complex_data(self):
        """Test YAML file operations with complex nested data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, "complex_metadata.yaml")
            
            # Create complex metadata
            original_metadata = EnhancedSaidataMetadata(
                version="0.1",
                description="Complex software with multiple components",
                packages={
                    "apt": EnhancedPackageConfig(name="complex-app", version="2.1.0"),
                    "brew": EnhancedPackageConfig(name="complex-app", version="2.1.1"),
                    "docker": EnhancedPackageConfig(name="complex-app/server")
                },
                ports={
                    "api": EnhancedPortConfig(number=8080, protocol="tcp", service="api"),
                    "metrics": EnhancedPortConfig(number=9090, protocol="tcp", service="metrics")
                },
                category=EnhancedCategoryConfig(
                    default="Development",
                    sub="Framework",
                    tags=["api", "microservice", "monitoring"]
                )
            )
            
            # Save to file
            original_metadata.to_yaml_file(file_path)
            
            # Load from file
            loaded_metadata = EnhancedSaidataMetadata.from_yaml_file(file_path)
            
            # Verify data integrity
            assert loaded_metadata.version == original_metadata.version
            assert loaded_metadata.description == original_metadata.description
            assert len(loaded_metadata.packages) == len(original_metadata.packages)
            assert len(loaded_metadata.ports) == len(original_metadata.ports)
            
            # Verify nested objects
            assert loaded_metadata.packages["apt"].name == "complex-app"
            assert loaded_metadata.packages["apt"].version == "2.1.0"
            assert loaded_metadata.ports["api"].number == 8080
            assert loaded_metadata.category.tags == ["api", "microservice", "monitoring"]