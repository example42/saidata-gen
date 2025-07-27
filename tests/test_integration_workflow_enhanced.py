"""
Integration tests for complete enhanced workflow.

This module contains end-to-end integration tests for the complete workflow
including metadata generation with override-only templates, AI enhancement,
directory structure creation, and backward compatibility.
"""

import json
import os
import tempfile
import unittest
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from saidata_gen.core.engine import SaidataEngine
from saidata_gen.generator.core import MetadataGenerator
from saidata_gen.generator.templates import TemplateEngine
from saidata_gen.ai.enhancer import AIMetadataEnhancer, AIEnhancementResult
from saidata_gen.core.interfaces import PackageInfo, SaidataMetadata
from saidata_gen.fetcher.base import RepositoryFetcher


class TestIntegrationWorkflowEnhanced(unittest.TestCase):
    """Integration tests for the complete enhanced workflow."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directories
        self.temp_dir = tempfile.TemporaryDirectory()
        self.templates_dir = Path(self.temp_dir.name) / "templates"
        self.output_dir = Path(self.temp_dir.name) / "output"
        
        self.templates_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        
        # Create comprehensive test templates
        self._create_test_templates()
        
        # Initialize components
        self.template_engine = TemplateEngine(str(self.templates_dir))
        self.metadata_generator = MetadataGenerator(template_engine=self.template_engine)
        self.saidata_engine = SaidataEngine()
        
        # Mock AI enhancer
        self.mock_ai_enhancer = Mock(spec=AIMetadataEnhancer)
        self.mock_ai_enhancer.is_available.return_value = True
        self.mock_ai_enhancer.enhance_metadata.return_value = AIEnhancementResult(
            enhanced_metadata={
                "description": "AI-enhanced web server for high-performance applications",
                "urls": {
                    "documentation": "https://nginx.org/en/docs/",
                    "support": "https://nginx.org/en/support.html",
                    "changelog": "https://nginx.org/en/CHANGES"
                },
                "category": {
                    "default": "server",
                    "sub": "web",
                    "tags": ["http", "proxy", "load-balancer"]
                },
                "language": "C",
                "license": "BSD-2-Clause"
            },
            confidence_scores={
                "description": 0.9,
                "urls.documentation": 0.85,
                "category.default": 0.95
            },
            sources_used=["openai-gpt-3.5-turbo"],
            processing_time=1.5,
            success=True
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()
    
    def _create_test_templates(self):
        """Create comprehensive test templates for integration testing."""
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
                    "status": "stopped",
                    "start_command": "systemctl start $software_name",
                    "stop_command": "systemctl stop $software_name"
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
                },
                "logs": {
                    "path": "/var/log/$software_name",
                    "owner": "$software_name",
                    "group": "adm",
                    "mode": "0755"
                }
            },
            "urls": {
                "website": None,
                "source": None,
                "documentation": None,
                "support": None,
                "download": None,
                "changelog": None,
                "icon": None
            },
            "category": {
                "default": None,
                "sub": None,
                "tags": []
            },
            "platforms": ["linux"],
            "ports": [],
            "processes": [],
            "description": None,
            "license": None,
            "language": None
        }
        
        with open(self.templates_dir / "defaults.yaml", "w") as f:
            yaml.dump(default_template, f)
        
        # Create APT provider template (override-only)
        apt_template = {
            "version": "0.1",
            "services": {
                "default": {
                    "enabled": True,  # Override default false
                    "start_command": "sudo systemctl start $software_name",
                    "stop_command": "sudo systemctl stop $software_name"
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
                    "enabled": True,
                    "start_command": "brew services start $software_name",
                    "stop_command": "brew services stop $software_name"
                }
            },
            "directories": {
                "config": {
                    "path": "/usr/local/etc/$software_name",  # Override path
                    "owner": "$(whoami)",  # Different owner
                    "group": "admin"  # Different group
                },
                "data": {
                    "path": "/usr/local/var/$software_name",
                    "owner": "$(whoami)",
                    "group": "admin"
                },
                "logs": {
                    "path": "/usr/local/var/log/$software_name",
                    "owner": "$(whoami)",
                    "group": "admin"
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
            "services": {
                "default": {
                    "enabled": True,
                    "start_command": "net start $software_name",
                    "stop_command": "net stop $software_name"
                }
            },
            "directories": {
                "config": {
                    "path": "C:\\ProgramData\\$software_name",
                    "owner": "Administrator",
                    "group": "Administrators"
                },
                "data": {
                    "path": "C:\\ProgramData\\$software_name\\data",
                    "owner": "Administrator",
                    "group": "Administrators"
                },
                "logs": {
                    "path": "C:\\ProgramData\\$software_name\\logs",
                    "owner": "Administrator",
                    "group": "Administrators"
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
        
        # Create language-specific provider (npm)
        npm_template = {
            "version": "0.1",
            "packages": {
                "default": {
                    "install_options": ["--global"]  # Override empty default
                }
            },
            "services": {
                "default": {
                    "enabled": True,
                    "start_command": "npm start",
                    "stop_command": "npm stop"
                }
            },
            "directories": {
                "config": {
                    "path": "~/.config/$software_name",
                    "owner": "$(whoami)",
                    "group": "$(whoami)"
                },
                "data": {
                    "path": "~/.local/share/$software_name",
                    "owner": "$(whoami)",
                    "group": "$(whoami)"
                }
            },
            "urls": {
                "npm_package": "https://www.npmjs.com/package/$software_name"
            },
            "platforms": ["linux", "macos", "windows"]
        }
        
        with open(providers_dir / "npm.yaml", "w") as f:
            yaml.dump(npm_template, f)
    
    def test_end_to_end_metadata_generation_with_override_templates(self):
        """Test complete end-to-end metadata generation with override-only templates."""
        # Mock package sources
        sources = [
            PackageInfo(
                name="nginx",
                version="1.18.0",
                provider="apt",
                description="HTTP and reverse proxy server",
                homepage="https://nginx.org"
            ),
            PackageInfo(
                name="nginx",
                version="1.18.0",
                provider="brew",
                description="HTTP server and reverse proxy",
                homepage="https://nginx.org"
            )
        ]
        
        # Generate metadata
        result = self.metadata_generator.generate_from_sources(
            software_name="nginx",
            sources=sources,
            providers=["apt", "brew", "winget", "unsupported"]
        )
        
        # Verify basic structure
        self.assertIsNotNone(result.metadata)
        metadata_dict = result.metadata.to_dict()
        
        # Verify version
        self.assertEqual(metadata_dict["version"], "0.1")
        
        # Verify packages section
        self.assertIn("packages", metadata_dict)
        self.assertEqual(metadata_dict["packages"]["default"]["name"], "nginx")
        
        # Verify services section with overrides applied
        self.assertIn("services", metadata_dict)
        # Should be enabled due to provider overrides
        self.assertTrue(metadata_dict["services"]["default"]["enabled"])
        
        # Verify directories with overrides
        self.assertIn("directories", metadata_dict)
        self.assertEqual(metadata_dict["directories"]["config"]["path"], "/etc/nginx")
        
        # Verify URLs from repository data
        self.assertIn("urls", metadata_dict)
        if "website" in metadata_dict["urls"]:
            self.assertEqual(metadata_dict["urls"]["website"], "https://nginx.org")
        
        # Verify platforms (should include overrides from providers)
        self.assertIn("platforms", metadata_dict)
        self.assertIn("linux", metadata_dict["platforms"])
    
    def test_ai_enhanced_generation_workflow(self):
        """Test complete AI-enhanced generation workflow."""
        # Mock package sources
        sources = [
            PackageInfo(
                name="nginx",
                version="1.18.0",
                provider="apt",
                description="HTTP server",
                homepage="https://nginx.org"
            )
        ]
        
        # Patch AI enhancer creation
        with patch('saidata_gen.generator.core.AIMetadataEnhancer') as mock_ai_class:
            mock_ai_class.return_value = self.mock_ai_enhancer
            
            # Generate AI-enhanced metadata
            result = self.metadata_generator.generate_with_ai_enhancement(
                software_name="nginx",
                sources=sources,
                providers=["apt", "brew"],
                ai_provider="openai",
                enhancement_types=["description", "categorization", "field_completion"]
            )
        
        # Verify AI enhancer was created and called
        mock_ai_class.assert_called_once_with(provider="openai")
        self.mock_ai_enhancer.enhance_metadata.assert_called_once()
        
        # Verify result structure
        self.assertIsNotNone(result.metadata)
        metadata_dict = result.metadata.to_dict()
        
        # Verify AI enhancements were applied
        self.assertIn("description", metadata_dict)
        self.assertIn("AI-enhanced", metadata_dict["description"])
        
        # Verify repository data takes precedence over AI data
        if "urls" in metadata_dict and "website" in metadata_dict["urls"]:
            # Repository data should take precedence
            self.assertEqual(metadata_dict["urls"]["website"], "https://nginx.org")
        
        # Verify AI data fills gaps
        if "urls" in metadata_dict:
            self.assertIn("documentation", metadata_dict["urls"])
            self.assertEqual(metadata_dict["urls"]["documentation"], "https://nginx.org/en/docs/")
        
        # Verify category enhancement
        if "category" in metadata_dict:
            self.assertEqual(metadata_dict["category"]["default"], "server")
            self.assertEqual(metadata_dict["category"]["sub"], "web")
    
    def test_directory_structure_creation_and_file_generation(self):
        """Test directory structure creation and file generation."""
        # Mock package sources
        sources = [
            PackageInfo(
                name="nginx",
                version="1.18.0",
                provider="apt",
                description="HTTP server"
            )
        ]
        
        # Generate metadata and create output structure
        result = self.metadata_generator.generate_from_sources(
            software_name="nginx",
            sources=sources,
            providers=["apt", "brew", "winget", "unsupported"]
        )
        
        # Create software directory structure
        software_dir = self.output_dir / "nginx"
        software_dir.mkdir(exist_ok=True)
        
        providers_dir = software_dir / "providers"
        providers_dir.mkdir(exist_ok=True)
        
        # Generate defaults.yaml (merged configuration)
        defaults_content = result.metadata.to_dict()
        with open(software_dir / "defaults.yaml", "w") as f:
            yaml.dump(defaults_content, f, default_flow_style=False)
        
        # Generate provider override files
        providers_to_test = ["apt", "brew", "winget", "unsupported"]
        
        for provider in providers_to_test:
            provider_overrides = self.template_engine.apply_provider_overrides_only(
                software_name="nginx",
                provider=provider
            )
            
            # Only create file if it has meaningful content
            if provider_overrides.get("supported") is False:
                # Unsupported provider - create file with supported: false
                with open(providers_dir / f"{provider}.yaml", "w") as f:
                    yaml.dump(provider_overrides, f, default_flow_style=False)
            elif len(provider_overrides) > 1:  # More than just version
                # Supported provider with overrides
                with open(providers_dir / f"{provider}.yaml", "w") as f:
                    yaml.dump(provider_overrides, f, default_flow_style=False)
        
        # Verify directory structure was created
        self.assertTrue(software_dir.exists())
        self.assertTrue(providers_dir.exists())
        self.assertTrue((software_dir / "defaults.yaml").exists())
        
        # Verify defaults.yaml content
        with open(software_dir / "defaults.yaml", "r") as f:
            defaults_data = yaml.safe_load(f)
        
        self.assertEqual(defaults_data["version"], "0.1")
        self.assertEqual(defaults_data["packages"]["default"]["name"], "nginx")
        
        # Verify provider files
        apt_file = providers_dir / "apt.yaml"
        if apt_file.exists():
            with open(apt_file, "r") as f:
                apt_data = yaml.safe_load(f)
            
            self.assertEqual(apt_data["version"], "0.1")
            self.assertNotIn("supported", apt_data)  # Should not include supported: true
            # Should contain overrides
            if "services" in apt_data:
                self.assertTrue(apt_data["services"]["default"]["enabled"])
        
        # Verify unsupported provider file
        unsupported_file = providers_dir / "unsupported.yaml"
        if unsupported_file.exists():
            with open(unsupported_file, "r") as f:
                unsupported_data = yaml.safe_load(f)
            
            self.assertEqual(unsupported_data["version"], "0.1")
            self.assertFalse(unsupported_data["supported"])
    
    def test_backward_compatibility_with_existing_configurations(self):
        """Test backward compatibility with existing configurations."""
        # Create old-style provider template (with full configuration)
        old_style_template = {
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
                    "enabled": True,  # Different from default
                    "status": "running"
                }
            },
            "directories": {
                "config": {
                    "path": "/etc/$software_name",  # Same as default
                    "owner": "root",  # Same as default
                    "group": "root",  # Same as default
                    "mode": "0755"  # Same as default
                }
            },
            "urls": {
                "website": None,
                "source": None,
                "documentation": None
            },
            "platforms": ["linux"]  # Same as default
        }
        
        # Create old-style template file
        old_style_file = self.templates_dir / "providers" / "old_style.yaml"
        with open(old_style_file, "w") as f:
            yaml.dump(old_style_template, f)
        
        # Test that the system can still process old-style templates
        sources = [
            PackageInfo(
                name="nginx",
                version="1.18.0",
                provider="old_style",
                description="HTTP server"
            )
        ]
        
        # Should work without errors
        result = self.metadata_generator.generate_from_sources(
            software_name="nginx",
            sources=sources,
            providers=["old_style"]
        )
        
        self.assertIsNotNone(result.metadata)
        metadata_dict = result.metadata.to_dict()
        
        # Verify the old-style template was processed correctly
        self.assertEqual(metadata_dict["version"], "0.1")
        self.assertTrue(metadata_dict["services"]["default"]["enabled"])
        
        # Test override-only generation from old-style template
        overrides = self.template_engine.apply_provider_overrides_only(
            software_name="nginx",
            provider="old_style"
        )
        
        # Should generate overrides correctly
        self.assertEqual(overrides["version"], "0.1")
        self.assertNotIn("supported", overrides)  # Should be supported
        
        # Should include meaningful overrides
        if "services" in overrides:
            self.assertTrue(overrides["services"]["default"]["enabled"])
    
    def test_provider_support_detection_integration(self):
        """Test provider support detection in complete workflow."""
        # Test with various provider scenarios
        test_scenarios = [
            {
                "provider": "apt",
                "repository_data": {"name": "nginx", "version": "1.18.0"},
                "expected_supported": True
            },
            {
                "provider": "brew", 
                "repository_data": {},  # Empty data
                "expected_supported": True  # Should fall back to template check
            },
            {
                "provider": "unsupported",
                "repository_data": None,
                "expected_supported": False  # Explicitly unsupported
            },
            {
                "provider": "nonexistent",
                "repository_data": None,
                "expected_supported": False  # No template
            }
        ]
        
        for scenario in test_scenarios:
            with self.subTest(provider=scenario["provider"]):
                is_supported = self.template_engine.is_provider_supported(
                    software_name="nginx",
                    provider=scenario["provider"],
                    repository_data=scenario["repository_data"]
                )
                
                self.assertEqual(
                    is_supported, 
                    scenario["expected_supported"],
                    f"Provider {scenario['provider']} support detection failed"
                )
                
                # Test override generation
                overrides = self.template_engine.apply_provider_overrides_only(
                    software_name="nginx",
                    provider=scenario["provider"],
                    repository_data=scenario["repository_data"]
                )
                
                if scenario["expected_supported"]:
                    self.assertNotIn("supported", overrides)
                else:
                    self.assertFalse(overrides["supported"])
    
    def test_configuration_merging_and_validation(self):
        """Test configuration merging and validation in complete workflow."""
        # Create test metadata with various data types
        base_metadata = {
            "version": "0.1",
            "packages": {
                "default": {
                    "name": "nginx",
                    "version": "1.18.0"
                }
            },
            "services": {
                "default": {
                    "enabled": False
                }
            },
            "platforms": ["linux"]
        }
        
        # Create provider overrides
        provider_overrides = {
            "version": "0.1",
            "services": {
                "default": {
                    "enabled": True,  # Override
                    "port": 80  # Add new field
                }
            },
            "platforms": ["linux", "ubuntu"],  # Override list
            "urls": {
                "website": "https://nginx.org"  # Add new section
            }
        }
        
        # Test merging
        merged = self.template_engine.merge_with_defaults(base_metadata, provider_overrides)
        
        # Verify merging results
        self.assertEqual(merged["version"], "0.1")
        self.assertEqual(merged["packages"]["default"]["name"], "nginx")  # Preserved
        self.assertTrue(merged["services"]["default"]["enabled"])  # Overridden
        self.assertEqual(merged["services"]["default"]["port"], 80)  # Added
        self.assertEqual(merged["platforms"], ["linux", "ubuntu"])  # Replaced
        self.assertEqual(merged["urls"]["website"], "https://nginx.org")  # Added
        
        # Test validation
        is_valid = self.template_engine._validate_merged_configuration(merged)
        self.assertTrue(is_valid)
        
        # Test with invalid configuration
        invalid_config = {
            "version": "invalid-version",  # Invalid version format
            "packages": "not a dict"  # Invalid structure
        }
        
        is_valid = self.template_engine._validate_merged_configuration(invalid_config)
        self.assertFalse(is_valid)
    
    def test_null_value_handling_in_complete_workflow(self):
        """Test null value handling throughout the complete workflow."""
        # Create template with null values
        template_with_nulls = {
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
                "documentation": "https://docs.example.com",  # Should be kept
                "source": None  # Should be removed
            },
            "empty_section": {},  # Should be removed
            "null_field": None  # Should be removed
        }
        
        # Create provider file with nulls
        null_provider_file = self.templates_dir / "providers" / "null_provider.yaml"
        with open(null_provider_file, "w") as f:
            yaml.dump(template_with_nulls, f)
        
        # Test override generation
        overrides = self.template_engine.apply_provider_overrides_only(
            software_name="nginx",
            provider="null_provider"
        )
        
        # Verify null values are handled correctly
        self.assertEqual(overrides["version"], "0.1")
        self.assertNotIn("supported", overrides)  # Should be supported
        
        # Should include non-null values
        self.assertEqual(overrides["packages"]["default"]["name"], "$software_name")
        self.assertEqual(overrides["urls"]["documentation"], "https://docs.example.com")
        
        # Should not include null values
        self.assertNotIn("version", overrides["packages"]["default"])
        self.assertNotIn("install_options", overrides["packages"]["default"])
        self.assertNotIn("website", overrides["urls"])
        self.assertNotIn("source", overrides["urls"])
        self.assertNotIn("empty_section", overrides)
        self.assertNotIn("null_field", overrides)
    
    def test_performance_with_multiple_providers(self):
        """Test performance with multiple providers in complete workflow."""
        import time
        
        # Create sources for multiple providers
        providers = ["apt", "brew", "winget", "npm", "unsupported"]
        sources = [
            PackageInfo(
                name="nginx",
                version="1.18.0",
                provider=provider,
                description=f"HTTP server from {provider}"
            )
            for provider in providers[:3]  # Only supported providers
        ]
        
        # Measure generation time
        start_time = time.time()
        
        result = self.metadata_generator.generate_from_sources(
            software_name="nginx",
            sources=sources,
            providers=providers
        )
        
        generation_time = time.time() - start_time
        
        # Verify result
        self.assertIsNotNone(result.metadata)
        
        # Performance should be reasonable (less than 5 seconds for this test)
        self.assertLess(generation_time, 5.0, "Generation took too long")
        
        # Test provider override generation performance
        start_time = time.time()
        
        for provider in providers:
            overrides = self.template_engine.apply_provider_overrides_only(
                software_name="nginx",
                provider=provider
            )
            self.assertIsInstance(overrides, dict)
        
        override_time = time.time() - start_time
        
        # Override generation should be fast
        self.assertLess(override_time, 2.0, "Override generation took too long")


if __name__ == "__main__":
    unittest.main()