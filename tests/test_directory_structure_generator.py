"""
Tests for the DirectoryStructureGenerator class.
"""

import os
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import pytest

from saidata_gen.core.directory_structure import DirectoryStructureGenerator
from saidata_gen.core.configuration import ConfigurationManager
from saidata_gen.core.exceptions import ConfigurationError


class TestDirectoryStructureGenerator:
    """Test cases for DirectoryStructureGenerator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config_manager = Mock(spec=ConfigurationManager)
        self.generator = DirectoryStructureGenerator(self.mock_config_manager)
    
    def test_init_with_config_manager(self):
        """Test initialization with provided config manager."""
        config_manager = Mock(spec=ConfigurationManager)
        generator = DirectoryStructureGenerator(config_manager)
        assert generator.config_manager is config_manager
    
    def test_init_without_config_manager(self):
        """Test initialization without config manager creates default one."""
        with patch('saidata_gen.core.directory_structure.ConfigurationManager') as mock_cm:
            generator = DirectoryStructureGenerator()
            mock_cm.assert_called_once_with()
            assert generator.config_manager is mock_cm.return_value
    
    def test_create_software_directory_success(self):
        """Test successful creation of software directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            software_name = "nginx"
            result_path = self.generator.create_software_directory(software_name, temp_dir)
            
            expected_path = Path(temp_dir).resolve() / software_name
            assert result_path == expected_path
            assert result_path.exists()
            assert result_path.is_dir()
            
            # Check providers directory was created
            providers_dir = result_path / "providers"
            assert providers_dir.exists()
            assert providers_dir.is_dir()
    
    def test_create_software_directory_existing(self):
        """Test creation of software directory when it already exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            software_name = "nginx"
            existing_dir = Path(temp_dir).resolve() / software_name
            existing_dir.mkdir(parents=True)
            
            result_path = self.generator.create_software_directory(software_name, temp_dir)
            
            assert result_path == existing_dir
            assert result_path.exists()
    
    def test_create_software_directory_path_expansion(self):
        """Test that paths are properly expanded."""
        # Test with a real temporary directory to verify path expansion works
        with tempfile.TemporaryDirectory() as temp_dir:
            # Use a path that would need expansion (relative path)
            relative_path = os.path.join(temp_dir, "subdir")
            
            result_path = self.generator.create_software_directory("test", relative_path)
            
            # Verify the path was resolved and the directory was created
            expected_path = Path(relative_path).resolve() / "test"
            assert result_path == expected_path
            assert result_path.exists()
            assert (result_path / "providers").exists()
    
    def test_create_software_directory_permission_error(self):
        """Test handling of permission errors during directory creation."""
        with patch('pathlib.Path.mkdir', side_effect=PermissionError("Permission denied")):
            with pytest.raises(PermissionError):
                self.generator.create_software_directory("test", "/root/forbidden")
    
    def test_write_defaults_file_success(self):
        """Test successful writing of defaults.yaml file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)
            software_config = {
                "version": "0.1",
                "description": "Test software",
                "packages": {"apt": {"name": "test-package"}}
            }
            
            result_path = self.generator.write_defaults_file(
                software_config, output_path, "test-software"
            )
            
            expected_path = output_path / "defaults.yaml"
            assert result_path == expected_path
            assert result_path.exists()
            
            # Verify file contents
            with open(result_path, 'r', encoding='utf-8') as f:
                loaded_config = yaml.safe_load(f)
            
            assert loaded_config == software_config
    
    def test_write_defaults_file_yaml_formatting(self):
        """Test that YAML is formatted correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)
            software_config = {"key": "value", "nested": {"inner": "data"}}
            
            self.generator.write_defaults_file(software_config, output_path)
            
            defaults_path = output_path / "defaults.yaml"
            with open(defaults_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check that it's not flow style (no {})
            assert "{" not in content
            assert "}" not in content
            # Check proper indentation
            assert "  inner: data" in content
    
    def test_write_defaults_file_io_error(self):
        """Test handling of IO errors during file writing."""
        with patch('builtins.open', side_effect=IOError("Disk full")):
            with pytest.raises(IOError):
                self.generator.write_defaults_file({}, Path("/tmp"), "test")
    
    def test_write_provider_files_creates_different_configs(self):
        """Test that provider files are created when configs differ from defaults."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)
            providers_dir = output_path / "providers"
            providers_dir.mkdir()
            
            provider_configs = {
                "apt": {"name": "custom-apt-package"},
                "brew": {"name": "custom-brew-package"}
            }
            
            # Mock should_create_provider_file to return True for both
            self.mock_config_manager.should_create_provider_file.side_effect = [True, True]
            
            result = self.generator.write_provider_files(
                provider_configs, output_path, "test-software"
            )
            
            assert len(result) == 2
            assert "apt" in result
            assert "brew" in result
            
            # Check files were created
            apt_file = providers_dir / "apt.yaml"
            brew_file = providers_dir / "brew.yaml"
            assert apt_file.exists()
            assert brew_file.exists()
            
            # Verify file contents
            with open(apt_file, 'r', encoding='utf-8') as f:
                apt_config = yaml.safe_load(f)
            assert apt_config == provider_configs["apt"]
    
    def test_write_provider_files_skips_matching_configs(self):
        """Test that provider files are skipped when configs match defaults."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)
            providers_dir = output_path / "providers"
            providers_dir.mkdir()
            
            provider_configs = {
                "apt": {"name": "default-package"},
                "brew": {"name": "custom-package"}
            }
            
            # Mock should_create_provider_file: False for apt, True for brew
            self.mock_config_manager.should_create_provider_file.side_effect = [False, True]
            
            result = self.generator.write_provider_files(
                provider_configs, output_path, "test-software"
            )
            
            assert len(result) == 1
            assert "brew" in result
            assert "apt" not in result
            
            # Check only brew file was created
            apt_file = providers_dir / "apt.yaml"
            brew_file = providers_dir / "brew.yaml"
            assert not apt_file.exists()
            assert brew_file.exists()
    
    def test_write_provider_files_handles_config_error(self):
        """Test handling of configuration errors for individual providers."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)
            providers_dir = output_path / "providers"
            providers_dir.mkdir()
            
            provider_configs = {
                "apt": {"name": "package1"},
                "brew": {"name": "package2"}
            }
            
            # Mock should_create_provider_file: ConfigurationError for apt, True for brew
            self.mock_config_manager.should_create_provider_file.side_effect = [
                ConfigurationError("Provider not found"), True
            ]
            
            # Should not raise exception, but continue with other providers
            result = self.generator.write_provider_files(
                provider_configs, output_path, "test-software"
            )
            
            assert len(result) == 1
            assert "brew" in result
            assert "apt" not in result
    
    def test_write_provider_files_yaml_error(self):
        """Test handling of YAML serialization errors."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)
            providers_dir = output_path / "providers"
            providers_dir.mkdir()
            
            provider_configs = {"apt": {"name": "test"}}
            
            self.mock_config_manager.should_create_provider_file.return_value = True
            
            # Mock yaml.dump to raise an error
            with patch('yaml.dump', side_effect=yaml.YAMLError("Serialization failed")):
                with pytest.raises(yaml.YAMLError):
                    self.generator.write_provider_files(
                        provider_configs, output_path, "test-software"
                    )
    
    def test_cleanup_empty_provider_directory_removes_empty(self):
        """Test that empty providers directory is removed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)
            providers_dir = output_path / "providers"
            providers_dir.mkdir()
            
            result = self.generator.cleanup_empty_provider_directory(output_path)
            
            assert result is True
            assert not providers_dir.exists()
    
    def test_cleanup_empty_provider_directory_keeps_non_empty(self):
        """Test that non-empty providers directory is kept."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)
            providers_dir = output_path / "providers"
            providers_dir.mkdir()
            
            # Create a file in the directory
            test_file = providers_dir / "test.yaml"
            test_file.write_text("test: data")
            
            result = self.generator.cleanup_empty_provider_directory(output_path)
            
            assert result is False
            assert providers_dir.exists()
            assert test_file.exists()
    
    def test_cleanup_empty_provider_directory_nonexistent(self):
        """Test cleanup when providers directory doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)
            
            result = self.generator.cleanup_empty_provider_directory(output_path)
            
            assert result is False
    
    def test_cleanup_empty_provider_directory_permission_error(self):
        """Test handling of permission errors during cleanup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir)
            providers_dir = output_path / "providers"
            providers_dir.mkdir()
            
            with patch('pathlib.Path.rmdir', side_effect=PermissionError("Permission denied")):
                result = self.generator.cleanup_empty_provider_directory(output_path)
                
                assert result is False
                assert providers_dir.exists()  # Directory should still exist
    
    def test_generate_complete_structure_success(self):
        """Test complete structure generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            software_name = "nginx"
            software_config = {"version": "0.1", "description": "Web server"}
            provider_configs = {
                "apt": {"name": "nginx"},
                "brew": {"name": "nginx"}
            }
            
            # Mock should_create_provider_file to create one file
            self.mock_config_manager.should_create_provider_file.side_effect = [True, False]
            
            result = self.generator.generate_complete_structure(
                software_name, software_config, provider_configs, temp_dir
            )
            
            assert "software_directory" in result
            assert "defaults_file" in result
            assert "provider_files" in result
            assert "providers_directory_removed" in result
            
            # Check directory structure
            software_dir = result["software_directory"]
            assert software_dir.exists()
            assert software_dir.name == software_name
            
            # Check defaults file
            defaults_file = result["defaults_file"]
            assert defaults_file.exists()
            assert defaults_file.name == "defaults.yaml"
            
            # Check provider files
            provider_files = result["provider_files"]
            assert len(provider_files) == 1
            assert "apt" in provider_files
            
            # Providers directory should not be removed (has files)
            assert result["providers_directory_removed"] is False
    
    def test_generate_complete_structure_no_provider_files(self):
        """Test complete structure generation with no provider files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            software_name = "nginx"
            software_config = {"version": "0.1"}
            provider_configs = {"apt": {"name": "nginx"}}
            
            # Mock should_create_provider_file to return False
            self.mock_config_manager.should_create_provider_file.return_value = False
            
            result = self.generator.generate_complete_structure(
                software_name, software_config, provider_configs, temp_dir
            )
            
            # No provider files should be created
            assert len(result["provider_files"]) == 0
            
            # Providers directory should be removed
            assert result["providers_directory_removed"] is True
    
    def test_validate_output_path_success(self):
        """Test successful output path validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.generator.validate_output_path(temp_dir)
            
            assert result == Path(temp_dir).resolve()
            assert result.exists()
    
    def test_validate_output_path_creates_missing_dirs(self):
        """Test that missing parent directories are created."""
        with tempfile.TemporaryDirectory() as temp_dir:
            nested_path = Path(temp_dir) / "level1" / "level2"
            
            result = self.generator.validate_output_path(nested_path)
            
            assert result == nested_path.resolve()
            assert result.exists()
    
    def test_validate_output_path_expands_user(self):
        """Test that user home directory is expanded."""
        with patch('saidata_gen.core.directory_structure.Path') as mock_path_class:
            mock_path = Mock()
            mock_resolved_path = Mock()
            
            mock_path_class.return_value = mock_path
            mock_path.expanduser.return_value = mock_path
            mock_path.resolve.return_value = mock_resolved_path
            
            with patch('os.access', return_value=True):
                result = self.generator.validate_output_path("~/test")
                
                mock_path_class.assert_called_once_with("~/test")
                mock_path.expanduser.assert_called_once()
                mock_path.resolve.assert_called_once()
                assert result is mock_resolved_path
    
    def test_validate_output_path_permission_error(self):
        """Test handling of permission errors during validation."""
        with patch('os.access', return_value=False):
            with tempfile.TemporaryDirectory() as temp_dir:
                with pytest.raises(OSError, match="No write permission"):
                    self.generator.validate_output_path(temp_dir)
    
    def test_get_structure_info_nonexistent(self):
        """Test getting info for non-existent directory."""
        non_existent = Path("/non/existent/path")
        
        info = self.generator.get_structure_info(non_existent)
        
        expected = {
            "exists": False,
            "has_defaults": False,
            "has_providers_dir": False,
            "provider_files": [],
            "total_files": 0
        }
        assert info == expected
    
    def test_get_structure_info_complete_structure(self):
        """Test getting info for complete directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            software_dir = Path(temp_dir) / "nginx"
            software_dir.mkdir()
            
            # Create defaults.yaml
            defaults_file = software_dir / "defaults.yaml"
            defaults_file.write_text("version: 0.1")
            
            # Create providers directory with files
            providers_dir = software_dir / "providers"
            providers_dir.mkdir()
            
            apt_file = providers_dir / "apt.yaml"
            apt_file.write_text("name: nginx")
            
            brew_file = providers_dir / "brew.yaml"
            brew_file.write_text("name: nginx")
            
            info = self.generator.get_structure_info(software_dir)
            
            assert info["exists"] is True
            assert info["has_defaults"] is True
            assert info["has_providers_dir"] is True
            assert set(info["provider_files"]) == {"apt", "brew"}
            assert info["total_files"] == 3  # defaults.yaml + 2 provider files
    
    def test_get_structure_info_defaults_only(self):
        """Test getting info for directory with only defaults.yaml."""
        with tempfile.TemporaryDirectory() as temp_dir:
            software_dir = Path(temp_dir) / "nginx"
            software_dir.mkdir()
            
            # Create only defaults.yaml
            defaults_file = software_dir / "defaults.yaml"
            defaults_file.write_text("version: 0.1")
            
            info = self.generator.get_structure_info(software_dir)
            
            assert info["exists"] is True
            assert info["has_defaults"] is True
            assert info["has_providers_dir"] is False
            assert info["provider_files"] == []
            assert info["total_files"] == 1
    
    def test_get_structure_info_providers_read_error(self):
        """Test handling of errors when reading providers directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            software_dir = Path(temp_dir) / "nginx"
            software_dir.mkdir()
            
            providers_dir = software_dir / "providers"
            providers_dir.mkdir()
            
            # Mock the glob method to raise an error
            with patch('pathlib.Path.glob', side_effect=OSError("Permission denied")):
                info = self.generator.get_structure_info(software_dir)
                
                assert info["has_providers_dir"] is True
                assert info["provider_files"] == []  # Should be empty due to error
                assert info["total_files"] == 0