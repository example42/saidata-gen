"""
System dependency checker for saidata-gen.

This module provides functionality to check for required system commands
and handle missing dependencies gracefully.
"""

import logging
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Set


logger = logging.getLogger(__name__)


class SystemDependencyChecker:
    """
    Checker for system dependencies and commands.
    
    This class provides functionality to validate required system commands,
    provide installation instructions, and handle missing dependencies gracefully.
    """
    
    # Installation instructions for common commands by platform
    INSTALLATION_INSTRUCTIONS = {
        "brew": {
            "darwin": "Install Homebrew from https://brew.sh/",
            "linux": "Install Homebrew for Linux from https://docs.brew.sh/Homebrew-on-Linux",
            "default": "Install Homebrew from https://brew.sh/"
        },
        "apt": {
            "linux": "apt is typically pre-installed on Debian/Ubuntu systems",
            "default": "apt is only available on Debian-based Linux distributions"
        },
        "dnf": {
            "linux": "dnf is typically pre-installed on Fedora systems. Install with: sudo yum install dnf",
            "default": "dnf is only available on Red Hat-based Linux distributions"
        },
        "yum": {
            "linux": "yum is typically pre-installed on RHEL/CentOS systems",
            "default": "yum is only available on Red Hat-based Linux distributions"
        },
        "pacman": {
            "linux": "pacman is typically pre-installed on Arch Linux systems",
            "default": "pacman is only available on Arch Linux systems"
        },
        "emerge": {
            "linux": "emerge is typically pre-installed on Gentoo systems",
            "default": "emerge is only available on Gentoo Linux systems"
        },
        "apk": {
            "linux": "apk is typically pre-installed on Alpine Linux systems",
            "default": "apk is only available on Alpine Linux systems"
        },
        "zypper": {
            "linux": "zypper is typically pre-installed on openSUSE systems",
            "default": "zypper is only available on openSUSE/SLES systems"
        },
        "pkg": {
            "freebsd": "pkg is typically pre-installed on FreeBSD systems",
            "default": "pkg is only available on FreeBSD systems"
        },
        "portage": {
            "linux": "portage is typically pre-installed on Gentoo systems",
            "default": "portage is only available on Gentoo Linux systems"
        },
        "nix": {
            "darwin": "Install Nix from https://nixos.org/download.html",
            "linux": "Install Nix from https://nixos.org/download.html",
            "default": "Install Nix from https://nixos.org/download.html"
        },
        "guix": {
            "linux": "Install GNU Guix from https://guix.gnu.org/download/",
            "default": "Install GNU Guix from https://guix.gnu.org/download/"
        },
        "spack": {
            "linux": "Install Spack from https://spack.io/",
            "darwin": "Install Spack from https://spack.io/",
            "default": "Install Spack from https://spack.io/"
        },
        "snap": {
            "linux": "Install snapd: sudo apt install snapd (Ubuntu/Debian) or sudo dnf install snapd (Fedora)",
            "default": "snap is only available on Linux systems with snapd installed"
        },
        "flatpak": {
            "linux": "Install Flatpak: sudo apt install flatpak (Ubuntu/Debian) or sudo dnf install flatpak (Fedora)",
            "default": "Flatpak is only available on Linux systems"
        },
        "choco": {
            "win32": "Install Chocolatey from https://chocolatey.org/install",
            "default": "Chocolatey is only available on Windows systems"
        },
        "scoop": {
            "win32": "Install Scoop from https://scoop.sh/",
            "default": "Scoop is only available on Windows systems"
        },
        "winget": {
            "win32": "winget is pre-installed on Windows 10 1709+ and Windows 11",
            "default": "winget is only available on Windows systems"
        },
        "npm": {
            "darwin": "Install Node.js from https://nodejs.org/ or use brew install node",
            "linux": "Install Node.js from your package manager or https://nodejs.org/",
            "win32": "Install Node.js from https://nodejs.org/",
            "default": "Install Node.js from https://nodejs.org/"
        },
        "pip": {
            "darwin": "pip is typically installed with Python. Install Python from https://python.org/",
            "linux": "Install python3-pip from your package manager",
            "win32": "pip is typically installed with Python. Install Python from https://python.org/",
            "default": "pip is typically installed with Python"
        },
        "cargo": {
            "darwin": "Install Rust from https://rustup.rs/",
            "linux": "Install Rust from https://rustup.rs/",
            "win32": "Install Rust from https://rustup.rs/",
            "default": "Install Rust from https://rustup.rs/"
        },
        "gem": {
            "darwin": "gem is typically installed with Ruby. Install Ruby from https://ruby-lang.org/",
            "linux": "Install ruby and ruby-dev from your package manager",
            "win32": "Install Ruby from https://rubyinstaller.org/",
            "default": "gem is typically installed with Ruby"
        },
        "go": {
            "darwin": "Install Go from https://golang.org/dl/ or use brew install go",
            "linux": "Install Go from your package manager or https://golang.org/dl/",
            "win32": "Install Go from https://golang.org/dl/",
            "default": "Install Go from https://golang.org/dl/"
        },
        "docker": {
            "darwin": "Install Docker Desktop from https://docker.com/products/docker-desktop",
            "linux": "Install Docker from your package manager or https://docs.docker.com/engine/install/",
            "win32": "Install Docker Desktop from https://docker.com/products/docker-desktop",
            "default": "Install Docker from https://docker.com/"
        },
        "helm": {
            "darwin": "Install Helm from https://helm.sh/docs/intro/install/ or use brew install helm",
            "linux": "Install Helm from https://helm.sh/docs/intro/install/",
            "win32": "Install Helm from https://helm.sh/docs/intro/install/",
            "default": "Install Helm from https://helm.sh/docs/intro/install/"
        },
        "git": {
            "darwin": "git is typically pre-installed or install with brew install git",
            "linux": "Install git from your package manager",
            "win32": "Install Git from https://git-scm.com/download/win",
            "default": "Install Git from https://git-scm.com/"
        }
    }
    
    def __init__(self):
        """Initialize the system dependency checker."""
        self._checked_commands: Dict[str, bool] = {}
        self._missing_commands: Set[str] = set()
        self._platform = sys.platform
    
    def check_command_availability(self, command: str) -> bool:
        """
        Check if a system command is available.
        
        Args:
            command: Name of the command to check.
            
        Returns:
            True if the command is available, False otherwise.
        """
        # Return cached result if we've already checked this command
        if command in self._checked_commands:
            return self._checked_commands[command]
        
        # Use shutil.which to check if the command is available
        available = shutil.which(command) is not None
        
        # Cache the result
        self._checked_commands[command] = available
        
        # Track missing commands
        if not available:
            self._missing_commands.add(command)
        
        logger.debug(f"Command '{command}' availability: {available}")
        return available
    
    def get_installation_instructions(self, command: str) -> str:
        """
        Get installation instructions for a command.
        
        Args:
            command: Name of the command to get instructions for.
            
        Returns:
            Installation instructions for the command.
        """
        if command not in self.INSTALLATION_INSTRUCTIONS:
            return f"Installation instructions for '{command}' are not available. Please consult the official documentation."
        
        instructions = self.INSTALLATION_INSTRUCTIONS[command]
        
        # Return platform-specific instructions if available, otherwise default
        if self._platform in instructions:
            return instructions[self._platform]
        else:
            return instructions.get("default", f"Please install '{command}' according to your system's package manager.")
    
    def log_missing_dependency(self, command: str, provider: str) -> None:
        """
        Log a missing dependency with consistent formatting.
        
        Args:
            command: Name of the missing command.
            provider: Name of the provider that requires the command.
        """
        # Create a unique key for command+provider combination to avoid duplicate logs
        log_key = f"{command}:{provider}"
        if not hasattr(self, '_logged_dependencies'):
            self._logged_dependencies = set()
        
        if log_key in self._logged_dependencies:
            # Only log once per command+provider combination to avoid spam
            return
        
        self._logged_dependencies.add(log_key)
        self._missing_commands.add(command)
        
        instructions = self.get_installation_instructions(command)
        
        logger.warning(
            f"Missing system dependency for {provider} provider: '{command}' command not found. "
            f"Provider will be skipped. {instructions}"
        )
    
    def check_multiple_commands(self, commands: List[str]) -> Dict[str, bool]:
        """
        Check availability of multiple commands at once.
        
        Args:
            commands: List of command names to check.
            
        Returns:
            Dictionary mapping command names to their availability status.
        """
        results = {}
        for command in commands:
            results[command] = self.check_command_availability(command)
        return results
    
    def get_missing_commands(self) -> Set[str]:
        """
        Get the set of commands that have been checked and found to be missing.
        
        Returns:
            Set of missing command names.
        """
        return self._missing_commands.copy()
    
    def validate_provider_dependencies(self, provider: str, required_commands: List[str]) -> bool:
        """
        Validate that all required commands for a provider are available.
        
        Args:
            provider: Name of the provider.
            required_commands: List of commands required by the provider.
            
        Returns:
            True if all commands are available, False otherwise.
        """
        all_available = True
        
        for command in required_commands:
            if not self.check_command_availability(command):
                self.log_missing_dependency(command, provider)
                all_available = False
        
        return all_available
    
    def execute_command_safely(self, command: List[str], provider: str, 
                              timeout: int = 30) -> Optional[subprocess.CompletedProcess]:
        """
        Execute a system command safely with proper error handling.
        
        Args:
            command: Command and arguments as a list.
            provider: Name of the provider executing the command.
            timeout: Timeout in seconds for command execution.
            
        Returns:
            CompletedProcess object if successful, None if failed.
        """
        if not command:
            logger.error(f"Empty command provided for {provider} provider")
            return None
        
        command_name = command[0]
        
        # Check if the command is available
        if not self.check_command_availability(command_name):
            self.log_missing_dependency(command_name, provider)
            return None
        
        try:
            logger.debug(f"Executing command for {provider}: {' '.join(command)}")
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False  # Don't raise exception on non-zero exit codes
            )
            
            # Log non-zero exit codes but don't treat them as fatal errors
            if result.returncode != 0:
                logger.warning(
                    f"Command '{' '.join(command)}' for {provider} provider returned "
                    f"exit code {result.returncode}. stderr: {result.stderr.strip()}"
                )
            
            return result
            
        except subprocess.TimeoutExpired:
            logger.error(f"Command '{' '.join(command)}' for {provider} provider timed out after {timeout} seconds")
            return None
        except subprocess.SubprocessError as e:
            logger.error(f"Failed to execute command '{' '.join(command)}' for {provider} provider: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error executing command '{' '.join(command)}' for {provider} provider: {e}")
            return None
    
    def clear_cache(self) -> None:
        """Clear the command availability cache."""
        self._checked_commands.clear()
        self._missing_commands.clear()
        if hasattr(self, '_logged_dependencies'):
            self._logged_dependencies.clear()
        logger.debug("System dependency checker cache cleared")