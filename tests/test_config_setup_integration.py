"""Integration tests for configuration and setup commands."""

import os
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from saidata_gen.cli.main import cli


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def temp_config_dir():
    """Create a temporary configuration directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


class TestConfigInit:
    """Test configuration initialization command."""
    
    def test_config_init_basic(self, runner, temp_config_dir):
        """Test basic configuration initialization."""
        result = runner.invoke(cli, [
            'config', 'init',
            '--config-dir', str(temp_config_dir)
        ])
        
        assert result.exit_code == 0
        assert 'Configuration initialized' in result.output
        
        # Check that config file was created
        config_file = temp_config_dir / 'config.yaml'
        assert config_file.exists()
        
        # Verify config content
        with open(config_file, 'r') as f:
            config_data = yaml.safe_load(f)
        
        assert 'providers' in config_data
        assert 'cache' in config_data
        assert 'output' in config_data
        assert 'rag' in config_data
        
        # Check default providers
        assert 'apt' in config_data['providers']
        assert 'brew' in config_data['providers']
        assert config_data['providers']['apt']['enabled'] is True
        
        # Check RAG defaults
        assert config_data['rag']['enabled'] is False
        assert config_data['rag']['provider'] == 'openai'
    
    def test_config_init_existing_no_force(self, runner, temp_config_dir):
        """Test initialization with existing config without force."""
        config_file = temp_config_dir / 'config.yaml'
        config_file.write_text("existing: config")
        
        result = runner.invoke(cli, [
            'config', 'init',
            '--config-dir', str(temp_config_dir)
        ])
        
        assert result.exit_code == 0
        assert 'Configuration already exists' in result.output
        assert 'Use --force to overwrite' in result.output
        
        # Config should not be changed
        assert config_file.read_text() == "existing: config"
    
    def test_config_init_existing_with_force(self, runner, temp_config_dir):
        """Test initialization with existing config with force."""
        config_file = temp_config_dir / 'config.yaml'
        config_file.write_text("existing: config")
        
        result = runner.invoke(cli, [
            'config', 'init',
            '--config-dir', str(temp_config_dir),
            '--force'
        ])
        
        assert result.exit_code == 0
        assert 'Configuration initialized' in result.output
        
        # Config should be overwritten
        with open(config_file, 'r') as f:
            config_data = yaml.safe_load(f)
        assert 'providers' in config_data


class TestConfigShow:
    """Test configuration show command."""
    
    def test_config_show_full(self, runner, temp_config_dir):
        """Test showing full configuration."""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'providers': {'apt': {'enabled': True}},
            'cache': {'directory': '/tmp/cache'},
            'output': {'default_format': 'yaml'}
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        result = runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'show'
        ])
        
        assert result.exit_code == 0
        assert 'providers:' in result.output
        assert 'cache:' in result.output
        assert 'output:' in result.output
    
    def test_config_show_section(self, runner, temp_config_dir):
        """Test showing specific configuration section."""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'providers': {'apt': {'enabled': True}},
            'cache': {'directory': '/tmp/cache'},
            'output': {'default_format': 'yaml'}
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        result = runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'show',
            '--section', 'providers'
        ])
        
        assert result.exit_code == 0
        assert 'providers:' in result.output
        assert 'cache:' not in result.output
    
    def test_config_show_nonexistent_section(self, runner, temp_config_dir):
        """Test showing nonexistent configuration section."""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {'providers': {'apt': {'enabled': True}}}
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        result = runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'show',
            '--section', 'nonexistent'
        ])
        
        assert result.exit_code == 1
        assert 'Section \'nonexistent\' not found' in result.output
    
    def test_config_show_missing_file(self, runner):
        """Test showing configuration when file doesn't exist."""
        result = runner.invoke(cli, [
            '--config', '/nonexistent/config.yaml',
            'config', 'show'
        ])
        
        assert result.exit_code == 1
        assert 'Configuration file not found' in result.output


