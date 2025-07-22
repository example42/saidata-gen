"""
Test coverage configuration and utilities.

This module provides configuration for test coverage measurement and quality gates.
"""

import os
from pathlib import Path
from typing import Dict, List, Set
import coverage


class CoverageConfig:
    """Configuration for test coverage measurement."""
    
    # Minimum coverage thresholds
    MINIMUM_LINE_COVERAGE = 80.0
    MINIMUM_BRANCH_COVERAGE = 70.0
    
    # Files to exclude from coverage
    EXCLUDE_PATTERNS = [
        "*/tests/*",
        "*/test_*",
        "*/__pycache__/*",
        "*/venv/*",
        "*/.venv/*",
        "*/build/*",
        "*/dist/*",
        "*/docs/*",
        "*/examples/*",
        "*/.git/*"
    ]
    
    # Directories to include in coverage
    INCLUDE_PATTERNS = [
        "saidata_gen/*"
    ]
    
    # Critical modules that must have high coverage
    CRITICAL_MODULES = [
        "saidata_gen.core.engine",
        "saidata_gen.core.interfaces", 
        "saidata_gen.core.models",
        "saidata_gen.validation.schema",
        "saidata_gen.generator.core",
        "saidata_gen.fetcher.base"
    ]
    
    # Modules that can have lower coverage (e.g., CLI, examples)
    RELAXED_MODULES = [
        "saidata_gen.cli.main",
        "saidata_gen.examples.*"
    ]
    
    @classmethod
    def get_coverage_config(cls) -> Dict:
        """Get coverage configuration dictionary."""
        return {
            "source": ["saidata_gen"],
            "omit": cls.EXCLUDE_PATTERNS,
            "include": cls.INCLUDE_PATTERNS,
            "branch": True,
            "show_missing": True,
            "skip_covered": False,
            "report": {
                "exclude_lines": [
                    "pragma: no cover",
                    "def __repr__",
                    "if self.debug:",
                    "if settings.DEBUG",
                    "raise AssertionError",
                    "raise NotImplementedError",
                    "if 0:",
                    "if __name__ == .__main__.:",
                    "class .*\\bProtocol\\):",
                    "@(abc\\.)?abstractmethod",
                ],
                "ignore_errors": True,
            },
            "html": {
                "directory": "htmlcov",
                "title": "saidata-gen Test Coverage Report"
            },
            "xml": {
                "output": "coverage.xml"
            }
        }


