"""
Unit tests for the metadata generator.
"""

import os
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Any, List

import yaml

from saidata_gen.core.interfaces import PackageInfo
from saidata_gen.generator.core import MetadataGenerator
from saidata_gen.generator.templates import TemplateEngine


class TestTemplateEngine(unittest.TestCase):
    """Test the template engine."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for templates
        self.temp_dir = tempfile.TemporaryDirectory()
        self.templates_dir = Path(self.temp_dir.name)
        
        # Create a default template
        os.makedirs(self.templates_dir, exist_ok=True)
        with open(os.path.join(self.templates_dir, "defaults.yaml"), "w") as f:
            yaml.dump({
                "version": "0.1",
                "packages": {
                    "default": {
                        "name": "$software_name",
                        "version": "latest"
                    }
                },
                "services": {
                    "default": {
                        "name": "$software_name"
                    }
                },
                "description": "Default description for $software_name"
            }, f)
        
        # Create a provider template
        os.makedirs(os.path.join(self.templates_dir, "providers"), exist_ok=True)
        with open(os.path.join(self.templates_dir, "providers", "apt.yaml"), "w") as f:
            yaml.dump({
                "packages": {
                    "apt": {
                        "name": "$software_name",
                        "version": "latest"
                    }
                },
                "platforms": ["linux", "debian", "ubuntu"]
            }, f)
        
        # Create the template engine
        self.template_engine = TemplateEngine(str(self.templates_dir))
    
    def tearDown(self):
        """Clean up the test environment."""
        self.temp_dir.cleanup()
    
    def test_load_default_template(self):
        """Test loading the default template."""
        self.assertIn("version", self.template_engine.default_template)
        self.assertIn("packages", self.template_engine.default_template)
        self.assertIn("default", self.template_engine.default_template["packages"])
        self.assertEqual("$software_name", self.template_engine.default_template["packages"]["default"]["name"])
    
    def test_load_provider_templates(self):
        """Test loading provider templates."""
        self.assertIn("apt", self.template_engine.provider_templates)
        self.assertIn("packages", self.template_engine.provider_templates["apt"])
        self.assertIn("apt", self.template_engine.provider_templates["apt"]["packages"])
        self.assertEqual("$software_name", self.template_engine.provider_templates["apt"]["packages"]["apt"]["name"])
    
    def test_apply_template(self):
        """Test applying templates."""
        result = self.template_engine.apply_template("nginx")
        
        self.assertEqual("0.1", result["version"])
        self.assertEqual("nginx", result["packages"]["default"]["name"])
        self.assertEqual("Default description for nginx", result["description"])
    
    def test_apply_template_with_providers(self):
        """Test applying templates with providers."""
        result = self.template_engine.apply_template("nginx", providers=["apt"])
        
        self.assertEqual("0.1", result["version"])
        self.assertEqual("nginx", result["packages"]["default"]["name"])
        self.assertEqual("nginx", result["packages"]["apt"]["name"])
        self.assertEqual("Default description for nginx", result["description"])
        self.assertIn("platforms", result)
        self.assertIn("linux", result["platforms"])
        self.assertIn("debian", result["platforms"])
        self.assertIn("ubuntu", result["platforms"])
    
    def test_apply_template_with_existing_metadata(self):
        """Test applying templates with existing metadata."""
        existing_metadata = {
            "description": "Nginx is a web server",
            "license": "BSD",
            "urls": {
                "website": "https://nginx.org"
            }
        }
        
        result = self.template_engine.apply_template("nginx", existing_metadata, providers=["apt"])
        
        self.assertEqual("0.1", result["version"])
        self.assertEqual("nginx", result["packages"]["default"]["name"])
        self.assertEqual("nginx", result["packages"]["apt"]["name"])
        self.assertEqual("Nginx is a web server", result["description"])
        self.assertEqual("BSD", result["license"])
        self.assertEqual("https://nginx.org", result["urls"]["website"])
        self.assertIn("platforms", result)
        self.assertIn("linux", result["platforms"])
        self.assertIn("debian", result["platforms"])
        self.assertIn("ubuntu", result["platforms"])
    
    def test_deep_merge(self):
        """Test deep merging of dictionaries."""
        base = {
            "a": 1,
            "b": {
                "c": 2,
                "d": 3
            },
            "e": [1, 2, 3]
        }
        
        overlay = {
            "b": {
                "c": 4,
                "f": 5
            },
            "e": [4, 5, 6],
            "g": 6
        }
        
        result = self.template_engine._deep_merge(base, overlay)
        
        self.assertEqual(1, result["a"])
        self.assertEqual(4, result["b"]["c"])
        self.assertEqual(3, result["b"]["d"])
        self.assertEqual(5, result["b"]["f"])
        self.assertEqual([4, 5, 6], result["e"])
        self.assertEqual(6, result["g"])
    
    def test_substitute_variables(self):
        """Test variable substitution."""
        data = {
            "name": "$software_name",
            "description": "This is $software_name",
            "nested": {
                "name": "$software_name",
                "version": "$version"
            },
            "list": ["$software_name", "$version"]
        }
        
        variables = {
            "software_name": "nginx",
            "version": "1.20.0"
        }
        
        result = self.template_engine._substitute_variables(data, variables)
        
        self.assertEqual("nginx", result["name"])
        self.assertEqual("This is nginx", result["description"])
        self.assertEqual("nginx", result["nested"]["name"])
        self.assertEqual("1.20.0", result["nested"]["version"])
        self.assertEqual(["nginx", "1.20.0"], result["list"])


class TestMetadataGenerator(unittest.TestCase):
    """Test the metadata generator."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for templates
        self.temp_dir = tempfile.TemporaryDirectory()
        self.templates_dir = Path(self.temp_dir.name)
        
        # Create a default template
        os.makedirs(self.templates_dir, exist_ok=True)
        with open(os.path.join(self.templates_dir, "defaults.yaml"), "w") as f:
            yaml.dump({
                "version": "0.1",
                "packages": {
                    "default": {
                        "name": "$software_name",
                        "version": "latest"
                    }
                },
                "services": {
                    "default": {
                        "name": "$software_name"
                    }
                },
                "description": "Default description for $software_name"
            }, f)
        
        # Create a provider template
        os.makedirs(os.path.join(self.templates_dir, "providers"), exist_ok=True)
        with open(os.path.join(self.templates_dir, "providers", "apt.yaml"), "w") as f:
            yaml.dump({
                "packages": {
                    "apt": {
                        "name": "$software_name",
                        "version": "latest"
                    }
                },
                "platforms": ["linux", "debian", "ubuntu"]
            }, f)
        
        # Create the template engine
        self.template_engine = TemplateEngine(str(self.templates_dir))
        
        # Create the metadata generator
        self.metadata_generator = MetadataGenerator(self.template_engine)
    
    def tearDown(self):
        """Clean up the test environment."""
        self.temp_dir.cleanup()
    
    def test_generate_from_sources(self):
        """Test generating metadata from sources."""
        sources = [
            PackageInfo(
                name="nginx",
                provider="apt",
                version="1.18.0",
                description="High-performance HTTP server and reverse proxy",
                details={
                    "license": "BSD",
                    "homepage": "https://nginx.org",
                    "source_url": "https://nginx.org/download/nginx-1.18.0.tar.gz",
                    "platforms": ["linux", "debian", "ubuntu"]
                }
            ),
            PackageInfo(
                name="nginx",
                provider="brew",
                version="1.19.0",
                description="HTTP server and reverse proxy",
                details={
                    "license": "BSD",
                    "homepage": "https://nginx.org",
                    "source_url": "https://nginx.org/download/nginx-1.19.0.tar.gz",
                    "platforms": ["macos", "linux"]
                }
            )
        ]
        
        result = self.metadata_generator.generate_from_sources("nginx", sources)
        
        self.assertEqual("0.1", result.metadata.version)
        self.assertIn("apt", result.metadata.packages)
        self.assertEqual("nginx", result.metadata.packages["apt"].name)
        self.assertEqual("1.18.0", result.metadata.packages["apt"].version)
        self.assertIn("brew", result.metadata.packages)
        self.assertEqual("nginx", result.metadata.packages["brew"].name)
        self.assertEqual("1.19.0", result.metadata.packages["brew"].version)
        self.assertEqual("High-performance HTTP server and reverse proxy", result.metadata.description)
        self.assertEqual("BSD", result.metadata.license)
        self.assertEqual("https://nginx.org", result.metadata.urls.website)
        self.assertTrue(result.metadata.urls.source in [
            "https://nginx.org/download/nginx-1.18.0.tar.gz",
            "https://nginx.org/download/nginx-1.19.0.tar.gz"
        ])
        self.assertIn("linux", result.metadata.platforms)
        self.assertIn("debian", result.metadata.platforms)
        self.assertIn("ubuntu", result.metadata.platforms)
        self.assertIn("macos", result.metadata.platforms)
    
    def test_merge_sources(self):
        """Test merging sources."""
        base = {
            "version": "0.1",
            "packages": {
                "default": {
                    "name": "nginx",
                    "version": "latest"
                }
            },
            "description": "Default description for nginx"
        }
        
        sources = [
            PackageInfo(
                name="nginx",
                provider="apt",
                version="1.18.0",
                description="High-performance HTTP server and reverse proxy",
                details={
                    "license": "BSD",
                    "homepage": "https://nginx.org",
                    "source_url": "https://nginx.org/download/nginx-1.18.0.tar.gz",
                    "platforms": ["linux", "debian", "ubuntu"]
                }
            ),
            PackageInfo(
                name="nginx",
                provider="brew",
                version="1.19.0",
                description="HTTP server and reverse proxy",
                details={
                    "license": "BSD",
                    "homepage": "https://nginx.org",
                    "source_url": "https://nginx.org/download/nginx-1.19.0.tar.gz",
                    "platforms": ["macos", "linux"]
                }
            )
        ]
        
        result = self.metadata_generator._merge_sources(base, sources)
        
        self.assertEqual("0.1", result["version"])
        self.assertIn("apt", result["packages"])
        self.assertEqual("nginx", result["packages"]["apt"]["name"])
        self.assertEqual("1.18.0", result["packages"]["apt"]["version"])
        self.assertIn("brew", result["packages"])
        self.assertEqual("nginx", result["packages"]["brew"]["name"])
        self.assertEqual("1.19.0", result["packages"]["brew"]["version"])
        self.assertEqual("High-performance HTTP server and reverse proxy", result["description"])
        self.assertEqual("BSD", result["license"])
        self.assertEqual("https://nginx.org", result["urls"]["website"])
        self.assertTrue(result["urls"]["source"] in [
            "https://nginx.org/download/nginx-1.18.0.tar.gz",
            "https://nginx.org/download/nginx-1.19.0.tar.gz"
        ])
        self.assertIn("linux", result["platforms"])
        self.assertIn("debian", result["platforms"])
        self.assertIn("ubuntu", result["platforms"])
        self.assertIn("macos", result["platforms"])
    
    def test_calculate_confidence_scores(self):
        """Test calculating confidence scores."""
        from saidata_gen.core.models import EnhancedSaidataMetadata
        
        metadata = EnhancedSaidataMetadata(
            version="0.1",
            description="High-performance HTTP server and reverse proxy",
            license="BSD",
            platforms=["linux", "debian", "ubuntu", "macos"]
        )
        
        metadata.urls.website = "https://nginx.org"
        metadata.urls.source = "https://nginx.org/download/nginx-1.18.0.tar.gz"
        
        sources = [
            PackageInfo(
                name="nginx",
                provider="apt",
                version="1.18.0",
                description="High-performance HTTP server and reverse proxy",
                details={
                    "license": "BSD",
                    "homepage": "https://nginx.org",
                    "source_url": "https://nginx.org/download/nginx-1.18.0.tar.gz",
                    "platforms": ["linux", "debian", "ubuntu"]
                }
            ),
            PackageInfo(
                name="nginx",
                provider="brew",
                version="1.19.0",
                description="HTTP server and reverse proxy",
                details={
                    "license": "BSD",
                    "homepage": "https://nginx.org",
                    "source_url": "https://nginx.org/download/nginx-1.19.0.tar.gz",
                    "platforms": ["macos", "linux"]
                }
            )
        ]
        
        confidence_scores = self.metadata_generator._calculate_confidence_scores(metadata, sources)
        
        self.assertIn("description", confidence_scores)
        self.assertIn("license", confidence_scores)
        self.assertIn("urls.website", confidence_scores)
        self.assertIn("urls.source", confidence_scores)
        self.assertIn("platforms.linux", confidence_scores)
        self.assertIn("platforms.debian", confidence_scores)
        self.assertIn("platforms.ubuntu", confidence_scores)
        self.assertIn("platforms.macos", confidence_scores)
        self.assertIn("overall", confidence_scores)
        
        # Description matches one source exactly
        self.assertEqual(0.5, confidence_scores["description"])
        
        # License matches both sources
        self.assertEqual(1.0, confidence_scores["license"])
        
        # Website matches both sources
        self.assertEqual(1.0, confidence_scores["urls.website"])
        
        # Source URL matches one source exactly
        self.assertEqual(0.5, confidence_scores["urls.source"])
        
        # Linux platform is in both sources
        self.assertEqual(1.0, confidence_scores["platforms.linux"])
        
        # Debian platform is in one source
        self.assertEqual(0.5, confidence_scores["platforms.debian"])
        
        # Ubuntu platform is in one source
        self.assertEqual(0.5, confidence_scores["platforms.ubuntu"])
        
        # macOS platform is in one source
        self.assertEqual(0.5, confidence_scores["platforms.macos"])
    
    def test_apply_defaults(self):
        """Test applying defaults."""
        metadata = {
            "packages": {
                "default": {
                    "name": "nginx"
                }
            },
            "license": "BSD"
        }
        
        result = self.metadata_generator.apply_defaults(metadata)
        
        self.assertEqual("0.1", result["version"])
        self.assertEqual("nginx", result["packages"]["default"]["name"])
        self.assertEqual("latest", result["packages"]["default"]["version"])
        self.assertEqual("Default description for nginx", result["description"])
        self.assertEqual("BSD", result["license"])
    
    def test_merge_provider_data(self):
        """Test merging provider data."""
        base = {
            "version": "0.1",
            "packages": {
                "default": {
                    "name": "nginx",
                    "version": "latest"
                }
            },
            "description": "Default description for nginx"
        }
        
        provider_data = {
            "apt": {
                "package": {
                    "name": "nginx",
                    "version": "1.18.0"
                },
                "description": "High-performance HTTP server and reverse proxy",
                "license": "BSD",
                "urls": {
                    "website": "https://nginx.org",
                    "source": "https://nginx.org/download/nginx-1.18.0.tar.gz"
                },
                "platforms": ["linux", "debian", "ubuntu"]
            },
            "brew": {
                "package": {
                    "name": "nginx",
                    "version": "1.19.0"
                },
                "description": "HTTP server and reverse proxy",
                "license": "BSD",
                "urls": {
                    "website": "https://nginx.org",
                    "source": "https://nginx.org/download/nginx-1.19.0.tar.gz"
                },
                "platforms": ["macos", "linux"]
            }
        }
        
        result = self.metadata_generator.merge_provider_data(base, provider_data)
        
        self.assertEqual("0.1", result["version"])
        self.assertIn("apt", result["packages"])
        self.assertEqual("nginx", result["packages"]["apt"]["name"])
        self.assertEqual("1.18.0", result["packages"]["apt"]["version"])
        self.assertIn("brew", result["packages"])
        self.assertEqual("nginx", result["packages"]["brew"]["name"])
        self.assertEqual("1.19.0", result["packages"]["brew"]["version"])
        self.assertEqual("High-performance HTTP server and reverse proxy", result["description"])
        self.assertEqual("BSD", result["license"])
        self.assertEqual("https://nginx.org", result["urls"]["website"])
        self.assertEqual("https://nginx.org/download/nginx-1.18.0.tar.gz", result["urls"]["source"])
        self.assertIn("linux", result["platforms"])
        self.assertIn("debian", result["platforms"])
        self.assertIn("ubuntu", result["platforms"])
        self.assertIn("macos", result["platforms"])


if __name__ == "__main__":
    unittest.main()