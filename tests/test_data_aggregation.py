"""
Unit tests for the data aggregation system.
"""

import unittest
from typing import Dict, Any, List

from saidata_gen.core.aggregation import (
    DataAggregator, ConflictResolutionStrategy, SourceInfo, DataPoint, AggregationResult
)
from saidata_gen.core.interfaces import PackageInfo


class TestDataAggregator(unittest.TestCase):
    """Test the data aggregator."""
    
    def setUp(self):
        """Set up the test environment."""
        self.aggregator = DataAggregator()
    
    def test_aggregate_package_data_single_source(self):
        """Test aggregating data from a single source."""
        sources = [
            PackageInfo(
                name="nginx",
                provider="apt",
                version="1.18.0",
                description="High-performance HTTP server and reverse proxy",
                details={
                    "license": "BSD",
                    "homepage": "https://nginx.org",
                    "source_url": "https://nginx.org/download/nginx-1.18.0.tar.gz",
                    "platforms": ["linux", "debian", "ubuntu"]
                }
            )
        ]
        
        aggregated_data, confidence_scores = self.aggregator.aggregate_package_data("nginx", sources)
        
        self.assertIn("packages", aggregated_data)
        self.assertIn("apt", aggregated_data["packages"])
        self.assertEqual("nginx", aggregated_data["packages"]["apt"]["name"])
        self.assertEqual("1.18.0", aggregated_data["packages"]["apt"]["version"])
        self.assertEqual("High-performance HTTP server and reverse proxy", aggregated_data["description"])
        self.assertEqual("BSD", aggregated_data["license"])
        self.assertEqual("https://nginx.org", aggregated_data["urls"]["website"])
        self.assertEqual("https://nginx.org/download/nginx-1.18.0.tar.gz", aggregated_data["urls"]["source"])
        self.assertEqual(["linux", "debian", "ubuntu"], aggregated_data["platforms"])
        
        # Check confidence scores
        self.assertIn("description", confidence_scores)
        self.assertIn("license", confidence_scores)
        self.assertIn("urls.website", confidence_scores)
        self.assertIn("urls.source", confidence_scores)
        self.assertIn("platforms", confidence_scores)
        self.assertIn("overall", confidence_scores)


if __name__ == "__main__":
    unittest.main()