"""Integration tests for CLI commands."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml
from click.testing import CliRunner

from saidata_gen.cli.main import cli
from saidata_gen.core.interfaces import (
    BatchResult,
    FetchResult,
    MetadataResult,
    SaidataMetadata,
    SoftwareMatch,
    ValidationResult,
    ValidationIssue,
    ValidationLevel,
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
        urls={"website": "https://example.com"}
    )


@pytest.fixture
def temp_files():
    """Create temporary files for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create sample input file for batch processing
        input_file = temp_path / "software_list.txt"
        input_file.write_text("nginx\napache2\n# comment\nmysql-server\n")
        
        # Create sample metadata file for validation
        metadata_file = temp_path / "test.yaml"
        metadata_file.write_text("""
version: "0.1"
description: "Test software"
packages:
  apt:
    name: "test-package"
    version: "1.0.0"
""")
        
        # Create invalid metadata file
        invalid_file = temp_path / "invalid.yaml"
        invalid_file.write_text("""
invalid_field: "this should not be here"
""")
        
        yield {
            'dir': temp_path,
            'input_file': input_file,
            'metadata_file': metadata_file,
            'invalid_file': invalid_file
        }


class TestGenerateCommand:
    """Test the generate command."""
    
    def test_generate_basic(self, runner, mock_engine, sample_metadata):
        """Test basic generate command."""
        mock_result = MetadataResult(metadata=sample_metadata)
        mock_engine.generate_metadata.return_value = mock_result
        
        result = runner.invoke(cli, ['generate', 'nginx'])
        
        assert result.exit_code == 0
        assert 'Generated Metadata for nginx' in result.output
        mock_engine.generate_metadata.assert_called_once()
        
        # Check that the correct options were passed
        call_args = mock_engine.generate_metadata.call_args
        assert call_args[0][0] == 'nginx'  # software_name
        options = call_args[0][1]  # GenerationOptions
        assert options.providers == []

        assert options.output_format == 'yaml'
    
    def test_generate_with_providers(self, runner, mock_engine, sample_metadata):
        """Test generate command with specific providers."""
        mock_result = MetadataResult(metadata=sample_metadata)
        mock_engine.generate_metadata.return_value = mock_result
        
        result = runner.invoke(cli, ['generate', 'nginx', '--providers', 'apt,brew,docker'])
        
        assert result.exit_code == 0
        call_args = mock_engine.generate_metadata.call_args
        options = call_args[0][1]
        assert options.providers == ['apt', 'brew', 'docker']
    

    
    def test_generate_with_output_file(self, runner, mock_engine, sample_metadata, temp_files):
        """Test generate command with output file."""
        mock_result = MetadataResult(metadata=sample_metadata)
        mock_engine.generate_metadata.return_value = mock_result
        
        output_file = temp_files['dir'] / 'output.yaml'
        result = runner.invoke(cli, ['generate', 'nginx', '--output', str(output_file)])
        
        assert result.exit_code == 0
        assert output_file.exists()
        assert 'Metadata generated and saved to' in result.output
        
        # Verify file content
        content = yaml.safe_load(output_file.read_text())
        assert content['version'] == '0.1'
        assert content['description'] == 'Test software'
    
    def test_generate_json_format(self, runner, mock_engine, sample_metadata, temp_files):
        """Test generate command with JSON format."""
        mock_result = MetadataResult(metadata=sample_metadata)
        mock_engine.generate_metadata.return_value = mock_result
        
        output_file = temp_files['dir'] / 'output.json'
        result = runner.invoke(cli, ['generate', 'nginx', '--format', 'json', '--output', str(output_file)])
        
        assert result.exit_code == 0
        assert output_file.exists()
        
        # Verify JSON content
        content = json.loads(output_file.read_text())
        assert content['version'] == '0.1'
        assert content['description'] == 'Test software'
    
    def test_generate_with_confidence_scores(self, runner, mock_engine, sample_metadata):
        """Test generate command displays confidence scores."""
        mock_result = MetadataResult(
            metadata=sample_metadata,
            confidence_scores={'description': 0.95, 'packages': 0.80, 'urls': 0.60}
        )
        mock_engine.generate_metadata.return_value = mock_result
        
        result = runner.invoke(cli, ['generate', 'nginx'])
        
        assert result.exit_code == 0
        assert 'Confidence Scores:' in result.output
        assert 'description: 0.95' in result.output
        assert 'packages: 0.80' in result.output
        assert 'urls: 0.60' in result.output
    
    def test_generate_error_handling(self, runner, mock_engine):
        """Test generate command error handling."""
        from saidata_gen.core.exceptions import SaidataGenError
        mock_engine.generate_metadata.side_effect = SaidataGenError("Test error")
        
        result = runner.invoke(cli, ['generate', 'nginx'])
        
        assert result.exit_code == 1
        assert 'Error: Test error' in result.output


