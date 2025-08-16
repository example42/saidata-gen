"""
Unit tests for fuzzy matching functionality.
"""

import unittest
from saidata_gen.search.fuzzy import FuzzyMatcher


class TestFuzzyMatcher(unittest.TestCase):
    """Test cases for FuzzyMatcher class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.matcher = FuzzyMatcher(min_similarity=0.3)
    
    def test_exact_match(self):
        """Test exact string matching."""
        similarity = self.matcher.calculate_similarity("nginx", "nginx")
        self.assertEqual(similarity, 1.0)
    
    def test_case_insensitive_match(self):
        """Test case insensitive matching."""
        similarity = self.matcher.calculate_similarity("NGINX", "nginx")
        self.assertEqual(similarity, 1.0)
    
    def test_substring_match(self):
        """Test substring matching."""
        similarity = self.matcher.calculate_similarity("nginx", "nginx-full")
        self.assertGreater(similarity, 0.5)
    
    def test_partial_match(self):
        """Test partial matching detection."""
        self.assertTrue(self.matcher.is_partial_match("ngin", "nginx"))
        self.assertTrue(self.matcher.is_partial_match("web", "web-server"))
        self.assertFalse(self.matcher.is_partial_match("xyz", "nginx"))
    
    def test_find_matches(self):
        """Test finding matches in candidate list."""
        candidates = ["nginx", "apache2", "nginx-full", "nginx-light", "httpd"]
        matches = self.matcher.find_matches("nginx", candidates)
        
        # Should find nginx-related packages
        match_names = [match[0] for match in matches]
        self.assertIn("nginx", match_names)
        self.assertIn("nginx-full", match_names)
        self.assertIn("nginx-light", match_names)
    
    def test_generate_suggestions(self):
        """Test suggestion generation."""
        candidates = ["nginx", "apache2", "nginx-full", "nginx-light", "httpd", "lighttpd"]
        suggestions = self.matcher.generate_suggestions("ngin", candidates, max_suggestions=3)
        
        self.assertLessEqual(len(suggestions), 3)
        self.assertIn("nginx", suggestions)
    
    def test_keyword_extraction(self):
        """Test keyword extraction from text."""
        keywords = self.matcher.extract_keywords("nginx-full-web-server")
        expected_keywords = {"nginx", "full", "web", "server"}
        self.assertEqual(keywords, expected_keywords)
    
    def test_keyword_similarity(self):
        """Test keyword-based similarity calculation."""
        similarity = self.matcher.keyword_similarity("web server", "nginx-web-server")
        self.assertGreater(similarity, 0.5)
    
    def test_empty_strings(self):
        """Test handling of empty strings."""
        self.assertEqual(self.matcher.calculate_similarity("", "nginx"), 0.0)
        self.assertEqual(self.matcher.calculate_similarity("nginx", ""), 0.0)
        self.assertEqual(self.matcher.calculate_similarity("", ""), 0.0)
    
    def test_minimum_similarity_threshold(self):
        """Test minimum similarity threshold filtering."""
        candidates = ["nginx", "completely-different-package", "nginx-full"]
        matches = self.matcher.find_matches("nginx", candidates)
        
        # All matches should meet minimum similarity threshold
        for _, score in matches:
            self.assertGreaterEqual(score, self.matcher.min_similarity)
    
    def test_word_matching(self):
        """Test multi-word matching."""
        similarity = self.matcher.calculate_similarity("web server", "nginx web server")
        self.assertGreater(similarity, 0.6)
    
    def test_prefix_matching(self):
        """Test prefix matching bonus."""
        # Prefix match should score higher than non-prefix match
        prefix_score = self.matcher.calculate_similarity("ngin", "nginx")
        non_prefix_score = self.matcher.calculate_similarity("ginx", "nginx")
        self.assertGreater(prefix_score, non_prefix_score)


if __name__ == '__main__':
    unittest.main()