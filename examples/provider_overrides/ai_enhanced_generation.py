#!/usr/bin/env python3
"""
AI-Enhanced Metadata Generation Example

This example demonstrates how to use AI enhancement to fill missing metadata fields
while maintaining repository data as the authoritative source.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any

# Add the parent directory to the path so we can import saidata_gen
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from saidata_gen.ai.enhancer import AIMetadataEnhancer, AIProviderConfig
from saidata_gen.generator.core import MetadataGenerator
from saidata_gen.core.interfaces import PackageInfo


def create_mock_repository_data() -> Dict[str, Any]:
    """Create mock repository data with some missing fields."""
    return {
        "version": "0.1",
        "packages": {
            "default": {
                "name": "nginx",
                "version": "1.18.0"
            }
        },
        "services": {
            "default": {
                "name": "nginx"
            }
        },
        "directories": {
            "config": {
                "path": "/etc/nginx"
            }
        },
        # Missing fields that AI can fill:
        # - description
        # - urls (website, source, documentation)
        # - category
        # - license
        # - platforms
    }


def create_mock_package_sources() -> list:
    """Create mock package sources for demonstration."""
    return [
        PackageInfo(
            name="nginx",
            version="1.18.0",
            description="High-performance web server",
            provider="apt",
            metadata={"architecture": "amd64"}
        ),
        PackageInfo(
            name="nginx",
            version="1.18.0", 
            description="HTTP and reverse proxy server",
            provider="brew",
            metadata={"formula": "nginx"}
        )
    ]


def demonstrate_ai_enhancement():
    """Demonstrate AI enhancement capabilities."""
    print("=== AI-Enhanced Metadata Generation Example ===\n")
    
    # Check if AI providers are available
    print("1. Checking AI provider availability...")
    
    providers_to_test = ["openai", "anthropic", "local"]
    available_providers = []
    
    for provider in providers_to_test:
        try:
            enhancer = AIMetadataEnhancer(provider=provider)
            if enhancer.is_available():
                available_providers.append(provider)
                print(f"✓ {provider} is available")
            else:
                print(f"✗ {provider} is not available (missing API key or configuration)")
        except Exception as e:
            print(f"✗ {provider} failed to initialize: {e}")
    
    if not available_providers:
        print("\n⚠️  No AI providers are available. This example will demonstrate the workflow")
        print("   with mock data. To use real AI enhancement, configure an API key:")
        print("   - OpenAI: Set OPENAI_API_KEY environment variable")
        print("   - Anthropic: Set ANTHROPIC_API_KEY environment variable")
        print("   - Local: Set up a local model server (e.g., Ollama)")
        use_mock_ai = True
        selected_provider = "openai"  # Use for demonstration
    else:
        use_mock_ai = False
        selected_provider = available_providers[0]
        print(f"\n✓ Using {selected_provider} for AI enhancement")
    
    print()
    
    # Initialize components
    print("2. Initializing AI enhancer and metadata generator...")
    
    if not use_mock_ai:
        ai_enhancer = AIMetadataEnhancer(provider=selected_provider)
    else:
        # Create a mock enhancer for demonstration
        ai_enhancer = None
    
    generator = MetadataGenerator(ai_enhancer=ai_enhancer)
    print(f"✓ Components initialized")
    print()
    
    # Prepare test data
    print("3. Preparing test data...")
    base_metadata = create_mock_repository_data()
    package_sources = create_mock_package_sources()
    
    print("Base metadata from repositories:")
    print(json.dumps(base_metadata, indent=2))
    print()
    
    # Identify missing fields
    print("4. Identifying missing fields...")
    if not use_mock_ai:
        missing_fields = ai_enhancer.get_missing_fields(base_metadata)
        print(f"Missing fields identified: {missing_fields}")
    else:
        # Mock missing fields for demonstration
        missing_fields = [
            "description", "urls.website", "urls.source", "urls.documentation",
            "category.default", "license", "platforms"
        ]
        print(f"Missing fields (mock): {missing_fields}")
    print()
    
    # Demonstrate AI enhancement
    print("5. Performing AI enhancement...")
    
    if not use_mock_ai:
        try:
            # Real AI enhancement
            result = generator.generate_with_ai_enhancement(
                software_name="nginx",
                sources=package_sources,
                providers=["apt", "brew", "winget"],
                ai_provider=selected_provider,
                enhancement_types=["description", "categorization", "field_completion"]
            )
            
            print(f"✓ AI enhancement completed in {result.confidence_scores.get('processing_time', 0):.2f}s")
            enhanced_metadata = result.metadata.to_dict()
            confidence_scores = result.confidence_scores
            
        except Exception as e:
            print(f"✗ AI enhancement failed: {e}")
            print("Falling back to repository data only...")
            result = generator.generate_from_sources("nginx", package_sources)
            enhanced_metadata = result.metadata.to_dict()
            confidence_scores = {}
    else:
        # Mock AI enhancement for demonstration
        print("✓ AI enhancement completed (mock)")
        enhanced_metadata = base_metadata.copy()
        enhanced_metadata.update({
            "description": "High-performance HTTP server and reverse proxy (AI-generated)",
            "urls": {
                "website": "https://nginx.org",
                "source": "https://github.com/nginx/nginx",
                "documentation": "https://nginx.org/en/docs/"
            },
            "category": {
                "default": "web",
                "sub": "server",
                "tags": ["http", "proxy", "load-balancer"]
            },
            "license": "BSD-2-Clause",
            "platforms": ["linux", "windows", "macos"]
        })
        confidence_scores = {
            "description": 0.85,
            "urls.website": 0.95,
            "category.default": 0.90,
            "license": 0.80
        }
    
    print()
    
    # Show enhanced metadata
    print("6. Enhanced metadata results...")
    print("Enhanced metadata (showing AI-filled fields):")
    
    # Show only the fields that were enhanced
    enhanced_fields = {}
    for field in missing_fields:
        keys = field.split('.')
        current = enhanced_metadata
        try:
            for key in keys:
                current = current[key]
            enhanced_fields[field] = current
        except (KeyError, TypeError):
            enhanced_fields[field] = "Not filled"
    
    print(json.dumps(enhanced_fields, indent=2))
    print()
    
    # Show confidence scores
    print("7. Confidence scores...")
    if confidence_scores:
        print("Confidence scores for enhanced fields:")
        for field, score in confidence_scores.items():
            print(f"  {field:20}: {score:.2f}")
    else:
        print("No confidence scores available (mock mode)")
    print()
    
    # Demonstrate data precedence
    print("8. Demonstrating repository data precedence...")
    
    # Show how repository data takes precedence over AI data
    repository_data = {
        "version": "0.1",
        "packages": {"default": {"name": "nginx", "version": "1.18.0"}},  # From repository
        "description": None  # Missing from repository
    }
    
    ai_data = {
        "version": "0.1",
        "packages": {"default": {"name": "nginx", "version": "latest"}},  # AI suggests different version
        "description": "AI-generated description",  # AI fills missing field
        "urls": {"website": "https://nginx.org"}  # AI adds new field
    }
    
    merged = generator.merge_ai_with_repository_data(repository_data, ai_data)
    
    print("Repository data (authoritative):")
    print(json.dumps(repository_data, indent=2))
    print("\nAI data (supplementary):")
    print(json.dumps(ai_data, indent=2))
    print("\nMerged result (repository takes precedence):")
    print(json.dumps(merged, indent=2))
    print()
    
    print("Key observations:")
    print(f"  - Package version: {merged['packages']['default']['version']} (repository wins)")
    print(f"  - Description: '{merged['description']}' (AI fills gap)")
    print(f"  - Website URL: '{merged['urls']['website']}' (AI adds new field)")
    print()
    
    # Configuration examples
    print("9. AI provider configuration examples...")
    
    print("OpenAI Configuration:")
    openai_config = AIProviderConfig(
        provider="openai",
        model="gpt-3.5-turbo",
        temperature=0.1,
        max_tokens=1000,
        rate_limit_requests_per_minute=60
    )
    print(f"  Model: {openai_config.model}")
    print(f"  Temperature: {openai_config.temperature}")
    print(f"  Rate limit: {openai_config.rate_limit_requests_per_minute} req/min")
    print()
    
    print("Anthropic Configuration:")
    anthropic_config = AIProviderConfig(
        provider="anthropic",
        model="claude-3-haiku-20240307",
        temperature=0.1,
        max_tokens=1500,
        rate_limit_requests_per_minute=30
    )
    print(f"  Model: {anthropic_config.model}")
    print(f"  Max tokens: {anthropic_config.max_tokens}")
    print(f"  Rate limit: {anthropic_config.rate_limit_requests_per_minute} req/min")
    print()
    
    print("Local Model Configuration:")
    local_config = AIProviderConfig(
        provider="local",
        model="llama2",
        base_url="http://localhost:11434",
        temperature=0.2,
        max_tokens=2000,
        rate_limit_requests_per_minute=120
    )
    print(f"  Model: {local_config.model}")
    print(f"  Base URL: {local_config.base_url}")
    print(f"  Temperature: {local_config.temperature}")
    print()
    
    print("=== Example completed successfully! ===")
    print("\nKey takeaways:")
    print("1. AI enhancement fills missing metadata fields automatically")
    print("2. Repository data always takes precedence over AI data")
    print("3. Confidence scores help assess AI-generated content quality")
    print("4. Multiple AI providers are supported (OpenAI, Anthropic, local)")
    print("5. Rate limiting and error handling ensure robust operation")
    print("6. AI enhancement is optional and gracefully degrades if unavailable")


def demonstrate_advanced_ai_features():
    """Demonstrate advanced AI enhancement features."""
    print("\n=== Advanced AI Enhancement Features ===\n")
    
    # Custom enhancement types
    print("1. Custom enhancement types...")
    enhancement_types = ["description", "categorization", "field_completion"]
    print(f"Available enhancement types: {enhancement_types}")
    print("  - description: Generate software description")
    print("  - categorization: Determine software category and tags")
    print("  - field_completion: Fill missing URLs, license, platforms")
    print()
    
    # Error handling and fallbacks
    print("2. Error handling and fallback strategies...")
    print("✓ Graceful degradation when AI is unavailable")
    print("✓ Retry logic with exponential backoff")
    print("✓ Rate limiting to respect API limits")
    print("✓ Response validation to ensure data quality")
    print("✓ Fallback to repository-only data on AI failure")
    print()
    
    # Security considerations
    print("3. Security and privacy features...")
    print("✓ Secure API key storage with encryption")
    print("✓ Input sanitization before sending to AI")
    print("✓ Output validation to prevent injection attacks")
    print("✓ No sensitive data sent to external AI services")
    print("✓ Local model support for privacy-sensitive environments")
    print()


if __name__ == "__main__":
    demonstrate_ai_enhancement()
    demonstrate_advanced_ai_features()