class TestValidateCommand:
    """Test the validate command."""
    
    def test_validate_valid_file(self, runner, mock_engine, temp_files):
        """Test validate command with valid file."""
        mock_result = ValidationResult(valid=True, issues=[])
        mock_engine.validate_metadata.return_value = mock_result
        
        result = runner.invoke(cli, ['validate', str(temp_files['metadata_file'])])
        
        assert result.exit_code == 0
        assert 'valid' in result.output
        mock_engine.validate_metadata.assert_called_once_with(str(temp_files['metadata_file']))
    
    def test_validate_invalid_file(self, runner, mock_engine, temp_files):
        """Test validate command with invalid file."""
        mock_issues = [
            ValidationIssue(
                level=ValidationLevel.ERROR,
                message="Invalid field 'invalid_field'",
                path="$.invalid_field"
            )
        ]
        mock_result = ValidationResult(valid=False, issues=mock_issues)
        mock_engine.validate_metadata.return_value = mock_result
        
        result = runner.invoke(cli, ['validate', str(temp_files['invalid_file'])])
        
        assert result.exit_code == 1
        assert 'validation errors' in result.output
        assert 'Invalid field' in result.output
    
    def test_validate_detailed_output(self, runner, mock_engine, temp_files):
        """Test validate command with detailed output."""
        mock_issues = [
            ValidationIssue(
                level=ValidationLevel.ERROR,
                message="Invalid field 'invalid_field'",
                path="$.invalid_field",
                schema_path="$.properties"
            )
        ]
        mock_result = ValidationResult(valid=False, issues=mock_issues)
        mock_engine.validate_metadata.return_value = mock_result
        
        result = runner.invoke(cli, ['validate', str(temp_files['invalid_file']), '--detailed'])
        
        assert result.exit_code == 1
        assert 'Detailed Issues:' in result.output
        assert 'Field path: $.invalid_field' in result.output
        assert 'Schema path: $.properties' in result.output
    
    def test_validate_nonexistent_file(self, runner):
        """Test validate command with nonexistent file."""
        result = runner.invoke(cli, ['validate', 'nonexistent.yaml'])
        
        assert result.exit_code == 2  # Click's file not found error
        assert 'does not exist' in result.output


class TestSearchCommand:
    """Test the search command."""
    
    def test_search_basic(self, runner, mock_engine):
        """Test basic search command."""
        mock_matches = [
            SoftwareMatch(name='nginx', provider='apt', version='1.18.0', description='Web server', score=0.95),
            SoftwareMatch(name='nginx', provider='brew', version='1.19.0', description='HTTP server', score=0.90),
        ]
        mock_engine.search_software.return_value = mock_matches
        
        result = runner.invoke(cli, ['search', 'nginx'])
        
        assert result.exit_code == 0
        assert 'Search Results' in result.output
        assert 'nginx' in result.output
        assert 'apt' in result.output
        assert 'brew' in result.output
        mock_engine.search_software.assert_called_once_with('nginx')
    
    def test_search_with_providers(self, runner, mock_engine):
        """Test search command with specific providers."""
        mock_matches = [
            SoftwareMatch(name='nginx', provider='apt', version='1.18.0', description='Web server', score=0.95),
        ]
        mock_engine.search_software.return_value = mock_matches
        
        result = runner.invoke(cli, ['search', 'nginx', '--providers', 'apt,brew'])
        
        assert result.exit_code == 0
        assert 'nginx' in result.output
    
    def test_search_no_results(self, runner, mock_engine):
        """Test search command with no results."""
        mock_engine.search_software.return_value = []
        
        result = runner.invoke(cli, ['search', 'nonexistent'])
        
        assert result.exit_code == 0
        assert 'No packages found' in result.output
    
    def test_search_with_limits(self, runner, mock_engine):
        """Test search command with result limits."""
        mock_matches = [
            SoftwareMatch(name=f'package{i}', provider='apt', score=0.8 - i*0.1) 
            for i in range(25)
        ]
        mock_engine.search_software.return_value = mock_matches
        
        result = runner.invoke(cli, ['search', 'package', '--limit', '5', '--min-score', '0.7'])
        
        assert result.exit_code == 0
        # Should only show packages with score >= 0.7 and limit to 5
        assert 'package0' in result.output
        assert 'package1' in result.output
        assert 'package2' not in result.output  # score would be 0.6


