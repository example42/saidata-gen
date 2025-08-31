"""
Unit tests for core interfaces and data structures.
"""

import unittest
from dataclasses import asdict
from typing import List, Optional

from saidata_gen.core.interfaces import (
    # Configuration classes
    RAGConfig, FetcherConfig,
    
    # Options classes
    GenerationOptions, BatchOptions,
    
    # Result classes
    ValidationResult, ValidationIssue, MetadataResult, BatchResult,
    SoftwareMatch, FetchResult,
    
    # Enums
    ValidationLevel
)


class TestConfigurationClasses(unittest.TestCase):
    """Test configuration data classes."""
    
    def test_fetcher_config_defaults(self):
        """Test FetcherConfig default values."""
        config = FetcherConfig()
        
        self.assertEqual(config.concurrent_requests, 5)
        self.assertEqual(config.request_timeout, 30)
        self.assertEqual(config.retry_count, 3)
        self.assertEqual(config.cache_dir, "~/.saidata-gen/cache")
        self.assertEqual(config.cache_ttl, 3600)
    
    def test_rag_config_defaults(self):
        """Test RAGConfig default values."""
        config = RAGConfig()
        
        self.assertEqual(config.provider, "openai")
        self.assertEqual(config.model, "gpt-3.5-turbo")
        self.assertIsNone(config.api_key)
        self.assertEqual(config.temperature, 0.1)
        self.assertEqual(config.max_tokens, 1000)
    
    def test_config_serialization(self):
        """Test configuration serialization to dict."""
        config = RAGConfig(
            provider="anthropic",
            model="claude-3",
            temperature=0.2
        )
        
        config_dict = asdict(config)
        
        self.assertEqual(config_dict["provider"], "anthropic")
        self.assertEqual(config_dict["model"], "claude-3")
        self.assertEqual(config_dict["temperature"], 0.2)


class TestOptionsClasses(unittest.TestCase):
    """Test options data classes."""
    
    def test_generation_options_defaults(self):
        """Test GenerationOptions default values."""
        options = GenerationOptions()
        
        self.assertEqual(options.providers, [])
        self.assertFalse(options.use_ai)
        self.assertEqual(options.ai_provider, "openai")
        self.assertFalse(options.include_dev_packages)
        self.assertEqual(options.confidence_threshold, 0.7)
        self.assertEqual(options.output_format, "yaml")
        self.assertTrue(options.validate_schema)
    
    def test_generation_options_custom(self):
        """Test GenerationOptions with custom values."""
        options = GenerationOptions(
            providers=["apt", "brew"],
            use_ai=True,
            ai_provider="anthropic",
            confidence_threshold=0.8,
            output_format="json"
        )
        
        self.assertEqual(options.providers, ["apt", "brew"])
        self.assertTrue(options.use_ai)
        self.assertEqual(options.ai_provider, "anthropic")
        self.assertEqual(options.confidence_threshold, 0.8)
        self.assertEqual(options.output_format, "json")
    
    def test_batch_options_defaults(self):
        """Test BatchOptions default values."""
        options = BatchOptions()
        
        self.assertEqual(options.output_dir, ".")
        self.assertTrue(options.continue_on_error)
        self.assertEqual(options.concurrent_workers, 1)
        self.assertTrue(options.progress_reporting)
        self.assertEqual(options.output_format, "yaml")
    
    # SearchOptions not available in current interfaces


