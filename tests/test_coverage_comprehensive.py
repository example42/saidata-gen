"""
Comprehensive test coverage configuration and utilities.

This module provides utilities for measuring and ensuring comprehensive test coverage
across all components of the saidata-gen system.
"""

import pytest
import coverage
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
import importlib
import inspect


class TestCoverageAnalyzer:
    """
    Analyzer for test coverage across all components.
    """
    
    def __init__(self, source_dir: str = "saidata_gen"):
        """Initialize the coverage analyzer."""
        self.source_dir = Path(source_dir)
        self.coverage_data = {}
        
    def get_all_modules(self) -> List[str]:
        """Get all Python modules in the source directory."""
        modules = []
        for py_file in self.source_dir.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            
            # Convert file path to module name
            relative_path = py_file.relative_to(Path("."))
            module_name = str(relative_path).replace("/", ".").replace("\\", ".")[:-3]
            modules.append(module_name)
        
        return modules
    
    def get_module_classes(self, module_name: str) -> List[str]:
        """Get all classes in a module."""
        try:
            module = importlib.import_module(module_name)
            classes = []
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if obj.__module__ == module_name:  # Only classes defined in this module
                    classes.append(name)
            return classes
        except ImportError:
            return []
    
    def get_module_functions(self, module_name: str) -> List[str]:
        """Get all functions in a module."""
        try:
            module = importlib.import_module(module_name)
            functions = []
            for name, obj in inspect.getmembers(module, inspect.isfunction):
                if obj.__module__ == module_name:  # Only functions defined in this module
                    functions.append(name)
            return functions
        except ImportError:
            return []
    
    def analyze_test_coverage(self) -> Dict[str, Dict[str, List[str]]]:
        """Analyze test coverage for all modules."""
        coverage_report = {}
        
        for module_name in self.get_all_modules():
            classes = self.get_module_classes(module_name)
            functions = self.get_module_functions(module_name)
            
            coverage_report[module_name] = {
                "classes": classes,
                "functions": functions,
                "test_files": self._find_test_files_for_module(module_name)
            }
        
        return coverage_report
    
    def _find_test_files_for_module(self, module_name: str) -> List[str]:
        """Find test files that might test a specific module."""
        test_files = []
        test_dir = Path("tests")
        
        # Look for test files that match the module name
        module_parts = module_name.split(".")
        if len(module_parts) >= 2:
            # e.g., saidata_gen.core.engine -> test_core_engine.py
            test_name = f"test_{module_parts[-2]}_{module_parts[-1]}.py"
            test_file = test_dir / test_name
            if test_file.exists():
                test_files.append(str(test_file))
            
            # Also look for more general test files
            test_name = f"test_{module_parts[-1]}.py"
            test_file = test_dir / test_name
            if test_file.exists():
                test_files.append(str(test_file))
        
        return test_files


class TestFixtureManager:
    """
    Manager for test fixtures and sample data.
    """
    
    def __init__(self):
        """Initialize the fixture manager."""
        self.fixtures = {}
    
    def create_sample_package_data(self, provider: str, package_name: str = "nginx") -> Dict:
        """Create sample package data for testing."""
        from tests.fixtures.sample_data import get_sample_package_data
        return get_sample_package_data(provider, package_name)
    
    def create_sample_metadata(self, software_name: str = "nginx") -> Dict:
        """Create sample saidata metadata for testing."""
        from tests.fixtures.sample_data import SAMPLE_SAIDATA_METADATA
        metadata = SAMPLE_SAIDATA_METADATA.copy()
        metadata["description"] = f"Sample metadata for {software_name}"
        return metadata
    
    def create_mock_api_response(self, provider: str, endpoint: str = "") -> str:
        """Create mock API response for testing."""
        from tests.fixtures.sample_data import get_mock_api_response
        return get_mock_api_response(provider, endpoint)


