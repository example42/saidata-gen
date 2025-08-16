"""
Dataset creation and augmentation tools for ML training.

This module provides functionality for creating balanced datasets,
augmenting training data, and managing data quality labels.
"""

import random
import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import json
import re

from .export import InstructionPair
from ..core.models import EnhancedSaidataMetadata as SaidataMetadata
from ..core.exceptions import SaidataGenError


logger = logging.getLogger(__name__)


class DatasetError(SaidataGenError):
    """Raised when dataset operations fail."""
    pass


@dataclass
class DatasetStats:
    """Statistics about a dataset."""
    total_samples: int
    samples_by_category: Dict[str, int]
    samples_by_template: Dict[str, int]
    avg_confidence_score: float
    quality_distribution: Dict[str, int]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_samples": self.total_samples,
            "samples_by_category": self.samples_by_category,
            "samples_by_template": self.samples_by_template,
            "avg_confidence_score": self.avg_confidence_score,
            "quality_distribution": self.quality_distribution
        }


@dataclass
class StratificationConfig:
    """Configuration for stratified sampling."""
    target_field: str = "category"
    min_samples_per_stratum: int = 10
    max_samples_per_stratum: int = 1000
    balance_method: str = "oversample"  # "oversample", "undersample", "hybrid"
    random_seed: int = 42


@dataclass
class AugmentationConfig:
    """Configuration for data augmentation."""
    paraphrase_probability: float = 0.3
    synonym_replacement_probability: float = 0.2
    instruction_variation_probability: float = 0.4
    noise_injection_probability: float = 0.1
    max_augmentations_per_sample: int = 3
    preserve_technical_terms: bool = True
    random_seed: int = 42


