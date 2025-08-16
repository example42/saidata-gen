"""
Tests for the Repository URL Manager.

This module tests the centralized repository URL management system.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, mock_open

import yaml

from saidata_gen.core.repository_url_manager import (
    RepositoryUrlManager, get_repository_url_manager, reset_repository_url_manager
)


class TestRepositoryUrlManager(unittest.TestCase):
    """Test cases for RepositoryUrlManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Reset the global instance before each test
        reset_repository_url_manager()
        
        # Sample configuration for testing
        self.sample_config = {
            'version': 0.1,
            'apt': {
                'default': {
                    'primary_url': 'https://deb.debian.org/debian/dists/{{ version }}',
                    'fallback_urls': [
                        'https://archive.debian.org/debian/dists/{{ version }}'
                    ]
                },
                'os': {
                    'ubuntu': {
                        'primary_url': 'http://archive.ubuntu.com/ubuntu/dists/{{ version }}',
                        'fallback_urls': [
                            'http://us.archive.ubuntu.com/ubuntu/dists/{{ version }}'
                        ],
                        'versions': {
                            'jammy': {
                                'primary_url': 'http://archive.ubuntu.com/ubuntu/dists/jammy',
                                'security_url': 'http://security.ubuntu.com/ubuntu/dists/jammy-security'
                            }
                        }
                    }
                }
            },
            'npm': {
                'default': {
                    'registry_url': 'https://registry.npmjs.org',
                    'search_url': 'https://registry.npmjs.org/-/v1/search?text={{ software_name }}',
                    'package_url': 'https://registry.npmjs.org/{{ software_name }}'
                }
            }
        }
    
    def test_load_configuration_from_file(self):
        """Test loading configuration from a YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.sample_config, f)
            config_path = f.name
        
        try:
            manager = RepositoryUrlManager(config_path=config_path)
            self.assertEqual(manager._url_config, self.sample_config)
        finally:
            os.unlink(config_path)
    
    def test_load_configuration_file_not_found(self):
        """Test handling of missing configuration file."""
        manager = RepositoryUrlManager(config_path='/nonexistent/path.yaml')
        # Should fall back to empty config
        self.assertEqual(manager._url_config, {})
    
    def test_load_configuration_invalid_yaml(self):
        """Test handling of invalid YAML configuration."""
        # Create a temporary file with invalid YAML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('invalid: yaml: content: [')
            config_path = f.name
        
        try:
            with patch('saidata_gen.core.repository_url_manager.logger') as mock_logger:
                manager = RepositoryUrlManager(config_path=config_path)
                self.assertEqual(manager._url_config, {})
                mock_logger.error.assert_called()
        finally:
            os.unlink(config_path)
    
    def test_get_urls_default_only(self):
        """Test getting URLs with default configuration only."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.sample_config, f)
            config_path = f.name
        
        try:
            manager = RepositoryUrlManager(config_path=config_path)
            urls = manager.get_urls('apt')
            
            # URLs should have template variables substituted with detected values
            self.assertIn('primary_url', urls)
            self.assertIn('fallback_urls', urls)
            self.assertIsInstance(urls['fallback_urls'], list)
            # Template variables should be substituted
            self.assertNotIn('{{ version }}', urls['primary_url'])
        finally:
            os.unlink(config_path)
    
    def test_get_urls_with_os_override(self):
        """Test getting URLs with OS-specific overrides."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.sample_config, f)
            config_path = f.name
        
        try:
            manager = RepositoryUrlManager(config_path=config_path)
            urls = manager.get_urls('apt', os_name='ubuntu')
            
            # Should include OS-specific overrides
            self.assertIn('primary_url', urls)
            self.assertIn('fallback_urls', urls)
            self.assertIn('versions', urls)
            # Should use Ubuntu URLs
            self.assertIn('ubuntu.com', urls['primary_url'])
            # Template variables should be substituted
            self.assertNotIn('{{ version }}', urls['primary_url'])
        finally:
            os.unlink(config_path)
    
    def test_get_urls_with_version_override(self):
        """Test getting URLs with version-specific overrides."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.sample_config, f)
            config_path = f.name
        
        try:
            manager = RepositoryUrlManager(config_path=config_path)
            urls = manager.get_urls('apt', os_name='ubuntu', os_version='jammy')
            
            # Should include version-specific overrides
            self.assertIn('primary_url', urls)
            self.assertIn('security_url', urls)
            self.assertEqual(urls['primary_url'], 'http://archive.ubuntu.com/ubuntu/dists/jammy')
            self.assertEqual(urls['security_url'], 'http://security.ubuntu.com/ubuntu/dists/jammy-security')
        finally:
            os.unlink(config_path)
    
    def test_get_primary_url(self):
        """Test getting the primary URL for a provider."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.sample_config, f)
            config_path = f.name
        
        try:
            manager = RepositoryUrlManager(config_path=config_path)
            
            # Test default primary URL
            primary_url = manager.get_primary_url('apt')
            self.assertIsNotNone(primary_url)
            self.assertIn('deb.debian.org', primary_url)
            # Template variables should be substituted
            self.assertNotIn('{{ version }}', primary_url)
            
            # Test registry URL fallback
            registry_url = manager.get_primary_url('npm')
            self.assertEqual(registry_url, 'https://registry.npmjs.org')
        finally:
            os.unlink(config_path)
    
    def test_get_fallback_urls(self):
        """Test getting fallback URLs for a provider."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.sample_config, f)
            config_path = f.name
        
        try:
            manager = RepositoryUrlManager(config_path=config_path)
            fallback_urls = manager.get_fallback_urls('apt')
            
            self.assertIsInstance(fallback_urls, list)
            self.assertGreater(len(fallback_urls), 0)
            self.assertIn('archive.debian.org', fallback_urls[0])
            # Template variables should be substituted
            self.assertNotIn('{{ version }}', fallback_urls[0])
        finally:
            os.unlink(config_path)
    
    def test_get_search_url(self):
        """Test getting search URL with software name substitution."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.sample_config, f)
            config_path = f.name
        
        try:
            manager = RepositoryUrlManager(config_path=config_path)
            search_url = manager.get_search_url('npm', 'express')
            
            expected_url = 'https://registry.npmjs.org/-/v1/search?text=express'
            self.assertEqual(search_url, expected_url)
        finally:
            os.unlink(config_path)
    
    def test_get_package_url(self):
        """Test getting package-specific URL."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.sample_config, f)
            config_path = f.name
        
        try:
            manager = RepositoryUrlManager(config_path=config_path)
            package_url = manager.get_package_url('npm', 'express')
            
            expected_url = 'https://registry.npmjs.org/express'
            self.assertEqual(package_url, expected_url)
        finally:
            os.unlink(config_path)
    
    def test_template_variable_substitution(self):
        """Test template variable substitution."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.sample_config, f)
            config_path = f.name
        
        try:
            manager = RepositoryUrlManager(config_path=config_path)
            
            # Test with context variables
            urls = manager.get_urls(
                'apt',
                context={'version': 'bookworm', 'arch': 'amd64'}
            )
            
            # URLs should have template variables substituted
            self.assertIn('bookworm', urls['primary_url'])
            self.assertNotIn('{{ version }}', urls['primary_url'])
        finally:
            os.unlink(config_path)
    
    def test_provider_not_found(self):
        """Test handling of unknown provider."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.sample_config, f)
            config_path = f.name
        
        try:
            manager = RepositoryUrlManager(config_path=config_path)
            urls = manager.get_urls('unknown_provider')
            
            self.assertEqual(urls, {})
        finally:
            os.unlink(config_path)
    
    def test_list_providers(self):
        """Test listing all configured providers."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.sample_config, f)
            config_path = f.name
        
        try:
            manager = RepositoryUrlManager(config_path=config_path)
            providers = manager.list_providers()
            
            expected_providers = ['version', 'apt', 'npm']
            self.assertEqual(sorted(providers), sorted(expected_providers))
        finally:
            os.unlink(config_path)
    
    def test_has_provider(self):
        """Test checking if a provider is configured."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.sample_config, f)
            config_path = f.name
        
        try:
            manager = RepositoryUrlManager(config_path=config_path)
            
            self.assertTrue(manager.has_provider('apt'))
            self.assertTrue(manager.has_provider('npm'))
            self.assertFalse(manager.has_provider('unknown'))
        finally:
            os.unlink(config_path)
    
    def test_get_provider_config(self):
        """Test getting full provider configuration."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.sample_config, f)
            config_path = f.name
        
        try:
            manager = RepositoryUrlManager(config_path=config_path)
            config = manager.get_provider_config('apt')
            
            self.assertEqual(config, self.sample_config['apt'])
        finally:
            os.unlink(config_path)
    
    @patch('platform.system')
    @patch('builtins.open', mock_open(read_data='ID=ubuntu\nVERSION_CODENAME=jammy\n'))
    def test_detect_os_linux(self, mock_system):
        """Test OS detection on Linux."""
        mock_system.return_value = 'Linux'
        
        manager = RepositoryUrlManager()
        os_name = manager._detect_os()
        
        self.assertEqual(os_name, 'ubuntu')
    
    @patch('platform.system')
    def test_detect_os_macos(self, mock_system):
        """Test OS detection on macOS."""
        mock_system.return_value = 'Darwin'
        
        manager = RepositoryUrlManager()
        os_name = manager._detect_os()
        
        self.assertEqual(os_name, 'macos')
    
    @patch('platform.system')
    def test_detect_os_windows(self, mock_system):
        """Test OS detection on Windows."""
        mock_system.return_value = 'Windows'
        
        manager = RepositoryUrlManager()
        os_name = manager._detect_os()
        
        self.assertEqual(os_name, 'windows')
    
    @patch('platform.machine')
    def test_detect_architecture(self, mock_machine):
        """Test architecture detection."""
        mock_machine.return_value = 'x86_64'
        
        manager = RepositoryUrlManager()
        arch = manager._detect_architecture()
        
        self.assertEqual(arch, 'x86_64')
        
        # Test architecture normalization
        mock_machine.return_value = 'amd64'
        arch = manager._detect_architecture()
        self.assertEqual(arch, 'x86_64')
    
    def test_global_instance(self):
        """Test the global instance functionality."""
        # First call should create instance
        manager1 = get_repository_url_manager()
        self.assertIsInstance(manager1, RepositoryUrlManager)
        
        # Second call should return same instance
        manager2 = get_repository_url_manager()
        self.assertIs(manager1, manager2)
        
        # Reset should clear the instance
        reset_repository_url_manager()
        manager3 = get_repository_url_manager()
        self.assertIsNot(manager1, manager3)
    
    def test_reload_configuration(self):
        """Test reloading configuration."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.sample_config, f)
            config_path = f.name
        
        try:
            manager = RepositoryUrlManager(config_path=config_path)
            original_config = manager._url_config.copy()
            
            # Modify the file
            modified_config = self.sample_config.copy()
            modified_config['new_provider'] = {'default': {'url': 'https://example.com'}}
            
            with open(config_path, 'w') as f:
                yaml.dump(modified_config, f)
            
            # Reload configuration
            manager.reload_configuration()
            
            # Configuration should be updated
            self.assertNotEqual(manager._url_config, original_config)
            self.assertIn('new_provider', manager._url_config)
        finally:
            os.unlink(config_path)


if __name__ == '__main__':
    unittest.main()