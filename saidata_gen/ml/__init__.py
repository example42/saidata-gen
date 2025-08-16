"""
Machine Learning training and fine-tuning module for saidata-gen.

This module provides functionality for:
- Training data export in various formats
- Dataset creation and augmentation
- Model fine-tuning with HuggingFace Transformers
- Model evaluation and serving
"""

from .export import TrainingDataExporter
from .dataset import DatasetCreator, DatasetAugmentor
from .training import ModelTrainer

__all__ = [
    "TrainingDataExporter",
    "DatasetCreator", 
    "DatasetAugmentor",
    "ModelTrainer",
]