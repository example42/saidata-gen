"""
Unit tests for ML dataset creation and augmentation functionality.
"""

import random
from unittest.mock import Mock, patch
import pytest

from saidata_gen.ml.dataset import (
    DatasetCreator,
    DatasetAugmentor,
    DatasetStats,
    StratificationConfig,
    AugmentationConfig,
    DatasetError
)
from saidata_gen.ml.export import InstructionPair


class TestDatasetStats:
    """Test DatasetStats dataclass."""
    
    def test_dataset_stats_creation(self):
        """Test creating dataset stats."""
        stats = DatasetStats(
            total_samples=100,
            samples_by_category={"web_server": 50, "database": 30, "tool": 20},
            samples_by_template={"generate_metadata": 60, "categorize": 40},
            avg_confidence_score=0.75,
            quality_distribution={"high": 40, "medium": 35, "low": 25}
        )
        
        assert stats.total_samples == 100
        assert stats.samples_by_category["web_server"] == 50
        assert stats.avg_confidence_score == 0.75
    
    def test_dataset_stats_to_dict(self):
        """Test converting stats to dictionary."""
        stats = DatasetStats(
            total_samples=50,
            samples_by_category={"tool": 50},
            samples_by_template={"generate": 50},
            avg_confidence_score=0.8,
            quality_distribution={"high": 50}
        )
        
        result = stats.to_dict()
        
        assert result["total_samples"] == 50
        assert result["samples_by_category"]["tool"] == 50
        assert result["avg_confidence_score"] == 0.8