class DatasetCreator:
    """
    Creates balanced datasets with stratified sampling.
    
    Supports various balancing strategies and quality-based filtering.
    """
    
    def __init__(self, config: Optional[StratificationConfig] = None):
        """
        Initialize the dataset creator.
        
        Args:
            config: Stratification configuration
        """
        self.config = config or StratificationConfig()
        random.seed(self.config.random_seed)
    
    def create_balanced_dataset(
        self,
        samples: List[InstructionPair],
        target_size: Optional[int] = None
    ) -> Tuple[List[InstructionPair], DatasetStats]:
        """
        Create a balanced dataset using stratified sampling.
        
        Args:
            samples: Input samples to balance
            target_size: Target dataset size (if None, uses balanced size)
            
        Returns:
            Tuple of (balanced_samples, dataset_stats)
        """
        if not samples:
            return [], DatasetStats(0, {}, {}, 0.0, {})
        
        # Group samples by stratification field
        strata = self._group_by_stratum(samples)
        
        # Calculate target samples per stratum
        if target_size is None:
            target_size = self._calculate_balanced_size(strata)
        
        samples_per_stratum = min(
            self.config.max_samples_per_stratum, 
            max(1, target_size // len(strata))  # At least 1 sample per stratum
        )
        
        # Ensure we don't exceed the target size
        if samples_per_stratum * len(strata) > target_size:
            samples_per_stratum = max(1, target_size // len(strata))
        
        # Balance each stratum
        balanced_samples = []
        for stratum_key, stratum_samples in strata.items():
            balanced_stratum = self._balance_stratum(
                stratum_samples, 
                samples_per_stratum
            )
            balanced_samples.extend(balanced_stratum)
        
        # Shuffle the final dataset
        random.shuffle(balanced_samples)
        
        # Calculate statistics
        stats = self._calculate_dataset_stats(balanced_samples)
        
        logger.info(f"Created balanced dataset with {len(balanced_samples)} samples")
        return balanced_samples, stats
    
    def filter_by_quality(
        self,
        samples: List[InstructionPair],
        min_confidence: float = 0.5,
        quality_labels: Optional[Dict[str, str]] = None
    ) -> List[InstructionPair]:
        """
        Filter samples by quality criteria.
        
        Args:
            samples: Input samples to filter
            min_confidence: Minimum confidence score
            quality_labels: Optional quality labels to filter by
            
        Returns:
            Filtered samples
        """
        filtered_samples = []
        
        for sample in samples:
            # Check confidence score
            if sample.confidence_score is not None and sample.confidence_score < min_confidence:
                continue
            
            # Check quality labels if provided
            if quality_labels and sample.metadata:
                sample_quality = sample.metadata.get('quality_label')
                if sample_quality and sample_quality not in quality_labels:
                    continue
            
            # Check for basic quality indicators
            if not self._is_quality_sample(sample):
                continue
            
            filtered_samples.append(sample)
        
        logger.info(f"Filtered {len(samples)} samples to {len(filtered_samples)} quality samples")
        return filtered_samples
    
    def split_dataset(
        self,
        samples: List[InstructionPair],
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
        test_ratio: float = 0.1,
        stratify: bool = True
    ) -> Tuple[List[InstructionPair], List[InstructionPair], List[InstructionPair]]:
        """
        Split dataset into train/validation/test sets.
        
        Args:
            samples: Input samples to split
            train_ratio: Ratio for training set
            val_ratio: Ratio for validation set
            test_ratio: Ratio for test set
            stratify: Whether to maintain stratum proportions
            
        Returns:
            Tuple of (train_samples, val_samples, test_samples)
        """
        if abs(train_ratio + val_ratio + test_ratio - 1.0) > 1e-6:
            raise DatasetError("Split ratios must sum to 1.0")
        
        if not stratify:
            # Simple random split
            random.shuffle(samples)
            n_train = int(len(samples) * train_ratio)
            n_val = int(len(samples) * val_ratio)
            
            train_samples = samples[:n_train]
            val_samples = samples[n_train:n_train + n_val]
            test_samples = samples[n_train + n_val:]
            
        else:
            # Stratified split
            strata = self._group_by_stratum(samples)
            train_samples, val_samples, test_samples = [], [], []
            
            for stratum_samples in strata.values():
                random.shuffle(stratum_samples)
                n_train = int(len(stratum_samples) * train_ratio)
                n_val = int(len(stratum_samples) * val_ratio)
                
                train_samples.extend(stratum_samples[:n_train])
                val_samples.extend(stratum_samples[n_train:n_train + n_val])
                test_samples.extend(stratum_samples[n_train + n_val:])
        
        # Final shuffle
        random.shuffle(train_samples)
        random.shuffle(val_samples)
        random.shuffle(test_samples)
        
        logger.info(f"Split dataset: {len(train_samples)} train, {len(val_samples)} val, {len(test_samples)} test")
        return train_samples, val_samples, test_samples
    
    def _group_by_stratum(self, samples: List[InstructionPair]) -> Dict[str, List[InstructionPair]]:
        """Group samples by stratification field."""
        strata = defaultdict(list)
        
        for sample in samples:
            stratum_key = self._get_stratum_key(sample)
            strata[stratum_key].append(sample)
        
        return dict(strata)
    
    def _get_stratum_key(self, sample: InstructionPair) -> str:
        """Get stratification key for a sample."""
        if self.config.target_field == "category":
            # Extract category from metadata or instruction
            if sample.metadata and "software_category" in sample.metadata:
                return sample.metadata["software_category"]
            elif sample.metadata and "template" in sample.metadata:
                return sample.metadata["template"]
            else:
                return "unknown"
        
        elif self.config.target_field == "template":
            if sample.metadata and "template" in sample.metadata:
                return sample.metadata["template"]
            else:
                return "unknown"
        
        elif self.config.target_field == "confidence":
            if sample.confidence_score is not None:
                if sample.confidence_score >= 0.8:
                    return "high_confidence"
                elif sample.confidence_score >= 0.5:
                    return "medium_confidence"
                else:
                    return "low_confidence"
            else:
                return "no_confidence"
        
        else:
            return "default"
    
    def _calculate_balanced_size(self, strata: Dict[str, List[InstructionPair]]) -> int:
        """Calculate balanced dataset size."""
        stratum_sizes = [len(samples) for samples in strata.values()]
        median_size = sorted(stratum_sizes)[len(stratum_sizes) // 2]
        # Use minimum to avoid excessive oversampling
        target_per_stratum = min(median_size, self.config.max_samples_per_stratum)
        return max(target_per_stratum * len(strata), len(strata) * self.config.min_samples_per_stratum)
    
    def _balance_stratum(
        self, 
        stratum_samples: List[InstructionPair], 
        target_size: int
    ) -> List[InstructionPair]:
        """Balance a single stratum."""
        if len(stratum_samples) == target_size:
            return stratum_samples
        
        elif len(stratum_samples) > target_size:
            # Undersample
            if self.config.balance_method in ["undersample", "hybrid"]:
                return random.sample(stratum_samples, target_size)
            else:
                return stratum_samples[:target_size]
        
        else:
            # Oversample
            if self.config.balance_method in ["oversample", "hybrid"]:
                balanced = stratum_samples.copy()
                while len(balanced) < target_size:
                    sample_to_duplicate = random.choice(stratum_samples)
                    balanced.append(sample_to_duplicate)
                return balanced[:target_size]
            else:
                return stratum_samples
    
    def _is_quality_sample(self, sample: InstructionPair) -> bool:
        """Check if sample meets basic quality criteria."""
        # Check for minimum content length
        if len(sample.instruction.strip()) < 10:
            return False
        if len(sample.input.strip()) < 5:
            return False
        if len(sample.output.strip()) < 10:
            return False
        
        # Check for placeholder content
        placeholders = ["TODO", "FIXME", "[PLACEHOLDER]", "TBD"]
        content = f"{sample.instruction} {sample.input} {sample.output}".lower()
        if any(placeholder.lower() in content for placeholder in placeholders):
            return False
        
        return True
    
    def _calculate_dataset_stats(self, samples: List[InstructionPair]) -> DatasetStats:
        """Calculate dataset statistics."""
        if not samples:
            return DatasetStats(0, {}, {}, 0.0, {})
        
        # Count by category
        category_counts = Counter()
        template_counts = Counter()
        confidence_scores = []
        quality_counts = Counter()
        
        for sample in samples:
            # Category
            category = self._get_stratum_key(sample)
            category_counts[category] += 1
            
            # Template
            if sample.metadata and "template" in sample.metadata:
                template_counts[sample.metadata["template"]] += 1
            
            # Confidence
            if sample.confidence_score is not None:
                confidence_scores.append(sample.confidence_score)
            
            # Quality
            if sample.metadata and "quality_label" in sample.metadata:
                quality_counts[sample.metadata["quality_label"]] += 1
            else:
                quality_counts["unlabeled"] += 1
        
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
        
        return DatasetStats(
            total_samples=len(samples),
            samples_by_category=dict(category_counts),
            samples_by_template=dict(template_counts),
            avg_confidence_score=avg_confidence,
            quality_distribution=dict(quality_counts)
        )


class DatasetAugmentor:
    """
    Augments training datasets with synthetic examples.
    
    Provides various augmentation techniques while preserving
    technical accuracy and semantic meaning.
    """
    
    def __init__(self, config: Optional[AugmentationConfig] = None):
        """
        Initialize the dataset augmentor.
        
        Args:
            config: Augmentation configuration
        """
        self.config = config or AugmentationConfig()
        random.seed(self.config.random_seed)
        
        # Technical terms to preserve during augmentation
        self.technical_terms = {
            "apt", "dnf", "brew", "winget", "scoop", "npm", "pip", "cargo",
            "docker", "kubernetes", "yaml", "json", "xml", "http", "https",
            "api", "cli", "gui", "server", "client", "database", "cache",
            "linux", "windows", "macos", "ubuntu", "debian", "fedora", "centos"
        }
        
        # Instruction variations
        self.instruction_variations = {
            "Generate saidata YAML metadata": [
                "Create saidata YAML metadata",
                "Produce saidata YAML configuration",
                "Build saidata YAML specification",
                "Generate metadata in saidata YAML format"
            ],
            "Enhance the description": [
                "Improve the description",
                "Refine the description",
                "Enrich the description",
                "Augment the description"
            ],
            "Categorize this software": [
                "Classify this software",
                "Determine the category of this software",
                "Identify the software category",
                "Assign a category to this software"
            ]
        }
        
        # Synonym mappings (preserving technical accuracy)
        self.synonyms = {
            "software": ["application", "program", "tool", "utility"],
            "package": ["software package", "application package", "program"],
            "install": ["set up", "deploy", "configure"],
            "server": ["service", "daemon", "backend"],
            "client": ["frontend", "user interface", "application"],
            "configuration": ["config", "settings", "setup"],
            "documentation": ["docs", "manual", "guide"],
            "repository": ["repo", "source", "codebase"]
        }
    
    def augment_dataset(
        self,
        samples: List[InstructionPair],
        target_multiplier: float = 2.0
    ) -> List[InstructionPair]:
        """
        Augment dataset with synthetic examples.
        
        Args:
            samples: Original samples to augment
            target_multiplier: Target size multiplier (2.0 = double the dataset)
            
        Returns:
            Augmented dataset including original samples
        """
        if not samples:
            return []
        
        target_size = int(len(samples) * target_multiplier)
        augmented_samples = samples.copy()
        
        while len(augmented_samples) < target_size:
            # Select random sample to augment
            original_sample = random.choice(samples)
            
            # Apply random augmentation
            augmented_sample = self._augment_sample(original_sample)
            if augmented_sample and augmented_sample != original_sample:
                augmented_samples.append(augmented_sample)
        
        # Shuffle the final dataset
        random.shuffle(augmented_samples)
        
        logger.info(f"Augmented dataset from {len(samples)} to {len(augmented_samples)} samples")
        return augmented_samples[:target_size]
    
    def _augment_sample(self, sample: InstructionPair) -> Optional[InstructionPair]:
        """Apply augmentation to a single sample."""
        augmented = InstructionPair(
            instruction=sample.instruction,
            input=sample.input,
            output=sample.output,
            metadata=sample.metadata.copy() if sample.metadata else None,
            confidence_score=sample.confidence_score,
            source=sample.source,
            timestamp=sample.timestamp
        )
        
        # Track if any augmentation was applied
        augmented_any = False
        
        # Instruction variation
        if random.random() < self.config.instruction_variation_probability:
            new_instruction = self._vary_instruction(augmented.instruction)
            if new_instruction != augmented.instruction:
                augmented.instruction = new_instruction
                augmented_any = True
        
        # Paraphrasing
        if random.random() < self.config.paraphrase_probability:
            new_input = self._paraphrase_text(augmented.input)
            if new_input != augmented.input:
                augmented.input = new_input
                augmented_any = True
        
        # Synonym replacement
        if random.random() < self.config.synonym_replacement_probability:
            new_input = self._replace_synonyms(augmented.input)
            if new_input != augmented.input:
                augmented.input = new_input
                augmented_any = True
        
        # Light noise injection (very conservative for technical content)
        if random.random() < self.config.noise_injection_probability:
            new_input = self._inject_light_noise(augmented.input)
            if new_input != augmented.input:
                augmented.input = new_input
                augmented_any = True
        
        # Update metadata to indicate augmentation
        if augmented_any:
            if augmented.metadata is None:
                augmented.metadata = {}
            augmented.metadata["augmented"] = True
            augmented.metadata["original_source"] = sample.source or "unknown"
            
            # Slightly reduce confidence for augmented samples
            if augmented.confidence_score is not None:
                augmented.confidence_score = max(0.1, augmented.confidence_score * 0.95)
        
        return augmented if augmented_any else None
    
    def _vary_instruction(self, instruction: str) -> str:
        """Apply instruction variations."""
        for original, variations in self.instruction_variations.items():
            if original.lower() in instruction.lower():
                return instruction.replace(original, random.choice(variations))
        return instruction
    
    def _paraphrase_text(self, text: str) -> str:
        """Apply simple paraphrasing transformations."""
        # Simple transformations that preserve technical meaning
        transformations = [
            (r'\bthis software\b', 'the software'),
            (r'\bthe given software\b', 'this software'),
            (r'\bpackage information\b', 'package details'),
            (r'\bmetadata information\b', 'metadata details'),
            (r'\bsoftware package\b', 'application'),
        ]
        
        result = text
        for pattern, replacement in transformations:
            if random.random() < 0.3:  # Apply transformation with 30% probability
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        return result
    
    def _replace_synonyms(self, text: str) -> str:
        """Replace words with synonyms while preserving technical terms."""
        words = text.split()
        result_words = []
        
        for word in words:
            word_lower = word.lower().strip('.,!?;:')
            
            # Skip technical terms
            if self.config.preserve_technical_terms and word_lower in self.technical_terms:
                result_words.append(word)
                continue
            
            # Apply synonym replacement
            if word_lower in self.synonyms and random.random() < 0.3:
                synonym = random.choice(self.synonyms[word_lower])
                # Preserve original capitalization
                if word[0].isupper():
                    synonym = synonym.capitalize()
                result_words.append(synonym)
            else:
                result_words.append(word)
        
        return ' '.join(result_words)
    
    def _inject_light_noise(self, text: str) -> str:
        """Inject very light noise while preserving technical accuracy."""
        # Only apply minor formatting changes
        transformations = [
            (r'\s+', ' '),  # Normalize whitespace
            (r':\s*', ': '),  # Normalize colons
            (r',\s*', ', '),  # Normalize commas
        ]
        
        result = text
        for pattern, replacement in transformations:
            if random.random() < 0.2:  # Very low probability
                result = re.sub(pattern, replacement, result)
        
        return result.strip()
    
    def add_quality_labels(
        self,
        samples: List[InstructionPair],
        labeling_strategy: str = "confidence_based"
    ) -> List[InstructionPair]:
        """
        Add quality labels to samples.
        
        Args:
            samples: Samples to label
            labeling_strategy: Strategy for labeling ("confidence_based", "heuristic")
            
        Returns:
            Samples with quality labels
        """
        labeled_samples = []
        
        for sample in samples:
            labeled_sample = InstructionPair(
                instruction=sample.instruction,
                input=sample.input,
                output=sample.output,
                metadata=sample.metadata.copy() if sample.metadata else {},
                confidence_score=sample.confidence_score,
                source=sample.source,
                timestamp=sample.timestamp
            )
            
            # Add quality label based on strategy
            if labeling_strategy == "confidence_based":
                quality_label = self._get_confidence_based_label(sample)
            elif labeling_strategy == "heuristic":
                quality_label = self._get_heuristic_based_label(sample)
            else:
                quality_label = "unlabeled"
            
            if labeled_sample.metadata is None:
                labeled_sample.metadata = {}
            labeled_sample.metadata["quality_label"] = quality_label
            
            labeled_samples.append(labeled_sample)
        
        logger.info(f"Added quality labels to {len(labeled_samples)} samples")
        return labeled_samples
    
    def _get_confidence_based_label(self, sample: InstructionPair) -> str:
        """Get quality label based on confidence score."""
        if sample.confidence_score is None:
            return "unknown"
        elif sample.confidence_score >= 0.8:
            return "high_quality"
        elif sample.confidence_score >= 0.6:
            return "medium_quality"
        elif sample.confidence_score >= 0.4:
            return "low_quality"
        else:
            return "poor_quality"
    
    def _get_heuristic_based_label(self, sample: InstructionPair) -> str:
        """Get quality label based on heuristics."""
        score = 0
        
        # Check instruction quality
        if len(sample.instruction.strip()) > 20:
            score += 1
        if any(word in sample.instruction.lower() for word in ["generate", "create", "enhance", "categorize"]):
            score += 1
        
        # Check input quality
        if len(sample.input.strip()) > 10:
            score += 1
        if "software" in sample.input.lower() or "package" in sample.input.lower():
            score += 1
        
        # Check output quality
        if len(sample.output.strip()) > 20:
            score += 1
        if any(format_indicator in sample.output.lower() for format_indicator in ["version:", "packages:", "description:"]):
            score += 1
        
        # Convert score to label
        if score >= 5:
            return "high_quality"
        elif score >= 3:
            return "medium_quality"
        elif score >= 2:
            return "low_quality"
        else:
            return "poor_quality"