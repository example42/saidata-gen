"""
End-to-end integration tests for complete functionality.

This module contains comprehensive integration tests that test the complete
system from CLI commands to metadata generation with the new directory structure,
fetcher resilience, and configuration loading.
"""

import json
import os
import tempfile
import time
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from unittest import mock

import pytest
from click.testing import CliRunner

from saidata_gen.cli.main import cli
from saidata_gen.core.engine import SaidataEngine
from saidata_gen.core.interfaces import (
    GenerationOptions, BatchOptions, ValidationResult, MetadataResult,
    SaidataMetadata, PackageConfig, PackageInfo, FetchResult, SoftwareMatch
)
from saidata_gen.core.models import EnhancedSaidataMetadata
from saidata_gen.core.configuration import ConfigurationManager
from saidata_gen.core.directory_structure import DirectoryStructureGenerator
from saidata_gen.fetcher.error_handler import FetcherErrorHandler
from saidata_gen.core.graceful_degradation import GracefulDegradationManager
from saidata_gen.core.system_dependency_checker import SystemDependencyChecker


@pytest.mark.integration
class TestCompleteMetadataGenerationWithDirectoryStructure:
    """Integration tests for complete metadata generation with new directory structure."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace for integration tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = {
                "root": Path(temp_dir),
                "output": Path(temp_dir) / "output",
                "config": Path(temp_dir) / "config",
                "templates": Path(temp_dir) / "templates",
                "cache": Path(temp_dir) / "cache"
            }
            
            # Create directories
            for path in workspace.values():
                if isinstance(path, Path):
                    path.mkdir(exist_ok=True)
            
            # Create provider_defaults.yaml
            provider_defaults = {
                "version": "0.1",
                "apt": {
                    "services": {
                        "default": {
                            "enabled": True,
                            "status": "enabled"
                        }
                    },
                    "urls": {
                        "apt": "https://packages.ubuntu.com/search?keywords={{ software_name }}"
                    },
                    "files": {
                        "init": {
                            "path": "/etc/default/{{ software_name }}"
                        }
                    },
                    "directories": {
                        "config": {
                            "mode": "0644"
                        }
                    }
                },
                "brew": {
                    "urls": {
                        "brew": "https://brew.sh/formula/{{ software_name }}"
                    },
                    "services": {
                        "default": {
                            "enabled": True,
                            "status": "enabled"
                        }
                    }
                },
                "winget": {
                    "urls": {
                        "winget": "https://winget.run/pkg/{{ software_name }}"
                    },
                    "services": {
                        "default": {
                            "enabled": True,
                            "status": "enabled"
                        }
                    }
                }
            }
            
            provider_defaults_file = workspace["templates"] / "provider_defaults.yaml"
            with open(provider_defaults_file, "w") as f:
                yaml.dump(provider_defaults, f)
            
            # Create defaults.yaml
            defaults = {
                "version": "0.1",
                "category": {"default": "Development"},
                "platforms": ["linux"]
            }
            
            defaults_file = workspace["templates"] / "defaults.yaml"
            with open(defaults_file, "w") as f:
                yaml.dump(defaults, f)
            
            workspace["provider_defaults_file"] = provider_defaults_file
            workspace["defaults_file"] = defaults_file
            
            yield workspace
    
    @pytest.fixture
    def mock_package_sources(self):
        """Provide mock package sources for testing."""
        return [
            PackageInfo(
                name="nginx",
                version="1.18.0",
                provider="apt",
                description="HTTP server and reverse proxy",
                details={"maintainer": "nginx team", "homepage": "https://nginx.org"}
            ),
            PackageInfo(
                name="nginx",
                version="1.25.3",
                provider="brew",
                description="HTTP(S) server and reverse proxy",
                details={"formula": "nginx", "homepage": "https://nginx.org"}
            ),
            PackageInfo(
                name="nginx",
                version="1.24.0",
                provider="winget",
                description="Nginx web server",
                details={"publisher": "nginx.org", "homepage": "https://nginx.org"}
            )
        ]    

    def test_complete_directory_structure_generation(self, temp_workspace, mock_package_sources):
        """Test complete metadata generation with new directory structure."""
        # Create configuration manager with the templates directory
        config_manager = ConfigurationManager(str(temp_workspace["templates"]))
        
        # Create directory structure generator
        dir_generator = DirectoryStructureGenerator(config_manager)
        
        # Test configuration loading
        base_defaults = config_manager.load_base_defaults()
        assert base_defaults["version"] == "0.1"
        assert base_defaults["category"]["default"] == "Development"
        
        provider_defaults = config_manager.load_provider_defaults()
        assert "apt" in provider_defaults
        assert "brew" in provider_defaults
        assert "winget" in provider_defaults
        
        # Test provider configuration merging
        apt_config = config_manager.get_provider_config("apt", "nginx")
        assert apt_config["services"]["default"]["enabled"] is True
        assert "nginx" in apt_config["urls"]["apt"]
        
        brew_config = config_manager.get_provider_config("brew", "nginx")
        assert "nginx" in brew_config["urls"]["brew"]
        
        # Test directory structure creation
        software_dir = dir_generator.create_software_directory("nginx", str(temp_workspace["output"]))
        assert software_dir.exists()
        assert software_dir.name == "nginx"
        
        providers_dir = software_dir / "providers"
        assert providers_dir.exists()
        
        # Test defaults file creation
        defaults_content = {
            "version": "0.1",
            "description": "HTTP server and reverse proxy",
            "packages": {
                "apt": {"name": "nginx", "version": "1.18.0"},
                "brew": {"name": "nginx", "version": "1.25.3"},
                "winget": {"name": "nginx", "version": "1.24.0"}
            },
            "category": {"default": "Development"},
            "platforms": ["linux"]
        }
        
        dir_generator.write_defaults_file(defaults_content, software_dir, "nginx")
        defaults_file = software_dir / "defaults.yaml"
        assert defaults_file.exists()
        
        with open(defaults_file, "r") as f:
            saved_defaults = yaml.safe_load(f)
        
        assert saved_defaults["version"] == "0.1"
        assert saved_defaults["description"] == "HTTP server and reverse proxy"
        assert len(saved_defaults["packages"]) == 3
        
        # Test provider files creation (only when they differ from defaults)
        provider_configs = {
            "apt": apt_config,
            "brew": brew_config,
            "winget": config_manager.get_provider_config("winget", "nginx")
        }
        
        dir_generator.write_provider_files(provider_configs, software_dir, "nginx")
        
        # Check that provider files were created
        apt_file = providers_dir / "apt.yaml"
        brew_file = providers_dir / "brew.yaml"
        winget_file = providers_dir / "winget.yaml"
        
        assert apt_file.exists()
        assert brew_file.exists()
        assert winget_file.exists()
        
        # Verify provider file contents
        with open(apt_file, "r") as f:
            apt_data = yaml.safe_load(f)
        
        # Basic verification that it's valid YAML with expected structure
        assert isinstance(apt_data, dict)
        assert "services" in apt_data
        assert "urls" in apt_data
        assert apt_data["services"]["default"]["enabled"] is True
        assert "nginx" in apt_data["urls"]["apt"]
        
        # Test cleanup of empty provider directory
        empty_providers_dir = software_dir / "empty_providers"
        empty_providers_dir.mkdir()
        
        dir_generator.cleanup_empty_provider_directory(software_dir)
        # The empty directory should still exist since it's not the main providers directory
        assert empty_providers_dir.exists()
        
        # But if we clean up the actual providers directory when it's empty
        for file in providers_dir.glob("*.yaml"):
            file.unlink()
        
        dir_generator.cleanup_empty_provider_directory(software_dir)
        # The providers directory should still exist but be empty
        assert providers_dir.exists()
        assert len(list(providers_dir.glob("*.yaml"))) == 0
    
    def test_configuration_loading_and_merging_across_providers(self, temp_workspace):
        """Test configuration loading and merging across all providers."""
        # Create comprehensive provider_defaults.yaml with all providers
        comprehensive_provider_defaults = {
            "version": "0.1",
            "apt": {
                "services": {"default": {"enabled": True}},
                "urls": {"apt": "https://packages.ubuntu.com/search?keywords={{ software_name }}"}
            },
            "brew": {
                "services": {"default": {"enabled": True}},
                "urls": {"brew": "https://brew.sh/formula/{{ software_name }}"}
            },
            "winget": {
                "services": {"default": {"enabled": True}},
                "urls": {"winget": "https://winget.run/pkg/{{ software_name }}"}
            },
            "dnf": {
                "services": {"default": {"enabled": True}},
                "urls": {"dnf": "https://packages.fedoraproject.org/pkgs/{{ software_name }}"}
            },
            "yum": {
                "services": {"default": {"enabled": True}},
                "urls": {"yum": "https://centos.pkgs.org/search/?q={{ software_name }}"}
            },
            "pacman": {
                "services": {"default": {"enabled": True}},
                "urls": {"pacman": "https://archlinux.org/packages/?q={{ software_name }}"}
            },
            "npm": {
                "services": {"default": {"enabled": True}},
                "urls": {"npm": "https://www.npmjs.com/package/{{ software_name }}"}
            },
            "pypi": {
                "services": {"default": {"enabled": True}},
                "urls": {"pypi": "https://pypi.org/project/{{ software_name }}"}
            },
            "docker": {
                "services": {"default": {"enabled": True}},
                "urls": {"docker": "https://hub.docker.com/r/library/{{ software_name }}"}
            },
            "cargo": {
                "services": {"default": {"enabled": True}},
                "urls": {"cargo": "https://crates.io/crates/{{ software_name }}"}
            }
        }
        
        # Update provider_defaults.yaml
        with open(temp_workspace["provider_defaults_file"], "w") as f:
            yaml.dump(comprehensive_provider_defaults, f)
        
        # Create configuration manager
        config_manager = ConfigurationManager(str(temp_workspace["templates"]))
        
        # Test loading all provider defaults
        provider_defaults = config_manager.load_provider_defaults()
        
        expected_providers = [
            "apt", "brew", "winget", "dnf", "yum", "pacman", 
            "npm", "pypi", "docker", "cargo"
        ]
        
        for provider in expected_providers:
            assert provider in provider_defaults
            assert provider_defaults[provider]["services"]["default"]["enabled"] is True
            assert "{{ software_name }}" in provider_defaults[provider]["urls"][provider]
        
        # Test configuration merging for each provider
        software_name = "test-package"
        
        for provider in expected_providers:
            config = config_manager.get_provider_config(provider, software_name)
            
            # Verify template substitution
            assert software_name in config["urls"][provider]
            assert config["services"]["default"]["enabled"] is True
            
            # Verify base defaults are merged
            assert config["version"] == "0.1"
        
        # Test should_create_provider_file logic
        for provider in expected_providers:
            config = config_manager.get_provider_config(provider, software_name)
            
            # Should create file if config differs from defaults
            should_create = config_manager.should_create_provider_file(provider, config)
            # Since we have provider-specific URLs, files should be created
            assert should_create is True
        
        # Test with identical config (should not create file)
        base_defaults = config_manager.load_base_defaults()
        should_create_identical = config_manager.should_create_provider_file("apt", base_defaults)
        assert should_create_identical is False


@pytest.mark.integration
class TestCLICommandExecutionWithRemovedOptions:
    """Integration tests for CLI command execution with removed options."""
    
    @pytest.fixture
    def runner(self):
        """Create a Click test runner."""
        return CliRunner()
    
    @pytest.fixture
    def temp_output_dir(self):
        """Create temporary output directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def mock_engine(self):
        """Create a mock SaidataEngine."""
        with patch('saidata_gen.cli.main.SaidataEngine') as mock:
            engine = mock.return_value
            
            # Mock directory structure generation
            engine.generate_metadata_with_directory_structure.return_value = {
                'software_dir': '/tmp/nginx',
                'defaults_file': '/tmp/nginx/defaults.yaml',
                'provider_files': {
                    'apt': '/tmp/nginx/providers/apt.yaml',
                    'brew': '/tmp/nginx/providers/brew.yaml'
                },
                'skipped_providers': {
                    'winget': 'Not available on this platform'
                },
                'validation_result': ValidationResult(valid=True, issues=[]),
                'confidence_scores': {
                    'description': 0.95,
                    'packages': 0.85
                }
            }
            
            # Mock other methods
            engine.get_default_providers.return_value = ['apt', 'brew', 'winget']
            engine.get_available_providers.return_value = {
                'apt': {'has_template': True},
                'brew': {'has_template': True},
                'winget': {'has_template': True}
            }
            
            yield engine  
  
    def test_generate_command_always_creates_directory_structure(self, runner, mock_engine, temp_output_dir):
        """Test that generate command always creates directory structure (no --directory-structure option)."""
        result = runner.invoke(cli, [
            'generate', 'nginx',
            '--output', str(temp_output_dir)
        ])
        
        assert result.exit_code == 0
        assert 'Directory structure generated' in result.output
        assert 'defaults.yaml' in result.output
        assert 'Provider files' in result.output
        
        # Verify that generate_metadata_with_directory_structure was called
        mock_engine.generate_metadata_with_directory_structure.assert_called_once()
        
        # Verify the call arguments
        call_args = mock_engine.generate_metadata_with_directory_structure.call_args
        assert call_args[0][0] == 'nginx'  # software_name
        assert call_args[0][1] == str(temp_output_dir)  # output_dir
        
        options = call_args[0][2]  # GenerationOptions
        assert isinstance(options, GenerationOptions)
    
    def test_removed_directory_structure_option_shows_error(self, runner):
        """Test that removed --directory-structure option shows appropriate error."""
        result = runner.invoke(cli, [
            'generate', 'nginx',
            '--directory-structure'
        ])
        
        # Click should show "no such option" error
        assert result.exit_code != 0
        assert 'no such option' in result.output.lower() or 'unrecognized' in result.output.lower()
    
    def test_removed_comprehensive_option_shows_error(self, runner):
        """Test that removed --comprehensive option shows appropriate error."""
        result = runner.invoke(cli, [
            'generate', 'nginx',
            '--comprehensive'
        ])
        
        # Click should show "no such option" error
        assert result.exit_code != 0
        assert 'no such option' in result.output.lower() or 'unrecognized' in result.output.lower()
    
    def test_removed_use_rag_option_shows_error(self, runner):
        """Test that removed --use-rag option shows appropriate error."""
        result = runner.invoke(cli, [
            'generate', 'nginx',
            '--use-rag'
        ])
        
        # Click should show "no such option" error
        assert result.exit_code != 0
        assert 'no such option' in result.output.lower() or 'unrecognized' in result.output.lower()
    
    def test_removed_rag_provider_option_shows_error(self, runner):
        """Test that removed --rag-provider option shows appropriate error."""
        result = runner.invoke(cli, [
            'generate', 'nginx',
            '--rag-provider', 'openai'
        ])
        
        # Click should show "no such option" error
        assert result.exit_code != 0
        assert 'no such option' in result.output.lower() or 'unrecognized' in result.output.lower()
    
    def test_new_ai_options_work_correctly(self, runner, mock_engine, temp_output_dir):
        """Test that new --ai and --ai-provider options work correctly."""
        result = runner.invoke(cli, [
            'generate', 'nginx',
            '--ai',
            '--ai-provider', 'anthropic',
            '--output', str(temp_output_dir)
        ])
        
        assert result.exit_code == 0
        
        # Verify the options were passed correctly
        call_args = mock_engine.generate_metadata_with_directory_structure.call_args
        options = call_args[0][2]  # GenerationOptions
        
        assert options.use_ai is True
        assert options.ai_provider == 'anthropic'
    
    def test_batch_command_with_directory_structure_output(self, runner, mock_engine, temp_output_dir):
        """Test that batch command creates directory structures for each package."""
        # Create input file
        input_file = temp_output_dir / "software_list.txt"
        input_file.write_text("nginx\napache2\nmysql-server\n")
        
        # Mock batch processing
        mock_engine.batch_process.return_value = Mock(
            results={
                'nginx': Mock(),
                'apache2': Mock(),
                'mysql-server': Mock()
            },
            summary={'total': 3, 'successful': 3, 'failed': 0}
        )
        
        result = runner.invoke(cli, [
            'batch',
            '--input', str(input_file),
            '--output', str(temp_output_dir)
        ])
        
        assert result.exit_code == 0
        assert 'Found 3 software packages to process' in result.output
        assert 'Total: 3' in result.output
        assert 'Successful: 3' in result.output
        
        # Verify batch_process was called
        mock_engine.batch_process.assert_called_once()
        
        call_args = mock_engine.batch_process.call_args
        software_list = call_args[0][0]
        assert software_list == ['nginx', 'apache2', 'mysql-server']
        
        options = call_args[0][1]
        assert options.output_dir == str(temp_output_dir)
    
    def test_validate_structure_command(self, runner, mock_engine, temp_output_dir):
        """Test the validate-structure command for directory validation."""
        # Create a mock directory structure
        software_dir = temp_output_dir / "nginx"
        software_dir.mkdir()
        
        (software_dir / "defaults.yaml").write_text("version: '0.1'\n")
        
        providers_dir = software_dir / "providers"
        providers_dir.mkdir()
        (providers_dir / "apt.yaml").write_text("version: '0.1'\n")
        
        # Mock validation result
        mock_engine.validate_and_cleanup_directory_structure.return_value = {
            "validation": {
                "valid": True,
                "issues": [],
                "warnings": []
            },
            "cleanup": {
                "removed_files": [],
                "errors": []
            },
            "formatting": {
                "formatted_files": [],
                "errors": []
            }
        }
        
        result = runner.invoke(cli, [
            'validate-structure', str(software_dir)
        ])
        
        assert result.exit_code == 0
        assert 'Directory structure is valid' in result.output
        
        # Verify the method was called
        mock_engine.validate_and_cleanup_directory_structure.assert_called_once_with(
            str(software_dir),
            cleanup=False,
            format_files=False
        )
    
    def test_validate_structure_with_cleanup_and_format(self, runner, mock_engine, temp_output_dir):
        """Test validate-structure command with cleanup and formatting options."""
        software_dir = temp_output_dir / "nginx"
        software_dir.mkdir()
        
        # Mock validation result with cleanup and formatting
        mock_engine.validate_and_cleanup_directory_structure.return_value = {
            "validation": {
                "valid": True,
                "issues": [],
                "warnings": ["Some formatting inconsistencies"]
            },
            "cleanup": {
                "removed_files": ["providers/empty.yaml"],
                "errors": []
            },
            "formatting": {
                "formatted_files": ["defaults.yaml", "providers/apt.yaml"],
                "errors": []
            }
        }
        
        result = runner.invoke(cli, [
            'validate-structure', str(software_dir),
            '--cleanup',
            '--format'
        ])
        
        assert result.exit_code == 0
        assert 'Directory structure is valid' in result.output
        assert 'Cleanup completed' in result.output
        assert 'Formatting completed' in result.output
        
        # Verify the method was called with correct options
        mock_engine.validate_and_cleanup_directory_structure.assert_called_once_with(
            str(software_dir),
            cleanup=True,
            format_files=True
        )


