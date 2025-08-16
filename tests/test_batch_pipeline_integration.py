"""Integration tests for batch processing and pipeline features."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from saidata_gen.cli.main import cli
from saidata_gen.core.interfaces import (
    BatchResult,
    MetadataResult,
    SaidataMetadata,
)


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def mock_engine():
    """Create a mock SaidataEngine."""
    with patch('saidata_gen.cli.main.SaidataEngine') as mock:
        yield mock.return_value


@pytest.fixture
def sample_metadata():
    """Create sample metadata for testing."""
    return SaidataMetadata(
        version="0.1",
        description="Test software",
        packages={"apt": {"name": "test-package", "version": "1.0.0"}},
    )


@pytest.fixture
def temp_files():
    """Create temporary files for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create sample input file for batch processing
        input_file = temp_path / "software_list.txt"
        input_file.write_text("nginx\napache2\n# comment\nmysql-server\n")
        
        yield {
            'dir': temp_path,
            'input_file': input_file,
        }


class TestBatchProcessingEnhancements:
    """Test enhanced batch processing features."""
    
    def test_batch_with_progress_formats(self, runner, mock_engine, sample_metadata, temp_files):
        """Test batch command with different progress formats."""
        mock_results = BatchResult(
            results={
                'nginx': MetadataResult(metadata=sample_metadata),
                'apache2': MetadataResult(metadata=sample_metadata),
                'mysql-server': MetadataResult(metadata=sample_metadata),
            },
            summary={'total': 3, 'successful': 3, 'failed': 0}
        )
        mock_engine.batch_process.return_value = mock_results
        
        # Test rich progress (default)
        result = runner.invoke(cli, [
            'batch', 
            '--input', str(temp_files['input_file']),
            '--progress-format', 'rich'
        ])
        assert result.exit_code == 0
        assert 'Processing packages' in result.output
        
        # Test simple progress
        result = runner.invoke(cli, [
            'batch', 
            '--input', str(temp_files['input_file']),
            '--progress-format', 'simple'
        ])
        assert result.exit_code == 0
        assert 'Processing' in result.output and '3' in result.output and 'packages' in result.output
        assert 'Processing complete' in result.output
        
        # Test JSON progress
        result = runner.invoke(cli, [
            'batch', 
            '--input', str(temp_files['input_file']),
            '--progress-format', 'json'
        ])
        assert result.exit_code == 0
        
        # Should contain JSON progress output
        lines = [line for line in result.output.strip().split('\n') if line.strip()]
        assert len(lines) >= 2
        
        start_data = json.loads(lines[0])
        end_data = json.loads(lines[1])
        
        assert start_data['status'] == 'started'
        assert start_data['total'] == 3
        assert end_data['status'] == 'completed'
        assert end_data['successful'] == 3
        assert end_data['failed'] == 0
    
    def test_batch_dry_run(self, runner, mock_engine, temp_files):
        """Test batch command dry run mode."""
        result = runner.invoke(cli, [
            'batch', 
            '--input', str(temp_files['input_file']),
            '--dry-run'
        ])
        
        assert result.exit_code == 0
        assert 'DRY RUN:' in result.output
        assert 'Would process 3 packages:' in result.output
        assert 'nginx' in result.output
        assert 'apache2' in result.output
        assert 'mysql-server' in result.output
        
        # Engine should not be called in dry run
        mock_engine.batch_process.assert_not_called()
    
    def test_batch_fail_fast(self, runner, mock_engine, sample_metadata, temp_files):
        """Test batch command with fail-fast option."""
        mock_results = BatchResult(
            results={
                'nginx': MetadataResult(metadata=sample_metadata),
                'apache2': Exception("Failed to generate"),
                'mysql-server': MetadataResult(metadata=sample_metadata),
            },
            summary={'total': 3, 'successful': 2, 'failed': 1}
        )
        mock_engine.batch_process.return_value = mock_results
        
        result = runner.invoke(cli, [
            'batch', 
            '--input', str(temp_files['input_file']),
            '--fail-fast'
        ])
        
        assert result.exit_code == 1
        assert 'Exiting with error code 1' in result.output
        
        # Check that continue_on_error was set to False
        call_args = mock_engine.batch_process.call_args
        options = call_args[0][1]
        assert options.continue_on_error is False
    
    def test_batch_show_details(self, runner, mock_engine, sample_metadata, temp_files):
        """Test batch command with detailed output."""
        mock_results = BatchResult(
            results={
                'nginx': MetadataResult(metadata=sample_metadata),
                'apache2': Exception("Failed to generate"),
                'mysql-server': MetadataResult(metadata=sample_metadata),
            },
            summary={'total': 3, 'successful': 2, 'failed': 1}
        )
        mock_engine.batch_process.return_value = mock_results
        
        result = runner.invoke(cli, [
            'batch', 
            '--input', str(temp_files['input_file']),
            '--show-details'
        ])
        
        assert result.exit_code == 0
        assert 'Successful packages:' in result.output
        assert '✅ nginx' in result.output
        assert '✅ mysql-server' in result.output
        assert 'Failed packages:' in result.output
        assert '❌ apache2: Failed to generate' in result.output