class TestBatchCommand:
    """Test the batch command."""
    
    def test_batch_basic(self, runner, mock_engine, temp_files, sample_metadata):
        """Test basic batch command."""
        mock_results = BatchResult(
            results={
                'nginx': MetadataResult(metadata=sample_metadata),
                'apache2': MetadataResult(metadata=sample_metadata),
                'mysql-server': MetadataResult(metadata=sample_metadata),
            },
            summary={'total': 3, 'successful': 3, 'failed': 0}
        )
        mock_engine.batch_process.return_value = mock_results
        
        result = runner.invoke(cli, ['batch', '--input', str(temp_files['input_file'])])
        
        assert result.exit_code == 0
        assert 'Found 3 software packages to process' in result.output
        assert 'Total: 3' in result.output
        assert 'Successful: 3' in result.output
        assert 'Failed: 0' in result.output
        
        # Verify the correct software list was passed
        call_args = mock_engine.batch_process.call_args
        software_list = call_args[0][0]
        assert software_list == ['nginx', 'apache2', 'mysql-server']
    
    def test_batch_with_output_dir(self, runner, mock_engine, temp_files, sample_metadata):
        """Test batch command with output directory."""
        mock_results = BatchResult(
            results={'nginx': MetadataResult(metadata=sample_metadata)},
            summary={'total': 1, 'successful': 1, 'failed': 0}
        )
        mock_engine.batch_process.return_value = mock_results
        
        output_dir = temp_files['dir'] / 'output'
        result = runner.invoke(cli, [
            'batch', 
            '--input', str(temp_files['input_file']),
            '--output', str(output_dir)
        ])
        
        assert result.exit_code == 0
        assert output_dir.exists()
        
        # Check that output directory was passed to batch options
        call_args = mock_engine.batch_process.call_args
        options = call_args[0][1]
        assert options.output_dir == str(output_dir)
    
    def test_batch_with_failures(self, runner, mock_engine, temp_files, sample_metadata):
        """Test batch command with some failures."""
        mock_results = BatchResult(
            results={
                'nginx': MetadataResult(metadata=sample_metadata),
                'apache2': Exception("Failed to generate"),
                'mysql-server': MetadataResult(metadata=sample_metadata),
            },
            summary={'total': 3, 'successful': 2, 'failed': 1}
        )
        mock_engine.batch_process.return_value = mock_results
        
        result = runner.invoke(cli, ['batch', '--input', str(temp_files['input_file'])])
        
        assert result.exit_code == 0  # continue_on_error is True by default
        assert 'Failed: 1' in result.output
        assert 'apache2: Failed to generate' in result.output
    
    def test_batch_empty_input_file(self, runner, temp_files):
        """Test batch command with empty input file."""
        empty_file = temp_files['dir'] / 'empty.txt'
        empty_file.write_text("# Only comments\n# No actual software names\n")
        
        result = runner.invoke(cli, ['batch', '--input', str(empty_file)])
        
        assert result.exit_code == 1
        assert 'No software names found' in result.output
    
    def test_batch_nonexistent_input_file(self, runner):
        """Test batch command with nonexistent input file."""
        result = runner.invoke(cli, ['batch', '--input', 'nonexistent.txt'])
        
        assert result.exit_code == 2  # Click's file not found error


class TestFetchCommand:
    """Test the fetch command."""
    
    def test_fetch_basic(self, runner, mock_engine):
        """Test basic fetch command."""
        mock_result = FetchResult(
            success=True,
            providers={'apt': True, 'brew': True, 'winget': False},
            errors={'winget': 'Connection timeout'},
            cache_hits={'apt': False, 'brew': True, 'winget': False}
        )
        mock_engine.fetch_repository_data.return_value = mock_result
        
        result = runner.invoke(cli, ['fetch'])
        
        assert result.exit_code == 0
        assert 'Repository Fetch Results' in result.output
        assert '✅ Success' in result.output
        assert '❌ Failed' in result.output
        assert 'Connection timeout' in result.output
        mock_engine.fetch_repository_data.assert_called_once_with([])
    
    def test_fetch_specific_providers(self, runner, mock_engine):
        """Test fetch command with specific providers."""
        mock_result = FetchResult(
            success=True,
            providers={'apt': True, 'brew': True},
            errors={},
            cache_hits={'apt': False, 'brew': False}
        )
        mock_engine.fetch_repository_data.return_value = mock_result
        
        result = runner.invoke(cli, ['fetch', '--providers', 'apt,brew'])
        
        assert result.exit_code == 0
        mock_engine.fetch_repository_data.assert_called_once_with(['apt', 'brew'])
    
    def test_fetch_with_stats(self, runner, mock_engine):
        """Test fetch command with statistics."""
        mock_result = FetchResult(
            success=True,
            providers={'apt': True, 'brew': True, 'winget': False},
            errors={'winget': 'Connection timeout'},
            cache_hits={'apt': False, 'brew': True, 'winget': False}
        )
        mock_engine.fetch_repository_data.return_value = mock_result
        
        result = runner.invoke(cli, ['fetch', '--show-stats'])
        
        assert result.exit_code == 0
        assert 'Statistics:' in result.output
        assert 'Total providers: 3' in result.output
        assert 'Successful: 2' in result.output
        assert 'Failed: 1' in result.output
        assert 'Cache hits: 1' in result.output
    
    def test_fetch_all_failed(self, runner, mock_engine):
        """Test fetch command when all providers fail."""
        mock_result = FetchResult(
            success=False,
            providers={'apt': False, 'brew': False},
            errors={'apt': 'Network error', 'brew': 'API error'},
            cache_hits={'apt': False, 'brew': False}
        )
        mock_engine.fetch_repository_data.return_value = mock_result
        
        result = runner.invoke(cli, ['fetch'])
        
        assert result.exit_code == 1
        assert '❌ Failed' in result.output


