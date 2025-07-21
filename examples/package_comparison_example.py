#!/usr/bin/env python3
"""
Example script demonstrating package comparison and selection functionality.

This script shows how to use the package comparison system to identify
alternatives, duplicates, and select the best package from search results.
"""

import sys
import os

# Add the parent directory to the path so we can import saidata_gen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from saidata_gen.core.interfaces import SoftwareMatch
from saidata_gen.search.comparison import PackageComparator, SelectionCriteria
from unittest.mock import Mock


def create_sample_packages():
    """Create sample packages for demonstration."""
    return [
        SoftwareMatch(
            name="nginx",
            provider="apt",
            version="1.18.0",
            description="High-performance web server and reverse proxy",
            score=0.9
        ),
        SoftwareMatch(
            name="nginx",
            provider="brew",
            version="1.21.0",
            description="HTTP and reverse proxy server",
            score=0.8
        ),
        SoftwareMatch(
            name="nginx-full",
            provider="apt",
            version="1.18.0",
            description="Full nginx package with all modules",
            score=0.7
        ),
        SoftwareMatch(
            name="apache2",
            provider="apt",
            version="2.4.41",
            description="Apache HTTP Server",
            score=0.6
        ),
        SoftwareMatch(
            name="httpd",
            provider="brew",
            version="2.4.54",
            description="Apache HTTP Server",
            score=0.5
        ),
        SoftwareMatch(
            name="lighttpd",
            provider="apt",
            version="1.4.55",
            description="Lightweight web server",
            score=0.4
        )
    ]


def create_mock_fetchers():
    """Create mock fetchers for demonstration."""
    return {
        "apt": Mock(),
        "brew": Mock(),
        "snap": Mock()
    }


def demonstrate_package_comparison():
    """Demonstrate package comparison functionality."""
    print("=== Package Comparison and Selection Demo ===\n")
    
    # Create sample data
    packages = create_sample_packages()
    fetchers = create_mock_fetchers()
    comparator = PackageComparator(fetchers)
    
    print("Sample packages:")
    for i, pkg in enumerate(packages, 1):
        print(f"  {i}. {pkg.name} ({pkg.provider}) v{pkg.version or 'unknown'}")
        print(f"     {pkg.description}")
    print()
    
    # 1. Compare packages to identify relationships
    print("1. Comparing packages to identify relationships:")
    comparisons = comparator.compare_packages(packages)
    
    for i, comp in enumerate(comparisons, 1):
        print(f"\n   Comparison {i}:")
        print(f"   Primary: {comp.primary_package.name} ({comp.primary_package.provider})")
        print(f"   Alternatives: {len(comp.alternative_packages)}")
        for alt in comp.alternative_packages:
            similarity = comp.similarity_scores.get(f"{alt.provider}:{alt.name}", 0.0)
            print(f"     - {alt.name} ({alt.provider}) - similarity: {similarity:.2f}")
        print(f"   Common features: {', '.join(comp.common_features) if comp.common_features else 'None'}")
        print(f"   Recommendation: {comp.recommendation_reason} (score: {comp.recommendation_score:.2f})")
    
    # 2. Identify duplicates
    print("\n2. Identifying duplicate packages:")
    duplicates = comparator.identify_duplicates(packages, similarity_threshold=0.8)
    
    if duplicates:
        for i, group in enumerate(duplicates, 1):
            print(f"\n   Duplicate group {i}: {group.canonical_name}")
            print(f"   Type: {group.group_type}, Confidence: {group.confidence:.2f}")
            for pkg in group.packages:
                print(f"     - {pkg.name} ({pkg.provider}) v{pkg.version or 'unknown'}")
    else:
        print("   No duplicates found with the current threshold.")
    
    # 3. Find alternatives for a specific package
    print("\n3. Finding alternatives for nginx (apt):")
    target = packages[0]  # nginx from apt
    candidates = packages[1:]  # all other packages
    
    alternatives = comparator.find_alternatives(target, candidates, similarity_threshold=0.3)
    
    if alternatives:
        print(f"   Found {len(alternatives)} alternatives:")
        for alt in alternatives:
            print(f"     - {alt.name} ({alt.provider}) - score: {alt.score:.2f}")
            print(f"       {alt.description}")
    else:
        print("   No alternatives found with the current threshold.")
    
    # 4. Select best package with different criteria
    print("\n4. Selecting best package with different criteria:")
    
    # Default criteria
    print("\n   a) Default criteria:")
    best_default = comparator.select_best_package(packages)
    if best_default:
        print(f"      Best: {best_default.name} ({best_default.provider}) v{best_default.version or 'unknown'}")
    
    # Prefer brew packages
    print("\n   b) Preferring brew packages:")
    brew_criteria = SelectionCriteria(prefer_popular_providers=["brew"])
    best_brew = comparator.select_best_package(packages, brew_criteria)
    if best_brew:
        print(f"      Best: {best_brew.name} ({best_brew.provider}) v{best_brew.version or 'unknown'}")
    
    # Require version and longer description
    print("\n   c) Requiring version and longer description:")
    strict_criteria = SelectionCriteria(
        require_version=True,
        minimum_description_length=30
    )
    best_strict = comparator.select_best_package(packages, strict_criteria)
    if best_strict:
        print(f"      Best: {best_strict.name} ({best_strict.provider}) v{best_strict.version or 'unknown'}")
    else:
        print("      No package meets the strict criteria.")
    
    # 5. Package similarity analysis
    print("\n5. Package similarity analysis:")
    nginx_apt = packages[0]
    nginx_brew = packages[1]
    apache_apt = packages[3]
    
    similarity_nginx = comparator._calculate_package_similarity(nginx_apt, nginx_brew)
    similarity_different = comparator._calculate_package_similarity(nginx_apt, apache_apt)
    
    print(f"   nginx (apt) vs nginx (brew): {similarity_nginx:.3f}")
    print(f"   nginx (apt) vs apache2 (apt): {similarity_different:.3f}")
    
    print("\n=== Demo completed ===")


if __name__ == "__main__":
    demonstrate_package_comparison()