class TestEnvironmentVariableSupport:
    """Test environment variable configuration support."""
    
    def test_global_env_vars(self, runner, mock_engine, sample_metadata):
        """Test global environment variables."""
        mock_result = MetadataResult(metadata=sample_metadata)
        mock_engine.generate_metadata.return_value = mock_result
        
        env_vars = {
            'SAIDATA_GEN_CONFIG': '/path/to/config.yaml',
            'SAIDATA_GEN_VERBOSE': 'true',
        }
        
        with patch.dict(os.environ, env_vars):
            with patch('saidata_gen.cli.main.SaidataEngine') as mock_engine_class:
                mock_engine_class.return_value = mock_engine
                result = runner.invoke(cli, ['generate', 'nginx'])
                
                assert result.exit_code == 0
                # Config should be passed from environment
                mock_engine_class.assert_called_once_with(config_path='/path/to/config.yaml')
    
    def test_generate_env_vars(self, runner, mock_engine, sample_metadata):
        """Test generate command environment variables."""
        mock_result = MetadataResult(metadata=sample_metadata)
        mock_engine.generate_metadata.return_value = mock_result
        
        env_vars = {
            'SAIDATA_GEN_PROVIDERS': 'apt,brew,docker',
            'SAIDATA_GEN_AI': 'true',
            'SAIDATA_GEN_AI_PROVIDER': 'anthropic',
            'SAIDATA_GEN_FORMAT': 'json',
            'SAIDATA_GEN_CONFIDENCE_THRESHOLD': '0.8',
        }
        
        with patch.dict(os.environ, env_vars):
            result = runner.invoke(cli, ['generate', 'nginx'])
            
            assert result.exit_code == 0
            
            # Check that environment variables were applied
            call_args = mock_engine.generate_metadata.call_args
            options = call_args[0][1]
            assert options.providers == ['apt', 'brew', 'docker']
            assert options.use_ai is True
            assert options.ai_provider == 'anthropic'
            assert options.output_format == 'json'
            assert options.confidence_threshold == 0.8
    
    def test_batch_env_vars(self, runner, mock_engine, sample_metadata, temp_files):
        """Test batch command environment variables."""
        mock_results = BatchResult(
            results={'nginx': MetadataResult(metadata=sample_metadata)},
            summary={'total': 1, 'successful': 1, 'failed': 0}
        )
        mock_engine.batch_process.return_value = mock_results
        
        output_dir = temp_files['dir'] / 'output'
        
        env_vars = {
            'SAIDATA_GEN_BATCH_INPUT': str(temp_files['input_file']),
            'SAIDATA_GEN_BATCH_OUTPUT': str(output_dir),
            'SAIDATA_GEN_PROVIDERS': 'apt,brew',
            'SAIDATA_GEN_AI': 'true',
            'SAIDATA_GEN_MAX_CONCURRENT': '10',
            'SAIDATA_GEN_PROGRESS_FORMAT': 'simple',
        }
        
        with patch.dict(os.environ, env_vars):
            # Should work without explicit --input since it's in env var
            result = runner.invoke(cli, ['batch'])
            
            assert result.exit_code == 0
            
            # Check that environment variables were applied
            call_args = mock_engine.batch_process.call_args
            options = call_args[0][1]
            assert options.output_dir == str(output_dir)
            assert options.providers == ['apt', 'brew']
            assert options.use_ai is True
            assert options.max_concurrent == 10
    
    def test_cli_args_override_env_vars(self, runner, mock_engine, sample_metadata):
        """Test that CLI arguments override environment variables."""
        mock_result = MetadataResult(metadata=sample_metadata)
        mock_engine.generate_metadata.return_value = mock_result
        
        env_vars = {
            'SAIDATA_GEN_PROVIDERS': 'apt,brew',
            'SAIDATA_GEN_FORMAT': 'json',
        }
        
        with patch.dict(os.environ, env_vars):
            result = runner.invoke(cli, [
                'generate', 'nginx',
                '--providers', 'winget,scoop',
                '--format', 'yaml'
            ])
            
            assert result.exit_code == 0
            
            # CLI args should override env vars
            call_args = mock_engine.generate_metadata.call_args
            options = call_args[0][1]
            assert options.providers == ['winget', 'scoop']
            assert options.output_format == 'yaml'


