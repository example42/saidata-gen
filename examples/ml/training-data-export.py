#!/usr/bin/env python3
"""
ML Training Data Export Example
Demonstrates how to export training data for model fine-tuning
"""

import json
import csv
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
import yaml
import argparse
from datetime import datetime

class TrainingDataExporter:
    """Example implementation of training data export functionality"""
    
    def __init__(self, metadata_dir: str, output_dir: str):
        self.metadata_dir = Path(metadata_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def load_metadata_files(self) -> List[Dict[str, Any]]:
        """Load all YAML metadata files from the directory"""
        metadata_files = []
        
        for yaml_file in self.metadata_dir.glob("*.yaml"):
            try:
                with open(yaml_file, 'r') as f:
                    data = yaml.safe_load(f)
                    data['_source_file'] = yaml_file.name
                    data['_software_name'] = yaml_file.stem
                    metadata_files.append(data)
            except Exception as e:
                print(f"Error loading {yaml_file}: {e}")
        
        return metadata_files
    
    def create_instruction_pairs(self, metadata_files: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Create instruction-response pairs for supervised learning"""
        instruction_pairs = []
        
        for metadata in metadata_files:
            software_name = metadata.get('_software_name', 'unknown')
            
            # Description enhancement task
            if 'description' in metadata:
                instruction_pairs.append({
                    'instruction': f"Generate a comprehensive description for the software package '{software_name}'.",
                    'input': f"Software: {software_name}\nPackage info: {self._extract_package_info(metadata)}",
                    'output': metadata['description'],
                    'task_type': 'description_enhancement',
                    'software': software_name
                })
            
            # Categorization task
            if 'category' in metadata:
                category_info = metadata['category']
                instruction_pairs.append({
                    'instruction': f"Categorize the software package '{software_name}' based on its functionality.",
                    'input': f"Software: {software_name}\nDescription: {metadata.get('description', 'N/A')}",
                    'output': self._format_category_output(category_info),
                    'task_type': 'categorization',
                    'software': software_name
                })
            
            # Package configuration task
            if 'packages' in metadata:
                packages_info = metadata['packages']
                instruction_pairs.append({
                    'instruction': f"Generate package manager configurations for '{software_name}'.",
                    'input': f"Software: {software_name}\nDescription: {metadata.get('description', 'N/A')}",
                    'output': self._format_packages_output(packages_info),
                    'task_type': 'package_configuration',
                    'software': software_name
                })
            
            # URL completion task
            if 'urls' in metadata:
                urls_info = metadata['urls']
                instruction_pairs.append({
                    'instruction': f"Provide relevant URLs for the software package '{software_name}'.",
                    'input': f"Software: {software_name}\nDescription: {metadata.get('description', 'N/A')}",
                    'output': self._format_urls_output(urls_info),
                    'task_type': 'url_completion',
                    'software': software_name
                })
        
        return instruction_pairs
    
    def _extract_package_info(self, metadata: Dict[str, Any]) -> str:
        """Extract basic package information for input context"""
        info_parts = []
        
        if 'packages' in metadata:
            packages = metadata['packages']
            for provider, config in packages.items():
                if isinstance(config, dict) and 'name' in config:
                    info_parts.append(f"{provider}: {config['name']}")
        
        if 'category' in metadata:
            category = metadata['category']
            if isinstance(category, dict) and 'default' in category:
                info_parts.append(f"Category: {category['default']}")
        
        return "; ".join(info_parts) if info_parts else "No package info available"
    
    def _format_category_output(self, category_info: Dict[str, Any]) -> str:
        """Format category information for training output"""
        output_parts = []
        
        if 'default' in category_info:
            output_parts.append(f"Primary Category: {category_info['default']}")
        
        if 'sub' in category_info:
            output_parts.append(f"Subcategory: {category_info['sub']}")
        
        if 'tags' in category_info and isinstance(category_info['tags'], list):
            tags = ", ".join(category_info['tags'])
            output_parts.append(f"Tags: {tags}")
        
        return "\n".join(output_parts)
    
    def _format_packages_output(self, packages_info: Dict[str, Any]) -> str:
        """Format package configuration for training output"""
        output_parts = []
        
        for provider, config in packages_info.items():
            if isinstance(config, dict):
                config_str = f"{provider}:"
                if 'name' in config:
                    config_str += f" name={config['name']}"
                if 'version' in config:
                    config_str += f" version={config['version']}"
                output_parts.append(config_str)
        
        return "\n".join(output_parts)
    
    def _format_urls_output(self, urls_info: Dict[str, Any]) -> str:
        """Format URLs information for training output"""
        output_parts = []
        
        for url_type, url_value in urls_info.items():
            if url_value:
                output_parts.append(f"{url_type}: {url_value}")
        
        return "\n".join(output_parts)
    
    def export_jsonl(self, instruction_pairs: List[Dict[str, str]], filename: str = "training_data.jsonl"):
        """Export training data in JSONL format"""
        output_file = self.output_dir / filename
        
        with open(output_file, 'w') as f:
            for pair in instruction_pairs:
                json.dump(pair, f)
                f.write('\n')
        
        print(f"Exported {len(instruction_pairs)} instruction pairs to {output_file}")
    
    def export_csv(self, instruction_pairs: List[Dict[str, str]], filename: str = "training_data.csv"):
        """Export training data in CSV format"""
        output_file = self.output_dir / filename
        
        df = pd.DataFrame(instruction_pairs)
        df.to_csv(output_file, index=False)
        
        print(f"Exported {len(instruction_pairs)} instruction pairs to {output_file}")
    
    def export_huggingface_format(self, instruction_pairs: List[Dict[str, str]], filename: str = "hf_training_data.json"):
        """Export in HuggingFace datasets format"""
        output_file = self.output_dir / filename
        
        # Group by task type for better organization
        task_groups = {}
        for pair in instruction_pairs:
            task_type = pair.get('task_type', 'general')
            if task_type not in task_groups:
                task_groups[task_type] = []
            task_groups[task_type].append(pair)
        
        hf_format = {
            'metadata': {
                'created': datetime.now().isoformat(),
                'total_samples': len(instruction_pairs),
                'task_distribution': {task: len(samples) for task, samples in task_groups.items()}
            },
            'data': instruction_pairs
        }
        
        with open(output_file, 'w') as f:
            json.dump(hf_format, f, indent=2)
        
        print(f"Exported HuggingFace format data to {output_file}")
    
    def create_augmented_data(self, instruction_pairs: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Create augmented training data with variations"""
        augmented_pairs = []
        
        for pair in instruction_pairs:
            # Original pair
            augmented_pairs.append(pair)
            
            # Create variations for description enhancement tasks
            if pair.get('task_type') == 'description_enhancement':
                # Variation 1: Different instruction phrasing
                variation1 = pair.copy()
                variation1['instruction'] = f"Provide a detailed description of the software '{pair['software']}'."
                augmented_pairs.append(variation1)
                
                # Variation 2: Focus on specific aspects
                variation2 = pair.copy()
                variation2['instruction'] = f"Explain what '{pair['software']}' does and its main features."
                augmented_pairs.append(variation2)
            
            # Create variations for categorization tasks
            elif pair.get('task_type') == 'categorization':
                variation1 = pair.copy()
                variation1['instruction'] = f"Classify the software '{pair['software']}' into appropriate categories."
                augmented_pairs.append(variation1)
        
        return augmented_pairs
    
    def generate_quality_labels(self, instruction_pairs: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Add quality labels and confidence scores to training data"""
        labeled_pairs = []
        
        for pair in instruction_pairs:
            labeled_pair = pair.copy()
            
            # Simple quality scoring based on output length and completeness
            output_length = len(pair['output'])
            
            if output_length > 200:
                quality_score = 0.9
            elif output_length > 100:
                quality_score = 0.7
            elif output_length > 50:
                quality_score = 0.5
            else:
                quality_score = 0.3
            
            # Adjust based on task type
            if pair.get('task_type') == 'description_enhancement':
                if 'features' in pair['output'].lower() or 'used for' in pair['output'].lower():
                    quality_score += 0.1
            
            labeled_pair['quality_score'] = min(quality_score, 1.0)
            labeled_pair['confidence'] = 'high' if quality_score > 0.8 else 'medium' if quality_score > 0.5 else 'low'
            
            labeled_pairs.append(labeled_pair)
        
        return labeled_pairs
    
    def export_statistics(self, instruction_pairs: List[Dict[str, str]]):
        """Export statistics about the training data"""
        stats = {
            'total_samples': len(instruction_pairs),
            'task_distribution': {},
            'software_distribution': {},
            'quality_distribution': {},
            'average_lengths': {}
        }
        
        # Task distribution
        for pair in instruction_pairs:
            task_type = pair.get('task_type', 'unknown')
            stats['task_distribution'][task_type] = stats['task_distribution'].get(task_type, 0) + 1
        
        # Software distribution
        for pair in instruction_pairs:
            software = pair.get('software', 'unknown')
            stats['software_distribution'][software] = stats['software_distribution'].get(software, 0) + 1
        
        # Quality distribution
        for pair in instruction_pairs:
            confidence = pair.get('confidence', 'unknown')
            stats['quality_distribution'][confidence] = stats['quality_distribution'].get(confidence, 0) + 1
        
        # Average lengths
        instruction_lengths = [len(pair['instruction']) for pair in instruction_pairs]
        output_lengths = [len(pair['output']) for pair in instruction_pairs]
        
        stats['average_lengths'] = {
            'instruction': sum(instruction_lengths) / len(instruction_lengths),
            'output': sum(output_lengths) / len(output_lengths)
        }
        
        # Export statistics
        stats_file = self.output_dir / "training_statistics.json"
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2)
        
        print(f"Training data statistics exported to {stats_file}")
        print(f"Total samples: {stats['total_samples']}")
        print(f"Task types: {list(stats['task_distribution'].keys())}")
        print(f"Quality distribution: {stats['quality_distribution']}")

def main():
    parser = argparse.ArgumentParser(description="Export training data from saidata metadata")
    parser.add_argument("--metadata-dir", required=True, help="Directory containing YAML metadata files")
    parser.add_argument("--output-dir", default="./training-output", help="Output directory for training data")
    parser.add_argument("--format", choices=["jsonl", "csv", "hf", "all"], default="all", help="Export format")
    parser.add_argument("--augment", action="store_true", help="Create augmented training data")
    parser.add_argument("--quality-labels", action="store_true", help="Add quality labels to training data")
    
    args = parser.parse_args()
    
    # Initialize exporter
    exporter = TrainingDataExporter(args.metadata_dir, args.output_dir)
    
    # Load metadata files
    print("Loading metadata files...")
    metadata_files = exporter.load_metadata_files()
    print(f"Loaded {len(metadata_files)} metadata files")
    
    # Create instruction pairs
    print("Creating instruction pairs...")
    instruction_pairs = exporter.create_instruction_pairs(metadata_files)
    print(f"Created {len(instruction_pairs)} instruction pairs")
    
    # Augment data if requested
    if args.augment:
        print("Creating augmented data...")
        instruction_pairs = exporter.create_augmented_data(instruction_pairs)
        print(f"Augmented to {len(instruction_pairs)} instruction pairs")
    
    # Add quality labels if requested
    if args.quality_labels:
        print("Adding quality labels...")
        instruction_pairs = exporter.generate_quality_labels(instruction_pairs)
    
    # Export in requested formats
    if args.format in ["jsonl", "all"]:
        exporter.export_jsonl(instruction_pairs)
    
    if args.format in ["csv", "all"]:
        exporter.export_csv(instruction_pairs)
    
    if args.format in ["hf", "all"]:
        exporter.export_huggingface_format(instruction_pairs)
    
    # Export statistics
    exporter.export_statistics(instruction_pairs)
    
    print("Training data export completed!")

if __name__ == "__main__":
    main()