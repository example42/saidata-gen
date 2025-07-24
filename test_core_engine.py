#!/usr/bin/env python3
"""
Simple test script to verify the core engine functionality.
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from saidata_gen.core.engine import SaidataEngine
from saidata_gen.core.interfaces import GenerationOptions

def test_core_engine():
    """Test the core engine with minimal providers."""
    print("Testing core engine...")
    
    # Initialize engine
    engine = SaidataEngine()
    
    # Test with just APT provider
    options = GenerationOptions(providers=["apt"])
    
    try:
        print("Generating metadata for nginx with APT provider only...")
        result = engine.generate_metadata("nginx", options)
        
        print(f"✅ Generation successful!")
        print(f"   - Validation: {'✅ Valid' if result.validation_result.valid else '❌ Invalid'}")
        print(f"   - Confidence: {result.confidence_scores.get('overall', 'N/A')}")
        
        # Save to file
        import yaml
        with open('nginx-test.yaml', 'w') as f:
            yaml.dump(result.metadata.to_dict(), f, default_flow_style=False)
        print("   - Saved to nginx-test.yaml")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_core_engine()
    sys.exit(0 if success else 1)