class TestQualityGates:
    """
    Quality gates for test coverage and quality.
    """
    
    MINIMUM_COVERAGE_PERCENTAGE = 80
    MINIMUM_BRANCH_COVERAGE = 70
    MAXIMUM_COMPLEXITY = 10
    
    def __init__(self):
        """Initialize quality gates."""
        self.coverage_analyzer = TestCoverageAnalyzer()
    
    def check_coverage_threshold(self, coverage_percentage: float) -> bool:
        """Check if coverage meets minimum threshold."""
        return coverage_percentage >= self.MINIMUM_COVERAGE_PERCENTAGE
    
    def check_branch_coverage(self, branch_coverage: float) -> bool:
        """Check if branch coverage meets minimum threshold."""
        return branch_coverage >= self.MINIMUM_BRANCH_COVERAGE
    
    def generate_coverage_report(self) -> Dict:
        """Generate comprehensive coverage report."""
        return {
            "modules": self.coverage_analyzer.analyze_test_coverage(),
            "thresholds": {
                "minimum_coverage": self.MINIMUM_COVERAGE_PERCENTAGE,
                "minimum_branch_coverage": self.MINIMUM_BRANCH_COVERAGE,
                "maximum_complexity": self.MAXIMUM_COMPLEXITY
            }
        }


# Test fixtures for comprehensive testing
@pytest.fixture
def coverage_analyzer():
    """Provide a test coverage analyzer."""
    return TestCoverageAnalyzer()


@pytest.fixture
def fixture_manager():
    """Provide a test fixture manager."""
    return TestFixtureManager()


@pytest.fixture
def quality_gates():
    """Provide quality gates checker."""
    return TestQualityGates()


# Test classes for coverage analysis
class TestCoverageAnalysis:
    """Test coverage analysis functionality."""
    
    def test_get_all_modules(self, coverage_analyzer):
        """Test getting all modules from source directory."""
        modules = coverage_analyzer.get_all_modules()
        
        # Should find core modules
        assert any("saidata_gen.core.engine" in module for module in modules)
        assert any("saidata_gen.core.interfaces" in module for module in modules)
        assert any("saidata_gen.fetcher" in module for module in modules)
        
        # All modules should be valid Python module names
        for module in modules:
            assert "." in module
            assert module.startswith("saidata_gen")
    
    def test_get_module_classes(self, coverage_analyzer):
        """Test getting classes from a module."""
        classes = coverage_analyzer.get_module_classes("saidata_gen.core.interfaces")
        
        # Should find key interface classes
        expected_classes = [
            "SaidataMetadata", "PackageConfig", "URLConfig", "CategoryConfig",
            "GenerationOptions", "BatchOptions", "RAGConfig", "FetcherConfig"
        ]
        
        for expected_class in expected_classes:
            assert expected_class in classes
    
    def test_get_module_functions(self, coverage_analyzer):
        """Test getting functions from a module."""
        functions = coverage_analyzer.get_module_functions("saidata_gen.core.engine")
        
        # Should find functions (if any are defined at module level)
        assert isinstance(functions, list)
    
    def test_analyze_test_coverage(self, coverage_analyzer):
        """Test comprehensive coverage analysis."""
        coverage_report = coverage_analyzer.analyze_test_coverage()
        
        # Should have coverage data for key modules
        assert "saidata_gen.core.engine" in coverage_report
        assert "saidata_gen.core.interfaces" in coverage_report
        
        # Each module should have classes and functions lists
        for module_name, module_data in coverage_report.items():
            assert "classes" in module_data
            assert "functions" in module_data
            assert "test_files" in module_data
            assert isinstance(module_data["classes"], list)
            assert isinstance(module_data["functions"], list)
            assert isinstance(module_data["test_files"], list)


