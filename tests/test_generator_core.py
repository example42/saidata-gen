"""
Unit tests for the metadata generator core.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

from saidata_gen.generator.core import MetadataGenerator
from saidata_gen.core.models import EnhancedSaidataMetadata
from saidata_gen.core.interfaces import GeneratorConfig
from tests.fixtures.sample_data import (
    SAMPLE_APT_PACKAGE, SAMPLE_BREW_PACKAGE, SAMPLE_NPM_PACKAGE,
    EXPECTED_NGINX_METADATA, get_sample_package_data
)


class TestMetadataGenerator(unittest.TestCase):
    """Test the MetadataGenerator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = GeneratorConfig()
        self.mock_template_engine = Mock()
        self.mock_schema_validator = Mock()
        
        self.generator = MetadataGenerator(
            config=self.config,
            template_engine=self.mock_template_engine,
            schema_validator=self.mock_schema_validator
        )
    
    def test_initialization(self):
        """Test generator initialization."""
        self.assertEqual(self.generator.config, self.config)
        self.assertEqual(self.generator.template_engine, self.mock_template_engine)
        self.assertEqual(self.generator.schema_validator, self.mock_schema_validator)
    
    def test_generate_from_single_source(self):
        """Test metadata generation from a single package source."""
        package_info = {
            "provider": "apt",
            "name": "nginx",
            "version": "1.18.0",
            "description": "HTTP server and reverse proxy",
            "homepage": "https://nginx.org/",
            "license": "BSD-2-Clause",
            "architecture": "amd64"
        }
        
        # Mock template engine
        self.mock_template_engine.apply_defaults.return_value = {
            "version": "0.1",
            "description": "HTTP server and reverse proxy",
            "license": "BSD-2-Clause",
            "platforms": ["linux"],
            "packages": {
                "apt": {
                    "name": "nginx",
                    "version": "1.18.0"
                }
            },
            "urls": {
                "website": "https://nginx.org/"
            },
            "category": {
                "default": "Web",
                "sub": "Server"
            }
        }
        
        result = self.generator.generate_from_sources("nginx", [package_info])
        
        self.assertIsInstance(result, EnhancedSaidataMetadata)
        self.assertEqual(result.description, "HTTP server and reverse proxy")
        self.assertEqual(result.license, "BSD-2-Clause")
        self.assertIn("apt", result.packages)
        self.assertEqual(result.packages["apt"].name, "nginx")
        self.mock_template_engine.apply_defaults.assert_called_once()
    
    def test_generate_from_multiple_sources(self):
        """Test metadata generation from multiple package sources."""
        package_sources = [
            {
                "provider": "apt",
                "name": "nginx",
                "version": "1.18.0",
                "description": "HTTP server and reverse proxy",
                "homepage": "https://nginx.org/",
                "license": "BSD-2-Clause"
            },
            {
                "provider": "brew",
                "name": "nginx", 
                "version": "1.25.3",
                "description": "HTTP(S) server and reverse proxy",
                "homepage": "https://nginx.org/",
                "license": "BSD-2-Clause"
            },
            {
                "provider": "dnf",
                "name": "nginx",
                "version": "1.20.1",
                "description": "High performance web server",
                "homepage": "http://nginx.org/",
                "license": "BSD"
            }
        ]
        
        # Mock template engine to return merged data
        self.mock_template_engine.apply_defaults.return_value = {
            "version": "0.1",
            "description": "HTTP(S) server and reverse proxy",
            "license": "BSD-2-Clause",
            "platforms": ["linux", "macos"],
            "packages": {
                "apt": {"name": "nginx", "version": "1.18.0"},
                "brew": {"name": "nginx", "version": "1.25.3"},
                "dnf": {"name": "nginx", "version": "1.20.1"}
            },
            "urls": {
                "website": "https://nginx.org/"
            },
            "category": {
                "default": "Web",
                "sub": "Server"
            }
        }
        
        result = self.generator.generate_from_sources("nginx", package_sources)
        
        self.assertIsInstance(result, EnhancedSaidataMetadata)
        self.assertEqual(len(result.packages), 3)
        self.assertIn("apt", result.packages)
        self.assertIn("brew", result.packages)
        self.assertIn("dnf", result.packages)
        self.assertEqual(result.description, "HTTP(S) server and reverse proxy")
    
    def test_apply_defaults(self):
        """Test applying default values to metadata."""
        base_metadata = {
            "version": "0.1",
            "description": "Test software",
            "packages": {
                "apt": {"name": "test-package"}
            }
        }
        
        # Mock template engine defaults
        self.mock_template_engine.apply_defaults.return_value = {
            **base_metadata,
            "license": "MIT",  # Added by defaults
            "platforms": ["linux"],  # Added by defaults
            "category": {
                "default": "Development",
                "tags": ["tool"]
            },
            "urls": {
                "website": "https://example.com"
            }
        }
        
        result = self.generator.apply_defaults(base_metadata)
        
        self.assertEqual(result["license"], "MIT")
        self.assertEqual(result["platforms"], ["linux"])
        self.assertEqual(result["category"]["default"], "Development")
        self.mock_template_engine.apply_defaults.assert_called_once_with(base_metadata)
    
    def test_merge_provider_data(self):
        """Test merging data from multiple providers."""
        base_metadata = {
            "version": "0.1",
            "description": "Base description",
            "packages": {}
        }
        
        provider_data = {
            "apt": {
                "packages": {"apt": {"name": "nginx", "version": "1.18.0"}},
                "platforms": ["linux"],
                "urls": {"website": "https://nginx.org/"}
            },
            "brew": {
                "packages": {"brew": {"name": "nginx", "version": "1.25.3"}},
                "platforms": ["macos"],
                "urls": {"documentation": "https://nginx.org/en/docs/"}
            }
        }
        
        result = self.generator.merge_provider_data(base_metadata, provider_data)
        
        # Should merge packages from both providers
        self.assertIn("apt", result["packages"])
        self.assertIn("brew", result["packages"])
        
        # Should merge platforms
        self.assertIn("linux", result["platforms"])
        self.assertIn("macos", result["platforms"])
        
        # Should merge URLs
        self.assertEqual(result["urls"]["website"], "https://nginx.org/")
        self.assertEqual(result["urls"]["documentation"], "https://nginx.org/en/docs/")
    

    
    def test_normalize_package_info(self):
        """Test normalizing package information from different providers."""
        # Test APT package normalization
        apt_package = {
            "Package": "nginx",
            "Version": "1.18.0-6ubuntu14.4",
            "Description": "small, powerful, scalable web/proxy server",
            "Homepage": "http://nginx.org",
            "Section": "httpd",
            "Architecture": "amd64"
        }
        
        normalized = self.generator._normalize_package_info("apt", apt_package)
        
        self.assertEqual(normalized["provider"], "apt")
        self.assertEqual(normalized["name"], "nginx")
        self.assertEqual(normalized["version"], "1.18.0-6ubuntu14.4")
        self.assertEqual(normalized["description"], "small, powerful, scalable web/proxy server")
        self.assertEqual(normalized["homepage"], "http://nginx.org")
        
        # Test Homebrew package normalization
        brew_package = {
            "name": "nginx",
            "versions": {"stable": "1.25.3"},
            "desc": "HTTP(S) server and reverse proxy",
            "homepage": "https://nginx.org/",
            "license": "BSD-2-Clause"
        }
        
        normalized = self.generator._normalize_package_info("brew", brew_package)
        
        self.assertEqual(normalized["provider"], "brew")
        self.assertEqual(normalized["name"], "nginx")
        self.assertEqual(normalized["version"], "1.25.3")
        self.assertEqual(normalized["description"], "HTTP(S) server and reverse proxy")
        self.assertEqual(normalized["license"], "BSD-2-Clause")
    
    def test_extract_common_metadata(self):
        """Test extracting common metadata from multiple sources."""
        sources = [
            {
                "provider": "apt",
                "name": "nginx",
                "description": "HTTP server and reverse proxy",
                "homepage": "https://nginx.org/",
                "license": "BSD-2-Clause"
            },
            {
                "provider": "brew",
                "name": "nginx",
                "description": "HTTP(S) server and reverse proxy",
                "homepage": "https://nginx.org/",
                "license": "BSD-2-Clause"
            },
            {
                "provider": "dnf",
                "name": "nginx",
                "description": "High performance web server",
                "homepage": "http://nginx.org/",
                "license": "BSD"
            }
        ]
        
        common = self.generator._extract_common_metadata(sources)
        
        self.assertEqual(common["name"], "nginx")
        self.assertEqual(common["homepage"], "https://nginx.org/")  # Should prefer HTTPS
        self.assertEqual(common["license"], "BSD-2-Clause")  # Should prefer more specific
        # Description should be the most comprehensive one
        self.assertIn("HTTP", common["description"])
    
    def test_resolve_conflicts(self):
        """Test conflict resolution between different sources."""
        conflicting_data = {
            "description": [
                "HTTP server",
                "HTTP(S) server and reverse proxy", 
                "High performance web server"
            ],
            "license": ["BSD", "BSD-2-Clause", "BSD-2-Clause"],
            "homepage": ["http://nginx.org/", "https://nginx.org/", "https://nginx.org/"]
        }
        
        resolved = self.generator._resolve_conflicts(conflicting_data)
        
        # Should choose the most comprehensive description
        self.assertEqual(resolved["description"], "HTTP(S) server and reverse proxy")
        # Should choose the more specific license
        self.assertEqual(resolved["license"], "BSD-2-Clause")
        # Should prefer HTTPS URL
        self.assertEqual(resolved["homepage"], "https://nginx.org/")
    
    def test_calculate_confidence_scores(self):
        """Test confidence score calculation."""
        metadata = {
            "version": "0.1",
            "description": "HTTP server and reverse proxy",
            "license": "BSD-2-Clause",
            "packages": {
                "apt": {"name": "nginx", "version": "1.18.0"},
                "brew": {"name": "nginx", "version": "1.25.3"}
            },
            "urls": {
                "website": "https://nginx.org/"
            }
        }
        
        sources_count = 2
        confidence_scores = self.generator._calculate_confidence_scores(metadata, sources_count)
        
        # Should have confidence scores for all fields
        self.assertIn("description", confidence_scores)
        self.assertIn("license", confidence_scores)
        self.assertIn("packages", confidence_scores)
        
        # Scores should be between 0 and 1
        for score in confidence_scores.values():
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)
        
        # More sources should generally mean higher confidence
        self.assertGreater(confidence_scores["packages"], 0.5)
    
    def test_generate_with_validation_failure(self):
        """Test generation with schema validation failure."""
        package_info = {
            "provider": "apt",
            "name": "nginx"
            # Missing required fields
        }
        
        # Mock template engine to return invalid data
        self.mock_template_engine.apply_defaults.return_value = {
            "version": "0.1"
            # Missing required fields like packages
        }
        
        # Mock validator to return validation failure
        from saidata_gen.core.interfaces import ValidationResult, ValidationIssue, ValidationLevel
        validation_result = ValidationResult(
            valid=False,
            issues=[
                ValidationIssue(
                    level=ValidationLevel.ERROR,
                    message="Required field 'packages' is missing",
                    path="packages"
                )
            ]
        )
        self.mock_schema_validator.validate_data.return_value = validation_result
        
        with self.assertRaises(ValueError) as context:
            self.generator.generate_from_sources("nginx", [package_info])
        
        self.assertIn("Schema validation failed", str(context.exception))
    
    def test_generate_empty_sources(self):
        """Test generation with empty sources list."""
        with self.assertRaises(ValueError) as context:
            self.generator.generate_from_sources("nginx", [])
        
        self.assertIn("No package sources provided", str(context.exception))
    
    def test_provider_specific_handling(self):
        """Test provider-specific metadata handling."""
        # Test NPM package with specific fields
        npm_package = {
            "name": "express",
            "version": "4.18.2",
            "description": "Fast, unopinionated, minimalist web framework",
            "keywords": ["express", "framework", "web", "http"],
            "repository": {"url": "git+https://github.com/expressjs/express.git"},
            "homepage": "http://expressjs.com/",
            "license": "MIT",
            "dependencies": {"accepts": "~1.3.8", "body-parser": "1.20.1"}
        }
        
        normalized = self.generator._normalize_package_info("npm", npm_package)
        
        self.assertEqual(normalized["provider"], "npm")
        self.assertEqual(normalized["name"], "express")
        self.assertEqual(normalized["keywords"], ["express", "framework", "web", "http"])
        self.assertEqual(normalized["repository"], "https://github.com/expressjs/express.git")
        self.assertIn("dependencies", normalized)
    
    def test_metadata_enrichment(self):
        """Test metadata enrichment with additional context."""
        base_metadata = {
            "version": "0.1",
            "description": "Web server",
            "packages": {"apt": {"name": "nginx"}}
        }
        
        # Test enrichment with common patterns
        enriched = self.generator._enrich_metadata(base_metadata, "nginx")
        
        # Should add common nginx-specific metadata
        self.assertIn("ports", enriched)
        self.assertIn("services", enriched)
        
        # Should have HTTP and HTTPS ports for nginx
        if "ports" in enriched:
            self.assertIn("http", enriched["ports"])
            self.assertIn("https", enriched["ports"])


if __name__ == "__main__":
    unittest.main()