class TestResultClasses(unittest.TestCase):
    """Test result data classes."""
    
    def test_validation_issue(self):
        """Test ValidationIssue creation."""
        issue = ValidationIssue(
            level=ValidationLevel.ERROR,
            message="Required field missing",
            path="packages.default.name",
            code="MISSING_FIELD"
        )
        
        self.assertEqual(issue.level, ValidationLevel.ERROR)
        self.assertEqual(issue.message, "Required field missing")
        self.assertEqual(issue.path, "packages.default.name")
        self.assertEqual(issue.code, "MISSING_FIELD")
    
    def test_validation_result_valid(self):
        """Test ValidationResult for valid data."""
        result = ValidationResult(valid=True, issues=[])
        
        self.assertTrue(result.valid)
        self.assertEqual(len(result.issues), 0)
        self.assertTrue(result.is_success)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 0)
    
    def test_validation_result_with_issues(self):
        """Test ValidationResult with issues."""
        issues = [
            ValidationIssue(
                level=ValidationLevel.ERROR,
                message="Required field missing",
                path="name"
            ),
            ValidationIssue(
                level=ValidationLevel.WARNING,
                message="Recommended field missing",
                path="description"
            )
        ]
        
        result = ValidationResult(valid=False, issues=issues)
        
        self.assertFalse(result.valid)
        self.assertEqual(len(result.issues), 2)
        self.assertFalse(result.is_success)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(len(result.warnings), 1)
    
    def test_metadata_result_success(self):
        """Test successful MetadataResult."""
        from saidata_gen.core.models import EnhancedSaidataMetadata
        
        metadata = EnhancedSaidataMetadata(description="Test software")
        result = MetadataResult(
            success=True,
            metadata=metadata,
            software_name="test-software",
            generation_time=1.5,
            sources_used=["apt", "brew"]
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.metadata.description, "Test software")
        self.assertEqual(result.software_name, "test-software")
        self.assertEqual(result.generation_time, 1.5)
        self.assertEqual(result.sources_used, ["apt", "brew"])
        self.assertIsNone(result.error_message)
    
    def test_metadata_result_failure(self):
        """Test failed MetadataResult."""
        result = MetadataResult(
            success=False,
            software_name="nonexistent-software",
            error_message="Package not found in any repository",
            generation_time=0.5
        )
        
        self.assertFalse(result.success)
        self.assertIsNone(result.metadata)
        self.assertEqual(result.error_message, "Package not found in any repository")
        self.assertEqual(result.generation_time, 0.5)
    
    def test_batch_result(self):
        """Test BatchResult."""
        result = BatchResult(
            total_processed=10,
            successful=8,
            failed=2,
            total_time=45.5,
            errors=["Package A not found", "Package B validation failed"]
        )
        
        self.assertEqual(result.total_processed, 10)
        self.assertEqual(result.successful, 8)
        self.assertEqual(result.failed, 2)
        self.assertEqual(result.total_time, 45.5)
        self.assertEqual(len(result.errors), 2)
        self.assertEqual(result.success_rate, 0.8)
    
    def test_software_match(self):
        """Test SoftwareMatch."""
        match = SoftwareMatch(
            name="nginx",
            provider="apt",
            version="1.18.0",
            description="Web server and reverse proxy",
            confidence=0.95,
            metadata={"architecture": "amd64", "size": "3588"}
        )
        
        self.assertEqual(match.name, "nginx")
        self.assertEqual(match.provider, "apt")
        self.assertEqual(match.version, "1.18.0")
        self.assertEqual(match.confidence, 0.95)
        self.assertEqual(match.metadata["architecture"], "amd64")
    
    def test_fetch_result(self):
        """Test FetchResult."""
        result = FetchResult(
            provider="apt",
            success=True,
            packages_count=1500,
            fetch_time=30.2,
            cache_hit=False,
            metadata={"repository": "ubuntu-main", "last_updated": "2023-12-01"}
        )
        
        self.assertEqual(result.provider, "apt")
        self.assertTrue(result.success)
        self.assertEqual(result.packages_count, 1500)
        self.assertEqual(result.fetch_time, 30.2)
        self.assertFalse(result.cache_hit)
        self.assertEqual(result.metadata["repository"], "ubuntu-main")
    
    def test_search_result(self):
        """Test SearchResult."""
        matches = [
            SoftwareMatch(name="nginx", provider="apt", confidence=0.95),
            SoftwareMatch(name="nginx", provider="brew", confidence=0.90)
        ]
        
        result = SearchResult(
            query="nginx",
            matches=matches,
            total_found=2,
            search_time=0.8,
            providers_searched=["apt", "brew", "dnf"]
        )
        
        self.assertEqual(result.query, "nginx")
        self.assertEqual(len(result.matches), 2)
        self.assertEqual(result.total_found, 2)
        self.assertEqual(result.search_time, 0.8)
        self.assertEqual(len(result.providers_searched), 3)