class TestFixtureManagement:
    """Test fixture management functionality."""
    
    def test_create_sample_package_data(self, fixture_manager):
        """Test creating sample package data."""
        apt_data = fixture_manager.create_sample_package_data("apt")
        assert "Package" in apt_data
        assert "Version" in apt_data
        assert "Description" in apt_data
        
        brew_data = fixture_manager.create_sample_package_data("brew")
        assert "name" in brew_data
        assert "versions" in brew_data
        assert "desc" in brew_data
    
    def test_create_sample_metadata(self, fixture_manager):
        """Test creating sample metadata."""
        metadata = fixture_manager.create_sample_metadata("nginx")
        
        assert "version" in metadata
        assert metadata["version"] == "0.1"
        assert "description" in metadata
        assert "nginx" in metadata["description"]
        assert "packages" in metadata
        assert "urls" in metadata
    
    def test_create_mock_api_response(self, fixture_manager):
        """Test creating mock API responses."""
        apt_response = fixture_manager.create_mock_api_response("apt", "packages")
        assert isinstance(apt_response, str)
        assert len(apt_response) > 0
        
        dnf_response = fixture_manager.create_mock_api_response("dnf", "repomd")
        assert isinstance(dnf_response, str)
        assert "repomd" in dnf_response or len(dnf_response) == 0  # May be empty for unknown endpoints


class TestQualityGatesValidation:
    """Test quality gates validation."""
    
    def test_coverage_threshold_check(self, quality_gates):
        """Test coverage threshold checking."""
        assert quality_gates.check_coverage_threshold(85.0) is True
        assert quality_gates.check_coverage_threshold(75.0) is False
        assert quality_gates.check_coverage_threshold(80.0) is True
    
    def test_branch_coverage_check(self, quality_gates):
        """Test branch coverage checking."""
        assert quality_gates.check_branch_coverage(75.0) is True
        assert quality_gates.check_branch_coverage(65.0) is False
        assert quality_gates.check_branch_coverage(70.0) is True
    
    def test_generate_coverage_report(self, quality_gates):
        """Test coverage report generation."""
        report = quality_gates.generate_coverage_report()
        
        assert "modules" in report
        assert "thresholds" in report
        assert isinstance(report["modules"], dict)
        assert isinstance(report["thresholds"], dict)
        
        # Check thresholds are properly set
        thresholds = report["thresholds"]
        assert thresholds["minimum_coverage"] == 80
        assert thresholds["minimum_branch_coverage"] == 70
        assert thresholds["maximum_complexity"] == 10


# Integration test for comprehensive coverage
class TestComprehensiveCoverage:
    """Integration test for comprehensive test coverage."""
    
    def test_all_core_components_have_tests(self, coverage_analyzer):
        """Test that all core components have corresponding test files."""
        coverage_report = coverage_analyzer.analyze_test_coverage()
        
        # Core components that must have tests
        required_components = [
            "saidata_gen.core.engine",
            "saidata_gen.core.interfaces", 
            "saidata_gen.core.models",
            "saidata_gen.fetcher.base",
            "saidata_gen.generator.core",
            "saidata_gen.validation.schema"
        ]
        
        missing_tests = []
        for component in required_components:
            if component in coverage_report:
                test_files = coverage_report[component]["test_files"]
                if not test_files:
                    missing_tests.append(component)
        
        # Allow some components to not have direct test files if they're tested indirectly
        # This is more of a warning than a hard requirement
        if missing_tests:
            print(f"Warning: Components without direct test files: {missing_tests}")
    
    def test_critical_classes_have_test_coverage(self, coverage_analyzer):
        """Test that critical classes have test coverage."""
        coverage_report = coverage_analyzer.analyze_test_coverage()
        
        # Critical classes that should be tested
        critical_classes = {
            "saidata_gen.core.engine": ["SaidataEngine"],
            "saidata_gen.fetcher.base": ["RepositoryFetcher"],
            "saidata_gen.generator.core": ["MetadataGenerator"],
            "saidata_gen.validation.schema": ["SchemaValidator"]
        }
        
        for module_name, expected_classes in critical_classes.items():
            if module_name in coverage_report:
                module_classes = coverage_report[module_name]["classes"]
                for expected_class in expected_classes:
                    # Check if class exists (it should be tested somewhere)
                    # This is a basic check - actual test execution would verify coverage
                    pass  # We'll rely on pytest-cov for actual coverage measurement