class TestCICDIntegration:
    """Test CI/CD integration features."""
    
    def test_ci_environment_detection(self, runner, mock_engine, sample_metadata, temp_files):
        """Test CI environment detection and output."""
        mock_results = BatchResult(
            results={
                'nginx': MetadataResult(metadata=sample_metadata),
                'apache2': Exception("Failed to generate"),
            },
            summary={'total': 2, 'successful': 1, 'failed': 1}
        )
        mock_engine.batch_process.return_value = mock_results
        
        # Simulate CI environment
        with patch.dict(os.environ, {'CI': 'true'}):
            result = runner.invoke(cli, [
                'batch', 
                '--input', str(temp_files['input_file'])
            ])
            
            assert result.exit_code == 0
            assert '::set-output name=total::2' in result.output
            assert '::set-output name=successful::1' in result.output
            assert '::set-output name=failed::1' in result.output
            assert '::error::Batch processing failed for 1 packages' in result.output
    
    def test_github_actions_integration(self, runner, mock_engine, sample_metadata, temp_files):
        """Test GitHub Actions specific integration."""
        mock_results = BatchResult(
            results={'nginx': MetadataResult(metadata=sample_metadata)},
            summary={'total': 1, 'successful': 1, 'failed': 0}
        )
        mock_engine.batch_process.return_value = mock_results
        
        with patch.dict(os.environ, {'GITHUB_ACTIONS': 'true'}):
            result = runner.invoke(cli, [
                'batch', 
                '--input', str(temp_files['input_file'])
            ])
            
            assert result.exit_code == 0
            assert '::set-output name=total::1' in result.output
            assert '::set-output name=successful::1' in result.output
            assert '::set-output name=failed::0' in result.output
    
    def test_json_progress_for_ci(self, runner, mock_engine, sample_metadata, temp_files):
        """Test JSON progress output for CI/CD systems."""
        mock_results = BatchResult(
            results={
                'nginx': MetadataResult(metadata=sample_metadata),
                'apache2': Exception("Failed to generate"),
                'mysql-server': MetadataResult(metadata=sample_metadata),
            },
            summary={'total': 3, 'successful': 2, 'failed': 1}
        )
        mock_engine.batch_process.return_value = mock_results
        
        result = runner.invoke(cli, [
            'batch', 
            '--input', str(temp_files['input_file']),
            '--progress-format', 'json'
        ])
        
        assert result.exit_code == 0
        
        lines = result.output.strip().split('\n')
        start_data = json.loads(lines[0])
        end_data = json.loads(lines[1])
        
        # Validate JSON structure (file has 3 packages: nginx, apache2, mysql-server)
        assert start_data['status'] == 'started'
        assert start_data['total'] == 3
        assert start_data['processed'] == 0
        
        assert end_data['status'] == 'completed'
        assert end_data['total'] == 3
        assert end_data['successful'] == 2  # nginx and mysql-server succeed
        assert end_data['failed'] == 1  # apache2 fails
        assert 'nginx' in end_data['results']
        assert 'apache2' in end_data['results']
        assert end_data['results']['nginx'] == 'success'
        assert 'Failed to generate' in end_data['results']['apache2']
    
    def test_exit_codes_for_ci(self, runner, mock_engine, sample_metadata, temp_files):
        """Test proper exit codes for CI/CD systems."""
        # Test successful batch
        mock_results = BatchResult(
            results={'nginx': MetadataResult(metadata=sample_metadata)},
            summary={'total': 1, 'successful': 1, 'failed': 0}
        )
        mock_engine.batch_process.return_value = mock_results
        
        result = runner.invoke(cli, [
            'batch', 
            '--input', str(temp_files['input_file'])
        ])
        assert result.exit_code == 0
        
        # Test failed batch with continue-on-error (default)
        mock_results = BatchResult(
            results={
                'nginx': Exception("Failed"),
                'apache2': MetadataResult(metadata=sample_metadata),
                'mysql-server': MetadataResult(metadata=sample_metadata),
            },
            summary={'total': 3, 'successful': 2, 'failed': 1}
        )
        mock_engine.batch_process.return_value = mock_results
        
        result = runner.invoke(cli, [
            'batch', 
            '--input', str(temp_files['input_file']),
            '--continue-on-error'
        ])
        assert result.exit_code == 0  # Should not fail with continue-on-error
        
        # Test failed batch with fail-fast
        mock_results = BatchResult(
            results={
                'nginx': Exception("Failed"),
                'apache2': MetadataResult(metadata=sample_metadata),
                'mysql-server': MetadataResult(metadata=sample_metadata),
            },
            summary={'total': 3, 'successful': 2, 'failed': 1}
        )
        mock_engine.batch_process.return_value = mock_results
        
        result = runner.invoke(cli, [
            'batch', 
            '--input', str(temp_files['input_file']),
            '--fail-fast'
        ])
        assert result.exit_code == 1  # Should fail with fail-fast