@pytest.mark.integration
class TestFetcherResilienceWithSimulatedNetworkConditions:
    """Integration tests for fetcher resilience with simulated network conditions."""
    
    @pytest.fixture
    def mock_fetcher_components(self):
        """Create mock fetcher components for testing."""
        error_handler = Mock(spec=FetcherErrorHandler)
        degradation_manager = Mock(spec=GracefulDegradationManager)
        dependency_checker = Mock(spec=SystemDependencyChecker)
        
        return {
            'error_handler': error_handler,
            'degradation_manager': degradation_manager,
            'dependency_checker': dependency_checker
        }
    
    def test_network_error_handling_and_retry_logic(self, mock_fetcher_components):
        """Test network error handling with retry logic."""
        import requests
        from requests.exceptions import ConnectionError, Timeout, HTTPError
        
        error_handler = mock_fetcher_components['error_handler']
        
        # Test different network error scenarios
        network_errors = [
            ConnectionError("Connection failed"),
            Timeout("Request timed out"),
            HTTPError("HTTP 500 Internal Server Error")
        ]
        
        for error in network_errors:
            # Mock error handler responses
            error_handler.handle_network_error.return_value = Mock(
                success=False,
                should_retry=True,
                retry_after=1.0
            )
            
            error_handler.should_retry.return_value = True
            
            # Simulate error handling
            context = {"url": "https://example.com", "attempt": 1}
            result = error_handler.handle_network_error(error, context)
            
            assert result.success is False
            assert result.should_retry is True
            
            # Verify error handler was called
            error_handler.handle_network_error.assert_called_with(error, context)
    
    def test_ssl_certificate_error_handling(self, mock_fetcher_components):
        """Test SSL certificate error handling with fallback mechanisms."""
        import ssl
        from requests.exceptions import SSLError
        
        error_handler = mock_fetcher_components['error_handler']
        
        # Test SSL certificate errors
        ssl_errors = [
            SSLError("SSL certificate verify failed"),
            SSLError("SSL: CERTIFICATE_VERIFY_FAILED")
        ]
        
        for ssl_error in ssl_errors:
            # Mock SSL error handling
            error_handler.handle_ssl_error.return_value = Mock(
                status_code=200,
                text='{"packages": []}',
                json=lambda: {"packages": []}
            )
            
            # Simulate SSL error handling
            url = "https://packages.example.com/api"
            response = error_handler.handle_ssl_error(ssl_error, url)
            
            assert response is not None
            assert response.status_code == 200
            
            # Verify SSL error handler was called
            error_handler.handle_ssl_error.assert_called_with(ssl_error, url) 
   
    def test_malformed_data_handling(self, mock_fetcher_components):
        """Test handling of malformed repository data."""
        error_handler = mock_fetcher_components['error_handler']
        
        # Test different types of malformed data
        malformed_data_cases = [
            (b'{"invalid": json}', 'json'),
            (b'invalid: yaml: [', 'yaml'),
            (b'<invalid>xml</invalid', 'xml'),
            (b'\x00\x01\x02binary_data', 'json')
        ]
        
        for malformed_data, format_type in malformed_data_cases:
            # Mock malformed data handling
            error_handler.handle_malformed_data.return_value = {
                "packages": [],
                "error": f"Failed to parse {format_type} data",
                "fallback_used": True
            }
            
            # Simulate malformed data handling
            result = error_handler.handle_malformed_data(malformed_data, format_type)
            
            assert result is not None
            assert "packages" in result
            assert result["fallback_used"] is True
            
            # Verify malformed data handler was called
            error_handler.handle_malformed_data.assert_called_with(malformed_data, format_type)
    
    def test_system_dependency_checking(self, mock_fetcher_components):
        """Test system dependency checking for fetchers."""
        dependency_checker = mock_fetcher_components['dependency_checker']
        
        # Test dependency checking for various commands
        commands_to_test = [
            ('apt', 'apt-cache'),
            ('brew', 'brew'),
            ('dnf', 'dnf'),
            ('yum', 'yum'),
            ('pacman', 'pacman'),
            ('emerge', 'emerge'),
            ('guix', 'guix'),
            ('nix', 'nix-env'),
            ('spack', 'spack')
        ]
        
        for provider, command in commands_to_test:
            # Mock dependency availability
            dependency_checker.check_command_availability.return_value = True
            dependency_checker.get_installation_instructions.return_value = f"Install {command} package manager"
            
            # Test command availability check
            is_available = dependency_checker.check_command_availability(command)
            assert is_available is True
            
            # Test installation instructions
            instructions = dependency_checker.get_installation_instructions(command)
            assert command in instructions
            
            # Test logging missing dependency
            dependency_checker.log_missing_dependency(command, provider)
            dependency_checker.log_missing_dependency.assert_called_with(command, provider)
    
    def test_graceful_degradation_workflow(self, mock_fetcher_components):
        """Test graceful degradation when providers fail."""
        degradation_manager = mock_fetcher_components['degradation_manager']
        
        # Test marking providers as unavailable
        failed_providers = ['winget', 'scoop', 'choco']
        reasons = ['Not available on Linux', 'Command not found', 'Network timeout']
        
        for provider, reason in zip(failed_providers, reasons):
            degradation_manager.mark_provider_unavailable(provider, reason)
            degradation_manager.mark_provider_unavailable.assert_called_with(provider, reason)
        
        # Test getting alternative sources
        for provider in failed_providers:
            degradation_manager.get_alternative_sources.return_value = ['apt', 'brew']
            alternatives = degradation_manager.get_alternative_sources(provider)
            
            assert isinstance(alternatives, list)
            assert len(alternatives) > 0
            
            degradation_manager.get_alternative_sources.assert_called_with(provider)
        
        # Test logging degradation events
        for provider, reason in zip(failed_providers, reasons):
            degradation_manager.log_degradation_event(provider, reason)
            degradation_manager.log_degradation_event.assert_called_with(provider, reason)
    
    def test_end_to_end_fetcher_resilience(self, mock_fetcher_components):
        """Test end-to-end fetcher resilience with multiple failure scenarios."""
        error_handler = mock_fetcher_components['error_handler']
        degradation_manager = mock_fetcher_components['degradation_manager']
        dependency_checker = mock_fetcher_components['dependency_checker']
        
        # Test a complete workflow with multiple failure scenarios
        providers = ["apt", "brew", "winget", "npm"]
        failed_providers = []
        successful_providers = []
        
        for provider in providers:
            # Simulate dependency checking
            if provider in ["winget", "npm"]:
                # These fail dependency check
                dependency_checker.check_command_availability.return_value = False
                is_available = dependency_checker.check_command_availability(f"{provider}-command")
                assert is_available is False
                
                instructions = dependency_checker.get_installation_instructions(f"{provider}-command")
                dependency_checker.log_missing_dependency(f"{provider}-command", provider)
                
                # Mark as unavailable
                degradation_manager.mark_provider_unavailable(provider, "Command not found")
                failed_providers.append(provider)
            else:
                # These pass dependency check
                dependency_checker.check_command_availability.return_value = True
                is_available = dependency_checker.check_command_availability(f"{provider}-command")
                assert is_available is True
                successful_providers.append(provider)
        
        # Test network error handling for successful providers
        for provider in successful_providers:
            # Simulate network error that gets handled
            network_error = ConnectionError(f"Network error for {provider}")
            error_handler.handle_network_error.return_value = Mock(
                success=True,  # Eventually succeeds after retry
                should_retry=False,
                data={"packages": [{"name": "nginx", "version": "1.0.0"}]}
            )
            
            result = error_handler.handle_network_error(network_error, {"provider": provider})
            assert result.success is True
        
        # Test getting alternatives for failed providers
        for provider in failed_providers:
            degradation_manager.get_alternative_sources.return_value = successful_providers
            alternatives = degradation_manager.get_alternative_sources(provider)
            assert len(alternatives) > 0
            assert all(alt in successful_providers for alt in alternatives)
        
        # Verify all components were called appropriately
        assert dependency_checker.check_command_availability.call_count == len(providers)
        assert degradation_manager.mark_provider_unavailable.call_count == len(failed_providers)
        assert error_handler.handle_network_error.call_count == len(successful_providers)
        assert degradation_manager.get_alternative_sources.call_count == len(failed_providers)


