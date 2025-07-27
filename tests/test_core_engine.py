"""
Unit tests for the core engine.
"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock

from saidata_gen.core.engine import SaidataEngine
from saidata_gen.core.interfaces import (
    GenerationOptions, BatchOptions, ValidationResult, 
    MetadataResult, BatchResult, SoftwareMatch
)
from saidata_gen.core.models import EnhancedSaidataMetadata
from tests.fixtures.sample_data import SAMPLE_SAIDATA_METADATA, EXPECTED_NGINX_METADATA


class TestSaidataEngine(unittest.TestCase):
    """Test the SaidataEngine class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.engine = SaidataEngine()
        
        # Mock dependencies
        self.mock_fetcher = Mock()
        self.mock_generator = Mock()
        self.mock_validator = Mock()
        self.mock_rag_engine = Mock()
        self.mock_search_engine = Mock()
        
        # Inject mocks
        self.engine.fetcher = self.mock_fetcher
        self.engine.generator = self.mock_generator
        self.engine.validator = self.mock_validator
        self.engine.rag_engine = self.mock_rag_engine
        self.engine.search_engine = self.mock_search_engine
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test engine initialization."""
        engine = SaidataEngine()
        self.assertIsNotNone(engine.config)
        self.assertIsNotNone(engine.cache_manager)
    
    def test_initialization_with_config(self):
        """Test engine initialization with custom config."""
        config_path = os.path.join(self.temp_dir, "config.yaml")
        with open(config_path, "w") as f:
            f.write("""
            cache:
              backend: memory
              default_ttl: 1800
            fetcher:
              concurrent_requests: 10
            """)
        
        engine = SaidataEngine(config_path=config_path)
        self.assertEqual(engine.config.cache.default_ttl, 1800)
        self.assertEqual(engine.config.fetcher.concurrent_requests, 10)
    
    def test_generate_metadata_success(self):
        """Test successful metadata generation."""
        # Setup mocks
        mock_package_info = [
            {"provider": "apt", "name": "nginx", "version": "1.18.0"},
            {"provider": "brew", "name": "nginx", "version": "1.25.3"}
        ]
        self.mock_fetcher.search_package.return_value = mock_package_info
        
        mock_metadata = EnhancedSaidataMetadata.from_dict(EXPECTED_NGINX_METADATA)
        self.mock_generator.generate_from_sources.return_value = mock_metadata
        
        mock_validation = ValidationResult(valid=True, issues=[])
        self.mock_validator.validate_data.return_value = mock_validation
        
        # Test generation
        options = GenerationOptions(providers=["apt", "brew"])
        result = self.engine.generate_metadata("nginx", options)
        
        self.assertIsInstance(result, MetadataResult)
        self.assertTrue(result.success)
        self.assertIsNotNone(result.metadata)
        self.assertEqual(result.metadata.description, EXPECTED_NGINX_METADATA["description"])
        
        # Verify mocks were called
        self.mock_fetcher.search_package.assert_called_once_with("nginx", ["apt", "brew"])
        self.mock_generator.generate_from_sources.assert_called_once()
        self.mock_validator.validate_data.assert_called_once()
    
    def test_generate_metadata_with_rag(self):
        """Test metadata generation with RAG enhancement."""
        # Setup mocks
        mock_package_info = [{"provider": "apt", "name": "nginx"}]
        self.mock_fetcher.search_package.return_value = mock_package_info
        
        mock_metadata = EnhancedSaidataMetadata.from_dict(EXPECTED_NGINX_METADATA)
        self.mock_generator.generate_from_sources.return_value = mock_metadata
        
        enhanced_metadata = mock_metadata.copy()
        enhanced_metadata.description = "Enhanced description from RAG"
        self.mock_rag_engine.enhance_metadata.return_value = enhanced_metadata
        
        mock_validation = ValidationResult(valid=True, issues=[])
        self.mock_validator.validate_data.return_value = mock_validation
        
        # Test generation with RAG
        options = GenerationOptions(use_rag=True, rag_provider="openai")
        result = self.engine.generate_metadata("nginx", options)
        
        self.assertTrue(result.success)
        self.assertEqual(result.metadata.description, "Enhanced description from RAG")
        self.mock_rag_engine.enhance_metadata.assert_called_once()
    
    def test_generate_metadata_no_packages_found(self):
        """Test metadata generation when no packages are found."""
        self.mock_fetcher.search_package.return_value = []
        
        options = GenerationOptions()
        result = self.engine.generate_metadata("nonexistent-package", options)
        
        self.assertFalse(result.success)
        self.assertIn("No packages found", result.error_message)
    
    def test_generate_metadata_validation_failure(self):
        """Test metadata generation with validation failure."""
        # Setup mocks
        mock_package_info = [{"provider": "apt", "name": "nginx"}]
        self.mock_fetcher.search_package.return_value = mock_package_info
        
        mock_metadata = EnhancedSaidataMetadata.from_dict(EXPECTED_NGINX_METADATA)
        self.mock_generator.generate_from_sources.return_value = mock_metadata
        
        mock_validation = ValidationResult(
            valid=False, 
            issues=[{"level": "ERROR", "message": "Invalid schema"}]
        )
        self.mock_validator.validate_data.return_value = mock_validation
        
        # Test generation
        options = GenerationOptions(validate_schema=True)
        result = self.engine.generate_metadata("nginx", options)
        
        self.assertFalse(result.success)
        self.assertIn("Validation failed", result.error_message)
    
    def test_validate_metadata_file(self):
        """Test metadata file validation."""
        # Create test file
        test_file = os.path.join(self.temp_dir, "test.yaml")
        with open(test_file, "w") as f:
            f.write("version: '0.1'\ndescription: Test")
        
        mock_validation = ValidationResult(valid=True, issues=[])
        self.mock_validator.validate_file.return_value = mock_validation
        
        result = self.engine.validate_metadata(test_file)
        
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.valid)
        self.mock_validator.validate_file.assert_called_once_with(test_file)
    
    def test_validate_metadata_nonexistent_file(self):
        """Test validation of non-existent file."""
        result = self.engine.validate_metadata("nonexistent.yaml")
        
        self.assertFalse(result.valid)
        self.assertIn("File not found", str(result.issues[0]))
    
    def test_batch_process_success(self):
        """Test successful batch processing."""
        software_list = ["nginx", "apache2", "mysql"]
        
        # Mock successful generation for all packages
        mock_results = []
        for software in software_list:
            mock_package_info = [{"provider": "apt", "name": software}]
            mock_metadata = EnhancedSaidataMetadata(description=f"{software} server")
            mock_result = MetadataResult(
                success=True,
                metadata=mock_metadata,
                software_name=software
            )
            mock_results.append(mock_result)
        
        with patch.object(self.engine, 'generate_metadata', side_effect=mock_results):
            options = BatchOptions(output_dir=self.temp_dir)
            result = self.engine.batch_process(software_list, options)
        
        self.assertIsInstance(result, BatchResult)
        self.assertEqual(result.total_processed, 3)
        self.assertEqual(result.successful, 3)
        self.assertEqual(result.failed, 0)
    
    def test_batch_process_partial_failure(self):
        """Test batch processing with some failures."""
        software_list = ["nginx", "nonexistent", "apache2"]
        
        # Mock mixed results with proper validation_result attributes
        mock_results = [
            MetadataResult(
                success=True, 
                software_name="nginx",
                validation_result=ValidationResult(valid=True, issues=[], file_path="")
            ),
            MetadataResult(
                success=False, 
                software_name="nonexistent", 
                error_message="Not found",
                validation_result=ValidationResult(valid=False, issues=["Not found"], file_path="")
            ),
            MetadataResult(
                success=True, 
                software_name="apache2",
                validation_result=ValidationResult(valid=True, issues=[], file_path="")
            )
        ]
        
        with patch.object(self.engine, 'generate_metadata', side_effect=mock_results):
            options = BatchOptions(output_dir=self.temp_dir, continue_on_error=True)
            result = self.engine.batch_process(software_list, options)
        
        self.assertEqual(result.total_processed, 3)
        self.assertEqual(result.successful, 2)
        self.assertEqual(result.failed, 1)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("nonexistent", result.errors[0])
    
    def test_batch_process_stop_on_error(self):
        """Test batch processing that stops on first error."""
        software_list = ["nginx", "nonexistent", "apache2"]
        
        # Mock results with early failure
        mock_results = [
            MetadataResult(success=True, software_name="nginx"),
            MetadataResult(success=False, software_name="nonexistent", error_message="Not found")
        ]
        
        with patch.object(self.engine, 'generate_metadata', side_effect=mock_results):
            options = BatchOptions(output_dir=self.temp_dir, continue_on_error=False)
            result = self.engine.batch_process(software_list, options)
        
        self.assertEqual(result.total_processed, 2)  # Should stop after failure
        self.assertEqual(result.successful, 1)
        self.assertEqual(result.failed, 1)
    
    def test_search_software(self):
        """Test software search functionality."""
        mock_matches = [
            SoftwareMatch(
                name="nginx",
                provider="apt",
                version="1.18.0",
                description="Web server",
                confidence=0.95
            ),
            SoftwareMatch(
                name="nginx",
                provider="brew", 
                version="1.25.3",
                description="HTTP server",
                confidence=0.90
            )
        ]
        self.mock_search_engine.search.return_value = mock_matches
        
        results = self.engine.search_software("nginx")
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].name, "nginx")
        self.assertEqual(results[0].provider, "apt")
        self.mock_search_engine.search.assert_called_once_with("nginx")
    
    def test_fetch_repository_data(self):
        """Test repository data fetching."""
        providers = ["apt", "brew"]
        mock_fetch_result = {
            "apt": {"status": "success", "packages_count": 1000},
            "brew": {"status": "success", "packages_count": 500}
        }
        self.mock_fetcher.fetch_repositories.return_value = mock_fetch_result
        
        result = self.engine.fetch_repository_data(providers)
        
        self.assertEqual(result["apt"]["status"], "success")
        self.assertEqual(result["brew"]["status"], "success")
        self.mock_fetcher.fetch_repositories.assert_called_once_with(providers)
    
    def test_get_supported_providers(self):
        """Test getting supported providers."""
        mock_providers = ["apt", "brew", "dnf", "npm", "pypi"]
        self.mock_fetcher.get_supported_providers.return_value = mock_providers
        
        providers = self.engine.get_supported_providers()
        
        self.assertEqual(len(providers), 5)
        self.assertIn("apt", providers)
        self.assertIn("npm", providers)
    
    def test_get_cache_info(self):
        """Test getting cache information."""
        mock_cache_info = {
            "backend": "memory",
            "size": 100,
            "hit_rate": 0.85
        }
        self.engine.cache_manager.get_info = Mock(return_value=mock_cache_info)
        
        info = self.engine.get_cache_info()
        
        self.assertEqual(info["backend"], "memory")
        self.assertEqual(info["hit_rate"], 0.85)
    
    def test_clear_cache(self):
        """Test cache clearing."""
        self.engine.cache_manager.clear = Mock()
        
        self.engine.clear_cache()
        
        self.engine.cache_manager.clear.assert_called_once()
    
    def test_context_manager(self):
        """Test using engine as context manager."""
        with SaidataEngine() as engine:
            self.assertIsNotNone(engine.config)
            self.assertIsNotNone(engine.cache_manager)
    
    @patch('saidata_gen.core.engine.logger')
    def test_error_logging(self, mock_logger):
        """Test that errors are properly logged."""
        self.mock_fetcher.search_package.side_effect = Exception("Test error")
        
        options = GenerationOptions()
        result = self.engine.generate_metadata("nginx", options)
        
        self.assertFalse(result.success)
        mock_logger.error.assert_called()
    
    def test_concurrent_generation(self):
        """Test concurrent metadata generation."""
        software_list = ["nginx", "apache2", "mysql", "postgresql"]
        
        # Mock successful generation
        def mock_generate(software, options):
            return MetadataResult(success=True, software_name=software)
        
        with patch.object(self.engine, 'generate_metadata', side_effect=mock_generate):
            options = BatchOptions(
                output_dir=self.temp_dir,
                concurrent_workers=2
            )
            result = self.engine.batch_process(software_list, options)
        
        self.assertEqual(result.successful, 4)
        self.assertEqual(result.failed, 0)


if __name__ == "__main__":
    unittest.main()