"""
Tests for RAG engine functionality.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from saidata_gen.core.interfaces import RAGConfig
from saidata_gen.rag.engine import RAGEngine, PromptTemplate, CategoryInfo, EnhancementResult
from saidata_gen.rag.providers import LLMResponse, OpenAIProvider, AnthropicProvider, LocalModelProvider
from saidata_gen.rag.exceptions import RAGError, PromptError, LLMProviderError


class TestPromptTemplate:
    """Test prompt template functionality."""
    
    def test_template_creation(self):
        """Test creating a prompt template."""
        template = PromptTemplate("Hello {name}, you are {age} years old.")
        assert template.variables == ['name', 'age']
    
    def test_template_rendering(self):
        """Test rendering a template with variables."""
        template = PromptTemplate("Hello {name}, you are {age} years old.")
        result = template.render(name="Alice", age=30)
        assert result == "Hello Alice, you are 30 years old."
    
    def test_template_missing_variables(self):
        """Test template rendering with missing variables."""
        template = PromptTemplate("Hello {name}, you are {age} years old.")
        with pytest.raises(PromptError, match="Missing template variables"):
            template.render(name="Alice")
    
    def test_template_extra_variables(self):
        """Test template rendering with extra variables."""
        template = PromptTemplate("Hello {name}!")
        result = template.render(name="Alice", extra="ignored")
        assert result == "Hello Alice!"
    
    def test_empty_template(self):
        """Test empty template."""
        template = PromptTemplate("")
        assert template.variables == []
        assert template.render() == ""


class TestRAGEngine:
    """Test RAG engine functionality."""
    
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
    def mock_llm_response(self):
        """Create mock LLM response."""
        return LLMResponse(
            content="Test response content",
            model="gpt-3.5-turbo",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            finish_reason="stop",
            metadata={"response_id": "test-123"}
        )
    
    def test_rag_engine_initialization(self, rag_config):
        """Test RAG engine initialization."""
        engine = RAGEngine(rag_config)
        assert engine.config == rag_config
        assert engine._provider is None
    
    @patch('saidata_gen.rag.engine.OpenAIProvider')
    def test_get_openai_provider(self, mock_provider_class, rag_config):
        """Test getting OpenAI provider."""
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        
        engine = RAGEngine(rag_config)
        provider = engine._get_provider()
        
        assert provider == mock_provider
        mock_provider_class.assert_called_once_with(
            model="gpt-3.5-turbo",
            api_key="test-key",
            base_url=None
        )
    
    @patch('saidata_gen.rag.engine.AnthropicProvider')
    def test_get_anthropic_provider(self, mock_provider_class, rag_config):
        """Test getting Anthropic provider."""
        rag_config.provider = "anthropic"
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        
        engine = RAGEngine(rag_config)
        provider = engine._get_provider()
        
        assert provider == mock_provider
        mock_provider_class.assert_called_once_with(
            model="gpt-3.5-turbo",
            api_key="test-key",
            base_url=None
        )
    
    @patch('saidata_gen.rag.engine.LocalModelProvider')
    def test_get_local_provider(self, mock_provider_class, rag_config):
        """Test getting local model provider."""
        rag_config.provider = "local"
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        
        engine = RAGEngine(rag_config)
        provider = engine._get_provider()
        
        assert provider == mock_provider
        mock_provider_class.assert_called_once_with(
            model="gpt-3.5-turbo",
            api_key="test-key",
            base_url="http://localhost:11434"
        )
    
    def test_unsupported_provider(self, rag_config):
        """Test unsupported provider raises error."""
        rag_config.provider = "unsupported"
        engine = RAGEngine(rag_config)
        
        with pytest.raises(RAGError, match="Unsupported RAG provider"):
            engine._get_provider()
    
    @patch('saidata_gen.rag.engine.RAGEngine._get_provider')
    def test_enhance_description(self, mock_get_provider, rag_config, mock_llm_response):
        """Test description enhancement."""
        mock_provider = Mock()
        mock_llm_response.content = "Enhanced description for nginx web server."
        mock_provider.generate.return_value = mock_llm_response
        mock_get_provider.return_value = mock_provider
        
        engine = RAGEngine(rag_config)
        
        basic_info = {
            'provider': 'apt',
            'version': '1.18.0',
            'description': 'HTTP server',
            'packages': {'apt': {'name': 'nginx'}},
            'license': 'BSD-2-Clause',
            'platforms': ['linux']
        }
        
        result = engine.enhance_description("nginx", basic_info)
        
        assert result == "Enhanced description for nginx web server."
        mock_provider.generate.assert_called_once()
        
        # Check that the prompt was properly formatted
        call_args = mock_provider.generate.call_args
        prompt = call_args[1]['prompt']
        assert "nginx" in prompt
        assert "apt" in prompt
        assert "1.18.0" in prompt
        assert "HTTP server" in prompt
    
    @patch('saidata_gen.rag.engine.RAGEngine._get_provider')
    def test_categorize_software(self, mock_get_provider, rag_config, mock_llm_response):
        """Test software categorization."""
        mock_provider = Mock()
        category_response = {
            "default": "web",
            "sub": "server",
            "tags": ["http", "proxy", "load-balancer"],
            "confidence": 0.9
        }
        mock_llm_response.content = json.dumps(category_response)
        mock_provider.generate.return_value = mock_llm_response
        mock_get_provider.return_value = mock_provider
        
        engine = RAGEngine(rag_config)
        
        software_info = {
            'name': 'nginx',
            'description': 'HTTP and reverse proxy server',
            'provider': 'apt',
            'packages': {'apt': {'name': 'nginx'}},
            'license': 'BSD-2-Clause',
            'platforms': ['linux'],
            'urls': {'website': 'https://nginx.org'}
        }
        
        result = engine.categorize_software(software_info)
        
        assert isinstance(result, CategoryInfo)
        assert result.default == "web"
        assert result.sub == "server"
        assert result.tags == ["http", "proxy", "load-balancer"]
        assert result.confidence == 0.9
    
    @patch('saidata_gen.rag.engine.RAGEngine._get_provider')
    def test_categorize_software_invalid_json(self, mock_get_provider, rag_config, mock_llm_response):
        """Test software categorization with invalid JSON response."""
        mock_provider = Mock()
        mock_llm_response.content = "Invalid JSON response"
        mock_provider.generate.return_value = mock_llm_response
        mock_get_provider.return_value = mock_provider
        
        engine = RAGEngine(rag_config)
        
        software_info = {
            'name': 'nginx',
            'description': 'HTTP server'
        }
        
        result = engine.categorize_software(software_info)
        
        # Should fallback to default values
        assert result.default == "utility"
        assert result.confidence == 0.1
    
    @patch('saidata_gen.rag.engine.RAGEngine._get_provider')
    def test_fill_missing_fields(self, mock_get_provider, rag_config, mock_llm_response):
        """Test filling missing metadata fields."""
        mock_provider = Mock()
        missing_fields_response = {
            "license": "BSD-2-Clause",
            "urls.website": "https://nginx.org",
            "urls.documentation": "https://nginx.org/en/docs/",
            "platforms": ["linux", "windows", "macos"]
        }
        mock_llm_response.content = json.dumps(missing_fields_response)
        mock_provider.generate.return_value = mock_llm_response
        mock_get_provider.return_value = mock_provider
        
        engine = RAGEngine(rag_config)
        
        metadata = {
            'name': 'nginx',
            'description': 'HTTP server',
            'packages': {'apt': {'name': 'nginx'}},
            'urls': {},
            'category': {'default': 'web'}
        }
        
        result = engine.fill_missing_fields(metadata)
        
        assert result['license'] == "BSD-2-Clause"
        assert result['urls.website'] == "https://nginx.org"
        assert result['urls.documentation'] == "https://nginx.org/en/docs/"
        assert result['platforms'] == ["linux", "windows", "macos"]
    
    @patch('saidata_gen.rag.engine.RAGEngine._get_provider')
    def test_fill_missing_fields_invalid_json(self, mock_get_provider, rag_config, mock_llm_response):
        """Test filling missing fields with invalid JSON response."""
        mock_provider = Mock()
        mock_llm_response.content = "Invalid JSON"
        mock_provider.generate.return_value = mock_llm_response
        mock_get_provider.return_value = mock_provider
        
        engine = RAGEngine(rag_config)
        
        metadata = {'name': 'nginx'}
        result = engine.fill_missing_fields(metadata)
        
        # Should return empty dict for invalid JSON
        assert result == {}
    
    def test_generate_confidence_scores(self, rag_config):
        """Test confidence score generation."""
        engine = RAGEngine(rag_config)
        
        metadata = {
            'description': 'A comprehensive HTTP server and reverse proxy with advanced features',
            'packages': {'apt': {'name': 'nginx'}, 'brew': {'name': 'nginx'}},
            'urls': {
                'website': 'https://nginx.org',
                'documentation': 'https://nginx.org/docs',
                'source': 'https://github.com/nginx/nginx'
            },
            'category': {'default': 'web'},
            'license': 'BSD-2-Clause',
            'platforms': ['linux', 'macos']
        }
        
        scores = engine.generate_confidence_scores(metadata)
        
        assert 'description' in scores
        assert 'packages' in scores
        assert 'urls' in scores
        assert 'category' in scores
        assert 'license' in scores
        assert 'platforms' in scores
        
        # Check score ranges
        for score in scores.values():
            assert 0.0 <= score <= 1.0
        
        # Long description should have high confidence
        assert scores['description'] >= 0.7
        
        # Multiple packages should increase confidence
        assert scores['packages'] >= 0.7
    
    @patch('saidata_gen.rag.engine.RAGEngine.enhance_description')
    @patch('saidata_gen.rag.engine.RAGEngine.categorize_software')
    @patch('saidata_gen.rag.engine.RAGEngine.fill_missing_fields')
    def test_enhance_metadata_full(self, mock_fill_fields, mock_categorize, 
                                  mock_enhance_desc, rag_config):
        """Test full metadata enhancement."""
        # Setup mocks
        mock_enhance_desc.return_value = "Enhanced description"
        mock_categorize.return_value = CategoryInfo(
            default="web", sub="server", tags=["http"], confidence=0.9
        )
        mock_fill_fields.return_value = {"license": "BSD-2-Clause"}
        
        engine = RAGEngine(rag_config)
        
        metadata = {
            'name': 'nginx',
            'packages': {'apt': {'name': 'nginx'}}
        }
        
        result = engine.enhance_metadata("nginx", metadata)
        
        assert isinstance(result, EnhancementResult)
        assert result.enhanced_data['description'] == "Enhanced description"
        assert result.enhanced_data['category']['default'] == "web"
        assert result.enhanced_data['license'] == "BSD-2-Clause"
        assert 'rag_description' in result.sources
        assert 'rag_categorization' in result.sources
        assert 'rag_field_completion' in result.sources
    
    @patch('saidata_gen.rag.engine.RAGEngine.enhance_description')
    def test_enhance_metadata_selective(self, mock_enhance_desc, rag_config):
        """Test selective metadata enhancement."""
        mock_enhance_desc.return_value = "Enhanced description"
        
        engine = RAGEngine(rag_config)
        
        metadata = {'name': 'nginx'}
        
        result = engine.enhance_metadata(
            "nginx", metadata, 
            enhancement_types=['description']
        )
        
        assert result.enhanced_data['description'] == "Enhanced description"
        assert 'rag_description' in result.sources
        assert len(result.sources) == 1
    
    @patch('saidata_gen.rag.engine.RAGEngine._get_provider')
    def test_enhance_description_error(self, mock_get_provider, rag_config):
        """Test description enhancement error handling."""
        mock_provider = Mock()
        mock_provider.generate.side_effect = LLMProviderError("API error")
        mock_get_provider.return_value = mock_provider
        
        engine = RAGEngine(rag_config)
        
        with pytest.raises(RAGError, match="Failed to enhance description"):
            engine.enhance_description("nginx", {})
    
    @patch('saidata_gen.rag.engine.RAGEngine._get_provider')
    def test_is_available_true(self, mock_get_provider, rag_config):
        """Test RAG engine availability check - available."""
        mock_provider = Mock()
        mock_provider.is_available.return_value = True
        mock_get_provider.return_value = mock_provider
        
        engine = RAGEngine(rag_config)
        assert engine.is_available() is True
    
    @patch('saidata_gen.rag.engine.RAGEngine._get_provider')
    def test_is_available_false(self, mock_get_provider, rag_config):
        """Test RAG engine availability check - not available."""
        mock_provider = Mock()
        mock_provider.is_available.return_value = False
        mock_get_provider.return_value = mock_provider
        
        engine = RAGEngine(rag_config)
        assert engine.is_available() is False
    
    @patch('saidata_gen.rag.engine.RAGEngine._get_provider')
    def test_is_available_exception(self, mock_get_provider, rag_config):
        """Test RAG engine availability check - exception."""
        mock_get_provider.side_effect = Exception("Provider error")
        
        engine = RAGEngine(rag_config)
        assert engine.is_available() is False