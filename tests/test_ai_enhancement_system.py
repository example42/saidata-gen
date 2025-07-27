"""
Unit tests for AI enhancement system.

This module contains comprehensive tests for the AI enhancement system including
AIMetadataEnhancer, MetadataGenerator AI integration, and related functionality.
"""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

from saidata_gen.ai.enhancer import (
    AIMetadataEnhancer, AIEnhancementRequest, AIEnhancementResult,
    AIProviderConfig, APIKeyManager, RateLimiter, ResponseValidator
)
from saidata_gen.generator.core import MetadataGenerator
from saidata_gen.core.interfaces import PackageInfo, MetadataResult
from saidata_gen.rag.engine import RAGEngine, EnhancementResult
from saidata_gen.rag.exceptions import RAGError, LLMProviderError, APIKeyError, RateLimitError


class TestAIMetadataEnhancer(unittest.TestCase):
    """Test cases for AIMetadataEnhancer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock RAG engine
        self.mock_rag_engine = Mock(spec=RAGEngine)
        self.mock_enhancement_result = EnhancementResult(
            enhanced_data={
                "description": "AI-generated description",
                "urls": {
                    "website": "https://example.com",
                    "documentation": "https://docs.example.com"
                },
                "category": {
                    "default": "development",
                    "sub": "web"
                }
            },
            confidence_scores={
                "description": 0.9,
                "urls.website": 0.8,
                "category.default": 0.85
            },
            sources=["openai-gpt-3.5-turbo"],
            metadata={"processing_time": 1.5}
        )
        self.mock_rag_engine.enhance_metadata.return_value = self.mock_enhancement_result
        
        # Create test configuration
        self.test_config = AIProviderConfig(
            provider="openai",
            model="gpt-3.5-turbo",
            api_key="test-api-key",
            temperature=0.1,
            max_tokens=1000,
            max_retries=2,
            retry_delay=0.1  # Short delay for tests
        )
        
        # Create enhancer with test config
        self.enhancer = AIMetadataEnhancer(provider="openai", config=self.test_config)
        
        # Mock the RAG engine creation
        with patch.object(self.enhancer, '_get_rag_engine', return_value=self.mock_rag_engine):
            pass
    
    def test_initialization(self):
        """Test AIMetadataEnhancer initialization."""
        # Test with default config
        enhancer = AIMetadataEnhancer(provider="openai")
        self.assertEqual(enhancer.provider, "openai")
        self.assertEqual(enhancer.config.provider, "openai")
        self.assertEqual(enhancer.config.model, "gpt-3.5-turbo")
        
        # Test with custom config
        custom_config = AIProviderConfig(
            provider="anthropic",
            model="claude-3-haiku-20240307",
            api_key="test-key"
        )
        enhancer = AIMetadataEnhancer(provider="anthropic", config=custom_config)
        self.assertEqual(enhancer.provider, "anthropic")
        self.assertEqual(enhancer.config.model, "claude-3-haiku-20240307")
    
    def test_get_missing_fields(self):
        """Test identification of missing fields."""
        # Test metadata with missing fields
        metadata = {
            "version": "0.1",
            "packages": {
                "default": {
                    "name": "nginx"
                }
            },
            "urls": {
                "website": None,
                "documentation": ""
            },
            "category": {
                "default": None
            }
        }
        
        missing_fields = self.enhancer.get_missing_fields(metadata)
        
        # Should identify missing fields
        expected_missing = [
            "description",
            "license", 
            "urls.website",
            "urls.source",
            "urls.documentation",
            "urls.support",
            "urls.download",
            "urls.changelog",
            "urls.icon",
            "category.default",
            "category.sub",
            "category.tags",
            "platforms",
            "language"
        ]
        
        for field in expected_missing:
            self.assertIn(field, missing_fields)
    
    def test_get_missing_fields_complete_metadata(self):
        """Test with complete metadata (no missing fields)."""
        complete_metadata = {
            "description": "Web server",
            "license": "BSD-2-Clause",
            "urls": {
                "website": "https://nginx.org",
                "source": "https://github.com/nginx/nginx",
                "documentation": "https://nginx.org/docs",
                "support": "https://nginx.org/support",
                "download": "https://nginx.org/download",
                "changelog": "https://nginx.org/changes",
                "icon": "https://nginx.org/icon.png"
            },
            "category": {
                "default": "server",
                "sub": "web",
                "tags": ["http", "proxy"]
            },
            "platforms": ["linux", "windows"],
            "language": "C"
        }
        
        missing_fields = self.enhancer.get_missing_fields(complete_metadata)
        self.assertEqual(missing_fields, [])
    
    @patch.object(AIMetadataEnhancer, '_get_rag_engine')
    def test_enhance_metadata_success(self, mock_get_rag_engine):
        """Test successful metadata enhancement."""
        mock_get_rag_engine.return_value = self.mock_rag_engine
        
        base_metadata = {
            "version": "0.1",
            "packages": {
                "default": {
                    "name": "nginx"
                }
            }
        }
        
        with patch.object(self.enhancer, 'is_available', return_value=True):
            result = self.enhancer.enhance_metadata("nginx", base_metadata)
        
        # Verify result
        self.assertTrue(result.success)
        self.assertIsNone(result.error_message)
        self.assertEqual(result.enhanced_metadata["description"], "AI-generated description")
        self.assertEqual(result.enhanced_metadata["urls"]["website"], "https://example.com")
        self.assertIn("description", result.confidence_scores)
        self.assertIn("openai-gpt-3.5-turbo", result.sources_used)
        self.assertGreater(result.processing_time, 0)
        
        # Verify RAG engine was called
        self.mock_rag_engine.enhance_metadata.assert_called_once()
    
    @patch.object(AIMetadataEnhancer, '_get_rag_engine')
    def test_enhance_metadata_provider_unavailable(self, mock_get_rag_engine):
        """Test enhancement when provider is unavailable."""
        base_metadata = {"version": "0.1"}
        
        with patch.object(self.enhancer, 'is_available', return_value=False):
            result = self.enhancer.enhance_metadata("nginx", base_metadata)
        
        # Should return failure result
        self.assertFalse(result.success)
        self.assertIn("not available", result.error_message)
        self.assertEqual(result.enhanced_metadata, base_metadata)
        self.assertEqual(result.confidence_scores, {})
        
        # RAG engine should not be called
        mock_get_rag_engine.assert_not_called()
    
    @patch.object(AIMetadataEnhancer, '_get_rag_engine')
    def test_enhance_metadata_with_retry_on_rate_limit(self, mock_get_rag_engine):
        """Test enhancement with retry on rate limit error."""
        mock_get_rag_engine.return_value = self.mock_rag_engine
        
        # First call raises rate limit error, second succeeds
        self.mock_rag_engine.enhance_metadata.side_effect = [
            RateLimitError("Rate limit exceeded"),
            self.mock_enhancement_result
        ]
        
        base_metadata = {"version": "0.1"}
        
        with patch.object(self.enhancer, 'is_available', return_value=True):
            with patch.object(self.enhancer.rate_limiter, 'can_make_request', return_value=(True, None)):
                result = self.enhancer.enhance_metadata("nginx", base_metadata)
        
        # Should succeed after retry
        self.assertTrue(result.success)
        self.assertEqual(self.mock_rag_engine.enhance_metadata.call_count, 2)
    
    @patch.object(AIMetadataEnhancer, '_get_rag_engine')
    def test_enhance_metadata_max_retries_exceeded(self, mock_get_rag_engine):
        """Test enhancement when max retries are exceeded."""
        mock_get_rag_engine.return_value = self.mock_rag_engine
        
        # All calls raise errors
        self.mock_rag_engine.enhance_metadata.side_effect = RAGError("Persistent error")
        
        base_metadata = {"version": "0.1"}
        
        with patch.object(self.enhancer, 'is_available', return_value=True):
            with patch.object(self.enhancer.rate_limiter, 'can_make_request', return_value=(True, None)):
                result = self.enhancer.enhance_metadata("nginx", base_metadata)
        
        # Should fail after max retries
        self.assertFalse(result.success)
        self.assertIn("failed after", result.error_message)
        self.assertEqual(self.mock_rag_engine.enhance_metadata.call_count, 3)  # max_retries + 1
    
    def test_is_field_missing(self):
        """Test field missing detection."""
        metadata = {
            "description": "Valid description",
            "license": None,
            "urls": {
                "website": "https://example.com",
                "source": "",
                "documentation": "   "  # Whitespace only
            },
            "category": {
                "tags": []  # Empty list
            }
        }
        
        # Test various missing field scenarios
        self.assertFalse(self.enhancer._is_field_missing(metadata, "description"))  # Present and valid
        self.assertTrue(self.enhancer._is_field_missing(metadata, "license"))  # None
        self.assertFalse(self.enhancer._is_field_missing(metadata, "urls.website"))  # Present and valid
        self.assertTrue(self.enhancer._is_field_missing(metadata, "urls.source"))  # Empty string
        self.assertTrue(self.enhancer._is_field_missing(metadata, "urls.documentation"))  # Whitespace only
        self.assertTrue(self.enhancer._is_field_missing(metadata, "urls.missing"))  # Not present
        self.assertTrue(self.enhancer._is_field_missing(metadata, "category.tags"))  # Empty list
        self.assertTrue(self.enhancer._is_field_missing(metadata, "missing.field"))  # Path doesn't exist
    
    def test_set_field_value(self):
        """Test setting field values using dot notation."""
        metadata = {}
        
        # Test setting nested values
        self.enhancer._set_field_value(metadata, "description", "Test description")
        self.enhancer._set_field_value(metadata, "urls.website", "https://example.com")
        self.enhancer._set_field_value(metadata, "category.default", "development")
        
        # Verify values were set correctly
        self.assertEqual(metadata["description"], "Test description")
        self.assertEqual(metadata["urls"]["website"], "https://example.com")
        self.assertEqual(metadata["category"]["default"], "development")
    
    def test_estimate_tokens(self):
        """Test token estimation."""
        metadata = {
            "description": "A web server",
            "urls": {"website": "https://example.com"}
        }
        enhancement_types = ["description", "categorization"]
        
        estimated_tokens = self.enhancer._estimate_tokens(metadata, enhancement_types)
        
        # Should return a reasonable estimate
        self.assertIsInstance(estimated_tokens, int)
        self.assertGreater(estimated_tokens, 0)
        self.assertLess(estimated_tokens, 10000)  # Reasonable upper bound


class TestAPIKeyManager(unittest.TestCase):
    """Test cases for APIKeyManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.api_key_manager = APIKeyManager(config_dir=self.temp_dir.name)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
    
    def test_store_and_get_api_key(self):
        """Test storing and retrieving API keys."""
        # Store API key
        self.api_key_manager.store_api_key("openai", "test-api-key-123")
        
        # Retrieve API key
        retrieved_key = self.api_key_manager.get_api_key("openai")
        self.assertEqual(retrieved_key, "test-api-key-123")
    
    def test_get_api_key_from_environment(self):
        """Test getting API key from environment variable."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-api-key"}):
            key = self.api_key_manager.get_api_key("openai")
            self.assertEqual(key, "env-api-key")
    
    def test_get_api_key_custom_env_var(self):
        """Test getting API key from custom environment variable."""
        with patch.dict(os.environ, {"CUSTOM_API_KEY": "custom-env-key"}):
            key = self.api_key_manager.get_api_key("openai", env_var="CUSTOM_API_KEY")
            self.assertEqual(key, "custom-env-key")
    
    def test_remove_api_key(self):
        """Test removing stored API keys."""
        # Store and verify key exists
        self.api_key_manager.store_api_key("openai", "test-key")
        self.assertIsNotNone(self.api_key_manager.get_api_key("openai"))
        
        # Remove key
        removed = self.api_key_manager.remove_api_key("openai")
        self.assertTrue(removed)
        
        # Verify key is gone
        self.assertIsNone(self.api_key_manager.get_api_key("openai"))
        
        # Try to remove non-existent key
        removed = self.api_key_manager.remove_api_key("nonexistent")
        self.assertFalse(removed)
    
    def test_list_stored_providers(self):
        """Test listing stored providers."""
        # Initially empty
        providers = self.api_key_manager.list_stored_providers()
        self.assertEqual(providers, [])
        
        # Store some keys
        self.api_key_manager.store_api_key("openai", "key1")
        self.api_key_manager.store_api_key("anthropic", "key2")
        
        # List providers
        providers = self.api_key_manager.list_stored_providers()
        self.assertIn("openai", providers)
        self.assertIn("anthropic", providers)
        self.assertEqual(len(providers), 2)


class TestRateLimiter(unittest.TestCase):
    """Test cases for RateLimiter class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.rate_limiter = RateLimiter(requests_per_minute=3, tokens_per_minute=1000)
    
    def test_can_make_request_within_limits(self):
        """Test request allowance within rate limits."""
        # Should allow initial requests
        can_proceed, wait_time = self.rate_limiter.can_make_request(100)
        self.assertTrue(can_proceed)
        self.assertIsNone(wait_time)
        
        # Record request and try again
        self.rate_limiter.record_request(100)
        can_proceed, wait_time = self.rate_limiter.can_make_request(100)
        self.assertTrue(can_proceed)
        self.assertIsNone(wait_time)
    
    def test_request_rate_limit_exceeded(self):
        """Test request rate limit enforcement."""
        # Make maximum allowed requests
        for _ in range(3):
            can_proceed, wait_time = self.rate_limiter.can_make_request(100)
            self.assertTrue(can_proceed)
            self.rate_limiter.record_request(100)
        
        # Next request should be blocked
        can_proceed, wait_time = self.rate_limiter.can_make_request(100)
        self.assertFalse(can_proceed)
        self.assertIsNotNone(wait_time)
        self.assertGreater(wait_time, 0)
    
    def test_token_rate_limit_exceeded(self):
        """Test token rate limit enforcement."""
        # Try to make request that exceeds token limit
        can_proceed, wait_time = self.rate_limiter.can_make_request(1500)  # Exceeds 1000 limit
        self.assertFalse(can_proceed)
        self.assertIsNotNone(wait_time)
    
    def test_rate_limit_reset_after_time(self):
        """Test that rate limits reset after time window."""
        # Fill up request limit
        for _ in range(3):
            self.rate_limiter.record_request(100)
        
        # Should be blocked
        can_proceed, wait_time = self.rate_limiter.can_make_request(100)
        self.assertFalse(can_proceed)
        
        # Mock time passage (simulate 61 seconds later)
        with patch('time.time', return_value=time.time() + 61):
            can_proceed, wait_time = self.rate_limiter.can_make_request(100)
            self.assertTrue(can_proceed)
            self.assertIsNone(wait_time)