class TestRunner:
    """Test runner with coverage measurement."""
    
    def __init__(self, config: CoverageConfig = None):
        """Initialize test runner."""
        self.config = config or CoverageConfig()
        self.project_root = Path(__file__).parent.parent
        
    def setup_coverage(self) -> coverage.Coverage:
        """Set up coverage measurement."""
        cov_config = self.config.get_coverage_config()
        
        cov = coverage.Coverage(
            source=cov_config["source"],
            omit=cov_config["omit"],
            include=cov_config["include"],
            branch=cov_config["branch"]
        )
        
        return cov
    
    def run_tests_with_coverage(self) -> Dict:
        """Run tests with coverage measurement."""
        cov = self.setup_coverage()
        
        # Start coverage
        cov.start()
        
        try:
            # Import and run tests
            import pytest
            
            # Run pytest programmatically
            exit_code = pytest.main([
                str(self.project_root / "tests"),
                "-v",
                "--tb=short"
            ])
            
        finally:
            # Stop coverage
            cov.stop()
            cov.save()
        
        # Generate reports
        coverage_data = self.generate_coverage_reports(cov)
        coverage_data["test_exit_code"] = exit_code
        coverage_data["tests_passed"] = exit_code == 0
        
        return coverage_data
    
    def generate_coverage_reports(self, cov: coverage.Coverage) -> Dict:
        """Generate coverage reports."""
        # Generate terminal report
        print("\n" + "="*50)
        print("COVERAGE REPORT")
        print("="*50)
        
        # Get coverage data
        total_coverage = cov.report(show_missing=True)
        
        # Generate HTML report
        html_dir = self.project_root / "htmlcov"
        cov.html_report(directory=str(html_dir))
        
        # Generate XML report
        xml_file = self.project_root / "coverage.xml"
        cov.xml_report(outfile=str(xml_file))
        
        # Analyze coverage by module
        module_coverage = self.analyze_module_coverage(cov)
        
        return {
            "total_coverage": total_coverage,
            "module_coverage": module_coverage,
            "html_report": str(html_dir),
            "xml_report": str(xml_file),
            "meets_threshold": total_coverage >= self.config.MINIMUM_LINE_COVERAGE
        }
    
    def analyze_module_coverage(self, cov: coverage.Coverage) -> Dict:
        """Analyze coverage by module."""
        module_coverage = {}
        
        # Get coverage data
        data = cov.get_data()
        
        for filename in data.measured_files():
            # Convert filename to module name
            rel_path = Path(filename).relative_to(self.project_root)
            if rel_path.parts[0] == "saidata_gen":
                module_parts = rel_path.parts[:-1] + (rel_path.stem,)
                module_name = ".".join(module_parts)
                
                # Get coverage stats for this file
                analysis = cov._analyze(filename)
                total_lines = len(analysis.statements)
                covered_lines = len(analysis.statements - analysis.missing)
                
                if total_lines > 0:
                    coverage_pct = (covered_lines / total_lines) * 100
                    module_coverage[module_name] = {
                        "filename": filename,
                        "total_lines": total_lines,
                        "covered_lines": covered_lines,
                        "coverage_percentage": coverage_pct,
                        "missing_lines": list(analysis.missing)
                    }
        
        return module_coverage
    
    def check_quality_gates(self, coverage_data: Dict) -> Dict:
        """Check if coverage meets quality gates."""
        results = {
            "overall_pass": True,
            "issues": []
        }
        
        # Check overall coverage
        total_coverage = coverage_data["total_coverage"]
        if total_coverage < self.config.MINIMUM_LINE_COVERAGE:
            results["overall_pass"] = False
            results["issues"].append(
                f"Total coverage {total_coverage:.1f}% is below minimum {self.config.MINIMUM_LINE_COVERAGE}%"
            )
        
        # Check critical modules
        module_coverage = coverage_data["module_coverage"]
        for module in self.config.CRITICAL_MODULES:
            if module in module_coverage:
                module_cov = module_coverage[module]["coverage_percentage"]
                if module_cov < self.config.MINIMUM_LINE_COVERAGE:
                    results["overall_pass"] = False
                    results["issues"].append(
                        f"Critical module {module} coverage {module_cov:.1f}% is below minimum {self.config.MINIMUM_LINE_COVERAGE}%"
                    )
            else:
                results["issues"].append(f"Critical module {module} not found in coverage report")
        
        return results


def run_coverage_analysis():
    """Run comprehensive coverage analysis."""
    runner = TestRunner()
    
    print("Starting comprehensive test coverage analysis...")
    
    # Run tests with coverage
    coverage_data = runner.run_tests_with_coverage()
    
    # Check quality gates
    quality_results = runner.check_quality_gates(coverage_data)
    
    # Print results
    print("\n" + "="*50)
    print("COVERAGE ANALYSIS RESULTS")
    print("="*50)
    
    print(f"Total Coverage: {coverage_data['total_coverage']:.1f}%")
    print(f"Meets Threshold: {'✅ YES' if coverage_data['meets_threshold'] else '❌ NO'}")
    print(f"Tests Passed: {'✅ YES' if coverage_data['tests_passed'] else '❌ NO'}")
    
    print(f"\nHTML Report: {coverage_data['html_report']}")
    print(f"XML Report: {coverage_data['xml_report']}")
    
    # Print module coverage
    print("\nMODULE COVERAGE:")
    print("-" * 30)
    for module, data in coverage_data["module_coverage"].items():
        coverage_pct = data["coverage_percentage"]
        status = "✅" if coverage_pct >= 80 else "⚠️" if coverage_pct >= 60 else "❌"
        print(f"{status} {module}: {coverage_pct:.1f}%")
    
    # Print quality gate results
    print("\nQUALITY GATES:")
    print("-" * 30)
    if quality_results["overall_pass"]:
        print("✅ All quality gates passed")
    else:
        print("❌ Quality gate failures:")
        for issue in quality_results["issues"]:
            print(f"  - {issue}")
    
    return coverage_data, quality_results


if __name__ == "__main__":
    coverage_data, quality_results = run_coverage_analysis()
    
    # Exit with appropriate code
    exit_code = 0
    if not coverage_data["tests_passed"]:
        exit_code = 1
    elif not quality_results["overall_pass"]:
        exit_code = 2
    
    exit(exit_code)