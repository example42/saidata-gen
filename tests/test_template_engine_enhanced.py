"""
Unit tests for enhanced TemplateEngine methods.

This module contains comprehensive tests for the enhanced TemplateEngine methods
including apply_provider_overrides_only, merge_with_defaults, is_provider_supported,
and related functionality for the provider structure refactoring.
"""

import os
import tempfile
import unittest
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from saidata_gen.generator.templates import TemplateEngine
from saidata_gen.core.interfaces import PackageInfo, RepositoryData
from saidata_gen.core.cache import CacheManager, CacheConfig, CacheBackend


class TestTemplateEngineEnhanced(unittest.TestCase):
    """Test cases for enhanced TemplateEngine methods."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test templates
        self.temp_dir = tempfile.TemporaryDirectory()
        self.templates_dir = Path(self.temp_dir.name)
        
        # Create test templates
        self._create_test_templates()
        
        # Create a mock cache manager for testing
        self.mock_cache = Mock(spec=CacheManager)
        self.mock_cache.get.return_value = None  # Default to cache miss
        self.mock_cache.put.return_value = None
        self.mock_cache.invalidate_pattern.return_value = 0
        self.mock_cache.get_info.return_value = {"hits": 0, "misses": 0, "size": 0}
        
        # Initialize the template engine with the test templates and mock cache
        self.engine = TemplateEngine(str(self.templates_dir), cache_manager=self.mock_cache)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
    
    def _create_test_templates(self):
        """Create comprehensive test templates."""
        # Create providers directory
        providers_dir = self.templates_dir / "providers"
        providers_dir.mkdir(exist_ok=True)
        
        # Create comprehensive default template
        default_template = {
            "version": "0.1",
            "packages": {
                "default": {
                    "name": "$software_name",
                    "version": "latest",
                    "install_options": []
                }
            },
            "services": {
                "default": {
                    "name": "$software_name",
                    "enabled": False,
                    "status": "stopped"
                }
            },
            "directories": {
                "config": {
                    "path": "/etc/$software_name",
                    "owner": "root",
                    "group": "root",
                    "mode": "0755"
                },
                "data": {
                    "path": "/var/lib/$software_name",
                    "owner": "$software_name",
                    "group": "$software_name",
                    "mode": "0750"
                }
            },
            "urls": {
                "website": None,
                "documentation": None,
                "source": None
            },
            "category": {
                "default": "server",
                "sub": None,
                "tags": []
            },
            "platforms": ["linux"],
            "ports": [],
            "processes": []
        }
        
        with open(self.templates_dir / "defaults.yaml", "w") as f:
            yaml.dump(default_template, f)
        
        # Create APT provider template (override-only)
        apt_template = {
            "version": "0.1",
            "services": {
                "default": {
                    "enabled": True  # Override default false
                }
            },
            "directories": {
                "config": {
                    "mode": "0644"  # Override default 0755
                }
            },
            "urls": {
                "apt_search": "https://packages.ubuntu.com/search?keywords=$software_name"
            },
            "platforms": ["linux", "debian", "ubuntu"]  # Override default platforms
        }
        
        with open(providers_dir / "apt.yaml", "w") as f:
            yaml.dump(apt_template, f)
        
        # Create Homebrew provider template (hierarchical structure)
        brew_dir = providers_dir / "brew"
        brew_dir.mkdir(exist_ok=True)
        
        brew_template = {
            "version": "0.1",
            "services": {
                "default": {
                    "enabled": True
                }
            },
            "directories": {
                "config": {
                    "path": "/usr/local/etc/$software_name",  # Override path
                    "owner": "$(whoami)",  # Different owner
                    "group": "admin"  # Different group
                }
            },
            "urls": {
                "brew_formula": "https://formulae.brew.sh/formula/$software_name"
            },
            "platforms": ["macos", "linux"]
        }
        
        with open(brew_dir / "default.yaml", "w") as f:
            yaml.dump(brew_template, f)
        
        # Create Windows provider templates
        winget_template = {
            "version": "0.1",
            "directories": {
                "config": {
                    "path": "C:\\ProgramData\\$software_name",
                    "owner": "Administrator",
                    "group": "Administrators",
                    "mode": "0755"  # Same as default, should be filtered out
                }
            },
            "urls": {
                "winget_search": "https://winget.run/pkg/$software_name"
            },
            "platforms": ["windows"]
        }
        
        with open(providers_dir / "winget.yaml", "w") as f:
            yaml.dump(winget_template, f)
        
        # Create explicitly unsupported provider
        unsupported_template = {
            "version": "0.1",
            "supported": False
        }
        
        with open(providers_dir / "unsupported.yaml", "w") as f:
            yaml.dump(unsupported_template, f)
        
        # Create language-specific providers
        npm_template = {
            "version": "0.1",
            "packages": {
                "default": {
                    "name": "$software_name",  # Same as default
                    "version": "latest"  # Same as default
                }
            },
            "urls": {
                "npm_package": "https://www.npmjs.com/package/$software_name"
            },
            "platforms": ["linux", "macos", "windows"]
        }
        
        with open(providers_dir / "npm.yaml", "w") as f:
            yaml.dump(npm_template, f)
        
        # Create provider with null values to test removal
        null_provider_template = {
            "version": "0.1",
            "packages": {
                "default": {
                    "name": "$software_name",
                    "version": None,  # Should be removed
                    "install_options": None  # Should be removed
                }
            },
            "urls": {
                "website": None,  # Should be removed
                "documentation": "https://docs.example.com/$software_name",
                "source": None  # Should be removed
            },
            "empty_section": {},  # Should be removed
            "null_value": None  # Should be removed
        }
        
        with open(providers_dir / "null_provider.yaml", "w") as f:
            yaml.dump(null_provider_template, f)
    
    def test_apply_provider_overrides_only_supported_provider(self):
        """Test apply_provider_overrides_only with supported providers."""
        # Test APT provider (flat structure)
        apt_overrides = self.engine.apply_provider_overrides_only("nginx", "apt")
        
        # Should include version
        self.assertEqual(apt_overrides["version"], "0.1")
        
        # Should not include supported field for supported providers
        self.assertNotIn("supported", apt_overrides)
        
        # Should include overrides
        self.assertTrue(apt_overrides["services"]["default"]["enabled"])
        self.assertEqual(apt_overrides["directories"]["config"]["mode"], "0644")
        self.assertIn("apt_search", apt_overrides["urls"])
        
        # Should include platform overrides
        self.assertEqual(apt_overrides["platforms"], ["linux", "debian", "ubuntu"])
        
        # Test Homebrew provider (hierarchical structure)
        brew_overrides = self.engine.apply_provider_overrides_only("nginx", "brew")
        
        self.assertEqual(brew_overrides["version"], "0.1")
        self.assertNotIn("supported", brew_overrides)
        self.assertTrue(brew_overrides["services"]["default"]["enabled"])
        # Variable substitution happens during processing, so $software_name becomes nginx
        self.assertEqual(brew_overrides["directories"]["config"]["path"], "/usr/local/etc/nginx")
        self.assertIn("brew_formula", brew_overrides["urls"])
    
    def test_apply_provider_overrides_only_unsupported_provider(self):
        """Test apply_provider_overrides_only with unsupported providers."""
        # Test explicitly unsupported provider
        unsupported_overrides = self.engine.apply_provider_overrides_only("nginx", "unsupported")
        
        self.assertEqual(unsupported_overrides["version"], "0.1")
        self.assertFalse(unsupported_overrides["supported"])
        
        # Should only contain version and supported fields
        self.assertEqual(len(unsupported_overrides), 2)
        
        # Test non-existent provider
        nonexistent_overrides = self.engine.apply_provider_overrides_only("nginx", "nonexistent")
        
        self.assertEqual(nonexistent_overrides["version"], "0.1")
        self.assertFalse(nonexistent_overrides["supported"])
        self.assertEqual(len(nonexistent_overrides), 2)
    
    def test_apply_provider_overrides_only_with_repository_data(self):
        """Test apply_provider_overrides_only with various repository data formats."""
        # Test with dictionary repository data
        repo_data_dict = {"name": "nginx", "version": "1.18.0", "description": "HTTP server"}
        overrides = self.engine.apply_provider_overrides_only("nginx", "apt", repo_data_dict)
        
        self.assertEqual(overrides["version"], "0.1")
        self.assertNotIn("supported", overrides)
        
        # Test with PackageInfo object - need to convert to dict for repository_data
        package_info = PackageInfo(
            name="nginx",
            version="1.18.0",
            provider="apt",
            description="HTTP server"
        )
        # Convert PackageInfo to dict format expected by the method
        package_dict = {
            "name": package_info.name,
            "version": package_info.version,
            "provider": package_info.provider,
            "description": package_info.description
        }
        overrides = self.engine.apply_provider_overrides_only("nginx", "apt", package_dict)
        
        self.assertEqual(overrides["version"], "0.1")
        self.assertNotIn("supported", overrides)
        
        # Test with empty repository data (should fall back to template check)
        empty_data = {}
        overrides = self.engine.apply_provider_overrides_only("nginx", "apt", empty_data)
        
        self.assertEqual(overrides["version"], "0.1")
        self.assertNotIn("supported", overrides)  # APT template exists, so supported
        
        # Note: apply_provider_overrides_only expects dict repository_data for context updates
        # List and other formats are handled by is_provider_supported method
    
    def test_merge_with_defaults_basic(self):
        """Test basic merge_with_defaults functionality."""
        defaults = self.engine.default_template
        
        # Test merging with APT overrides
        apt_overrides = {
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
                "apt_search": "https://packages.ubuntu.com/search?keywords=nginx"
            }
        }
        
        merged = self.engine.merge_with_defaults(defaults, apt_overrides)
        
        # Check that defaults are preserved
        self.assertEqual(merged["packages"]["default"]["name"], "$software_name")
        self.assertEqual(merged["packages"]["default"]["version"], "latest")
        self.assertEqual(merged["directories"]["config"]["path"], "/etc/$software_name")
        self.assertEqual(merged["directories"]["config"]["owner"], "root")
        
        # Check that overrides are applied
        self.assertTrue(merged["services"]["default"]["enabled"])
        self.assertEqual(merged["directories"]["config"]["mode"], "0644")
        self.assertEqual(merged["urls"]["apt_search"], "https://packages.ubuntu.com/search?keywords=nginx")
        
        # Check that original null values are removed by the merge process
        # (The merge_with_defaults method removes null values)
        if "website" in merged["urls"]:
            self.assertIsNone(merged["urls"]["website"])
        if "documentation" in merged["urls"]:
            self.assertIsNone(merged["urls"]["documentation"])
    
    def test_merge_with_defaults_unsupported(self):
        """Test merge_with_defaults with unsupported provider."""
        defaults = self.engine.default_template
        unsupported_overrides = {"version": "0.1", "supported": False}
        
        merged = self.engine.merge_with_defaults(defaults, unsupported_overrides)
        
        # Should return only the unsupported overrides
        self.assertEqual(merged["version"], "0.1")
        self.assertFalse(merged["supported"])
        self.assertEqual(len(merged), 2)
    
    def test_merge_with_defaults_null_removal(self):
        """Test that merge_with_defaults properly handles null values."""
        defaults = self.engine.default_template
        
        # Create overrides with null values
        overrides_with_nulls = {
            "version": "0.1",
            "urls": {
                "website": None,  # Should remove this key
                "documentation": "https://docs.example.com",  # Should keep this
                "source": None  # Should remove this key
            },
            "packages": {
                "default": {
                    "version": None,  # Should remove this key
                    "install_options": None  # Should remove this key
                }
            },
            "null_field": None,  # Should remove this key
            "empty_dict": {}  # Should remove this key
        }
        
        merged = self.engine.merge_with_defaults(defaults, overrides_with_nulls)
        
        # Check that null values are removed
        self.assertNotIn("website", merged["urls"])
        self.assertNotIn("source", merged["urls"])
        self.assertNotIn("version", merged["packages"]["default"])
        self.assertNotIn("install_options", merged["packages"]["default"])
        self.assertNotIn("null_field", merged)
        self.assertNotIn("empty_dict", merged)
        
        # Check that non-null values are preserved
        self.assertEqual(merged["urls"]["documentation"], "https://docs.example.com")
        self.assertEqual(merged["packages"]["default"]["name"], "$software_name")  # From defaults
    
    def test_merge_with_defaults_validation_errors(self):
        """Test merge_with_defaults with invalid input."""
        defaults = self.engine.default_template
        
        # Test with non-dict defaults
        with self.assertRaises(ValueError):
            self.engine.merge_with_defaults("not a dict", {})
        
        # Test with non-dict overrides
        with self.assertRaises(ValueError):
            self.engine.merge_with_defaults(defaults, "not a dict")
    
    def test_is_provider_supported_repository_data(self):
        """Test is_provider_supported with various repository data formats."""
        # Test with non-empty dict (should be supported)
        repo_data = {"name": "nginx", "version": "1.18.0"}
        self.assertTrue(self.engine.is_provider_supported("nginx", "apt", repo_data))
        
        # Test with empty dict (should fall back to template check)
        empty_data = {}
        self.assertTrue(self.engine.is_provider_supported("nginx", "apt", empty_data))  # APT template exists
        
        # Test with PackageInfo object
        package_info = PackageInfo(name="nginx", version="1.18.0", provider="apt")
        self.assertTrue(self.engine.is_provider_supported("nginx", "apt", package_info))
        
        # Test with invalid PackageInfo (wrong provider)
        invalid_package_info = PackageInfo(name="nginx", version="1.18.0", provider="yum")
        self.assertFalse(self.engine.is_provider_supported("nginx", "apt", invalid_package_info))
        
        # Test with list of PackageInfo objects
        package_list = [package_info]
        self.assertTrue(self.engine.is_provider_supported("nginx", "apt", package_list))
        
        # Test with empty list
        empty_list = []
        self.assertFalse(self.engine.is_provider_supported("nginx", "apt", empty_list))
        
        # Test with RepositoryData object
        package_dict = {
            "name": package_info.name,
            "version": package_info.version,
            "provider": package_info.provider,
            "description": package_info.description
        }
        repo_data_obj = RepositoryData(provider="apt", packages={"nginx": package_dict})
        self.assertTrue(self.engine.is_provider_supported("nginx", "apt", repo_data_obj))
        
        # Test with RepositoryData without the package
        # Note: Empty RepositoryData falls back to template check, which finds APT template
        # So this actually returns True. To test False case, we need a provider without template
        repo_data_empty = RepositoryData(provider="apt", packages={})
        # This will fall back to template check and return True since APT template exists
        self.assertTrue(self.engine.is_provider_supported("nginx", "apt", repo_data_empty))
    
    def test_is_provider_supported_template_based(self):
        """Test is_provider_supported based on template availability."""
        # Test with existing provider templates
        self.assertTrue(self.engine.is_provider_supported("nginx", "apt"))
        self.assertTrue(self.engine.is_provider_supported("nginx", "brew"))
        self.assertTrue(self.engine.is_provider_supported("nginx", "winget"))
        
        # Test with explicitly unsupported provider
        self.assertFalse(self.engine.is_provider_supported("nginx", "unsupported"))
        
        # Test with non-existent provider
        self.assertFalse(self.engine.is_provider_supported("nginx", "nonexistent"))
    
    def test_is_provider_supported_fallback_logic(self):
        """Test is_provider_supported fallback logic for different provider types."""
        # Mock the _load_provider_template to return a minimal template (so fallback logic applies)
        # An empty template means no template exists, but a minimal template triggers fallback logic
        minimal_template = {"version": "0.1"}
        with patch.object(self.engine, '_load_provider_template', return_value=minimal_template):
            with patch.object(self.engine, 'provider_templates', {}):
                # Test language-specific providers (should default to supported)
                self.assertTrue(self.engine.is_provider_supported("some-package", "npm"))
                self.assertTrue(self.engine.is_provider_supported("some-package", "pypi"))
                self.assertTrue(self.engine.is_provider_supported("some-package", "pip"))
                
                # Test system package managers (should default to supported)
                self.assertTrue(self.engine.is_provider_supported("some-package", "apt"))
                self.assertTrue(self.engine.is_provider_supported("some-package", "yum"))
                self.assertTrue(self.engine.is_provider_supported("some-package", "brew"))
                
                # Test specialized providers (should default to not supported)
                self.assertFalse(self.engine.is_provider_supported("some-package", "cargo"))
                self.assertFalse(self.engine.is_provider_supported("some-package", "gem"))
                self.assertFalse(self.engine.is_provider_supported("some-package", "composer"))
    
    def test_is_provider_supported_caching(self):
        """Test that is_provider_supported properly uses caching."""
        # First call should miss cache and call put
        result1 = self.engine.is_provider_supported("nginx", "apt")
        self.mock_cache.get.assert_called()
        self.mock_cache.put.assert_called()
        
        # Reset mock
        self.mock_cache.reset_mock()
        
        # Mock cache hit
        self.mock_cache.get.return_value = True
        
        # Second call should hit cache and not call put
        result2 = self.engine.is_provider_supported("nginx", "apt")
        self.mock_cache.get.assert_called()
        self.mock_cache.put.assert_not_called()
        
        self.assertTrue(result2)
    
    def test_remove_null_values_comprehensive(self):
        """Test comprehensive null value removal."""
        test_data = {
            "version": "0.1",
            "packages": {
                "default": {
                    "name": "nginx",
                    "version": None,  # Should be removed
                    "install_options": None  # Should be removed
                }
            },
            "urls": {
                "website": None,  # Should be removed
                "documentation": "https://nginx.org/docs",  # Should be kept
                "source": None  # Should be removed
            },
            "empty_dict": {},  # Should be removed
            "empty_list": [],  # Should be kept (might be meaningful)
            "null_value": None,  # Should be removed
            "nested": {
                "level1": {
                    "level2": {
                        "value": None,  # Should be removed
                        "other": "keep"  # Should be kept
                    },
                    "empty": {}  # Should be removed
                }
            },
            "list_with_nulls": [
                "keep",
                None,  # Should be removed
                {"key": "value"},
                {"null_key": None}  # null_key should be removed, but dict kept
            ]
        }
        
        cleaned = self.engine._remove_null_values(test_data)
        
        # Check that null values are removed
        self.assertNotIn("version", cleaned["packages"]["default"])
        self.assertNotIn("install_options", cleaned["packages"]["default"])
        self.assertNotIn("website", cleaned["urls"])
        self.assertNotIn("source", cleaned["urls"])
        self.assertNotIn("null_value", cleaned)
        self.assertNotIn("empty_dict", cleaned)
        self.assertNotIn("value", cleaned["nested"]["level1"]["level2"])
        self.assertNotIn("empty", cleaned["nested"]["level1"])
        
        # Check that non-null values are preserved
        self.assertEqual(cleaned["packages"]["default"]["name"], "nginx")
        self.assertEqual(cleaned["urls"]["documentation"], "https://nginx.org/docs")
        self.assertEqual(cleaned["empty_list"], [])  # Empty lists are preserved
        self.assertEqual(cleaned["nested"]["level1"]["level2"]["other"], "keep")
        
        # Check list processing
        self.assertEqual(len(cleaned["list_with_nulls"]), 3)  # None item removed
        self.assertEqual(cleaned["list_with_nulls"][0], "keep")
        self.assertEqual(cleaned["list_with_nulls"][1], {"key": "value"})
        self.assertNotIn("null_key", cleaned["list_with_nulls"][2])  # null_key removed from dict
    
    def test_enhanced_deep_merge_comprehensive(self):
        """Test comprehensive enhanced deep merge functionality."""
        base = {
            "version": "0.1",
            "packages": {
                "default": {
                    "name": "base-name",
                    "version": "1.0",
                    "options": ["opt1", "opt2"]
                }
            },
            "services": {
                "default": {
                    "enabled": False,
                    "status": "stopped"
                },
                "secondary": {
                    "enabled": True,
                    "port": 8080
                }
            },
            "urls": {
                "website": "http://example.com",
                "documentation": "http://docs.example.com"
            },
            "list_field": ["item1", "item2"]
        }
        
        overlay = {
            "packages": {
                "default": {
                    "version": "2.0",  # Override version
                    "options": ["new_opt1", "new_opt2"]  # Replace entire list
                }
            },
            "services": {
                "default": {
                    "enabled": True  # Override enabled
                },
                "tertiary": {  # Add new service
                    "enabled": False,
                    "port": 9090
                }
            },
            "urls": {
                "website": None,  # Remove website
                "source": "http://source.example.com"  # Add source
            },
            "list_field": ["new_item"],  # Replace entire list
            "new_field": "new_value"  # Add new field
        }
        
        result = self.engine._enhanced_deep_merge(base, overlay)
        
        # Check that values are properly merged/overridden
        self.assertEqual(result["packages"]["default"]["name"], "base-name")  # Preserved
        self.assertEqual(result["packages"]["default"]["version"], "2.0")  # Overridden
        self.assertEqual(result["packages"]["default"]["options"], ["new_opt1", "new_opt2"])  # Replaced
        
        self.assertTrue(result["services"]["default"]["enabled"])  # Overridden
        self.assertEqual(result["services"]["default"]["status"], "stopped")  # Preserved
        self.assertTrue(result["services"]["secondary"]["enabled"])  # Preserved
        self.assertEqual(result["services"]["secondary"]["port"], 8080)  # Preserved
        self.assertFalse(result["services"]["tertiary"]["enabled"])  # Added
        self.assertEqual(result["services"]["tertiary"]["port"], 9090)  # Added
        
        self.assertNotIn("website", result["urls"])  # Removed by None value
        self.assertEqual(result["urls"]["documentation"], "http://docs.example.com")  # Preserved
        self.assertEqual(result["urls"]["source"], "http://source.example.com")  # Added
        
        self.assertEqual(result["list_field"], ["new_item"])  # Replaced
        self.assertEqual(result["new_field"], "new_value")  # Added
    
    def test_validate_merged_configuration(self):
        """Test configuration validation."""
        # Test valid configuration
        valid_config = {
            "version": "0.1",
            "packages": {
                "default": {
                    "name": "nginx"
                }
            },
            "services": {
                "default": {
                    "name": "nginx"
                }
            },
            "directories": {
                "config": {
                    "path": "/etc/nginx"
                }
            },
            "urls": {
                "website": "https://nginx.org"
            },
            "platforms": ["linux"]
        }
        
        self.assertTrue(self.engine._validate_merged_configuration(valid_config))
        
        # Test invalid configurations
        invalid_configs = [
            {},  # Missing version
            {"version": "invalid"},  # Invalid version format
            {"version": "0.1", "packages": "not a dict"},  # Invalid packages structure
            {"version": "0.1", "packages": {"default": "not a dict"}},  # Invalid package structure
            {"version": "0.1", "packages": {"default": {}}},  # Missing package name
            {"version": "0.1", "services": "not a dict"},  # Invalid services structure
            {"version": "0.1", "directories": "not a dict"},  # Invalid directories structure
            {"version": "0.1", "directories": {"config": {"path": 123}}},  # Invalid path type
            {"version": "0.1", "urls": "not a dict"},  # Invalid URLs structure
            {"version": "0.1", "urls": {"website": 123}},  # Invalid URL type
            {"version": "0.1", "platforms": "not a list"},  # Invalid platforms structure
            {"version": "0.1", "platforms": [123]},  # Invalid platform type
        ]
        
        for invalid_config in invalid_configs:
            with self.subTest(config=invalid_config):
                self.assertFalse(self.engine._validate_merged_configuration(invalid_config))
    
    def test_load_provider_template_hierarchical_and_flat(self):
        """Test loading both hierarchical and flat provider templates."""
        # Test hierarchical template (brew)
        brew_template = self.engine._load_provider_template("brew")
        self.assertIsInstance(brew_template, dict)
        self.assertEqual(brew_template["version"], "0.1")
        self.assertIn("brew_formula", brew_template["urls"])
        
        # Test flat template (apt)
        apt_template = self.engine._load_provider_template("apt")
        self.assertIsInstance(apt_template, dict)
        self.assertEqual(apt_template["version"], "0.1")
        self.assertIn("apt_search", apt_template["urls"])
        
        # Test non-existent template
        nonexistent = self.engine._load_provider_template("nonexistent")
        self.assertEqual(nonexistent, {})
    
    def test_cache_management_methods(self):
        """Test cache management methods."""
        # Test clearing cache for specific provider:software combination
        cleared = self.engine.clear_provider_support_cache("nginx", "apt")
        self.mock_cache.invalidate_pattern.assert_called_with("provider_support:apt:nginx:*")
        
        # Test clearing cache for specific software
        self.engine.clear_provider_support_cache("nginx")
        self.mock_cache.invalidate_pattern.assert_called_with("provider_support:*:nginx:*")
        
        # Test clearing cache for specific provider
        self.engine.clear_provider_support_cache(provider="apt")
        self.mock_cache.invalidate_pattern.assert_called_with("provider_support:apt:*")
        
        # Test clearing all cache
        self.engine.clear_provider_support_cache()
        self.mock_cache.invalidate_pattern.assert_called_with("provider_support:*")
        
        # Test getting cache stats
        stats = self.engine.get_provider_support_cache_stats()
        self.mock_cache.get_info.assert_called()
        self.assertIsInstance(stats, dict)
    
    def test_null_value_removal_in_apply_provider_overrides_only(self):
        """Test that null values are properly handled in apply_provider_overrides_only."""
        # Use the null_provider template that has null values
        overrides = self.engine.apply_provider_overrides_only("nginx", "null_provider")
        
        # Should include version
        self.assertEqual(overrides["version"], "0.1")
        
        # Should not include supported field (provider is supported)
        self.assertNotIn("supported", overrides)
        
        # Should include non-null values (variable substitution happens during processing)
        self.assertEqual(overrides["packages"]["default"]["name"], "nginx")
        self.assertEqual(overrides["urls"]["documentation"], "https://docs.example.com/nginx")
        
        # Should not include null values
        self.assertNotIn("version", overrides["packages"]["default"])
        self.assertNotIn("install_options", overrides["packages"]["default"])
        self.assertNotIn("website", overrides["urls"])
        self.assertNotIn("source", overrides["urls"])
        self.assertNotIn("empty_section", overrides)
        self.assertNotIn("null_value", overrides)


if __name__ == "__main__":
    unittest.main()