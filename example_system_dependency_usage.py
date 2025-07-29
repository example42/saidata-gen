#!/usr/bin/env python3
"""
Example usage of SystemDependencyChecker in a fetcher.

This demonstrates how the SystemDependencyChecker would be integrated
into fetcher classes to handle missing system dependencies gracefully.
"""

from saidata_gen.core.system_dependency_checker import SystemDependencyChecker


class ExampleFetcher:
    """Example fetcher showing SystemDependencyChecker integration."""
    
    def __init__(self):
        self.dependency_checker = SystemDependencyChecker()
        self.provider_name = "example"
        self.required_commands = ["git", "curl", "jq"]
    
    def initialize(self):
        """Initialize the fetcher and check dependencies."""
        print(f"Initializing {self.provider_name} fetcher...")
        
        # Validate all required dependencies
        if not self.dependency_checker.validate_provider_dependencies(
            self.provider_name, self.required_commands
        ):
            print(f"Some dependencies are missing for {self.provider_name} provider")
            return False
        
        print(f"All dependencies available for {self.provider_name} provider")
        return True
    
    def fetch_data(self):
        """Fetch data using system commands."""
        # Example: Execute git command safely
        result = self.dependency_checker.execute_command_safely(
            ["git", "--version"], self.provider_name
        )
        
        if result and result.returncode == 0:
            print(f"Git version: {result.stdout.strip()}")
        else:
            print("Failed to get git version")
        
        # Example: Execute curl command safely
        result = self.dependency_checker.execute_command_safely(
            ["curl", "--version"], self.provider_name, timeout=10
        )
        
        if result and result.returncode == 0:
            print("Curl is available")
        else:
            print("Curl command failed")


def main():
    """Demonstrate SystemDependencyChecker usage."""
    print("=== SystemDependencyChecker Example ===\n")
    
    # Create a dependency checker
    checker = SystemDependencyChecker()
    
    # Check individual commands
    print("1. Checking individual commands:")
    commands_to_check = ["git", "python", "nonexistent_command"]
    for cmd in commands_to_check:
        available = checker.check_command_availability(cmd)
        print(f"   {cmd}: {'✓ Available' if available else '✗ Missing'}")
        if not available:
            instructions = checker.get_installation_instructions(cmd)
            print(f"      Installation: {instructions}")
    
    print("\n2. Checking multiple commands at once:")
    results = checker.check_multiple_commands(["git", "docker", "kubectl"])
    for cmd, available in results.items():
        print(f"   {cmd}: {'✓ Available' if available else '✗ Missing'}")
    
    print("\n3. Example fetcher integration:")
    fetcher = ExampleFetcher()
    if fetcher.initialize():
        fetcher.fetch_data()
    
    print("\n4. Missing commands summary:")
    missing = checker.get_missing_commands()
    if missing:
        print(f"   Missing commands: {', '.join(missing)}")
    else:
        print("   No missing commands detected")


if __name__ == "__main__":
    main()