class TestGlobalOptions:
    """Test global CLI options."""
    
    def test_verbose_option(self, runner, mock_engine, sample_metadata):
        """Test verbose option enables debug logging."""
        mock_result = MetadataResult(metadata=sample_metadata)
        mock_engine.generate_metadata.return_value = mock_result
        
        with patch('saidata_gen.cli.main.setup_logging') as mock_logging:
            result = runner.invoke(cli, ['--verbose', 'generate', 'nginx'])
            
            assert result.exit_code == 0
            mock_logging.assert_called_once_with(True)
    
    def test_config_option(self, runner, mock_engine, sample_metadata, temp_files):
        """Test config option passes config path to engine."""
        config_file = temp_files['dir'] / 'config.yaml'
        config_file.write_text("test: config")
        
        mock_result = MetadataResult(metadata=sample_metadata)
        mock_engine.generate_metadata.return_value = mock_result
        
        with patch('saidata_gen.cli.main.SaidataEngine') as mock_engine_class:
            mock_engine_class.return_value = mock_engine
            result = runner.invoke(cli, ['--config', str(config_file), 'generate', 'nginx'])
            
            assert result.exit_code == 0
            # Verify config was passed to engine
            mock_engine_class.assert_called_once_with(config_path=str(config_file))
    
    def test_help_output(self, runner):
        """Test help output contains examples and usage guidance."""
        result = runner.invoke(cli, ['--help'])
        
        assert result.exit_code == 0
        assert 'Generate, validate, and manage saidata YAML files' in result.output
        assert 'Examples:' in result.output
        assert 'saidata-gen generate nginx' in result.output
        assert 'saidata-gen search' in result.output
    
    def test_command_help(self, runner):
        """Test individual command help."""
        result = runner.invoke(cli, ['generate', '--help'])
        
        assert result.exit_code == 0
        assert 'Generate metadata for a software package' in result.output
        assert 'Examples:' in result.output
        assert '--providers' in result.output



class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_keyboard_interrupt(self, runner, mock_engine):
        """Test handling of keyboard interrupt."""
        mock_engine.generate_metadata.side_effect = KeyboardInterrupt()
        
        result = runner.invoke(cli, ['generate', 'nginx'], catch_exceptions=False)
        
        # Click runner catches KeyboardInterrupt and converts to exit code 1
        # The actual keyboard interrupt handling would be tested in integration tests
        assert result.exit_code in [1, 130]
    
    def test_unexpected_error_with_verbose(self, runner, mock_engine):
        """Test handling of unexpected errors with verbose output."""
        mock_engine.generate_metadata.side_effect = RuntimeError("Unexpected error")
        
        result = runner.invoke(cli, ['--verbose', 'generate', 'nginx'])
        
        assert result.exit_code == 1
        assert 'Unexpected error: Unexpected error' in result.output
    
    def test_no_command_shows_help(self, runner):
        """Test that running without command shows help."""
        result = runner.invoke(cli, [])
        
        # Click returns exit code 0 for help, but 2 for missing command
        assert result.exit_code in [0, 2]
        assert 'Usage:' in result.output
        assert 'Commands:' in result.output


class TestEnvironmentVariables:
    """Test environment variable support."""
    
    def test_environment_variable_config(self, runner, mock_engine, sample_metadata):
        """Test that environment variables can be used for configuration."""
        mock_result = MetadataResult(metadata=sample_metadata)
        mock_engine.generate_metadata.return_value = mock_result
        
        # Test that CLI works with environment variables
        # (This would be implemented in the actual configuration system)
        with patch.dict(os.environ, {'SAIDATA_GEN_CONFIG': '/path/to/config.yaml'}):
            result = runner.invoke(cli, ['generate', 'nginx'])
            
            # The test passes if the command runs without error
            # Actual environment variable handling would be tested in configuration tests
            assert result.exit_code == 0