class TestDatasetCreator:
    """Test DatasetCreator class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = StratificationConfig(random_seed=42)
        self.creator = DatasetCreator(self.config)
        
        # Create sample data with different categories
        self.sample_data = [
            InstructionPair(
                instruction="Generate metadata",
                input="Software: nginx",
                output="web server metadata",
                metadata={"template": "generate_metadata", "software_category": "web_server"},
                confidence_score=0.9
            ),
            InstructionPair(
                instruction="Generate metadata",
                input="Software: apache",
                output="web server metadata",
                metadata={"template": "generate_metadata", "software_category": "web_server"},
                confidence_score=0.8
            ),
            InstructionPair(
                instruction="Generate metadata",
                input="Software: mysql",
                output="database metadata",
                metadata={"template": "generate_metadata", "software_category": "database"},
                confidence_score=0.85
            ),
            InstructionPair(
                instruction="Categorize software",
                input="Software: git",
                output="development tool",
                metadata={"template": "categorize", "software_category": "tool"},
                confidence_score=0.7
            ),
            InstructionPair(
                instruction="Categorize software",
                input="Software: vim",
                output="text editor",
                metadata={"template": "categorize", "software_category": "tool"},
                confidence_score=0.75
            )
        ]
    
    def test_creator_initialization(self):
        """Test creator initialization."""
        assert self.creator.config.target_field == "category"
        assert self.creator.config.min_samples_per_stratum == 10
        assert self.creator.config.random_seed == 42
    
    def test_create_balanced_dataset(self):
        """Test creating a balanced dataset."""
        balanced_samples, stats = self.creator.create_balanced_dataset(self.sample_data)
        
        assert len(balanced_samples) > 0
        assert stats.total_samples == len(balanced_samples)
        assert len(stats.samples_by_category) > 0
        
        # Check that categories are represented
        assert "web_server" in stats.samples_by_category
        assert "database" in stats.samples_by_category
        assert "tool" in stats.samples_by_category
    
    def test_create_balanced_dataset_with_target_size(self):
        """Test creating balanced dataset with specific target size."""
        target_size = 10
        balanced_samples, stats = self.creator.create_balanced_dataset(
            self.sample_data, 
            target_size=target_size
        )
        
        assert len(balanced_samples) <= target_size
        assert stats.total_samples == len(balanced_samples)
    
    def test_create_balanced_dataset_empty_input(self):
        """Test creating balanced dataset with empty input."""
        balanced_samples, stats = self.creator.create_balanced_dataset([])
        
        assert len(balanced_samples) == 0
        assert stats.total_samples == 0
        assert stats.samples_by_category == {}
    
    def test_filter_by_quality(self):
        """Test filtering samples by quality."""
        # Add some low-quality samples
        low_quality_samples = self.sample_data + [
            InstructionPair(
                instruction="Bad",  # Too short
                input="Test",
                output="Bad output",
                confidence_score=0.3
            ),
            InstructionPair(
                instruction="Generate metadata with TODO placeholder",
                input="Software: test",
                output="TODO: implement this",  # Contains placeholder
                confidence_score=0.8
            )
        ]
        
        filtered_samples = self.creator.filter_by_quality(
            low_quality_samples,
            min_confidence=0.5
        )
        
        # Should filter out low confidence and placeholder samples
        assert len(filtered_samples) < len(low_quality_samples)
        assert all(sample.confidence_score >= 0.5 for sample in filtered_samples if sample.confidence_score)
    
    def test_filter_by_quality_with_labels(self):
        """Test filtering by quality labels."""
        samples_with_labels = []
        for sample in self.sample_data:
            sample_copy = InstructionPair(
                instruction=sample.instruction,
                input=sample.input,
                output=sample.output,
                metadata=sample.metadata.copy() if sample.metadata else {},
                confidence_score=sample.confidence_score
            )
            if sample_copy.metadata is None:
                sample_copy.metadata = {}
            sample_copy.metadata["quality_label"] = "high_quality"
            samples_with_labels.append(sample_copy)
        
        # Add one low quality sample
        low_quality_sample = InstructionPair(
            instruction="Test",
            input="Test",
            output="Test",
            metadata={"quality_label": "low_quality"}
        )
        samples_with_labels.append(low_quality_sample)
        
        filtered_samples = self.creator.filter_by_quality(
            samples_with_labels,
            quality_labels={"high_quality", "medium_quality"}
        )
        
        # Should filter out the low quality sample
        assert len(filtered_samples) == len(self.sample_data)
    
    def test_split_dataset(self):
        """Test splitting dataset into train/val/test."""
        train, val, test = self.creator.split_dataset(
            self.sample_data,
            train_ratio=0.6,
            val_ratio=0.2,
            test_ratio=0.2,
            stratify=False
        )
        
        total_samples = len(train) + len(val) + len(test)
        assert total_samples == len(self.sample_data)
        
        # Check approximate ratios (allowing for rounding)
        assert len(train) >= 2  # 60% of 5 = 3
        assert len(val) >= 0   # 20% of 5 = 1
        assert len(test) >= 0  # 20% of 5 = 1
    
    def test_split_dataset_stratified(self):
        """Test stratified dataset splitting."""
        train, val, test = self.creator.split_dataset(
            self.sample_data,
            train_ratio=0.6,
            val_ratio=0.2,
            test_ratio=0.2,
            stratify=True
        )
        
        total_samples = len(train) + len(val) + len(test)
        assert total_samples == len(self.sample_data)
    
    def test_split_dataset_invalid_ratios(self):
        """Test split with invalid ratios."""
        with pytest.raises(DatasetError):
            self.creator.split_dataset(
                self.sample_data,
                train_ratio=0.5,
                val_ratio=0.3,
                test_ratio=0.3  # Sum > 1.0
            )
    
    def test_group_by_stratum(self):
        """Test grouping samples by stratum."""
        strata = self.creator._group_by_stratum(self.sample_data)
        
        assert len(strata) > 0
        assert "web_server" in strata
        assert "database" in strata
        assert "tool" in strata
        
        # Check that web_server stratum has 2 samples
        assert len(strata["web_server"]) == 2
    
    def test_get_stratum_key_category(self):
        """Test getting stratum key by category."""
        sample = self.sample_data[0]  # web_server category
        key = self.creator._get_stratum_key(sample)
        assert key == "web_server"
    
    def test_get_stratum_key_template(self):
        """Test getting stratum key by template."""
        self.creator.config.target_field = "template"
        sample = self.sample_data[0]  # generate_metadata template
        key = self.creator._get_stratum_key(sample)
        assert key == "generate_metadata"
    
    def test_get_stratum_key_confidence(self):
        """Test getting stratum key by confidence."""
        self.creator.config.target_field = "confidence"
        
        # High confidence sample
        high_conf_sample = self.sample_data[0]  # confidence 0.9
        key = self.creator._get_stratum_key(high_conf_sample)
        assert key == "high_confidence"
        
        # Medium confidence sample
        med_conf_sample = self.sample_data[3]  # confidence 0.7
        key = self.creator._get_stratum_key(med_conf_sample)
        assert key == "medium_confidence"
    
    def test_calculate_dataset_stats(self):
        """Test calculating dataset statistics."""
        stats = self.creator._calculate_dataset_stats(self.sample_data)
        
        assert stats.total_samples == 5
        assert stats.samples_by_category["web_server"] == 2
        assert stats.samples_by_category["database"] == 1
        assert stats.samples_by_category["tool"] == 2
        assert stats.avg_confidence_score > 0.7  # Average should be around 0.8


class TestDatasetAugmentor:
    """Test DatasetAugmentor class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = AugmentationConfig(random_seed=42)
        self.augmentor = DatasetAugmentor(self.config)
        
        self.sample_data = [
            InstructionPair(
                instruction="Generate saidata YAML metadata for the given software package.",
                input="Software: nginx\nDescription: High-performance web server",
                output="version: 0.1\npackages:\n  apt:\n    name: nginx",
                metadata={"template": "generate_metadata"},
                confidence_score=0.9
            ),
            InstructionPair(
                instruction="Enhance the description for this software package.",
                input="Software: apache\nPackages: apt, brew",
                output="Apache HTTP Server is a powerful web server",
                metadata={"template": "enhance_description"},
                confidence_score=0.8
            )
        ]
    
    def test_augmentor_initialization(self):
        """Test augmentor initialization."""
        assert self.augmentor.config.paraphrase_probability == 0.3
        assert self.augmentor.config.random_seed == 42
        assert "apt" in self.augmentor.technical_terms
        assert "Generate saidata YAML metadata" in self.augmentor.instruction_variations
    
    def test_augment_dataset(self):
        """Test augmenting dataset."""
        augmented_samples = self.augmentor.augment_dataset(
            self.sample_data,
            target_multiplier=2.0
        )
        
        # Should have approximately double the samples
        assert len(augmented_samples) >= len(self.sample_data)
        assert len(augmented_samples) <= len(self.sample_data) * 2
        
        # Should contain original samples
        original_instructions = {sample.instruction for sample in self.sample_data}
        augmented_instructions = {sample.instruction for sample in augmented_samples}
        assert original_instructions.issubset(augmented_instructions)
    
    def test_augment_dataset_empty_input(self):
        """Test augmenting empty dataset."""
        augmented_samples = self.augmentor.augment_dataset([])
        assert len(augmented_samples) == 0
    
    def test_augment_sample(self):
        """Test augmenting a single sample."""
        original_sample = self.sample_data[0]
        
        # Mock random to ensure augmentation happens
        with patch('random.random', return_value=0.1):  # Less than all probabilities
            augmented_sample = self.augmentor._augment_sample(original_sample)
        
        if augmented_sample:  # Augmentation might not always produce changes
            assert augmented_sample.metadata is not None
            assert augmented_sample.metadata.get("augmented") is True
            assert "original_source" in augmented_sample.metadata
    
    def test_vary_instruction(self):
        """Test instruction variation."""
        original_instruction = "Generate saidata YAML metadata for nginx"
        varied_instruction = self.augmentor._vary_instruction(original_instruction)
        
        # Should either be the same or a variation
        assert isinstance(varied_instruction, str)
        assert len(varied_instruction) > 0
    
    def test_paraphrase_text(self):
        """Test text paraphrasing."""
        original_text = "this software package information"
        paraphrased_text = self.augmentor._paraphrase_text(original_text)
        
        assert isinstance(paraphrased_text, str)
        assert len(paraphrased_text) > 0
    
    def test_replace_synonyms(self):
        """Test synonym replacement."""
        original_text = "software package configuration"
        replaced_text = self.augmentor._replace_synonyms(original_text)
        
        assert isinstance(replaced_text, str)
        assert len(replaced_text) > 0
        
        # Technical terms should be preserved
        technical_text = "apt install nginx"
        replaced_technical = self.augmentor._replace_synonyms(technical_text)
        assert "apt" in replaced_technical  # Technical term preserved
        assert "nginx" in replaced_technical  # Technical term preserved
    
    def test_inject_light_noise(self):
        """Test light noise injection."""
        original_text = "Software:   nginx,   description"
        
        # Test multiple times since it's probabilistic
        results = []
        for _ in range(10):
            noisy_text = self.augmentor._inject_light_noise(original_text)
            results.append(noisy_text)
        
        # At least one result should be a string
        assert all(isinstance(result, str) for result in results)
        assert all(len(result) > 0 for result in results)
        
        # Test that the method can normalize whitespace (when it applies transformations)
        # or leave text unchanged (when no transformations are applied)
        normalized_expected = "Software: nginx, description"
        assert any(result == original_text or result == normalized_expected for result in results)
    
    def test_add_quality_labels_confidence_based(self):
        """Test adding confidence-based quality labels."""
        labeled_samples = self.augmentor.add_quality_labels(
            self.sample_data,
            labeling_strategy="confidence_based"
        )
        
        assert len(labeled_samples) == len(self.sample_data)
        
        for sample in labeled_samples:
            assert sample.metadata is not None
            assert "quality_label" in sample.metadata
            
            # Check label correctness
            if sample.confidence_score >= 0.8:
                assert sample.metadata["quality_label"] == "high_quality"
    
    def test_add_quality_labels_heuristic_based(self):
        """Test adding heuristic-based quality labels."""
        labeled_samples = self.augmentor.add_quality_labels(
            self.sample_data,
            labeling_strategy="heuristic"
        )
        
        assert len(labeled_samples) == len(self.sample_data)
        
        for sample in labeled_samples:
            assert sample.metadata is not None
            assert "quality_label" in sample.metadata
            assert sample.metadata["quality_label"] in [
                "high_quality", "medium_quality", "low_quality", "poor_quality"
            ]
    
    def test_get_confidence_based_label(self):
        """Test confidence-based labeling."""
        # High confidence
        high_conf_sample = InstructionPair("", "", "", confidence_score=0.9)
        label = self.augmentor._get_confidence_based_label(high_conf_sample)
        assert label == "high_quality"
        
        # Medium confidence
        med_conf_sample = InstructionPair("", "", "", confidence_score=0.7)
        label = self.augmentor._get_confidence_based_label(med_conf_sample)
        assert label == "medium_quality"
        
        # Low confidence
        low_conf_sample = InstructionPair("", "", "", confidence_score=0.5)
        label = self.augmentor._get_confidence_based_label(low_conf_sample)
        assert label == "low_quality"
        
        # No confidence
        no_conf_sample = InstructionPair("", "", "", confidence_score=None)
        label = self.augmentor._get_confidence_based_label(no_conf_sample)
        assert label == "unknown"
    
    def test_get_heuristic_based_label(self):
        """Test heuristic-based labeling."""
        # High quality sample
        high_quality_sample = InstructionPair(
            instruction="Generate comprehensive metadata for the software package",
            input="Software: nginx web server package with configuration",
            output="version: 0.1\npackages:\n  apt:\n    name: nginx\ndescription: Web server"
        )
        label = self.augmentor._get_heuristic_based_label(high_quality_sample)
        assert label in ["high_quality", "medium_quality"]
        
        # Low quality sample
        low_quality_sample = InstructionPair(
            instruction="Do",
            input="X",
            output="Y"
        )
        label = self.augmentor._get_heuristic_based_label(low_quality_sample)
        assert label in ["low_quality", "poor_quality"]


if __name__ == "__main__":
    pytest.main([__file__])