class TestConfigValidate:
    """Test configuration validation command."""
    
    def test_config_validate_valid(self, runner, temp_config_dir):
        """Test validating valid configuration."""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'providers': {
                'apt': {'enabled': True, 'cache_ttl': 3600}
            },
            'cache': {
                'directory': '/tmp/cache',
                'default_ttl': 3600
            },
            'output': {
                'default_format': 'yaml'
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        result = runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'validate'
        ])
        
        assert result.exit_code == 0
        assert 'Configuration is valid' in result.output
    
    def test_config_validate_missing_sections(self, runner, temp_config_dir):
        """Test validating configuration with missing sections."""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'providers': {'apt': {'enabled': True}}
            # Missing cache and output sections
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        result = runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'validate'
        ])
        
        assert result.exit_code == 1
        assert 'Configuration validation failed' in result.output
        assert 'Missing required section: cache' in result.output
        assert 'Missing required section: output' in result.output
    
    def test_config_validate_invalid_provider(self, runner, temp_config_dir):
        """Test validating configuration with invalid provider settings."""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'providers': {
                'apt': 'invalid_settings'  # Should be a dict
            },
            'cache': {
                'directory': '/tmp/cache',
                'default_ttl': 3600
            },
            'output': {
                'default_format': 'yaml'
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        result = runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'validate'
        ])
        
        assert result.exit_code == 1
        assert 'Provider \'apt\' settings must be a dictionary' in result.output
    
    def test_config_validate_yaml_error(self, runner, temp_config_dir):
        """Test validating configuration with YAML syntax error."""
        config_file = temp_config_dir / 'config.yaml'
        config_file.write_text("invalid: yaml: content: [")
        
        result = runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'validate'
        ])
        
        assert result.exit_code == 1
        assert 'YAML syntax error' in result.output


class TestConfigRAG:
    """Test RAG configuration command."""
    
    def test_config_rag_set_provider(self, runner, temp_config_dir):
        """Test setting RAG provider."""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'providers': {},
            'cache': {'directory': '/tmp'},
            'output': {},
            'rag': {'enabled': False}
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        result = runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'rag',
            '--provider', 'anthropic',
            '--api-key', 'test-key',
            '--model', 'claude-3'
        ])
        
        assert result.exit_code == 0
        assert 'RAG configuration updated' in result.output
        
        # Verify configuration was updated
        with open(config_file, 'r') as f:
            updated_config = yaml.safe_load(f)
        
        assert updated_config['rag']['provider'] == 'anthropic'
        assert updated_config['rag']['api_key'] == 'test-key'
        assert updated_config['rag']['model'] == 'claude-3'
    
    def test_config_rag_enable(self, runner, temp_config_dir):
        """Test enabling RAG."""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'providers': {},
            'cache': {'directory': '/tmp'},
            'output': {},
            'rag': {'enabled': False, 'provider': 'openai'}
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        result = runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'rag',
            '--enable'
        ])
        
        assert result.exit_code == 0
        
        # Verify RAG was enabled
        with open(config_file, 'r') as f:
            updated_config = yaml.safe_load(f)
        
        assert updated_config['rag']['enabled'] is True
    
    def test_config_rag_test_disabled(self, runner, temp_config_dir):
        """Test testing RAG configuration when disabled."""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'providers': {},
            'cache': {'directory': '/tmp'},
            'output': {},
            'rag': {'enabled': False}
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        result = runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'rag',
            '--test'
        ])
        
        assert result.exit_code == 0
        assert 'RAG is disabled' in result.output
    
    def test_config_rag_test_openai_missing_key(self, runner, temp_config_dir):
        """Test testing OpenAI RAG configuration without API key."""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'providers': {},
            'cache': {'directory': '/tmp'},
            'output': {},
            'rag': {'enabled': True, 'provider': 'openai'}
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        result = runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'rag',
            '--test'
        ])
        
        assert result.exit_code == 1
        assert 'OpenAI API key not configured' in result.output
    
    def test_config_rag_test_openai_valid(self, runner, temp_config_dir):
        """Test testing valid OpenAI RAG configuration."""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'providers': {},
            'cache': {'directory': '/tmp'},
            'output': {},
            'rag': {
                'enabled': True,
                'provider': 'openai',
                'api_key': 'test-key'
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        result = runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'rag',
            '--test'
        ])
        
        assert result.exit_code == 0
        assert 'OpenAI configuration looks valid' in result.output