class TestResponseValidator(unittest.TestCase):
    """Test cases for ResponseValidator class."""
    
    def test_validate_json_response_valid(self):
        """Test validation of valid JSON responses."""
        valid_json = '{"description": "Test software", "category": "development"}'
        is_valid, data, error = ResponseValidator.validate_json_response(valid_json)
        
        self.assertTrue(is_valid)
        self.assertEqual(data["description"], "Test software")
        self.assertIsNone(error)
    
    def test_validate_json_response_invalid(self):
        """Test validation of invalid JSON responses."""
        invalid_json = '{"description": "Test software", "category":}'  # Missing value
        is_valid, data, error = ResponseValidator.validate_json_response(invalid_json)
        
        self.assertFalse(is_valid)
        self.assertIsNone(data)
        self.assertIn("Invalid JSON", error)
    
    def test_validate_description_valid(self):
        """Test validation of valid descriptions."""
        valid_descriptions = [
            "A powerful web server for high-performance applications",
            "Database management system with ACID compliance",
            "Cross-platform development framework for mobile apps"
        ]
        
        for description in valid_descriptions:
            is_valid, error = ResponseValidator.validate_description(description)
            self.assertTrue(is_valid, f"Description should be valid: {description}")
            self.assertIsNone(error)
    
    def test_validate_description_invalid(self):
        """Test validation of invalid descriptions."""
        invalid_descriptions = [
            "",  # Empty
            "   ",  # Whitespace only
            "Short",  # Too short
            "I cannot provide information about this software",  # AI artifact
            "As an AI, I don't have specific details",  # AI artifact
            "x" * 1001  # Too long
        ]
        
        for description in invalid_descriptions:
            is_valid, error = ResponseValidator.validate_description(description)
            self.assertFalse(is_valid, f"Description should be invalid: {description}")
            self.assertIsNotNone(error)
    
    def test_validate_category_valid(self):
        """Test validation of valid category data."""
        valid_categories = [
            {"default": "development"},
            {"default": "system", "sub": "server"},
            {"default": "web", "confidence": 0.9}
        ]
        
        for category in valid_categories:
            is_valid, error = ResponseValidator.validate_category(category)
            self.assertTrue(is_valid, f"Category should be valid: {category}")
            self.assertIsNone(error)
    
    def test_validate_category_invalid(self):
        """Test validation of invalid category data."""
        invalid_categories = [
            "not a dict",  # Not a dictionary
            {},  # Missing default
            {"default": ""},  # Empty default
            {"default": "development", "confidence": 1.5}  # Invalid confidence
        ]
        
        for category in invalid_categories:
            is_valid, error = ResponseValidator.validate_category(category)
            self.assertFalse(is_valid, f"Category should be invalid: {category}")
            self.assertIsNotNone(error)
    
    def test_validate_field_completion_valid(self):
        """Test validation of valid field completion data."""
        valid_field_data = [
            {"website": "https://example.com"},
            {"platforms": ["linux", "windows"]},
            {"website": "https://example.com", "platforms": ["macos"]}
        ]
        
        for field_data in valid_field_data:
            is_valid, error = ResponseValidator.validate_field_completion(field_data)
            self.assertTrue(is_valid, f"Field data should be valid: {field_data}")
            self.assertIsNone(error)
    
    def test_validate_field_completion_invalid(self):
        """Test validation of invalid field completion data."""
        invalid_field_data = [
            "not a dict",  # Not a dictionary
            {"website": 123},  # Invalid URL type
            {"website": "not-a-url"},  # Invalid URL format
            {"platforms": "not a list"}  # Invalid platforms type
        ]
        
        for field_data in invalid_field_data:
            is_valid, error = ResponseValidator.validate_field_completion(field_data)
            self.assertFalse(is_valid, f"Field data should be invalid: {field_data}")
            self.assertIsNotNone(error)


