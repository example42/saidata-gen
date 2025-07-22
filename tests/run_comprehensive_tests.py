#!/usr/bin/env python3
"""
Comprehensive test runner for saidata-gen.

This script runs all tests with comprehensive coverage reporting and quality gates.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict, Any
import json


class TestRunner:
    """Comprehensive test runner with coverage and quality reporting."""
    
    def __init__(self, project_root: str = None):
        """Initialize the test runner."""
        self.project_root = Path(project_root) if project_root else Path(__file__).parent.parent
        self.test_dir = self.project_root / "tests"
        self.source_dir = self.project_root / "saidata_gen"
        self.coverage_dir = self.project_root / "htmlcov"
        
    def run_unit_tests(self, verbose: bool = True, fail_fast: bool = False) -> Dict[str, Any]:
        """Run unit tests with coverage."""
        print("🧪 Running unit tests...")
        
        cmd = [
            sys.executable, "-m", "pytest",
            str(self.test_dir),
            "--cov=" + str(self.source_dir),
            "--cov-report=term-missing",
            "--cov-report=html:" + str(self.coverage_dir),
            "--cov-report=xml:coverage.xml",
            "--cov-branch",
            "-m", "unit"
        ]
        
        if verbose:
            cmd.append("-v")
        
        if fail_fast:
            cmd.append("-x")
        
        # Add coverage threshold
        cmd.extend(["--cov-fail-under=80"])
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root)
        
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0
        }
    
    def run_integration_tests(self, verbose: bool = True) -> Dict[str, Any]:
        """Run integration tests."""
        print("🔗 Running integration tests...")
        
        cmd = [
            sys.executable, "-m", "pytest",
            str(self.test_dir),
            "-m", "integration"
        ]
        
        if verbose:
            cmd.append("-v")
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root)
        
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0
        }
    
    def run_smoke_tests(self) -> Dict[str, Any]:
        """Run smoke tests for basic functionality."""
        print("💨 Running smoke tests...")
        
        cmd = [
            sys.executable, "-m", "pytest",
            str(self.test_dir),
            "-m", "smoke",
            "-v"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root)
        
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0
        }
    
    def run_specific_test_file(self, test_file: str, verbose: bool = True) -> Dict[str, Any]:
        """Run a specific test file."""
        print(f"🎯 Running specific test file: {test_file}")
        
        test_path = self.test_dir / test_file
        if not test_path.exists():
            return {
                "returncode": 1,
                "stdout": "",
                "stderr": f"Test file not found: {test_path}",
                "success": False
            }
        
        cmd = [
            sys.executable, "-m", "pytest",
            str(test_path)
        ]
        
        if verbose:
            cmd.append("-v")
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root)
        
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0
        }
    
    def run_coverage_analysis(self) -> Dict[str, Any]:
        """Run comprehensive coverage analysis."""
        print("📊 Running coverage analysis...")
        
        # Run tests with coverage
        unit_result = self.run_unit_tests(verbose=False)
        
        if not unit_result["success"]:
            return {
                "success": False,
                "error": "Unit tests failed, cannot generate coverage report"
            }
        
        # Generate coverage report
        coverage_xml = self.project_root / "coverage.xml"
        coverage_html = self.coverage_dir
        
        analysis = {
            "success": True,
            "coverage_xml": str(coverage_xml) if coverage_xml.exists() else None,
            "coverage_html": str(coverage_html) if coverage_html.exists() else None,
            "unit_test_result": unit_result
        }
        
        # Parse coverage percentage if available
        if "%" in unit_result["stdout"]:
            lines = unit_result["stdout"].split("\n")
            for line in lines:
                if "TOTAL" in line and "%" in line:
                    parts = line.split()
                    for part in parts:
                        if "%" in part:
                            try:
                                coverage_pct = float(part.replace("%", ""))
                                analysis["coverage_percentage"] = coverage_pct
                                analysis["meets_threshold"] = coverage_pct >= 80.0
                                break
                            except ValueError:
                                pass
        
        return analysis
    
    def run_quality_checks(self) -> Dict[str, Any]:
        """Run code quality checks."""
        print("✨ Running quality checks...")
        
        results = {}
        
        # Run mypy type checking
        print("  🔍 Running mypy type checking...")
        mypy_cmd = [sys.executable, "-m", "mypy", str(self.source_dir)]
        mypy_result = subprocess.run(mypy_cmd, capture_output=True, text=True, cwd=self.project_root)
        results["mypy"] = {
            "success": mypy_result.returncode == 0,
            "output": mypy_result.stdout,
            "errors": mypy_result.stderr
        }
        
        # Run black code formatting check
        print("  🎨 Running black code formatting check...")
        black_cmd = [sys.executable, "-m", "black", "--check", str(self.source_dir), str(self.test_dir)]
        black_result = subprocess.run(black_cmd, capture_output=True, text=True, cwd=self.project_root)
        results["black"] = {
            "success": black_result.returncode == 0,
            "output": black_result.stdout,
            "errors": black_result.stderr
        }
        
        # Run isort import sorting check
        print("  📦 Running isort import sorting check...")
        isort_cmd = [sys.executable, "-m", "isort", "--check-only", str(self.source_dir), str(self.test_dir)]
        isort_result = subprocess.run(isort_cmd, capture_output=True, text=True, cwd=self.project_root)
        results["isort"] = {
            "success": isort_result.returncode == 0,
            "output": isort_result.stdout,
            "errors": isort_result.stderr
        }
        
        return results
    
    def generate_test_report(self, results: Dict[str, Any]) -> str:
        """Generate a comprehensive test report."""
        report_lines = [
            "# Comprehensive Test Report",
            "=" * 50,
            ""
        ]
        
        # Unit tests
        if "unit_tests" in results:
            unit_result = results["unit_tests"]
            status = "✅ PASSED" if unit_result["success"] else "❌ FAILED"
            report_lines.extend([
                f"## Unit Tests: {status}",
                f"Return code: {unit_result['returncode']}",
                ""
            ])
            
            if not unit_result["success"]:
                report_lines.extend([
                    "### Errors:",
                    unit_result["stderr"],
                    ""
                ])
        
        # Coverage analysis
        if "coverage" in results:
            coverage_result = results["coverage"]
            if coverage_result["success"]:
                coverage_pct = coverage_result.get("coverage_percentage", "Unknown")
                meets_threshold = coverage_result.get("meets_threshold", False)
                threshold_status = "✅" if meets_threshold else "❌"
                
                report_lines.extend([
                    f"## Coverage Analysis: {threshold_status}",
                    f"Coverage: {coverage_pct}%",
                    f"Meets 80% threshold: {meets_threshold}",
                    ""
                ])
                
                if coverage_result.get("coverage_html"):
                    report_lines.extend([
                        f"HTML Report: {coverage_result['coverage_html']}",
                        ""
                    ])
        
        # Integration tests
        if "integration_tests" in results:
            integration_result = results["integration_tests"]
            status = "✅ PASSED" if integration_result["success"] else "❌ FAILED"
            report_lines.extend([
                f"## Integration Tests: {status}",
                ""
            ])
        
        # Quality checks
        if "quality" in results:
            quality_results = results["quality"]
            report_lines.extend([
                "## Quality Checks:",
                ""
            ])
            
            for check_name, check_result in quality_results.items():
                status = "✅ PASSED" if check_result["success"] else "❌ FAILED"
                report_lines.extend([
                    f"### {check_name.upper()}: {status}",
                    ""
                ])
                
                if not check_result["success"] and check_result["errors"]:
                    report_lines.extend([
                        "Errors:",
                        check_result["errors"],
                        ""
                    ])
        
        return "\n".join(report_lines)
    
    def run_comprehensive_tests(self, 
                              include_integration: bool = True,
                              include_quality: bool = True,
                              verbose: bool = True,
                              fail_fast: bool = False) -> Dict[str, Any]:
        """Run comprehensive test suite."""
        print("🚀 Starting comprehensive test suite...")
        
        results = {}
        
        # Run unit tests with coverage
        results["coverage"] = self.run_coverage_analysis()
        results["unit_tests"] = results["coverage"]["unit_test_result"]
        
        # Run smoke tests
        results["smoke_tests"] = self.run_smoke_tests()
        
        # Run integration tests if requested
        if include_integration:
            results["integration_tests"] = self.run_integration_tests(verbose=verbose)
        
        # Run quality checks if requested
        if include_quality:
            results["quality"] = self.run_quality_checks()
        
        # Generate report
        report = self.generate_test_report(results)
        
        # Save report to file
        report_file = self.project_root / "test_report.md"
        with open(report_file, "w") as f:
            f.write(report)
        
        results["report"] = report
        results["report_file"] = str(report_file)
        
        # Overall success
        overall_success = (
            results["unit_tests"]["success"] and
            results["smoke_tests"]["success"] and
            (not include_integration or results.get("integration_tests", {}).get("success", True)) and
            (not include_quality or all(
                check["success"] for check in results.get("quality", {}).values()
            ))
        )
        
        results["overall_success"] = overall_success
        
        print(f"📋 Test report saved to: {report_file}")
        print(f"🎯 Overall result: {'✅ SUCCESS' if overall_success else '❌ FAILURE'}")
        
        return results


def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(description="Comprehensive test runner for saidata-gen")
    parser.add_argument("--unit-only", action="store_true", help="Run only unit tests")
    parser.add_argument("--integration-only", action="store_true", help="Run only integration tests")
    parser.add_argument("--smoke-only", action="store_true", help="Run only smoke tests")
    parser.add_argument("--coverage-only", action="store_true", help="Run coverage analysis only")
    parser.add_argument("--quality-only", action="store_true", help="Run quality checks only")
    parser.add_argument("--file", help="Run specific test file")
    parser.add_argument("--no-integration", action="store_true", help="Skip integration tests")
    parser.add_argument("--no-quality", action="store_true", help="Skip quality checks")
    parser.add_argument("--quiet", action="store_true", help="Reduce output verbosity")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    # Handle specific modes
    if args.file:
        result = runner.run_specific_test_file(args.file, verbose=not args.quiet)
        sys.exit(0 if result["success"] else 1)
    
    if args.unit_only:
        result = runner.run_unit_tests(verbose=not args.quiet, fail_fast=args.fail_fast)
        print(result["stdout"])
        if result["stderr"]:
            print(result["stderr"], file=sys.stderr)
        sys.exit(result["returncode"])
    
    if args.integration_only:
        result = runner.run_integration_tests(verbose=not args.quiet)
        print(result["stdout"])
        if result["stderr"]:
            print(result["stderr"], file=sys.stderr)
        sys.exit(result["returncode"])
    
    if args.smoke_only:
        result = runner.run_smoke_tests()
        print(result["stdout"])
        if result["stderr"]:
            print(result["stderr"], file=sys.stderr)
        sys.exit(result["returncode"])
    
    if args.coverage_only:
        result = runner.run_coverage_analysis()
        if result["success"]:
            print("Coverage analysis completed successfully")
            if "coverage_percentage" in result:
                print(f"Coverage: {result['coverage_percentage']}%")
        else:
            print("Coverage analysis failed:", result.get("error", "Unknown error"))
        sys.exit(0 if result["success"] else 1)
    
    if args.quality_only:
        results = runner.run_quality_checks()
        all_passed = all(check["success"] for check in results.values())
        for check_name, check_result in results.items():
            status = "✅ PASSED" if check_result["success"] else "❌ FAILED"
            print(f"{check_name}: {status}")
            if not check_result["success"]:
                print(check_result["errors"])
        sys.exit(0 if all_passed else 1)
    
    # Run comprehensive tests
    results = runner.run_comprehensive_tests(
        include_integration=not args.no_integration,
        include_quality=not args.no_quality,
        verbose=not args.quiet,
        fail_fast=args.fail_fast
    )
    
    # Print summary
    print("\n" + "=" * 50)
    print("COMPREHENSIVE TEST SUMMARY")
    print("=" * 50)
    print(results["report"])
    
    sys.exit(0 if results["overall_success"] else 1)


if __name__ == "__main__":
    main()