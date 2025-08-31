"""
Tests for TemplateEngine override methods.

This module tests the new override-only functionality added to the TemplateEngine class.
"""

import os
import tempfile
import unittest
import yaml
from pathlib import Path
from unittest.mock import Mock, patch

from saidata_gen.generator.templates import TemplateEngine


class TestTemplateEngineOverrides(unittest.TestCase):
    """Test cases for TemplateEngine override methods."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test templates
        self.temp_dir = tempfile.TemporaryDirectory()
        self.templates_dir = Path(self.temp_dir.name)
        
        # Create test templates
        self._create_test_templates()
        
        # Initialize the template engine with the test templates
        self.engine = TemplateEngine(str(self.templates_dir))
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
    
    def _create_test_templates(self):
        """Create test templates in the temporary directory."""
        # Create providers directory
        providers_dir = self.templates_dir / "providers"
        providers_dir.mkdir(exist_ok=True)
        
        # Create default template
        default_template = {
            "version": "0.1",
            "packages": {
                "default": {
                    "name": "$software_name",
                    "version": "latest"
                }
            },
            "services": {
                "default": {
                    "name": "$software_name",
                    "enabled": False
                }
            },
            "directories": {
                "config": {
                    "path": "/etc/$software_name",
                    "owner": "root",
                    "group": "root",
                    "mode": "0755"
                }
            },
            "urls": {
                "website": None,
                "documentation": None
            },
            "platforms": ["linux"]
        }
        
        with open(self.templates_dir / "defaults.yaml", "w") as f:
            yaml.dump(default_template, f)
        
        # Create APT provider template (hierarchical)
        apt_dir = providers_dir / "apt"
        apt_dir.mkdir(exist_ok=True)
        
        apt_template = {
            "version": "0.1",
            "services": {
                "default": {
                    "enabled": True
                }
            },
            "directories": {
                "config": {
                    "mode": "0644"
                }
            },
            "urls": {
                "apt": "https://packages.ubuntu.com/search?keywords=$software_name"
            }
        }
        
        with open(apt_dir / "default.yaml", "w") as f:
            yaml.dump(apt_template, f)
        
        # Create Homebrew provider template (flat)
        brew_template = {
            "version": "0.1",
            "services": {
                "default": {
                    "enabled": True
                }
            },
            "urls": {
                "brew": "https://formulae.brew.sh/formula/$software_name"
            }
        }
        
        with open(providers_dir / "brew.yaml", "w") as f:
            yaml.dump(brew_template, f)
        
        # Create unsupported provider template
        unsupported_template = {
            "version": "0.1",
            "supported": False
        }
        
        with open(providers_dir / "unsupported.yaml", "w") as f:
            yaml.dump(unsupported_template, f)
    
    def test_apply_provider_overrides_only_supported_provider(self):
        """Test apply_provider_overrides_only with a supported provider."""
        # Test APT provider (hierarchical)
        apt_overrides = self.engine.apply_provider_overrides_only("nginx", "apt")
        
        self.assertEqual(apt_overrides["version"], "0.1")
        self.assertTrue(apt_overrides["services"]["default"]["enabled"])
        self.assertEqual(apt_overrides["directories"]["config"]["mode"], "0644")
        self.assertNotIn("supported", apt_overrides)
        
        # Test Homebrew provider (flat)
        brew_overrides = self.engine.apply_provider_overrides_only("nginx", "brew")
        
        self.assertEqual(brew_overrides["version"], "0.1")
        self.assertTrue(brew_overrides["services"]["default"]["enabled"])
        self.assertNotIn("supported", brew_overrides)
    
    def test_apply_provider_overrides_only_unsupported_provider(self):
        """Test apply_provider_overrides_only with an unsupported provider."""
        # Test explicitly unsupported provider
        unsupported_overrides = self.engine.apply_provider_overrides_only("nginx", "unsupported")
        
        self.assertEqual(unsupported_overrides["version"], "0.1")
        self.assertFalse(unsupported_overrides["supported"])
        
        # Test non-existent provider
        nonexistent_overrides = self.engine.apply_provider_overrides_only("nginx", "nonexistent")
        
        self.assertEqual(nonexistent_overrides["version"], "0.1")
        self.assertFalse(nonexistent_overrides["supported"])
    
    def test_apply_provider_overrides_only_with_repository_data(self):
        """Test apply_provider_overrides_only with repository data."""
        repo_data = {"name": "nginx", "version": "1.18.0", "description": "HTTP server"}
        
        # Should be supported with repository data
        overrides = self.engine.apply_provider_overrides_only("nginx", "apt", repo_data)
        
        self.assertEqual(overrides["version"], "0.1")
        self.assertNotIn("supported", overrides)
        self.assertTrue(overrides["services"]["default"]["enabled"])
    
    def test_apply_provider_overrides_only_supported_provider(self):
        """Test apply_provider_overrides_only with a supported provider."""
        # Test APT provider
        apt_overrides = self.engine.apply_provider_overrides_only("nginx", "apt")
        
        self.assertEqual(apt_overrides["version"], "0.1")
        self.assertNotIn("supported", apt_overrides)  # Should not include supported=True
        
        # Test Homebrew provider
        brew_overrides = self.engine.apply_provider_overrides_only("nginx", "brew")
        
        self.assertEqual(brew_overrides["version"], "0.1")
        self.assertNotIn("supported", brew_overrides)
    
    def test_apply_provider_overrides_only_unsupported_provider(self):
        """Test apply_provider_overrides_only with an unsupported provider."""
        # Test explicitly unsupported provider
        unsupported_overrides = self.engine.apply_provider_overrides_only("nginx", "unsupported")
        
        self.assertEqual(unsupported_overrides["version"], "0.1")
        self.assertFalse(unsupported_overrides["supported"])
        
        # Test non-existent provider
        nonexistent_overrides = self.engine.apply_provider_overrides_only("nginx", "nonexistent")
        
        self.assertEqual(nonexistent_overrides["version"], "0.1")
        self.assertFalse(nonexistent_overrides["supported"])
    
    def test_apply_provider_overrides_only_with_repository_data(self):
        """Test apply_provider_overrides_only with repository data."""
        repo_data = {"name": "nginx", "version": "1.18.0", "description": "HTTP server"}
        
        # Should be supported with repository data
        overrides = self.engine.apply_provider_overrides_only("nginx", "apt", repo_data)
        
        self.assertEqual(overrides["version"], "0.1")
        self.assertNotIn("supported", overrides)  # Should not include supported=True
    
    def test_merge_with_defaults(self):
        """Test merge_with_defaults method."""
        defaults = self.engine.default_template
        
        # Test merging with supported provider overrides
        apt_overrides = self.engine.apply_provider_overrides_only("nginx", "apt")
        merged = self.engine.merge_with_defaults(defaults, apt_overrides)
        
        # Check that defaults are preserved
        self.assertEqual(merged["packages"]["default"]["name"], "$software_name")
        self.assertEqual(merged["packages"]["default"]["version"], "latest")
        
        # Check that overrides are applied
        self.assertTrue(merged["services"]["default"]["enabled"])
        self.assertEqual(merged["directories"]["config"]["mode"], "0644")
        self.assertIn("apt", merged["urls"])
        
        # Check that null values are removed
        self.assertNotIn("website", merged["urls"])
        self.assertNotIn("documentation", merged["urls"])
        
        # Test merging with unsupported provider
        unsupported_overrides = {"version": "0.1", "supported": False}
        merged_unsupported = self.engine.merge_with_defaults(defaults, unsupported_overrides)
        
        self.assertEqual(merged_unsupported["version"], "0.1")
        self.assertFalse(merged_unsupported["supported"])
    
    def test_is_provider_supported_with_repository_data(self):
        """Test is_provider_supported with repository data."""
        # Test with non-empty repository data (should be supported)
        repo_data = {"name": "nginx", "version": "1.18.0"}
        self.assertTrue(self.engine.is_provider_supported("nginx", "apt", repo_data))
        
        # Test with empty repository data (should fall back to template check, which returns True for apt)
        empty_repo_data = {}
        self.assertTrue(self.engine.is_provider_supported("nginx", "apt", empty_repo_data))
        
        # Test with None repository data (should fall back to template check)
        self.assertTrue(self.engine.is_provider_supported("nginx", "apt", None))
    
    def test_is_provider_supported_template_based(self):
        """Test is_provider_supported based on template availability."""
        # Test with existing provider templates
        self.assertTrue(self.engine.is_provider_supported("nginx", "apt"))
        self.assertTrue(self.engine.is_provider_supported("nginx", "brew"))
        
        # Test with explicitly unsupported provider
        self.assertFalse(self.engine.is_provider_supported("nginx", "unsupported"))
        
        # Test with non-existent provider
        self.assertFalse(self.engine.is_provider_supported("nginx", "nonexistent"))
    
    def test_remove_null_values(self):
        """Test null value removal functionality."""
        test_data = {
            "version": "0.1",
            "packages": {
                "default": {
                    "name": "nginx",
                    "version": None,
                    "install_options": None
                }
            },
            "urls": {
                "website": None,
                "documentation": "https://nginx.org/docs",
                "source": None
            },
            "empty_dict": {},
            "empty_list": [],
            "null_value": None
        }
        
        cleaned = self.engine._remove_null_values(test_data)
        
        # Check that null values are removed
        self.assertNotIn("version", cleaned["packages"]["default"])
        self.assertNotIn("install_options", cleaned["packages"]["default"])
        self.assertNotIn("website", cleaned["urls"])
        self.assertNotIn("source", cleaned["urls"])
        self.assertNotIn("null_value", cleaned)
        self.assertNotIn("empty_dict", cleaned)
        
        # Check that non-null values are preserved
        self.assertEqual(cleaned["packages"]["default"]["name"], "nginx")
        self.assertEqual(cleaned["urls"]["documentation"], "https://nginx.org/docs")
        self.assertEqual(cleaned["empty_list"], [])  # Empty lists are preserved
    
    def test_enhanced_deep_merge(self):
        """Test enhanced deep merge functionality."""
        base = {
            "version": "0.1",
            "packages": {
                "default": {
                    "name": "base-name",
                    "version": "1.0"
                }
            },
            "services": {
                "default": {
                    "enabled": False,
                    "status": "stopped"
                }
            },
            "urls": {
                "website": "http://example.com",
                "documentation": "http://docs.example.com"
            }
        }
        
        overlay = {
            "packages": {
                "default": {
                    "version": "2.0"  # Override version
                }
            },
            "services": {
                "default": {
                    "enabled": True  # Override enabled
                }
            },
            "urls": {
                "website": None,  # Remove website
                "source": "http://source.example.com"  # Add source
            }
        }
        
        result = self.engine._enhanced_deep_merge(base, overlay)
        
        # Check that values are properly merged/overridden
        self.assertEqual(result["packages"]["default"]["name"], "base-name")  # Preserved
        self.assertEqual(result["packages"]["default"]["version"], "2.0")  # Overridden
        self.assertTrue(result["services"]["default"]["enabled"])  # Overridden
        self.assertEqual(result["services"]["default"]["status"], "stopped")  # Preserved
        self.assertNotIn("website", result["urls"])  # Removed by None value
        self.assertEqual(result["urls"]["documentation"], "http://docs.example.com")  # Preserved
        self.assertEqual(result["urls"]["source"], "http://source.example.com")  # Added
    
    def test_load_provider_template_hierarchical(self):
        """Test loading hierarchical provider templates."""
        # Test loading APT template (hierarchical structure)
        apt_template = self.engine._load_provider_template("apt")
        
        self.assertIsInstance(apt_template, dict)
        self.assertEqual(apt_template["version"], "0.1")
        self.assertTrue(apt_template["services"]["default"]["enabled"])
        self.assertIn("apt", apt_template["urls"])
    
    def test_load_provider_template_flat(self):
        """Test loading flat provider templates."""
        # Test loading Homebrew template (flat structure)
        brew_template = self.engine._load_provider_template("brew")
        
        self.assertIsInstance(brew_template, dict)
        self.assertEqual(brew_template["version"], "0.1")
        self.assertTrue(brew_template["services"]["default"]["enabled"])
        self.assertIn("brew", brew_template["urls"])
    
    def test_load_provider_template_nonexistent(self):
        """Test loading non-existent provider templates."""
        nonexistent_template = self.engine._load_provider_template("nonexistent")
        
        self.assertEqual(nonexistent_template, {})


if __name__ == "__main__":
    unittest.main()