class TestMetadataGeneratorAIIntegration(unittest.TestCase):
    """Test cases for MetadataGenerator AI integration methods."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.generator = MetadataGenerator()
        
        # Mock AI enhancer
        self.mock_ai_enhancer = Mock(spec=AIMetadataEnhancer)
        self.mock_ai_enhancer.provider = "openai"
        self.mock_ai_enhancer.is_available.return_value = True
        
        # Mock enhancement result
        self.mock_ai_result = AIEnhancementResult(
            enhanced_metadata={
                "description": "AI-generated description",
                "urls": {
                    "website": "https://ai-generated.com",
                    "documentation": "https://ai-docs.com"
                },
                "category": {
                    "default": "development"
                }
            },
            confidence_scores={
                "description": 0.8,
                "urls.website": 0.7
            },
            sources_used=["openai-gpt-3.5-turbo"],
            processing_time=1.2,
            success=True
        )
        self.mock_ai_enhancer.enhance_metadata.return_value = self.mock_ai_result
        
        # Mock base metadata generation
        self.mock_base_result = Mock(spec=MetadataResult)
        self.mock_base_result.metadata.to_dict.return_value = {
            "version": "0.1",
            "packages": {
                "default": {
                    "name": "nginx",
                    "version": "1.18.0"
                }
            },
            "urls": {
                "website": "https://nginx.org"  # Repository data (should take precedence)
            }
        }
        self.mock_base_result.confidence_scores = {"packages.default.name": 1.0}
    
    @patch.object(MetadataGenerator, 'generate_from_sources')
    @patch('saidata_gen.generator.core.AIMetadataEnhancer')
    def test_generate_with_ai_enhancement_success(self, mock_ai_enhancer_class, mock_generate_from_sources):
        """Test successful AI-enhanced metadata generation."""
        # Setup mocks
        mock_generate_from_sources.return_value = self.mock_base_result
        mock_ai_enhancer_class.return_value = self.mock_ai_enhancer
        
        # Test data
        sources = [PackageInfo(name="nginx", version="1.18.0", provider="apt")]
        
        # Call method
        result = self.generator.generate_with_ai_enhancement(
            software_name="nginx",
            sources=sources,
            ai_provider="openai"
        )
        
        # Verify AI enhancer was created and called
        mock_ai_enhancer_class.assert_called_once_with(provider="openai")
        self.mock_ai_enhancer.enhance_metadata.assert_called_once()
        
        # Verify base generation was called
        mock_generate_from_sources.assert_called_once_with("nginx", sources, None)
    
    @patch.object(MetadataGenerator, 'generate_from_sources')
    @patch('saidata_gen.generator.core.AIMetadataEnhancer')
    def test_generate_with_ai_enhancement_provider_unavailable(self, mock_ai_enhancer_class, mock_generate_from_sources):
        """Test AI enhancement when provider is unavailable."""
        # Setup mocks
        mock_generate_from_sources.return_value = self.mock_base_result
        self.mock_ai_enhancer.is_available.return_value = False
        mock_ai_enhancer_class.return_value = self.mock_ai_enhancer
        
        sources = [PackageInfo(name="nginx", version="1.18.0", provider="apt")]
        
        # Call method
        result = self.generator.generate_with_ai_enhancement(
            software_name="nginx",
            sources=sources,
            ai_provider="openai"
        )
        
        # Should return base result without AI enhancement
        self.assertEqual(result, self.mock_base_result)
        self.mock_ai_enhancer.enhance_metadata.assert_not_called()
    
    @patch.object(MetadataGenerator, 'generate_from_sources')
    @patch('saidata_gen.generator.core.AIMetadataEnhancer')
    def test_generate_with_ai_enhancement_ai_failure(self, mock_ai_enhancer_class, mock_generate_from_sources):
        """Test AI enhancement when AI enhancement fails."""
        # Setup mocks
        mock_generate_from_sources.return_value = self.mock_base_result
        failed_ai_result = AIEnhancementResult(
            enhanced_metadata={},
            confidence_scores={},
            sources_used=[],
            processing_time=0.5,
            success=False,
            error_message="AI service unavailable"
        )
        self.mock_ai_enhancer.enhance_metadata.return_value = failed_ai_result
        mock_ai_enhancer_class.return_value = self.mock_ai_enhancer
        
        sources = [PackageInfo(name="nginx", version="1.18.0", provider="apt")]
        
        # Call method
        result = self.generator.generate_with_ai_enhancement(
            software_name="nginx",
            sources=sources,
            ai_provider="openai"
        )
        
        # Should return base result when AI fails
        self.assertEqual(result, self.mock_base_result)
    
    def test_merge_ai_with_repository_data(self):
        """Test merging AI data with repository data."""
        repository_data = {
            "version": "0.1",
            "packages": {
                "default": {
                    "name": "nginx",
                    "version": "1.18.0"
                }
            },
            "urls": {
                "website": "https://nginx.org"  # Repository data
            },
            "description": "Official repository description"
        }
        
        ai_data = {
            "description": "AI-generated description",  # Should be overridden
            "urls": {
                "website": "https://ai-generated.com",  # Should be overridden
                "documentation": "https://ai-docs.com"  # Should be kept
            },
            "category": {
                "default": "web-server"  # Should be kept (not in repository data)
            }
        }
        
        merged = self.generator.merge_ai_with_repository_data(repository_data, ai_data)
        
        # Repository data should take precedence
        self.assertEqual(merged["description"], "Official repository description")
        self.assertEqual(merged["urls"]["website"], "https://nginx.org")
        
        # AI data should fill gaps
        self.assertEqual(merged["urls"]["documentation"], "https://ai-docs.com")
        self.assertEqual(merged["category"]["default"], "web-server")
        
        # Repository data should be preserved
        self.assertEqual(merged["packages"]["default"]["name"], "nginx")
        self.assertEqual(merged["packages"]["default"]["version"], "1.18.0")
    
    def test_deep_merge_with_precedence_repository_precedence(self):
        """Test deep merge with repository precedence."""
        base = {
            "urls": {
                "website": "https://ai-generated.com",
                "documentation": "https://ai-docs.com"
            },
            "category": {
                "default": "ai-category",
                "tags": ["ai-tag"]
            }
        }
        
        overlay = {
            "urls": {
                "website": "https://official.com",  # Should override
                "source": "https://github.com/official"  # Should be added
            },
            "category": {
                "default": "official-category",  # Should override
                "sub": "official-sub"  # Should be added
            }
        }
        
        result = self.generator._deep_merge_with_precedence(
            base, overlay, repository_precedence=True
        )
        
        # Repository (overlay) data should take precedence
        self.assertEqual(result["urls"]["website"], "https://official.com")
        self.assertEqual(result["category"]["default"], "official-category")
        
        # AI (base) data should be preserved where no conflict
        self.assertEqual(result["urls"]["documentation"], "https://ai-docs.com")
        self.assertEqual(result["category"]["tags"], ["ai-tag"])
        
        # New repository data should be added
        self.assertEqual(result["urls"]["source"], "https://github.com/official")
        self.assertEqual(result["category"]["sub"], "official-sub")
    
    def test_deep_merge_with_precedence_list_handling(self):
        """Test deep merge list handling with precedence."""
        base = {
            "platforms": ["linux", "macos"],
            "tags": ["ai-tag1", "ai-tag2"]
        }
        
        overlay = {
            "platforms": ["windows", "linux"],  # Some overlap
            "tags": ["repo-tag1"]
        }
        
        result = self.generator._deep_merge_with_precedence(
            base, overlay, repository_precedence=True
        )
        
        # Repository data should come first, then unique AI data
        self.assertEqual(result["platforms"], ["windows", "linux", "macos"])
        self.assertEqual(result["tags"], ["repo-tag1", "ai-tag1", "ai-tag2"])


if __name__ == "__main__":
    unittest.main()