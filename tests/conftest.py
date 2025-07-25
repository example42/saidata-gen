"""
Pytest configuration and fixtures for saidata-gen tests.
"""

import os
import tempfile
import pytest
from unittest.mock import Mock, MagicMock
from typing import Dict, Any

from saidata_gen.core.interfaces import (
    RAGConfig, FetcherConfig, GenerationOptions, BatchOptions,
    ValidationResult, ValidationIssue, ValidationLevel,
    MetadataResult, BatchResult, SoftwareMatch, FetchResult
)
# from saidata_gen.core.cache import CacheManager
from tests.fixtures.sample_data import (
    SAMPLE_APT_PACKAGE, SAMPLE_BREW_PACKAGE, SAMPLE_NPM_PACKAGE,
    SAMPLE_PYPI_PACKAGE, SAMPLE_SAIDATA_METADATA
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def fetcher_config():
    """Create a test fetcher configuration."""
    return FetcherConfig(
        concurrent_requests=2,  # Lower for tests
        request_timeout=5,      # Shorter timeout
        retry_count=1          # Fewer retries
    )


@pytest.fixture
def rag_config():
    """Create a test RAG configuration."""
    return RAGConfig(
        provider="openai",
        model="gpt-3.5-turbo",
        api_key="test-api-key",
        temperature=0.0,  # Deterministic for tests
        max_tokens=100    # Shorter responses
    )


@pytest.fixture
def mock_http_session():
    """Create a mock HTTP session for testing."""
    session = Mock()
    
    # Mock common HTTP responses
    def mock_get(url, **kwargs):
        response = Mock()
        response.status_code = 200
        response.headers = {'content-type': 'application/json'}
        
        # Return different responses based on URL patterns
        if 'packages.gz' in url:
            response.content = b'mock package data'
            response.text = 'mock package data'
        elif 'api.github.com' in url:
            response.json.return_value = {"name": "test-repo"}
        elif 'registry.npmjs.org' in url:
            response.json.return_value = SAMPLE_NPM_PACKAGE
        elif 'pypi.org' in url:
            response.json.return_value = SAMPLE_PYPI_PACKAGE
        else:
            response.text = 'mock response'
            response.json.return_value = {"status": "ok"}
        
        return response
    
    session.get.side_effect = mock_get
    return session


@pytest.fixture
def mock_repository_fetcher():
    """Create a mock repository fetcher."""
    fetcher = Mock()
    
    # Mock search results
    fetcher.search_package.return_value = [
        {
            "provider": "apt",
            "name": "nginx",
            "version": "1.18.0",
            "description": "HTTP server and reverse proxy"
        },
        {
            "provider": "brew",
            "name": "nginx", 
            "version": "1.25.3",
            "description": "HTTP(S) server and reverse proxy"
        }
    ]
    
    # Mock repository data
    fetcher.fetch_repositories.return_value = {
        "apt": {"status": "success", "packages_count": 1000},
        "brew": {"status": "success", "packages_count": 500}
    }
    
    fetcher.get_supported_providers.return_value = [
        "apt", "brew", "dnf", "npm", "pypi", "cargo"
    ]
    
    return fetcher


@pytest.fixture
def mock_metadata_generator():
    """Create a mock metadata generator."""
    generator = Mock()
    
    from saidata_gen.core.models import EnhancedSaidataMetadata
    
    # Mock generation result
    mock_metadata = EnhancedSaidataMetadata.from_dict(SAMPLE_SAIDATA_METADATA)
    generator.generate_from_sources.return_value = mock_metadata
    
    return generator


@pytest.fixture
def mock_schema_validator():
    """Create a mock schema validator."""
    validator = Mock()
    
    from saidata_gen.core.interfaces import ValidationResult
    
    # Mock successful validation by default
    validator.validate_data.return_value = ValidationResult(valid=True, issues=[])
    validator.validate_file.return_value = ValidationResult(valid=True, issues=[])
    
    return validator


@pytest.fixture
def mock_rag_engine():
    """Create a mock RAG engine."""
    rag_engine = Mock()
    
    # Mock RAG responses
    rag_engine.enhance_description.return_value = "Enhanced description with AI insights"
    rag_engine.categorize_software.return_value = {
        "default": "Web",
        "sub": "Server",
        "tags": ["http", "proxy", "server"]
    }
    rag_engine.fill_missing_fields.return_value = {
        "urls": {
            "website": "https://nginx.org/",
            "documentation": "https://nginx.org/en/docs/"
        }
    }
    
    return rag_engine


@pytest.fixture
def mock_search_engine():
    """Create a mock search engine."""
    search_engine = Mock()
    
    from saidata_gen.core.interfaces import SoftwareMatch
    
    # Mock search results
    search_engine.search.return_value = [
        SoftwareMatch(
            name="nginx",
            provider="apt",
            version="1.18.0",
            description="HTTP server and reverse proxy",
            confidence=0.95
        ),
        SoftwareMatch(
            name="nginx",
            provider="brew",
            version="1.25.3", 
            description="HTTP(S) server and reverse proxy",
            confidence=0.90
        )
    ]
    
    return search_engine


@pytest.fixture
def sample_package_data():
    """Provide sample package data for different providers."""
    return {
        "apt": SAMPLE_APT_PACKAGE,
        "brew": SAMPLE_BREW_PACKAGE,
        "npm": SAMPLE_NPM_PACKAGE,
        "pypi": SAMPLE_PYPI_PACKAGE
    }


@pytest.fixture
def sample_saidata_metadata():
    """Provide sample saidata metadata."""
    return SAMPLE_SAIDATA_METADATA.copy()


@pytest.fixture
def mock_file_system(temp_dir):
    """Create a mock file system with test files."""
    # Create test schema file
    schema_content = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "version": {"type": "string", "enum": ["0.1"]},
            "description": {"type": "string"},
            "packages": {"type": "object"}
        },
        "required": ["version"]
    }
    
    schema_path = os.path.join(temp_dir, "schema.json")
    with open(schema_path, "w") as f:
        import json
        json.dump(schema_content, f)
    
    # Create test template files
    templates_dir = os.path.join(temp_dir, "templates")
    os.makedirs(templates_dir, exist_ok=True)
    
    defaults_content = """
version: '0.1'
category:
  default: Development
platforms:
  - linux
urls:
  website: https://example.com
"""
    
    defaults_path = os.path.join(templates_dir, "defaults.yaml")
    with open(defaults_path, "w") as f:
        f.write(defaults_content)
    
    return {
        "temp_dir": temp_dir,
        "schema_path": schema_path,
        "templates_dir": templates_dir,
        "defaults_path": defaults_path
    }


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Set up test environment variables."""
    # Set test environment variables
    monkeypatch.setenv("SAIDATA_GEN_TEST_MODE", "true")
    monkeypatch.setenv("SAIDATA_GEN_LOG_LEVEL", "DEBUG")
    
    # Mock external API keys for tests
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")


@pytest.fixture
def mock_external_apis(monkeypatch):
    """Mock external API calls."""
    # Mock OpenAI API
    mock_openai = Mock()
    mock_openai.chat.completions.create.return_value = Mock(
        choices=[Mock(message=Mock(content="Mocked AI response"))]
    )
    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: mock_openai)
    
    # Mock Anthropic API
    mock_anthropic = Mock()
    mock_anthropic.messages.create.return_value = Mock(
        content=[Mock(text="Mocked Anthropic response")]
    )
    monkeypatch.setattr("anthropic.Anthropic", lambda **kwargs: mock_anthropic)
    
    return {
        "openai": mock_openai,
        "anthropic": mock_anthropic
    }


# Pytest markers for test categorization
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "network: mark test as requiring network access"
    )
    config.addinivalue_line(
        "markers", "rag: mark test as requiring RAG/AI services"
    )


# Custom test collection
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Add unit marker to all tests by default
        if not any(marker.name in ["integration", "slow", "network", "rag"] 
                  for marker in item.iter_markers()):
            item.add_marker(pytest.mark.unit)
        
        # Add slow marker to tests that might be slow
        if any(keyword in item.name.lower() 
               for keyword in ["batch", "concurrent", "performance", "load"]):
            item.add_marker(pytest.mark.slow)
        
        # Add network marker to tests that use external APIs
        if any(keyword in item.name.lower() 
               for keyword in ["fetch", "api", "http", "download"]):
            item.add_marker(pytest.mark.network)
        
        # Add RAG marker to AI-related tests
        if any(keyword in item.name.lower() 
               for keyword in ["rag", "ai", "llm", "openai", "anthropic"]):
            item.add_marker(pytest.mark.rag)