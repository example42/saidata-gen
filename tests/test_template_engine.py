"""
Unit tests for the template engine.

This module contains tests for the template engine, including variable substitution,
conditional logic, provider overrides, and template includes.
"""

import os
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Any

import yaml

from saidata_gen.generator.templates import TemplateEngine


class TestTemplateEngine(unittest.TestCase):
    """Test cases for the template engine."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test templates
        self.temp_dir = tempfile.TemporaryDirectory()
        self.templates_dir = Path(self.temp_dir.name)
        
        # Create test templates
        self._create_test_templates()
        
        # Create template engine with test templates
        self.engine = TemplateEngine(str(self.templates_dir))
    
    def tearDown(self):
        """Tear down test fixtures."""
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
            "urls": {},
            "category": {
                "default": None,
                "sub": None,
                "tags": []
            },
            "platforms": []
        }
        
        with open(self.templates_dir / "defaults.yaml", "w") as f:
            yaml.dump(default_template, f)
        
        # Create apt provider template
        apt_template = {
            "packages": {
                "apt": {
                    "name": "$software_name",
                    "version": "latest"
                }
            },
            "services": {
                "default": {
                    "name": "$software_name",
                    "enabled": True
                }
            },
            "$if: current_provider == 'apt'": {
                "platforms": ["linux", "debian", "ubuntu"]
            },
            "$provider_override: urls.website": "https://packages.debian.org/$software_name"
        }
        
        with open(providers_dir / "apt.yaml", "w") as f:
            yaml.dump(apt_template, f)
        
        # Create brew provider template
        brew_template = {
            "packages": {
                "brew": {
                    "name": "$software_name",
                    "version": "latest"
                }
            },
            "$platform: macos": {
                "directories": {
                    "config": {
                        "path": "/usr/local/etc/$software_name",
                        "owner": "${current_user | root}",
                        "group": "admin"
                    }
                }
            },
            "$platform: linux": {
                "directories": {
                    "config": {
                        "path": "/home/linuxbrew/.linuxbrew/etc/$software_name",
                        "owner": "${current_user | root}",
                        "group": "${current_user | root}"
                    }
                }
            },
            "$include: common_urls": {}
        }
        
        with open(providers_dir / "brew.yaml", "w") as f:
            yaml.dump(brew_template, f)
        
        # Create winget provider template with loops and functions
        winget_template = {
            "packages": {
                "winget": {
                    "name": "$software_name",
                    "version": "latest"
                }
            },
            "$for: platform in platforms": {
                "platform_${platform}": {
                    "supported": True
                }
            },
            "$function: lower(software_name)": "lowercase_name",
            "directories": {
                "config": {
                    "path": "C:\\ProgramData\\$software_name",
                    "owner": "Administrator",
                    "group": "Administrators"
                }
            },
            "platforms": ["windows"]
        }
        
        with open(providers_dir / "winget.yaml", "w") as f:
            yaml.dump(winget_template, f)
        
        # Create common_urls template for inclusion
        common_urls = {
            "urls": {
                "documentation": "https://docs.example.com/$software_name",
                "issues": "https://github.com/example/$software_name/issues",
                "source": "https://github.com/example/$software_name"
            }
        }
        
        with open(self.templates_dir / "common_urls.yaml", "w") as f:
            yaml.dump(common_urls, f)
    
    def test_variable_substitution(self):
        """Test variable substitution in templates."""
        result = self.engine.apply_template("nginx", context={"current_user": "testuser"})
        
        # Check simple variable substitution
        self.assertEqual(result["packages"]["default"]["name"], "nginx")
        self.assertEqual(result["services"]["default"]["name"], "nginx")
        self.assertEqual(result["directories"]["config"]["path"], "/etc/nginx")
    
    def test_provider_specific_templates(self):
        """Test provider-specific templates."""
        result = self.engine.apply_template("nginx", providers=["apt"])
        
        # Check that apt-specific values are applied
        self.assertIn("apt", result["packages"])
        self.assertEqual(result["packages"]["apt"]["name"], "nginx")
        self.assertTrue(result["services"]["default"]["enabled"])
        self.assertIn("website", result["urls"])
        self.assertEqual(result["urls"]["website"], "https://packages.debian.org/nginx")
    
    def test_conditional_logic(self):
        """Test conditional logic in templates."""
        # Test with apt provider
        result = self.engine.apply_template("nginx", providers=["apt"])
        self.assertIn("platforms", result)
        self.assertIn("linux", result["platforms"])
        self.assertIn("debian", result["platforms"])
        
        # Test with brew provider (no conditional platforms)
        result = self.engine.apply_template("nginx", providers=["brew"])
        self.assertNotIn("linux", result.get("platforms", []))
    
    def test_platform_specific_templates(self):
        """Test platform-specific templates."""
        # Test with macos platform
        result = self.engine.apply_template(
            "nginx", 
            providers=["brew"], 
            platforms=["macos"],
            context={"current_user": "testuser"}
        )
        
        self.assertEqual(result["directories"]["config"]["path"], "/usr/local/etc/nginx")
        self.assertEqual(result["directories"]["config"]["owner"], "testuser")
        self.assertEqual(result["directories"]["config"]["group"], "admin")
        
        # Test with linux platform
        result = self.engine.apply_template(
            "nginx", 
            providers=["brew"], 
            platforms=["linux"],
            context={"current_user": "testuser"}
        )
        
        self.assertEqual(result["directories"]["config"]["path"], "/home/linuxbrew/.linuxbrew/etc/nginx")
        self.assertEqual(result["directories"]["config"]["owner"], "testuser")
        self.assertEqual(result["directories"]["config"]["group"], "testuser")
    
    def test_provider_overrides(self):
        """Test provider overrides."""
        result = self.engine.apply_template("nginx", providers=["apt"])
        
        # Check that the provider override was applied
        self.assertEqual(result["urls"]["website"], "https://packages.debian.org/nginx")
    
    def test_template_includes(self):
        """Test template includes."""
        result = self.engine.apply_template("nginx", providers=["brew"])
        
        # Check that the included template was applied
        self.assertEqual(result["urls"]["documentation"], "https://docs.example.com/nginx")
        self.assertEqual(result["urls"]["issues"], "https://github.com/example/nginx/issues")
        self.assertEqual(result["urls"]["source"], "https://github.com/example/nginx")
    
    def test_complex_variable_substitution(self):
        """Test complex variable substitution with defaults."""
        # Test with current_user provided
        result = self.engine.apply_template(
            "nginx", 
            providers=["brew"], 
            platforms=["macos"],
            context={"current_user": "testuser"}
        )
        
        self.assertEqual(result["directories"]["config"]["owner"], "testuser")
        
        # Test with no current_user (should use default)
        result = self.engine.apply_template(
            "nginx", 
            providers=["brew"], 
            platforms=["macos"]
        )
        
        self.assertEqual(result["directories"]["config"]["owner"], "root")
    
    def test_condition_evaluation(self):
        """Test condition evaluation."""
        # Test simple equality
        self.assertTrue(self.engine.evaluate_condition("value == 'test'", {"value": "test"}))
        self.assertFalse(self.engine.evaluate_condition("value == 'test'", {"value": "other"}))
        
        # Test inequality
        self.assertTrue(self.engine.evaluate_condition("value != 'test'", {"value": "other"}))
        self.assertFalse(self.engine.evaluate_condition("value != 'test'", {"value": "test"}))
        
        # Test in operator
        self.assertTrue(self.engine.evaluate_condition("value in list", {"value": "test", "list": ["test", "other"]}))
        self.assertFalse(self.engine.evaluate_condition("value in list", {"value": "missing", "list": ["test", "other"]}))
        
        # Test not in operator with string literals
        self.assertTrue(self.engine.evaluate_condition("value not in ['test', 'other']", {"value": "missing"}))
        self.assertFalse(self.engine.evaluate_condition("value not in ['test', 'other']", {"value": "test"}))
        
        # Test exists
        self.assertTrue(self.engine.evaluate_condition("exists value", {"value": "test"}))
        self.assertFalse(self.engine.evaluate_condition("exists missing", {"value": "test"}))
        
        # Test boolean values
        self.assertTrue(self.engine.evaluate_condition("true", {}))
        self.assertFalse(self.engine.evaluate_condition("false", {}))
        
        # Test complex conditions
        self.assertTrue(self.engine.evaluate_condition("value == 'test' and other == 'yes'", {"value": "test", "other": "yes"}))
        self.assertFalse(self.engine.evaluate_condition("value == 'test' and other == 'yes'", {"value": "test", "other": "no"}))
        self.assertTrue(self.engine.evaluate_condition("value == 'test' or other == 'yes'", {"value": "test", "other": "no"}))
        self.assertTrue(self.engine.evaluate_condition("not value == 'other'", {"value": "test"}))
    
    def test_nested_value_access(self):
        """Test nested value access."""
        context = {
            "user": {
                "name": "test",
                "roles": ["admin", "user"],
                "settings": {
                    "theme": "dark"
                }
            },
            "items": [
                {"id": 1, "name": "first"},
                {"id": 2, "name": "second"}
            ]
        }
        
        # Test simple nested access
        self.assertEqual(self.engine._get_nested_value(context, "user.name"), "test")
        self.assertEqual(self.engine._get_nested_value(context, "user.settings.theme"), "dark")
        
        # Test array access
        self.assertEqual(self.engine._get_nested_value(context, "user.roles[0]"), "admin")
        self.assertEqual(self.engine._get_nested_value(context, "items[1].name"), "second")
        
        # Test missing values
        self.assertIsNone(self.engine._get_nested_value(context, "user.missing"))
        self.assertIsNone(self.engine._get_nested_value(context, "user.roles[5]"))
    
    def test_loop_processing(self):
        """Test loop processing in templates."""
        # Test with winget provider that has loops
        result = self.engine.apply_template(
            "nginx", 
            providers=["winget"], 
            platforms=["windows", "macos", "linux"]
        )
        
        # Check that the loop was processed
        self.assertIn("platform_windows", result)
        self.assertIn("platform_macos", result)
        self.assertIn("platform_linux", result)
        self.assertTrue(result["platform_windows"]["supported"])
        self.assertTrue(result["platform_macos"]["supported"])
        self.assertTrue(result["platform_linux"]["supported"])
    
    def test_function_calls(self):
        """Test function calls in templates."""
        # Test with winget provider that has function calls
        result = self.engine.apply_template("Nginx", providers=["winget"])
        
        # Check that the function was called
        self.assertEqual(result["lowercase_name"], "nginx")
    
    def test_custom_function_registration(self):
        """Test registering custom functions."""
        # Register a custom function
        self.engine.register_function("reverse", lambda s: s[::-1])
        
        # Create a template with the custom function
        template = {
            "$function: reverse(software_name)": "reversed_name"
        }
        
        # Apply the template
        result = self.engine._process_template(template, {"software_name": "nginx"})
        
        # Check that the function was called
        self.assertEqual(result["reversed_name"], "xnign")
    
    def test_parse_value(self):
        """Test parsing values from templates."""
        context = {"var": "test", "num": 42}
        
        # Test variable reference
        self.assertEqual(self.engine._parse_value("$var", context), "test")
        
        # Test string literals
        self.assertEqual(self.engine._parse_value('"hello"', context), "hello")
        self.assertEqual(self.engine._parse_value("'world'", context), "world")
        
        # Test numbers
        self.assertEqual(self.engine._parse_value("123", context), 123)
        self.assertEqual(self.engine._parse_value("3.14", context), 3.14)
        
        # Test booleans
        self.assertEqual(self.engine._parse_value("true", context), True)
        self.assertEqual(self.engine._parse_value("false", context), False)
        
        # Test None/null
        self.assertIsNone(self.engine._parse_value("null", context))
        self.assertIsNone(self.engine._parse_value("none", context))


if __name__ == "__main__":
    unittest.main()