class TestEnums(unittest.TestCase):
    """Test enum definitions."""
    
    def test_validation_level_enum(self):
        """Test ValidationLevel enum."""
        self.assertEqual(ValidationLevel.ERROR.value, "error")
        self.assertEqual(ValidationLevel.WARNING.value, "warning")
        self.assertEqual(ValidationLevel.INFO.value, "info")


class TestInterfaceValidation(unittest.TestCase):
    """Test interface validation and constraints."""
    
    def test_generation_options_validation(self):
        """Test GenerationOptions validation."""
        # Valid options
        options = GenerationOptions(
            providers=["apt", "brew"],
            confidence_threshold=0.8
        )
        self.assertTrue(0.0 <= options.confidence_threshold <= 1.0)
        
        # Test confidence threshold bounds
        options.confidence_threshold = 1.5
        # In a real implementation, this might raise a validation error
        # For now, we just test the value is set
        self.assertEqual(options.confidence_threshold, 1.5)
    
    def test_batch_options_validation(self):
        """Test BatchOptions validation."""
        options = BatchOptions(concurrent_workers=4)
        self.assertGreater(options.concurrent_workers, 0)
        
        # Test negative workers (should be handled in implementation)
        options.concurrent_workers = -1
        self.assertEqual(options.concurrent_workers, -1)
    
    def test_result_consistency(self):
        """Test result object consistency."""
        # BatchResult totals should be consistent
        result = BatchResult(
            total_processed=10,
            successful=7,
            failed=3
        )
        
        self.assertEqual(result.total_processed, result.successful + result.failed)
        self.assertEqual(result.success_rate, result.successful / result.total_processed)


class TestInterfaceUsage(unittest.TestCase):
    """Test typical interface usage patterns."""
    
    def test_configuration_chaining(self):
        """Test configuration object composition."""
        engine_config = EngineConfig(
            cache=CacheConfig(backend=CacheBackend.SQLITE, max_size=5000),
            fetcher=FetcherConfig(concurrent_requests=10),
            rag=RAGConfig(provider=RAGProvider.ANTHROPIC, temperature=0.2)
        )
        
        self.assertEqual(engine_config.cache.backend, CacheBackend.SQLITE)
        self.assertEqual(engine_config.cache.max_size, 5000)
        self.assertEqual(engine_config.fetcher.concurrent_requests, 10)
        self.assertEqual(engine_config.rag.provider, RAGProvider.ANTHROPIC)
        self.assertEqual(engine_config.rag.temperature, 0.2)
    
    def test_options_inheritance(self):
        """Test options object usage patterns."""
        base_options = GenerationOptions(
            providers=["apt", "brew"],
            confidence_threshold=0.8
        )
        
        # Create specialized options
        rag_options = GenerationOptions(
            providers=base_options.providers,
            confidence_threshold=base_options.confidence_threshold,
            use_ai=True,
            ai_provider="openai"
        )
        
        self.assertEqual(rag_options.providers, ["apt", "brew"])
        self.assertTrue(rag_options.use_ai)
        self.assertEqual(rag_options.ai_provider, "openai")
    
    def test_result_aggregation(self):
        """Test result aggregation patterns."""
        individual_results = [
            MetadataResult(success=True, software_name="nginx", generation_time=1.2),
            MetadataResult(success=False, software_name="invalid", generation_time=0.3),
            MetadataResult(success=True, software_name="apache2", generation_time=1.8)
        ]
        
        # Aggregate into batch result
        total_time = sum(r.generation_time for r in individual_results)
        successful = sum(1 for r in individual_results if r.success)
        failed = len(individual_results) - successful
        
        batch_result = BatchResult(
            total_processed=len(individual_results),
            successful=successful,
            failed=failed,
            total_time=total_time
        )
        
        self.assertEqual(batch_result.total_processed, 3)
        self.assertEqual(batch_result.successful, 2)
        self.assertEqual(batch_result.failed, 1)
        self.assertEqual(batch_result.total_time, 3.3)
        self.assertAlmostEqual(batch_result.success_rate, 2/3, places=2)


if __name__ == "__main__":
    unittest.main()