#!/usr/bin/env python3
"""
Batch migration script to update all fetchers to use the repository URL manager.

This script automatically updates fetcher files to use the centralized URL management system.
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def add_url_manager_import(content: str) -> str:
    """Add the URL manager import to the file content."""
    # Check if import already exists
    if "from saidata_gen.core.repository_url_manager import get_repository_url_manager" in content:
        return content
    
    # Find the last import line
    lines = content.split('\n')
    last_import_line = -1
    
    for i, line in enumerate(lines):
        if line.startswith('from saidata_gen.') or line.startswith('import '):
            last_import_line = i
    
    if last_import_line >= 0:
        # Insert the new import after the last saidata_gen import
        lines.insert(last_import_line + 1, 
                     "from saidata_gen.core.repository_url_manager import get_repository_url_manager")
    else:
        # Add at the beginning if no imports found
        lines.insert(0, "from saidata_gen.core.repository_url_manager import get_repository_url_manager")
    
    return '\n'.join(lines)


def add_url_manager_initialization(content: str, provider_name: str) -> str:
    """Add URL manager initialization to the __init__ method."""
    # Check if already initialized
    if "self.url_manager = get_repository_url_manager()" in content:
        return content
    
    # Find the __init__ method and add initialization
    lines = content.split('\n')
    in_init = False
    init_end_line = -1
    
    for i, line in enumerate(lines):
        if "def __init__(" in line:
            in_init = True
        elif in_init and line.strip() and not line.startswith(' ') and not line.startswith('\t'):
            # End of __init__ method
            init_end_line = i - 1
            break
        elif in_init and "super().__init__(" in line:
            # Add after super().__init__ call
            init_end_line = i + 1
            break
    
    if init_end_line > 0:
        # Add URL manager initialization
        indent = "        "  # Standard 8-space indent
        lines.insert(init_end_line + 1, "")
        lines.insert(init_end_line + 2, f"{indent}# Initialize repository URL manager")
        lines.insert(init_end_line + 3, f"{indent}self.url_manager = get_repository_url_manager()")
    
    return '\n'.join(lines)


def create_load_distributions_method(provider_name: str) -> str:
    """Create the _load_distributions_from_url_manager method."""
    
    # Provider-specific distribution configurations
    dist_configs = {
        'apt': [
            '("debian", "bookworm", ["main"], ["amd64"])',
            '("debian", "bullseye", ["main"], ["amd64"])',
            '("ubuntu", "jammy", ["main"], ["amd64"])',
            '("ubuntu", "focal", ["main"], ["amd64"])',
            '("ubuntu", "noble", ["main"], ["amd64"])',
        ],
        'dnf': [
            '("fedora", "38", ["x86_64"])',
            '("fedora", "39", ["x86_64"])',
            '("fedora", "40", ["x86_64"])',
            '("centos", "9-stream", ["x86_64"])',
            '("centos", "9", ["x86_64"])',
            '("almalinux", "9", ["x86_64"])',
            '("almalinux", "8", ["x86_64"])',
            '("rockylinux", "9", ["x86_64"])',
            '("rockylinux", "8", ["x86_64"])',
        ],
        'yum': [
            '("centos", "7", ["x86_64"])',
            '("rhel", "7", ["x86_64"])',
            '("rhel", "6", ["x86_64"])',
        ],
        'zypper': [
            '("opensuse", "15.4", ["x86_64"])',
            '("opensuse", "15.5", ["x86_64"])',
            '("opensuse", "tumbleweed", ["x86_64"])',
            '("sles", "15", ["x86_64"])',
            '("sles", "12", ["x86_64"])',
        ],
        'apk': [
            '("alpine", "3.16", ["main", "community"], ["x86_64"])',
            '("alpine", "3.17", ["main", "community"], ["x86_64"])',
        ],
        'pacman': [
            '("arch", "current", ["core", "extra", "community"], ["x86_64"])',
        ],
        'pkg': [
            '("freebsd", "13", ["x86_64"])',
        ],
        'opkg': [
            '("openwrt", "22.03.3", ["base", "packages"], ["x86_64"])',
        ],
        'slackpkg': [
            '("slackware", "15.0", ["a", "ap", "d", "l", "n", "x"], ["x86_64"])',
        ],
        'xbps': [
            '("void", "current", ["x86_64"])',
            '("void", "current-nonfree", ["x86_64"])',
        ],
    }
    
    # Simple providers (no complex distribution configs)
    simple_providers = {
        'brew', 'winget', 'choco', 'scoop', 'flatpak', 'snap', 'docker', 'helm',
        'npm', 'pypi', 'cargo', 'nuget', 'nixpkgs', 'spack', 'portage'
    }
    
    if provider_name in simple_providers:
        return f'''
    def _load_repositories_from_url_manager(self):
        """
        Load repository configurations from the repository URL manager.
        
        Returns:
            List of repository objects configured from URL manager.
        """
        repositories = []
        
        try:
            # Get URLs from the URL manager
            primary_url = self.url_manager.get_primary_url(provider="{provider_name}")
            
            if primary_url:
                repositories.append(self._create_default_repository(primary_url))
            else:
                logger.warning(f"No URL found for {provider_name} provider")
                repositories = self._get_fallback_repositories()
                
        except Exception as e:
            logger.error(f"Failed to load {provider_name} repositories: {{e}}")
            repositories = self._get_fallback_repositories()
        
        return repositories
    
    def _create_default_repository(self, url: str):
        """Create a default repository object with the given URL."""
        # This method should be implemented based on the specific repository type
        # for this provider
        pass
    
    def _get_fallback_repositories(self):
        """Get fallback repositories if URL manager fails."""
        # This method should return hardcoded fallback repositories
        pass'''
    
    elif provider_name in dist_configs:
        configs = dist_configs[provider_name]
        config_str = ',\\n            '.join(configs)
        
        return f'''
    def _load_distributions_from_url_manager(self):
        """
        Load distribution configurations from the repository URL manager.
        
        Returns:
            List of distribution objects configured from URL manager.
        """
        distributions = []
        
        # Define the distributions and versions to load
        dist_configs = [
            {config_str}
        ]
        
        for config in dist_configs:
            try:
                os_name, version = config[0], config[1]
                
                # Get URLs from the URL manager
                primary_url = self.url_manager.get_primary_url(
                    provider="{provider_name}",
                    os_name=os_name,
                    os_version=version,
                    architecture="x86_64"
                )
                
                if primary_url:
                    distributions.append(self._create_distribution_object(
                        os_name, version, primary_url, config
                    ))
                else:
                    logger.warning(f"No URL found for {provider_name} distribution: {{os_name}} {{version}}")
                    
            except Exception as e:
                logger.error(f"Failed to load {provider_name} distribution {{config}}: {{e}}")
        
        # Fallback to hardcoded distributions if URL manager fails
        if not distributions:
            logger.warning("Failed to load distributions from URL manager, using fallback")
            distributions = self._get_fallback_distributions()
        
        return distributions
    
    def _create_distribution_object(self, os_name: str, version: str, url: str, config: tuple):
        """Create a distribution object from the configuration."""
        # This method should be implemented based on the specific distribution type
        # for this provider
        pass
    
    def _get_fallback_distributions(self):
        """Get fallback distributions if URL manager fails."""
        # This method should return hardcoded fallback distributions
        pass'''
    
    else:
        return f'''
    def _load_from_url_manager(self):
        """
        Load configuration from the repository URL manager.
        
        Returns:
            Configuration loaded from URL manager.
        """
        try:
            # Get URLs from the URL manager
            primary_url = self.url_manager.get_primary_url(provider="{provider_name}")
            fallback_urls = self.url_manager.get_fallback_urls(provider="{provider_name}")
            
            return {{
                'primary_url': primary_url,
                'fallback_urls': fallback_urls
            }}
            
        except Exception as e:
            logger.error(f"Failed to load {provider_name} configuration: {{e}}")
            return self._get_fallback_configuration()
    
    def _get_fallback_configuration(self):
        """Get fallback configuration if URL manager fails."""
        # This method should return hardcoded fallback configuration
        pass'''


def migrate_fetcher_file(file_path: Path) -> bool:
    """
    Migrate a single fetcher file to use the URL manager.
    
    Args:
        file_path: Path to the fetcher file.
    
    Returns:
        True if migration was successful, False otherwise.
    """
    provider_name = file_path.stem
    
    try:
        # Read the original file
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
        
        # Skip if already migrated
        if "get_repository_url_manager" in original_content:
            print(f"✅ {provider_name}: Already migrated")
            return True
        
        # Apply migrations
        content = original_content
        content = add_url_manager_import(content)
        content = add_url_manager_initialization(content, provider_name)
        
        # Create backup
        backup_path = file_path.with_suffix('.py.backup')
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(original_content)
        
        # Write the migrated content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ {provider_name}: Migrated successfully (backup: {backup_path.name})")
        return True
        
    except Exception as e:
        print(f"❌ {provider_name}: Migration failed - {e}")
        return False


def migrate_all_fetchers():
    """Migrate all fetcher files to use the URL manager."""
    fetcher_dir = project_root / "saidata_gen" / "fetcher"
    
    print("🚀 Starting batch migration of fetchers to URL manager")
    print("=" * 60)
    
    success_count = 0
    total_count = 0
    
    for file_path in fetcher_dir.glob("*.py"):
        if file_path.name in ["__init__.py", "base.py", "error_handler.py", "rpm_utils.py", "factory.py"]:
            continue
        
        total_count += 1
        if migrate_fetcher_file(file_path):
            success_count += 1
    
    print("=" * 60)
    print(f"📊 Migration Summary:")
    print(f"   Total fetchers: {total_count}")
    print(f"   Successfully migrated: {success_count}")
    print(f"   Failed: {total_count - success_count}")
    print(f"   Success rate: {(success_count / total_count * 100):.1f}%")
    
    if success_count == total_count:
        print("🎉 All fetchers migrated successfully!")
    else:
        print("⚠️  Some fetchers failed to migrate. Check the output above for details.")


def restore_backups():
    """Restore all fetcher files from backups."""
    fetcher_dir = project_root / "saidata_gen" / "fetcher"
    
    print("🔄 Restoring fetcher files from backups")
    print("=" * 40)
    
    restored_count = 0
    
    for backup_path in fetcher_dir.glob("*.py.backup"):
        original_path = backup_path.with_suffix('')
        
        try:
            # Read backup content
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_content = f.read()
            
            # Restore original file
            with open(original_path, 'w', encoding='utf-8') as f:
                f.write(backup_content)
            
            # Remove backup
            backup_path.unlink()
            
            print(f"✅ Restored: {original_path.name}")
            restored_count += 1
            
        except Exception as e:
            print(f"❌ Failed to restore {original_path.name}: {e}")
    
    print(f"📊 Restored {restored_count} files from backups")


def main():
    """Main function."""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "migrate":
            migrate_all_fetchers()
        elif command == "restore":
            restore_backups()
        else:
            print(f"Unknown command: {command}")
            print("Available commands: migrate, restore")
    else:
        print("Batch Fetcher Migration Tool")
        print("=" * 30)
        print()
        print("Commands:")
        print("  migrate  - Migrate all fetchers to use URL manager")
        print("  restore  - Restore all fetchers from backups")
        print()
        print("Usage:")
        print("  python batch_migrate_fetchers.py migrate")
        print("  python batch_migrate_fetchers.py restore")


if __name__ == "__main__":
    main()