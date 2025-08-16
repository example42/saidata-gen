"""
Integration tests for metadata enhancement capabilities.
"""

import json
import pytest
from unittest.mock import Mock, patch

from saidata_gen.core.interfaces import RAGConfig
from saidata_gen.rag.engine import RAGEngine, CategoryInfo, EnhancementResult
from saidata_gen.rag.providers import LLMResponse


class TestMetadataEnhancement:
    """Test metadata enhancement integration."""
    
    @pytest.fixture
    def rag_config(self):
        """Create RAG configuration for testing."""
        return RAGConfig(
            provider="openai",
            model="gpt-3.5-turbo",
            api_key="test-key",
            temperature=0.1,
            max_tokens=1000
        )
    
    @pytest.fixture
    def sample_metadata(self):
        """Sample metadata for testing."""
        return {
            'name': 'nginx',
            'packages': {'apt': {'name': 'nginx'}},
            'urls': {},
            'category': {}
        }
    
    @patch('saidata_gen.rag.engine.RAGEngine._get_provider')
    def test_description_enhancement(self, mock_get_provider, rag_config, sample_metadata):
        """Test description enhancement capability."""
        mock_provider = Mock()
        mock_response = LLMResponse(
            content="Nginx is a high-performance HTTP server and reverse proxy server.",
            model="gpt-3.5-turbo",
            usage={"prompt_tokens": 50, "completion_tokens": 15, "total_tokens": 65},
            finish_reason="stop",
            metadata={"response_id": "test-123"}
        )
        mock_provider.generate.return_value = mock_response
        mock_get_provider.return_value = mock_provider
        
        engine = RAGEngine(rag_config)
        
        enhanced_desc = engine.enhance_description("nginx", sample_metadata)
        
        assert enhanced_desc == "Nginx is a high-performance HTTP server and reverse proxy server."
        mock_provider.generate.assert_called_once()
        
        # Verify prompt contains expected information
        call_args = mock_provider.generate.call_args
        prompt = call_args[1]['prompt']
        assert "nginx" in prompt.lower()
        assert "software name" in prompt.lower()
    
    @patch('saidata_gen.rag.engine.RAGEngine._get_provider')
    def test_categorization_capability(self, mock_get_provider, rag_config, sample_metadata):
        """Test software categorization capability."""
        mock_provider = Mock()
        category_response = {
            "default": "web",
            "sub": "server",
            "tags": ["http", "proxy", "load-balancer"],
            "confidence": 0.9
        }
        mock_response = LLMResponse(
            content=json.dumps(category_response),
            model="gpt-3.5-turbo",
            usage={"prompt_tokens": 60, "completion_tokens": 25, "total_tokens": 85},
            finish_reason="stop",
            metadata={"response_id": "test-456"}
        )
        mock_provider.generate.return_value = mock_response
        mock_get_provider.return_value = mock_provider
        
        engine = RAGEngine(rag_config)
        
        category_info = engine.categorize_software(sample_metadata)
        
        assert isinstance(category_info, CategoryInfo)
        assert category_info.default == "web"
        assert category_info.sub == "server"
        assert category_info.tags == ["http", "proxy", "load-balancer"]
        assert category_info.confidence == 0.9
    
    @patch('saidata_gen.rag.engine.RAGEngine._get_provider')
    def test_missing_field_completion(self, mock_get_provider, rag_config, sample_metadata):
        """Test missing field completion capability."""
        mock_provider = Mock()
        missing_fields_response = {
            "license": "BSD-2-Clause",
            "urls.website": "https://nginx.org",
            "urls.documentation": "https://nginx.org/en/docs/",
            "platforms": ["linux", "windows", "macos"]
        }
        mock_response = LLMResponse(
            content=json.dumps(missing_fields_response),
            model="gpt-3.5-turbo",
            usage={"prompt_tokens": 80, "completion_tokens": 40, "total_tokens": 120},
            finish_reason="stop",
            metadata={"response_id": "test-789"}
        )
        mock_provider.generate.return_value = mock_response
        mock_get_provider.return_value = mock_provider
        
        engine = RAGEngine(rag_config)
        
        completed_fields = engine.fill_missing_fields(sample_metadata)
        
        assert completed_fields['license'] == "BSD-2-Clause"
        assert completed_fields['urls.website'] == "https://nginx.org"
        assert completed_fields['urls.documentation'] == "https://nginx.org/en/docs/"
        assert completed_fields['platforms'] == ["linux", "windows", "macos"]
    
    @patch('saidata_gen.rag.engine.RAGEngine.enhance_description')
    @patch('saidata_gen.rag.engine.RAGEngine.categorize_software')
    @patch('saidata_gen.rag.engine.RAGEngine.fill_missing_fields')
    def test_full_metadata_enhancement(self, mock_fill_fields, mock_categorize, 
                                      mock_enhance_desc, rag_config, sample_metadata):
        """Test full metadata enhancement workflow."""
        # Setup mocks
        mock_enhance_desc.return_value = "Enhanced nginx description"
        mock_categorize.return_value = CategoryInfo(
            default="web", sub="server", tags=["http"], confidence=0.9
        )
        mock_fill_fields.return_value = {
            "license": "BSD-2-Clause",
            "urls.website": "https://nginx.org"
        }
        
        engine = RAGEngine(rag_config)
        
        result = engine.enhance_metadata("nginx", sample_metadata)
        
        assert isinstance(result, EnhancementResult)
        assert result.enhanced_data['description'] == "Enhanced nginx description"
        assert result.enhanced_data['category']['default'] == "web"
        assert result.enhanced_data['license'] == "BSD-2-Clause"
        assert 'rag_description' in result.sources
        assert 'rag_categorization' in result.sources
        assert 'rag_field_completion' in result.sources
        
        # Verify confidence scores are generated
        assert 'description' in result.confidence_scores
        assert 'category' in result.confidence_scores
    
    @patch('saidata_gen.rag.engine.RAGEngine.enhance_description')
    def test_selective_enhancement(self, mock_enhance_desc, rag_config, sample_metadata):
        """Test selective metadata enhancement."""
        mock_enhance_desc.return_value = "Enhanced description only"
        
        engine = RAGEngine(rag_config)
        
        result = engine.enhance_metadata(
            "nginx", sample_metadata, 
            enhancement_types=['description']
        )
        
        assert result.enhanced_data['description'] == "Enhanced description only"
        assert 'rag_description' in result.sources
        assert len(result.sources) == 1
        
        # Category should not be enhanced
        assert not result.enhanced_data.get('category', {}).get('default')
    
    def test_confidence_score_generation(self, rag_config):
        """Test confidence score generation for various metadata."""
        engine = RAGEngine(rag_config)
        
        # Test with comprehensive metadata
        comprehensive_metadata = {
            'description': 'A very detailed description of the software with lots of information',
            'packages': {'apt': {'name': 'test'}, 'brew': {'name': 'test'}, 'pip': {'name': 'test'}},
            'urls': {
                'website': 'https://example.com',
                'documentation': 'https://docs.example.com',
                'source': 'https://github.com/example/test'
            },
            'category': {'default': 'development'},
            'license': 'MIT',
            'platforms': ['linux', 'macos', 'windows']
        }
        
        scores = engine.generate_confidence_scores(comprehensive_metadata)
        
        # Should have high confidence for comprehensive data
        assert scores['description'] >= 0.7
        assert scores['packages'] >= 0.7
        assert scores['urls'] >= 0.5
        assert scores['category'] == 0.8
        assert scores['license'] == 0.8
        assert scores['platforms'] == 0.7
        
        # Test with minimal metadata
        minimal_metadata = {
            'description': 'Short desc',
            'packages': {'apt': {'name': 'test'}}
        }
        
        minimal_scores = engine.generate_confidence_scores(minimal_metadata)
        
        # Should have lower confidence for minimal data
        assert minimal_scores['description'] <= 0.7
        assert minimal_scores['packages'] <= 0.6
    
    @patch('saidata_gen.rag.engine.RAGEngine._get_provider')
    def test_categorization_fallback(self, mock_get_provider, rag_config, sample_metadata):
        """Test categorization fallback for invalid JSON."""
        mock_provider = Mock()
        mock_response = LLMResponse(
            content="Invalid JSON response that cannot be parsed",
            model="gpt-3.5-turbo",
            usage={"prompt_tokens": 60, "completion_tokens": 10, "total_tokens": 70},
            finish_reason="stop",
            metadata={"response_id": "test-error"}
        )
        mock_provider.generate.return_value = mock_response
        mock_get_provider.return_value = mock_provider
        
        engine = RAGEngine(rag_config)
        
        category_info = engine.categorize_software(sample_metadata)
        
        # Should fallback to default values
        assert category_info.default == "utility"
        assert category_info.confidence == 0.1
        assert category_info.sub is None
        assert category_info.tags is None
    
    @patch('saidata_gen.rag.engine.RAGEngine._get_provider')
    def test_field_completion_fallback(self, mock_get_provider, rag_config, sample_metadata):
        """Test field completion fallback for invalid JSON."""
        mock_provider = Mock()
        mock_response = LLMResponse(
            content="Not valid JSON at all",
            model="gpt-3.5-turbo",
            usage={"prompt_tokens": 80, "completion_tokens": 5, "total_tokens": 85},
            finish_reason="stop",
            metadata={"response_id": "test-error2"}
        )
        mock_provider.generate.return_value = mock_response
        mock_get_provider.return_value = mock_provider
        
        engine = RAGEngine(rag_config)
        
        completed_fields = engine.fill_missing_fields(sample_metadata)
        
        # Should return empty dict for invalid JSON
        assert completed_fields == {}