class TestConfigProviders:
    """Test provider configuration command."""
    
    def test_config_providers_list(self, runner):
        """Test listing available providers."""
        result = runner.invoke(cli, [
            'config', 'providers',
            '--list'
        ])
        
        assert result.exit_code == 0
        assert 'Available Package Repository Providers' in result.output
        assert 'apt' in result.output
        assert 'brew' in result.output
        assert 'winget' in result.output
        assert 'npm' in result.output
        assert 'pypi' in result.output
        assert 'cargo' in result.output
    
    def test_config_providers_enable(self, runner, temp_config_dir):
        """Test enabling providers."""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'providers': {
                'apt': {'enabled': False}
            },
            'cache': {'directory': '/tmp'},
            'output': {}
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        result = runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'providers',
            '--enable', 'apt,brew,winget'
        ])
        
        assert result.exit_code == 0
        assert 'Enabled provider: apt' in result.output
        assert 'Enabled provider: brew' in result.output
        assert 'Enabled provider: winget' in result.output
        
        # Verify configuration was updated
        with open(config_file, 'r') as f:
            updated_config = yaml.safe_load(f)
        
        assert updated_config['providers']['apt']['enabled'] is True
        assert updated_config['providers']['brew']['enabled'] is True
        assert updated_config['providers']['winget']['enabled'] is True
    
    def test_config_providers_disable(self, runner, temp_config_dir):
        """Test disabling providers."""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'providers': {
                'apt': {'enabled': True},
                'brew': {'enabled': True}
            },
            'cache': {'directory': '/tmp'},
            'output': {}
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        result = runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'providers',
            '--disable', 'apt'
        ])
        
        assert result.exit_code == 0
        assert 'Disabled provider: apt' in result.output
        
        # Verify configuration was updated
        with open(config_file, 'r') as f:
            updated_config = yaml.safe_load(f)
        
        assert updated_config['providers']['apt']['enabled'] is False
        assert updated_config['providers']['brew']['enabled'] is True
    
    def test_config_providers_show_status(self, runner, temp_config_dir):
        """Test showing provider status."""
        config_file = temp_config_dir / 'config.yaml'
        config_data = {
            'providers': {
                'apt': {'enabled': True, 'cache_ttl': 3600},
                'brew': {'enabled': False, 'cache_ttl': 7200}
            },
            'cache': {'directory': '/tmp'},
            'output': {}
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        result = runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'providers'
        ])
        
        assert result.exit_code == 0
        assert 'Provider Status' in result.output
        assert 'apt' in result.output
        assert 'brew' in result.output
        assert 'Enabled' in result.output
        assert 'Disabled' in result.output


class TestConfigIntegration:
    """Test configuration command integration."""
    
    def test_config_workflow(self, runner, temp_config_dir):
        """Test complete configuration workflow."""
        # 1. Initialize configuration
        result = runner.invoke(cli, [
            'config', 'init',
            '--config-dir', str(temp_config_dir)
        ])
        assert result.exit_code == 0
        
        config_file = temp_config_dir / 'config.yaml'
        
        # 2. Validate configuration
        result = runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'validate'
        ])
        assert result.exit_code == 0
        
        # 3. Configure RAG
        result = runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'rag',
            '--provider', 'openai',
            '--api-key', 'test-key',
            '--enable'
        ])
        assert result.exit_code == 0
        
        # 4. Configure providers
        result = runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'providers',
            '--disable', 'apt,brew'
        ])
        assert result.exit_code == 0
        
        # 5. Show final configuration
        result = runner.invoke(cli, [
            '--config', str(config_file),
            'config', 'show'
        ])
        assert result.exit_code == 0
        assert 'rag:' in result.output
        assert 'providers:' in result.output
        
        # Verify final state
        with open(config_file, 'r') as f:
            final_config = yaml.safe_load(f)
        
        assert final_config['rag']['enabled'] is True
        assert final_config['rag']['provider'] == 'openai'
        assert final_config['rag']['api_key'] == 'test-key'
        assert final_config['providers']['apt']['enabled'] is False
        assert final_config['providers']['brew']['enabled'] is False


class TestEnvironmentVariableIntegration:
    """Test environment variable integration with config commands."""
    
    def test_config_with_env_vars(self, runner, temp_config_dir):
        """Test configuration commands with environment variables."""
        config_file = temp_config_dir / 'config.yaml'
        
        # Initialize with environment variable
        with patch.dict(os.environ, {'SAIDATA_GEN_CONFIG': str(config_file)}):
            result = runner.invoke(cli, [
                'config', 'init',
                '--config-dir', str(temp_config_dir)
            ])
            assert result.exit_code == 0
            
            # Show config using environment variable
            result = runner.invoke(cli, ['config', 'show'])
            assert result.exit_code == 0
            assert 'providers:' in result.output