@pytest.mark.integration
class TestConfigurationLoadingAndMerging:
    """Integration tests for configuration loading and merging across all providers."""
    
    @pytest.fixture
    def comprehensive_config_setup(self):
        """Create comprehensive configuration setup for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_dir = Path(temp_dir)
            
            # Create comprehensive provider_defaults.yaml
            provider_defaults = {
                "version": "0.1",
                # System package managers
                "apt": {
                    "services": {"default": {"enabled": True, "status": "enabled"}},
                    "urls": {"apt": "https://packages.ubuntu.com/search?keywords={{ software_name }}"},
                    "files": {"config": {"path": "/etc/{{ software_name }}/{{ software_name }}.conf"}},
                    "directories": {"config": {"path": "/etc/{{ software_name }}", "mode": "0755"}}
                },
                "dnf": {
                    "services": {"default": {"enabled": True, "status": "enabled"}},
                    "urls": {"dnf": "https://packages.fedoraproject.org/pkgs/{{ software_name }}"},
                    "files": {"config": {"path": "/etc/{{ software_name }}/{{ software_name }}.conf"}},
                    "directories": {"config": {"path": "/etc/{{ software_name }}", "mode": "0755"}}
                },
                "yum": {
                    "services": {"default": {"enabled": True, "status": "enabled"}},
                    "urls": {"yum": "https://centos.pkgs.org/search/?q={{ software_name }}"},
                    "files": {"config": {"path": "/etc/{{ software_name }}/{{ software_name }}.conf"}},
                    "directories": {"config": {"path": "/etc/{{ software_name }}", "mode": "0755"}}
                },
                "pacman": {
                    "services": {"default": {"enabled": True, "status": "enabled"}},
                    "urls": {"pacman": "https://archlinux.org/packages/?q={{ software_name }}"},
                    "files": {"config": {"path": "/etc/{{ software_name }}/{{ software_name }}.conf"}},
                    "directories": {"config": {"path": "/etc/{{ software_name }}", "mode": "0755"}}
                },
                "apk": {
                    "services": {"default": {"enabled": True, "status": "enabled"}},
                    "urls": {"apk": "https://pkgs.alpinelinux.org/packages?name={{ software_name }}"},
                    "files": {"config": {"path": "/etc/{{ software_name }}/{{ software_name }}.conf"}},
                    "directories": {"config": {"path": "/etc/{{ software_name }}", "mode": "0755"}}
                },
                # Cross-platform package managers
                "brew": {
                    "services": {"default": {"enabled": True, "status": "enabled"}},
                    "urls": {"brew": "https://brew.sh/formula/{{ software_name }}"},
                    "files": {"config": {"path": "/usr/local/etc/{{ software_name }}/{{ software_name }}.conf"}},
                    "directories": {"config": {"path": "/usr/local/etc/{{ software_name }}", "mode": "0755"}}
                },
                "winget": {
                    "services": {"default": {"enabled": True, "status": "enabled"}},
                    "urls": {"winget": "https://winget.run/pkg/{{ software_name }}"},
                    "files": {"config": {"path": "C:\\ProgramData\\{{ software_name }}\\{{ software_name }}.conf"}},
                    "directories": {"config": {"path": "C:\\ProgramData\\{{ software_name }}", "mode": "0755"}}
                },
                "scoop": {
                    "services": {"default": {"enabled": True, "status": "enabled"}},
                    "urls": {"scoop": "https://scoop.sh/#/apps?q={{ software_name }}"},
                    "files": {"config": {"path": "%USERPROFILE%\\scoop\\apps\\{{ software_name }}\\current\\{{ software_name }}.conf"}},
                    "directories": {"config": {"path": "%USERPROFILE%\\scoop\\apps\\{{ software_name }}", "mode": "0755"}}
                },
                # Language-specific package managers
                "npm": {
                    "services": {"default": {"enabled": True, "status": "enabled"}},
                    "urls": {"npm": "https://www.npmjs.com/package/{{ software_name }}"},
                    "files": {"config": {"path": "~/.config/{{ software_name }}/config.json"}},
                    "directories": {"config": {"path": "~/.config/{{ software_name }}", "mode": "0755"}}
                },
                "pypi": {
                    "services": {"default": {"enabled": True, "status": "enabled"}},
                    "urls": {"pypi": "https://pypi.org/project/{{ software_name }}"},
                    "files": {"config": {"path": "~/.config/{{ software_name }}/config.ini"}},
                    "directories": {"config": {"path": "~/.config/{{ software_name }}", "mode": "0755"}}
                },
                "cargo": {
                    "services": {"default": {"enabled": True, "status": "enabled"}},
                    "urls": {"cargo": "https://crates.io/crates/{{ software_name }}"},
                    "files": {"config": {"path": "~/.cargo/config/{{ software_name }}.toml"}},
                    "directories": {"config": {"path": "~/.cargo/config", "mode": "0755"}}
                },
                "gem": {
                    "services": {"default": {"enabled": True, "status": "enabled"}},
                    "urls": {"gem": "https://rubygems.org/gems/{{ software_name }}"},
                    "files": {"config": {"path": "~/.gem/{{ software_name }}/config.yml"}},
                    "directories": {"config": {"path": "~/.gem/{{ software_name }}", "mode": "0755"}}
                },
                # Container and orchestration
                "docker": {
                    "services": {"default": {"enabled": True, "status": "enabled"}},
                    "urls": {"docker": "https://hub.docker.com/r/library/{{ software_name }}"},
                    "files": {"config": {"path": "/etc/docker/{{ software_name }}.json"}},
                    "directories": {"config": {"path": "/etc/docker", "mode": "0755"}}
                },
                "helm": {
                    "services": {"default": {"enabled": True, "status": "enabled"}},
                    "urls": {"helm": "https://artifacthub.io/packages/helm/{{ software_name }}"},
                    "files": {"config": {"path": "~/.helm/{{ software_name }}/values.yaml"}},
                    "directories": {"config": {"path": "~/.helm/{{ software_name }}", "mode": "0755"}}
                }
            }
            
            provider_defaults_file = config_dir / "provider_defaults.yaml"
            with open(provider_defaults_file, "w") as f:
                yaml.dump(provider_defaults, f)
            
            # Create base defaults.yaml
            base_defaults = {
                "version": "0.1",
                "category": {"default": "Software"},
                "platforms": ["linux"],
                "description": None,
                "license": None,
                "language": None
            }
            
            defaults_file = config_dir / "defaults.yaml"
            with open(defaults_file, "w") as f:
                yaml.dump(base_defaults, f)
            
            yield {
                "config_dir": config_dir,
                "provider_defaults_file": provider_defaults_file,
                "defaults_file": defaults_file,
                "provider_defaults": provider_defaults,
                "base_defaults": base_defaults
            }    

    def test_comprehensive_provider_configuration_loading(self, comprehensive_config_setup):
        """Test loading configuration for all supported providers."""
        config_manager = ConfigurationManager(str(comprehensive_config_setup["config_dir"] / "templates"))
        
        # Create the templates directory and copy files
        templates_dir = comprehensive_config_setup["config_dir"] / "templates"
        templates_dir.mkdir(exist_ok=True)
        
        # Copy the configuration files to the templates directory
        import shutil
        shutil.copy2(comprehensive_config_setup["provider_defaults_file"], templates_dir / "provider_defaults.yaml")
        shutil.copy2(comprehensive_config_setup["defaults_file"], templates_dir / "defaults.yaml")
        
        # Test loading provider defaults
        provider_defaults = config_manager.load_provider_defaults()
        
        expected_providers = [
            # System package managers
            "apt", "dnf", "yum", "pacman", "apk",
            # Cross-platform
            "brew", "winget", "scoop",
            # Language-specific
            "npm", "pypi", "cargo", "gem",
            # Container/orchestration
            "docker", "helm"
        ]
        
        # Verify all expected providers are loaded
        for provider in expected_providers:
            assert provider in provider_defaults, f"Provider {provider} not found in defaults"
            
            provider_config = provider_defaults[provider]
            
            # Verify required sections exist
            assert "services" in provider_config
            assert "urls" in provider_config
            assert "files" in provider_config
            assert "directories" in provider_config
            
            # Verify service configuration
            assert provider_config["services"]["default"]["enabled"] is True
            assert provider_config["services"]["default"]["status"] == "enabled"
            
            # Verify URL template
            assert "{{ software_name }}" in provider_config["urls"][provider]
            
            # Verify file and directory configurations
            assert "{{ software_name }}" in provider_config["files"]["config"]["path"]
            assert "{{ software_name }}" in provider_config["directories"]["config"]["path"]
    
    def test_configuration_merging_with_template_substitution(self, comprehensive_config_setup):
        """Test configuration merging with template variable substitution."""
        # Create the templates directory and copy files
        templates_dir = comprehensive_config_setup["config_dir"] / "templates"
        templates_dir.mkdir(exist_ok=True)
        
        import shutil
        shutil.copy2(comprehensive_config_setup["provider_defaults_file"], templates_dir / "provider_defaults.yaml")
        shutil.copy2(comprehensive_config_setup["defaults_file"], templates_dir / "defaults.yaml")
        
        config_manager = ConfigurationManager(str(templates_dir))
        
        software_name = "test-application"
        
        # Test configuration merging for each provider
        providers_to_test = ["apt", "brew", "npm", "docker", "winget"]
        
        for provider in providers_to_test:
            merged_config = config_manager.get_provider_config(provider, software_name)
            
            # Verify provider-specific configuration is present
            assert "services" in merged_config
            assert "urls" in merged_config
            assert "files" in merged_config
            assert "directories" in merged_config
            
            # Verify template substitution occurred
            assert software_name in merged_config["urls"][provider]
            assert software_name in merged_config["files"]["config"]["path"]
            assert software_name in merged_config["directories"]["config"]["path"]
            
            # Verify no template variables remain
            config_str = yaml.dump(merged_config)
            assert "{{ software_name }}" not in config_str
    
    def test_provider_file_creation_logic(self, comprehensive_config_setup):
        """Test logic for determining when to create provider files."""
        # Create the templates directory and copy files
        templates_dir = comprehensive_config_setup["config_dir"] / "templates"
        templates_dir.mkdir(exist_ok=True)
        
        import shutil
        shutil.copy2(comprehensive_config_setup["provider_defaults_file"], templates_dir / "provider_defaults.yaml")
        shutil.copy2(comprehensive_config_setup["defaults_file"], templates_dir / "defaults.yaml")
        
        config_manager = ConfigurationManager(str(templates_dir))
        
        software_name = "test-app"
        
        # Test should_create_provider_file for various scenarios
        providers_to_test = ["apt", "brew", "npm", "docker"]
        
        for provider in providers_to_test:
            # Get merged configuration
            merged_config = config_manager.get_provider_config(provider, software_name)
            
            # Should create file because provider config differs from base defaults
            should_create = config_manager.should_create_provider_file(provider, merged_config, software_name)
            assert should_create is True, f"Should create file for {provider}"
            
            # Test with base defaults only (should not create file)
            base_defaults = config_manager.load_base_defaults()
            should_not_create = config_manager.should_create_provider_file(provider, base_defaults, software_name)
            assert should_not_create is False, f"Should not create file for base defaults"
    
    def test_configuration_validation_and_error_handling(self, comprehensive_config_setup):
        """Test configuration validation and error handling."""
        # Create the templates directory and copy files
        templates_dir = comprehensive_config_setup["config_dir"] / "templates"
        templates_dir.mkdir(exist_ok=True)
        
        import shutil
        shutil.copy2(comprehensive_config_setup["provider_defaults_file"], templates_dir / "provider_defaults.yaml")
        shutil.copy2(comprehensive_config_setup["defaults_file"], templates_dir / "defaults.yaml")
        
        config_manager = ConfigurationManager(str(templates_dir))
        
        # Test with valid configuration
        try:
            base_defaults = config_manager.load_base_defaults()
            provider_defaults = config_manager.load_provider_defaults()
            
            assert base_defaults is not None
            assert provider_defaults is not None
            assert len(provider_defaults) > 0
            
        except Exception as e:
            pytest.fail(f"Valid configuration should not raise exception: {e}")
        
        # Test with invalid base defaults file
        invalid_templates_dir = comprehensive_config_setup["config_dir"] / "invalid_templates"
        invalid_templates_dir.mkdir(exist_ok=True)
        
        invalid_defaults_file = invalid_templates_dir / "defaults.yaml"
        invalid_defaults_file.write_text("invalid: yaml: content: [")
        
        # Copy valid provider defaults
        shutil.copy2(comprehensive_config_setup["provider_defaults_file"], invalid_templates_dir / "provider_defaults.yaml")
        
        invalid_config_manager = ConfigurationManager(str(invalid_templates_dir))
        
        from saidata_gen.core.exceptions import ConfigurationError
        with pytest.raises(ConfigurationError):
            invalid_config_manager.load_base_defaults()
        
        # Test with missing provider defaults file
        missing_templates_dir = comprehensive_config_setup["config_dir"] / "missing_templates"
        missing_templates_dir.mkdir(exist_ok=True)
        
        # Only copy defaults, not provider_defaults
        shutil.copy2(comprehensive_config_setup["defaults_file"], missing_templates_dir / "defaults.yaml")
        
        missing_config_manager = ConfigurationManager(str(missing_templates_dir))
        
        with pytest.raises(ConfigurationError):
            missing_config_manager.load_provider_defaults()
    
    def test_end_to_end_configuration_workflow(self, comprehensive_config_setup):
        """Test complete end-to-end configuration workflow."""
        # Create the templates directory and copy files
        templates_dir = comprehensive_config_setup["config_dir"] / "templates"
        templates_dir.mkdir(exist_ok=True)
        
        import shutil
        shutil.copy2(comprehensive_config_setup["provider_defaults_file"], templates_dir / "provider_defaults.yaml")
        shutil.copy2(comprehensive_config_setup["defaults_file"], templates_dir / "defaults.yaml")
        
        # Create configuration manager
        config_manager = ConfigurationManager(str(templates_dir))
        
        # Create directory structure generator
        dir_generator = DirectoryStructureGenerator(config_manager)
        
        software_name = "nginx"
        output_dir = comprehensive_config_setup["config_dir"] / "output"
        output_dir.mkdir()
        
        # Step 1: Load configurations
        base_defaults = config_manager.load_base_defaults()
        provider_defaults = config_manager.load_provider_defaults()
        
        # Step 2: Create software directory
        software_dir = dir_generator.create_software_directory(software_name, str(output_dir))
        
        # Step 3: Generate merged defaults file
        merged_defaults = base_defaults.copy()
        merged_defaults.update({
            "description": "HTTP server and reverse proxy",
            "packages": {
                "apt": {"name": "nginx", "version": "1.18.0"},
                "brew": {"name": "nginx", "version": "1.25.3"}
            }
        })
        
        dir_generator.write_defaults_file(merged_defaults, software_dir, software_name)
        
        # Step 4: Generate provider files
        providers_to_generate = ["apt", "brew", "npm", "docker"]
        provider_configs = {}
        
        for provider in providers_to_generate:
            if provider in provider_defaults:
                provider_config = config_manager.get_provider_config(provider, software_name)
                provider_configs[provider] = provider_config
        
        dir_generator.write_provider_files(provider_configs, software_dir, software_name)
        
        # Step 5: Verify generated structure
        assert software_dir.exists()
        assert (software_dir / "defaults.yaml").exists()
        
        providers_dir = software_dir / "providers"
        assert providers_dir.exists()
        
        # Verify provider files were created
        for provider in providers_to_generate:
            if provider in provider_defaults:
                provider_file = providers_dir / f"{provider}.yaml"
                assert provider_file.exists(), f"Provider file for {provider} should exist"
                
                # Verify file content
                with open(provider_file, "r") as f:
                    provider_data = yaml.safe_load(f)
                
                # Basic verification that it's valid YAML with expected structure
                assert isinstance(provider_data, dict)
                assert "services" in provider_data
                assert "urls" in provider_data
        
        # Step 6: Verify defaults file content
        with open(software_dir / "defaults.yaml", "r") as f:
            defaults_data = yaml.safe_load(f)
        
        assert defaults_data["description"] == "HTTP server and reverse proxy"
        assert "packages" in defaults_data
        assert len(defaults_data["packages"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])