class TestLoggingConfiguration:
    """Test logging configuration via environment variables."""
    
    def test_log_level_env_var(self, runner, mock_engine, sample_metadata):
        """Test log level configuration via environment variable."""
        mock_result = MetadataResult(metadata=sample_metadata)
        mock_engine.generate_metadata.return_value = mock_result
        
        with patch.dict(os.environ, {'SAIDATA_GEN_LOG_LEVEL': 'DEBUG'}):
            with patch('saidata_gen.cli.main.setup_logging') as mock_logging:
                result = runner.invoke(cli, ['generate', 'nginx'])
                
                assert result.exit_code == 0
                # Should be called with verbose=False but env var should override
                mock_logging.assert_called_once_with(False)
    
    def test_log_format_env_var(self, runner, mock_engine, sample_metadata):
        """Test log format configuration via environment variable."""
        mock_result = MetadataResult(metadata=sample_metadata)
        mock_engine.generate_metadata.return_value = mock_result
        
        custom_format = '%(levelname)s: %(message)s'
        with patch.dict(os.environ, {'SAIDATA_GEN_LOG_FORMAT': custom_format}):
            with patch('logging.basicConfig') as mock_basic_config:
                result = runner.invoke(cli, ['generate', 'nginx'])
                
                assert result.exit_code == 0
                # Check that custom format was used
                mock_basic_config.assert_called_once()
                call_kwargs = mock_basic_config.call_args[1]
                assert call_kwargs['format'] == custom_format


class TestProgressReporting:
    """Test enhanced progress reporting features."""
    
    def test_rich_progress_with_time_remaining(self, runner, mock_engine, sample_metadata, temp_files):
        """Test rich progress with time remaining."""
        mock_results = BatchResult(
            results={
                'nginx': MetadataResult(metadata=sample_metadata),
                'apache2': MetadataResult(metadata=sample_metadata),
                'mysql-server': MetadataResult(metadata=sample_metadata),
            },
            summary={'total': 3, 'successful': 3, 'failed': 0}
        )
        mock_engine.batch_process.return_value = mock_results
        
        result = runner.invoke(cli, [
            'batch', 
            '--input', str(temp_files['input_file']),
            '--progress-format', 'rich'
        ])
        
        assert result.exit_code == 0
        # Rich progress should show processing information
        assert 'Processing packages' in result.output
    
    def test_concurrent_processing_reporting(self, runner, mock_engine, sample_metadata, temp_files):
        """Test progress reporting with concurrent processing."""
        mock_results = BatchResult(
            results={
                'nginx': MetadataResult(metadata=sample_metadata),
                'apache2': MetadataResult(metadata=sample_metadata),
                'mysql-server': MetadataResult(metadata=sample_metadata),
            },
            summary={'total': 3, 'successful': 3, 'failed': 0}
        )
        mock_engine.batch_process.return_value = mock_results
        
        result = runner.invoke(cli, [
            'batch', 
            '--input', str(temp_files['input_file']),
            '--max-concurrent', '10'
        ])
        
        assert result.exit_code == 0
        
        # Check that max_concurrent was passed correctly
        call_args = mock_engine.batch_process.call_args
        options = call_args[0][1]
        assert options.max_concurrent == 10