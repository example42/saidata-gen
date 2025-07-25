"""
Integration tests for complete workflows.

This module provides integration tests that test complete workflows
from end-to-end, including metadata generation, validation, and file operations.
"""

import pytest
import tempfile
import os
import json
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from saidata_gen.core.engine import SaidataEngine
from saidata_gen.core.interfaces import (
    GenerationOptions, BatchOptions, ValidationResult, MetadataResult,
    SaidataMetadata, PackageConfig
)
from saidata_gen.core.models import EnhancedSaidataMetadata
from saidata_gen.validation.schema import SchemaValidator
from saidata_gen.validation.quality import QualityAssessment


@pytest.mark.integration
class TestMetadataGenerationWorkflow:
    """Integration tests for complete metadata generation workflow."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace for integration tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = {
                "root": Path(temp_dir),
                "schemas": Path(temp_dir) / "schemas",
                "templates": Path(temp_dir) / "templates",
                "output": Path(temp_dir) / "output",
                "cache": Path(temp_dir) / "cache"
            }
            
            # Create directories
            for path in workspace.values():
                if isinstance(path, Path):
                    path.mkdir(exist_ok=True)
            
            # Create sample schema
            schema_content = {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": {
                    "version": {"type": "string", "enum": ["0.1"]},
                    "description": {"type": "string"},
                    "packages": {"type": "object"},
                    "urls": {"type": "object"}
                },
                "required": ["version"]
            }
            
            schema_file = workspace["schemas"] / "saidata-0.1.schema.json"
            with open(schema_file, "w") as f:
                json.dump(schema_content, f)
            
            # Create sample template
            template_content = {
                "version": "0.1",
                "category": {"default": "Development"},
                "platforms": ["linux"]
            }
            
            template_file = workspace["templates"] / "defaults.yaml"
            with open(template_file, "w") as f:
                yaml.dump(template_content, f)
            
            workspace["schema_file"] = schema_file
            workspace["template_file"] = template_file
            
            yield workspace
    
    @pytest.fixture
    def mock_repository_data(self):
        """Provide mock repository data for testing."""
        return {
            "apt": {
                "nginx": {
                    "name": "nginx",
                    "version": "1.18.0",
                    "description": "HTTP server and reverse proxy",
                    "homepage": "https://nginx.org",
                    "license": "BSD-2-Clause"
                }
            },
            "brew": {
                "nginx": {
                    "name": "nginx",
                    "version": "1.25.3",
                    "description": "HTTP(S) server and reverse proxy",
                    "homepage": "https://nginx.org",
                    "license": "BSD-2-Clause"
                }
            }
        }
    
    def test_complete_metadata_generation_workflow(self, temp_workspace, mock_repository_data):
        """Test complete metadata generation workflow from start to finish."""
        # This is a mock integration test since the actual implementation is not complete
        # In a real scenario, this would test the full pipeline
        
        # Step 1: Create enhanced metadata
        metadata = EnhancedSaidataMetadata(
            version="0.1",
            description="Nginx HTTP server and reverse proxy",
            language="c",
            license="BSD-2-Clause",
            platforms=["linux", "macos", "windows"],
            packages={
                "apt": PackageConfig(name="nginx", version="1.18.0"),
                "brew": PackageConfig(name="nginx", version="1.25.3")
            }
        )
        
        # Step 2: Validate metadata
        validation_result = metadata.validate()
        assert validation_result.valid is True
        
        # Step 3: Save to file
        output_file = temp_workspace["output"] / "nginx.yaml"
        metadata.to_yaml_file(output_file)
        
        # Step 4: Validate saved file against schema
        validator = SchemaValidator(str(temp_workspace["schema_file"]))
        file_validation = validator.validate_file(str(output_file))
        assert file_validation.valid is True
        
        # Step 5: Load and verify roundtrip
        loaded_metadata = EnhancedSaidataMetadata.from_yaml_file(output_file)
        assert loaded_metadata.version == metadata.version
        assert loaded_metadata.description == metadata.description
        assert len(loaded_metadata.packages) == len(metadata.packages)
    
    def test_batch_metadata_generation_workflow(self, temp_workspace):
        """Test batch metadata generation workflow."""
        software_list = ["nginx", "apache2", "mysql"]
        
        # Create mock metadata for each software
        mock_metadata = {}
        for software in software_list:
            metadata = EnhancedSaidataMetadata(
                version="0.1",
                description=f"{software} software package",
                packages={"apt": PackageConfig(name=software, version="1.0.0")}
            )
            mock_metadata[software] = metadata
            
            # Save to output directory
            output_file = temp_workspace["output"] / f"{software}.yaml"
            metadata.to_yaml_file(output_file)
        
        # Validate all generated files
        validator = SchemaValidator(str(temp_workspace["schema_file"]))
        
        validation_results = {}
        for software in software_list:
            output_file = temp_workspace["output"] / f"{software}.yaml"
            result = validator.validate_file(str(output_file))
            validation_results[software] = result
        
        # All should be valid
        for software, result in validation_results.items():
            assert result.valid is True, f"Validation failed for {software}"
        
        # Test batch validation
        file_paths = [str(temp_workspace["output"] / f"{software}.yaml") for software in software_list]
        batch_result = validator.validate_batch(file_paths)
        
        assert len(batch_result.results) == len(software_list)
        assert batch_result.summary["valid"] == len(software_list)
        assert batch_result.summary["invalid"] == 0
    
    def test_quality_assessment_workflow(self, temp_workspace):
        """Test quality assessment workflow."""
        # Create enhanced metadata objects for testing
        from saidata_gen.core.interfaces import PackageInfo
        
        # Create high quality metadata
        high_quality_metadata = EnhancedSaidataMetadata(
            version="0.1",
            description="High-quality comprehensive software metadata",
            language="python",
            license="MIT",
            platforms=["linux", "macos", "windows"],
            packages={
                "apt": PackageConfig(name="high-quality-app", version="2.1.0"),
                "brew": PackageConfig(name="high-quality-app", version="2.1.0")
            }
        )
        
        # Create low quality metadata
        low_quality_metadata = EnhancedSaidataMetadata(
            version="0.1",
            description="App"
        )
        
        # Create mock source data
        high_quality_source_data = {
            "apt": [
                PackageInfo(
                    name="high-quality-app",
                    provider="apt",
                    version="2.1.0",
                    description="High-quality comprehensive software metadata"
                )
            ],
            "brew": [
                PackageInfo(
                    name="high-quality-app", 
                    provider="brew",
                    version="2.1.0",
                    description="High-quality comprehensive software metadata"
                )
            ]
        }
        
        low_quality_source_data = {
            "apt": [
                PackageInfo(
                    name="app",
                    provider="apt",
                    version="1.0.0",
                    description="App"
                )
            ]
        }
        
        # Assess quality
        quality_assessor = QualityAssessment()
        
        high_quality_assessment = quality_assessor.assess_metadata_quality(
            high_quality_metadata, high_quality_source_data, "high-quality-app"
        )
        low_quality_assessment = quality_assessor.assess_metadata_quality(
            low_quality_metadata, low_quality_source_data, "app"
        )
        
        # High quality should score better than low quality
        assert high_quality_assessment.overall_quality_score > low_quality_assessment.overall_quality_score
        assert high_quality_assessment.overall_confidence_score > low_quality_assessment.overall_confidence_score
        
        # High quality should have fewer consistency issues
        assert len(high_quality_assessment.consistency_issues) <= len(low_quality_assessment.consistency_issues)
    
    def test_error_handling_workflow(self, temp_workspace):
        """Test error handling in workflows."""
        # Test with invalid schema file
        invalid_schema_file = temp_workspace["schemas"] / "invalid.json"
        with open(invalid_schema_file, "w") as f:
            f.write("invalid json content")
        
        with pytest.raises(json.JSONDecodeError):
            SchemaValidator(str(invalid_schema_file))
        
        # Test with nonexistent file validation
        validator = SchemaValidator(str(temp_workspace["schema_file"]))
        nonexistent_file = temp_workspace["output"] / "nonexistent.yaml"
        
        result = validator.validate_file(str(nonexistent_file))
        assert result.valid is False
        assert len(result.issues) > 0
        
        # Test with invalid YAML file
        invalid_yaml_file = temp_workspace["output"] / "invalid.yaml"
        with open(invalid_yaml_file, "w") as f:
            f.write("invalid: yaml: content: [")
        
        result = validator.validate_file(str(invalid_yaml_file))
        assert result.valid is False
        assert len(result.issues) > 0


@pytest.mark.integration
class TestSearchAndDiscoveryWorkflow:
    """Integration tests for search and discovery workflows."""
    
    @pytest.fixture
    def mock_search_engine(self):
        """Create a mock search engine for testing."""
        from saidata_gen.core.interfaces import SoftwareMatch
        
        search_engine = Mock()
        search_engine.search.return_value = [
            SoftwareMatch(
                name="nginx",
                provider="apt",
                version="1.18.0",
                description="HTTP server and reverse proxy",
                score=0.95
            ),
            SoftwareMatch(
                name="nginx",
                provider="brew",
                version="1.25.3",
                description="HTTP(S) server and reverse proxy",
                score=0.90
            ),
            SoftwareMatch(
                name="apache2",
                provider="apt",
                version="2.4.41",
                description="Apache HTTP Server",
                score=0.75
            )
        ]
        return search_engine
    
    def test_software_search_workflow(self, mock_search_engine):
        """Test software search workflow."""
        # Search for software
        query = "web server"
        results = mock_search_engine.search(query)
        
        assert len(results) > 0
        assert all(isinstance(match, SoftwareMatch) for match in results)
        
        # Results should be sorted by score
        scores = [match.score for match in results]
        assert scores == sorted(scores, reverse=True)
        
        # Test filtering and ranking
        from saidata_gen.search.ranking import SearchRanker
        ranker = SearchRanker()
        
        ranked_results = ranker.rank_results(results, query)
        assert len(ranked_results) == len(results)
        
        # Test deduplication
        deduplicated_results = ranker.deduplicate_results(results)
        assert len(deduplicated_results) <= len(results)
    
    def test_package_comparison_workflow(self, mock_search_engine):
        """Test package comparison workflow."""
        # Get search results
        results = mock_search_engine.search("nginx")
        
        # Group by package name
        from saidata_gen.search.ranking import SearchRanker
        ranker = SearchRanker()
        
        grouped_results = ranker.group_by_provider(results)
        
        # Should have results from different providers
        assert len(grouped_results) > 1
        assert "apt" in grouped_results
        assert "brew" in grouped_results
        
        # Test diversity calculation
        diversity_score = ranker.calculate_diversity_score(results)
        assert 0.0 <= diversity_score <= 1.0


@pytest.mark.integration
class TestCacheAndPerformanceWorkflow:
    """Integration tests for caching and performance workflows."""
    
    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    def test_cache_workflow(self, temp_cache_dir):
        """Test caching workflow."""
        from saidata_gen.core.cache import CacheManager, FilesystemCacheStorage
        
        # Create cache manager
        storage = FilesystemCacheStorage(str(temp_cache_dir))
        cache_manager = CacheManager(storage)
        
        # Test cache operations
        test_data = {"software": "nginx", "version": "1.18.0"}
        cache_key = "test_package_nginx"
        
        # Store data
        cache_manager.put(cache_key, test_data)
        
        # Retrieve data
        cached_data = cache_manager.get(cache_key)
        assert cached_data == test_data
        
        # Test cache info
        info = cache_manager.get_info()
        assert "total_entries" in info
        assert info["total_entries"] >= 1
        
        # Test cache cleanup
        cache_manager.cleanup_expired()
        
        # Data should still be there (not expired)
        cached_data = cache_manager.get(cache_key)
        assert cached_data == test_data
    
    def test_performance_monitoring_workflow(self):
        """Test performance monitoring workflow."""
        from saidata_gen.core.performance import PerformanceMonitor
        
        monitor = PerformanceMonitor()
        
        # Test timing context
        with monitor.time_operation("test_operation"):
            # Simulate some work
            import time
            time.sleep(0.01)
        
        # Get metrics
        metrics = monitor.get_metrics()
        assert "test_operation" in metrics
        assert metrics["test_operation"]["count"] >= 1
        assert metrics["test_operation"]["total_time"] > 0
        
        # Test memory monitoring
        memory_info = monitor.get_memory_info()
        assert "current_memory_mb" in memory_info
        assert "peak_memory_mb" in memory_info


@pytest.mark.integration
class TestConfigurationWorkflow:
    """Integration tests for configuration workflows."""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary configuration directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    def test_configuration_loading_workflow(self, temp_config_dir):
        """Test configuration loading workflow."""
        # Create configuration file
        config_data = {
            "fetcher": {
                "cache_dir": str(temp_config_dir / "cache"),
                "cache_ttl": 3600,
                "concurrent_requests": 5
            },
            "generator": {
                "template_dir": str(temp_config_dir / "templates"),
                "confidence_threshold": 0.8
            },
            "rag": {
                "provider": "openai",
                "model": "gpt-3.5-turbo",
                "temperature": 0.1
            }
        }
        
        config_file = temp_config_dir / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        
        # Test loading configuration
        with open(config_file, "r") as f:
            loaded_config = yaml.safe_load(f)
        
        assert loaded_config == config_data
        
        # Test configuration validation
        assert "fetcher" in loaded_config
        assert "generator" in loaded_config
        assert "rag" in loaded_config
        
        # Test individual config sections
        fetcher_config = loaded_config["fetcher"]
        assert fetcher_config["cache_ttl"] == 3600
        assert fetcher_config["concurrent_requests"] == 5
        
        generator_config = loaded_config["generator"]
        assert generator_config["confidence_threshold"] == 0.8
        
        rag_config = loaded_config["rag"]
        assert rag_config["provider"] == "openai"
        assert rag_config["model"] == "gpt-3.5-turbo"


@pytest.mark.integration
@pytest.mark.slow
class TestEndToEndWorkflows:
    """End-to-end integration tests for complete system workflows."""
    
    @pytest.fixture
    def full_workspace(self):
        """Create a complete workspace for end-to-end testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            
            # Create directory structure
            directories = [
                "schemas", "templates", "output", "cache", "config"
            ]
            
            for directory in directories:
                (workspace / directory).mkdir()
            
            # Create comprehensive schema
            schema = {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
                "properties": {
                    "version": {"type": "string", "enum": ["0.1"]},
                    "description": {"type": "string", "minLength": 1},
                    "language": {"type": "string"},
                    "license": {"type": "string"},
                    "platforms": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "packages": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "version": {"type": "string"}
                            }
                        }
                    },
                    "urls": {
                        "type": "object",
                        "properties": {
                            "website": {"type": "string", "format": "uri"},
                            "documentation": {"type": "string", "format": "uri"},
                            "source": {"type": "string", "format": "uri"}
                        }
                    },
                    "category": {
                        "type": "object",
                        "properties": {
                            "default": {"type": "string"},
                            "sub": {"type": "string"},
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        }
                    }
                },
                "required": ["version"]
            }
            
            schema_file = workspace / "schemas" / "saidata-0.1.schema.json"
            with open(schema_file, "w") as f:
                json.dump(schema, f, indent=2)
            
            # Create comprehensive template
            template = {
                "version": "0.1",
                "category": {"default": "Software"},
                "platforms": ["linux"],
                "urls": {}
            }
            
            template_file = workspace / "templates" / "defaults.yaml"
            with open(template_file, "w") as f:
                yaml.dump(template, f)
            
            yield {
                "workspace": workspace,
                "schema_file": schema_file,
                "template_file": template_file
            }
    
    def test_complete_system_workflow(self, full_workspace):
        """Test complete system workflow from configuration to output."""
        workspace = full_workspace["workspace"]
        schema_file = full_workspace["schema_file"]
        
        # Step 1: Create comprehensive metadata
        software_packages = [
            {
                "name": "nginx",
                "description": "HTTP server and reverse proxy",
                "language": "c",
                "license": "BSD-2-Clause",
                "platforms": ["linux", "macos", "windows"],
                "packages": {
                    "apt": {"name": "nginx", "version": "1.18.0"},
                    "brew": {"name": "nginx", "version": "1.25.3"}
                },
                "urls": {
                    "website": "https://nginx.org",
                    "documentation": "https://nginx.org/docs",
                    "source": "https://github.com/nginx/nginx"
                },
                "category": {
                    "default": "Web",
                    "sub": "Server",
                    "tags": ["http", "proxy", "server"]
                }
            },
            {
                "name": "apache2",
                "description": "Apache HTTP Server",
                "language": "c",
                "license": "Apache-2.0",
                "platforms": ["linux", "macos", "windows"],
                "packages": {
                    "apt": {"name": "apache2", "version": "2.4.41"}
                },
                "urls": {
                    "website": "https://httpd.apache.org",
                    "documentation": "https://httpd.apache.org/docs/"
                },
                "category": {
                    "default": "Web",
                    "sub": "Server",
                    "tags": ["http", "server"]
                }
            }
        ]
        
        # Step 2: Generate and save metadata files
        validator = SchemaValidator(str(schema_file))
        quality_assessor = QualityAssessment()
        
        results = {}
        
        for package_data in software_packages:
            software_name = package_data["name"]
            
            # Create enhanced metadata
            metadata_dict = {"version": "0.1", **package_data}
            metadata = EnhancedSaidataMetadata.from_dict(metadata_dict)
            
            # Validate metadata
            validation_result = metadata.validate()
            
            # Assess quality
            quality_assessment = quality_assessor.assess_metadata_quality(metadata_dict)
            
            # Save to file
            output_file = workspace / "output" / f"{software_name}.yaml"
            metadata.to_yaml_file(output_file)
            
            # Validate saved file
            file_validation = validator.validate_file(str(output_file))
            
            results[software_name] = {
                "metadata": metadata,
                "validation": validation_result,
                "quality": quality_assessment,
                "file_validation": file_validation,
                "output_file": output_file
            }
        
        # Step 3: Verify all results
        for software_name, result in results.items():
            # Metadata should be valid
            assert result["validation"].valid is True, f"Metadata validation failed for {software_name}"
            
            # File should be valid
            assert result["file_validation"].valid is True, f"File validation failed for {software_name}"
            
            # Quality should be reasonable
            assert result["quality"]["overall_score"] > 0.5, f"Quality too low for {software_name}"
            
            # File should exist and be readable
            assert result["output_file"].exists(), f"Output file missing for {software_name}"
            
            # Should be able to load back
            loaded_metadata = EnhancedSaidataMetadata.from_yaml_file(result["output_file"])
            assert loaded_metadata.version == "0.1"
            assert loaded_metadata.description is not None
        
        # Step 4: Batch validation
        output_files = [str(result["output_file"]) for result in results.values()]
        batch_validation = validator.validate_batch(output_files)
        
        assert len(batch_validation.results) == len(software_packages)
        assert batch_validation.summary["valid"] == len(software_packages)
        assert batch_validation.summary["invalid"] == 0
        
        # Step 5: Quality comparison
        quality_scores = [result["quality"]["overall_score"] for result in results.values()]
        
        # All should have reasonable quality
        assert all(score > 0.5 for score in quality_scores)
        
        # Should have some variation in quality
        assert max(quality_scores) > min(quality_scores)
    
    def test_error_recovery_workflow(self, full_workspace):
        """Test error recovery in end-to-end workflows."""
        workspace = full_workspace["workspace"]
        schema_file = full_workspace["schema_file"]
        
        # Test with mixed valid and invalid data
        test_cases = [
            {
                "name": "valid_package",
                "data": {
                    "version": "0.1",
                    "description": "Valid package",
                    "packages": {"apt": {"name": "valid-pkg"}}
                },
                "should_be_valid": True
            },
            {
                "name": "invalid_version",
                "data": {
                    "version": "2.0",  # Invalid version
                    "description": "Invalid version package"
                },
                "should_be_valid": False
            },
            {
                "name": "missing_version",
                "data": {
                    "description": "Missing version package"
                },
                "should_be_valid": False
            }
        ]
        
        validator = SchemaValidator(str(schema_file))
        results = {}
        
        for test_case in test_cases:
            name = test_case["name"]
            data = test_case["data"]
            expected_valid = test_case["should_be_valid"]
            
            # Create metadata
            try:
                metadata = EnhancedSaidataMetadata.from_dict(data)
                
                # Save to file
                output_file = workspace / "output" / f"{name}.yaml"
                metadata.to_yaml_file(output_file)
                
                # Validate
                validation_result = validator.validate_file(str(output_file))
                
                results[name] = {
                    "success": True,
                    "validation": validation_result,
                    "expected_valid": expected_valid
                }
                
            except Exception as e:
                results[name] = {
                    "success": False,
                    "error": str(e),
                    "expected_valid": expected_valid
                }
        
        # Verify results match expectations
        for name, result in results.items():
            if result["expected_valid"]:
                # Should succeed and be valid
                assert result["success"] is True, f"Expected {name} to succeed"
                assert result["validation"].valid is True, f"Expected {name} to be valid"
            else:
                # Should either fail to create or be invalid
                if result["success"]:
                    assert result["validation"].valid is False, f"Expected {name} to be invalid"
                # If it failed to create, that's also acceptable for invalid data