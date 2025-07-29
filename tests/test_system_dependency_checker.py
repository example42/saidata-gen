"""
Tests for the SystemDependencyChecker class.
"""

import subprocess
import sys
from unittest.mock import Mock, patch, MagicMock
import pytest

from saidata_gen.core.system_dependency_checker import SystemDependencyChecker


class TestSystemDependencyChecker:
    """Test cases for SystemDependencyChecker."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.checker = SystemDependencyChecker()
    
    def test_init(self):
        """Test SystemDependencyChecker initialization."""
        assert isinstance(self.checker._checked_commands, dict)
        assert isinstance(self.checker._missing_commands, set)
        assert self.checker._platform == sys.platform
        assert len(self.checker._checked_commands) == 0
        assert len(self.checker._missing_commands) == 0
    
    @patch('shutil.which')
    def test_check_command_availability_available(self, mock_which):
        """Test checking for an available command."""
        mock_which.return_value = '/usr/bin/git'
        
        result = self.checker.check_command_availability('git')
        
        assert result is True
        assert self.checker._checked_commands['git'] is True
        assert 'git' not in self.checker._missing_commands
        mock_which.assert_called_once_with('git')
    
    @patch('shutil.which')
    def test_check_command_availability_missing(self, mock_which):
        """Test checking for a missing command."""
        mock_which.return_value = None
        
        result = self.checker.check_command_availability('nonexistent')
        
        assert result is False
        assert self.checker._checked_commands['nonexistent'] is False
        assert 'nonexistent' in self.checker._missing_commands
        mock_which.assert_called_once_with('nonexistent')
    
    @patch('shutil.which')
    def test_check_command_availability_cached(self, mock_which):
        """Test that command availability is cached."""
        mock_which.return_value = '/usr/bin/git'
        
        # First call
        result1 = self.checker.check_command_availability('git')
        # Second call should use cache
        result2 = self.checker.check_command_availability('git')
        
        assert result1 is True
        assert result2 is True
        # shutil.which should only be called once due to caching
        mock_which.assert_called_once_with('git')
    
    def test_get_installation_instructions_known_command(self):
        """Test getting installation instructions for a known command."""
        instructions = self.checker.get_installation_instructions('git')
        
        assert isinstance(instructions, str)
        assert len(instructions) > 0
        # Should contain platform-specific or default instructions
        assert 'git' in instructions.lower() or 'Git' in instructions
    
    def test_get_installation_instructions_unknown_command(self):
        """Test getting installation instructions for an unknown command."""
        instructions = self.checker.get_installation_instructions('unknowncommand')
        
        assert isinstance(instructions, str)
        assert 'unknowncommand' in instructions
        assert 'not available' in instructions
    
    def test_get_installation_instructions_platform_specific(self):
        """Test that platform-specific instructions are returned when available."""
        # Test with a command that has platform-specific instructions
        instructions = self.checker.get_installation_instructions('brew')
        
        assert isinstance(instructions, str)
        assert len(instructions) > 0
        # Should contain relevant platform information
        if sys.platform == 'darwin':
            assert 'https://brew.sh/' in instructions
        elif sys.platform == 'linux':
            assert 'Linux' in instructions
    
    @patch('saidata_gen.core.system_dependency_checker.logger')
    def test_log_missing_dependency_first_time(self, mock_logger):
        """Test logging a missing dependency for the first time."""
        self.checker.log_missing_dependency('nonexistent', 'test_provider')
        
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        assert 'nonexistent' in call_args
        assert 'test_provider' in call_args
        assert 'nonexistent' in self.checker._missing_commands
    
    @patch('saidata_gen.core.system_dependency_checker.logger')
    def test_log_missing_dependency_duplicate(self, mock_logger):
        """Test that duplicate missing dependency logs are suppressed."""
        # Log the same command+provider combination twice
        self.checker.log_missing_dependency('nonexistent', 'test_provider')
        self.checker.log_missing_dependency('nonexistent', 'test_provider')
        
        # Should only log once
        mock_logger.warning.assert_called_once()
    
    @patch('shutil.which')
    def test_check_multiple_commands(self, mock_which):
        """Test checking multiple commands at once."""
        # Mock different return values for different commands
        def which_side_effect(cmd):
            if cmd == 'git':
                return '/usr/bin/git'
            elif cmd == 'docker':
                return '/usr/bin/docker'
            else:
                return None
        
        mock_which.side_effect = which_side_effect
        
        commands = ['git', 'docker', 'nonexistent']
        results = self.checker.check_multiple_commands(commands)
        
        assert results == {
            'git': True,
            'docker': True,
            'nonexistent': False
        }
        assert mock_which.call_count == 3
    
    def test_get_missing_commands(self):
        """Test getting the set of missing commands."""
        # Add some missing commands
        self.checker._missing_commands.update(['cmd1', 'cmd2'])
        
        missing = self.checker.get_missing_commands()
        
        assert missing == {'cmd1', 'cmd2'}
        # Should return a copy, not the original set
        assert missing is not self.checker._missing_commands
    
    @patch('shutil.which')
    @patch('saidata_gen.core.system_dependency_checker.logger')
    def test_validate_provider_dependencies_all_available(self, mock_logger, mock_which):
        """Test validating provider dependencies when all are available."""
        mock_which.return_value = '/usr/bin/command'
        
        result = self.checker.validate_provider_dependencies('test_provider', ['git', 'docker'])
        
        assert result is True
        mock_logger.warning.assert_not_called()
    
    @patch('shutil.which')
    @patch('saidata_gen.core.system_dependency_checker.logger')
    def test_validate_provider_dependencies_some_missing(self, mock_logger, mock_which):
        """Test validating provider dependencies when some are missing."""
        def which_side_effect(cmd):
            return '/usr/bin/git' if cmd == 'git' else None
        
        mock_which.side_effect = which_side_effect
        
        result = self.checker.validate_provider_dependencies('test_provider', ['git', 'nonexistent'])
        
        assert result is False
        # The warning should be called once for the missing command
        mock_logger.warning.assert_called_once()
        # Verify the missing command was tracked
        assert 'nonexistent' in self.checker._missing_commands
    
    @patch('subprocess.run')
    @patch('shutil.which')
    def test_execute_command_safely_success(self, mock_which, mock_run):
        """Test executing a command successfully."""
        mock_which.return_value = '/usr/bin/git'
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = 'success'
        mock_result.stderr = ''
        mock_run.return_value = mock_result
        
        result = self.checker.execute_command_safely(['git', '--version'], 'test_provider')
        
        assert result is not None
        assert result.returncode == 0
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    @patch('shutil.which')
    def test_execute_command_safely_non_zero_exit(self, mock_which, mock_run):
        """Test executing a command that returns non-zero exit code."""
        mock_which.return_value = '/usr/bin/git'
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ''
        mock_result.stderr = 'error message'
        mock_run.return_value = mock_result
        
        with patch('saidata_gen.core.system_dependency_checker.logger') as mock_logger:
            result = self.checker.execute_command_safely(['git', 'invalid'], 'test_provider')
        
        assert result is not None
        assert result.returncode == 1
        mock_logger.warning.assert_called_once()
    
    @patch('shutil.which')
    def test_execute_command_safely_missing_command(self, mock_which):
        """Test executing a command that doesn't exist."""
        mock_which.return_value = None
        
        with patch('saidata_gen.core.system_dependency_checker.logger') as mock_logger:
            result = self.checker.execute_command_safely(['nonexistent'], 'test_provider')
        
        assert result is None
        # The warning should be called once for the missing command
        mock_logger.warning.assert_called_once()
        # Verify the missing command was tracked
        assert 'nonexistent' in self.checker._missing_commands
    
    def test_execute_command_safely_empty_command(self):
        """Test executing an empty command."""
        with patch('saidata_gen.core.system_dependency_checker.logger') as mock_logger:
            result = self.checker.execute_command_safely([], 'test_provider')
        
        assert result is None
        mock_logger.error.assert_called_once()
    
    @patch('subprocess.run')
    @patch('shutil.which')
    def test_execute_command_safely_timeout(self, mock_which, mock_run):
        """Test executing a command that times out."""
        mock_which.return_value = '/usr/bin/sleep'
        mock_run.side_effect = subprocess.TimeoutExpired(['sleep', '60'], 30)
        
        with patch('saidata_gen.core.system_dependency_checker.logger') as mock_logger:
            result = self.checker.execute_command_safely(['sleep', '60'], 'test_provider', timeout=1)
        
        assert result is None
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0][0]
        assert 'timed out' in call_args
    
    @patch('subprocess.run')
    @patch('shutil.which')
    def test_execute_command_safely_subprocess_error(self, mock_which, mock_run):
        """Test executing a command that raises a subprocess error."""
        mock_which.return_value = '/usr/bin/git'
        mock_run.side_effect = subprocess.SubprocessError('Test error')
        
        with patch('saidata_gen.core.system_dependency_checker.logger') as mock_logger:
            result = self.checker.execute_command_safely(['git', '--version'], 'test_provider')
        
        assert result is None
        mock_logger.error.assert_called_once()
    
    def test_clear_cache(self):
        """Test clearing the command cache."""
        # Add some data to the cache
        self.checker._checked_commands['git'] = True
        self.checker._missing_commands.add('nonexistent')
        
        self.checker.clear_cache()
        
        assert len(self.checker._checked_commands) == 0
        assert len(self.checker._missing_commands) == 0
    
    def test_installation_instructions_coverage(self):
        """Test that installation instructions are available for common commands."""
        common_commands = [
            'brew', 'apt', 'dnf', 'yum', 'pacman', 'emerge', 'apk', 'zypper',
            'pkg', 'nix', 'guix', 'spack', 'snap', 'flatpak', 'choco', 'scoop',
            'winget', 'npm', 'pip', 'cargo', 'gem', 'go', 'docker', 'helm', 'git'
        ]
        
        for command in common_commands:
            instructions = self.checker.get_installation_instructions(command)
            assert isinstance(instructions, str)
            assert len(instructions) > 0
            # Should not be the generic "not available" message
            assert 'not available' not in instructions