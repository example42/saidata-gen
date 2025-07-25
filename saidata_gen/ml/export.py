"""
Training data export functionality for ML model training.

This module provides the TrainingDataExporter class for generating
training datasets in various formats suitable for machine learning.
"""

import json
import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Iterator
from dataclasses import dataclass, asdict
from datetime import datetime

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from ..core.models import EnhancedSaidataMetadata as SaidataMetadata
from ..core.exceptions import SaidataGenError


logger = logging.getLogger(__name__)


class ExportError(SaidataGenError):
    """Raised when training data export fails."""
    pass


@dataclass
class InstructionPair:
    """Represents an instruction-response pair for supervised learning."""
    instruction: str
    input: str
    output: str
    metadata: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = None
    source: Optional[str] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return asdict(self)


@dataclass
class ExportResult:
    """Result of training data export operation."""
    success: bool
    output_path: str
    format: str
    record_count: int
    file_size_bytes: int
    errors: List[str]
    export_time: str


class TrainingDataExporter:
    """
    Exports training data for ML model training in various formats.
    
    Supports JSONL, CSV, and Parquet formats with instruction-response
    pair generation for supervised learning.
    """

    def __init__(self, output_dir: str = "./training_data"):
        """
        Initialize the training data exporter.
        
        Args:
            output_dir: Directory to save exported training data
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def export_training_data(
        self,
        data: List[Dict[str, Any]],
        format: str,
        output_filename: str,
        include_metadata: bool = True
    ) -> ExportResult:
        """
        Export training data in the specified format.
        
        Args:
            data: List of training data records
            format: Export format ('jsonl', 'csv', 'parquet')
            output_filename: Name of output file (without extension)
            include_metadata: Whether to include metadata fields
            
        Returns:
            ExportResult with export details
            
        Raises:
            ExportError: If export fails
        """
        start_time = datetime.now()
        errors = []
        
        try:
            # Validate format
            if format.lower() not in ['jsonl', 'csv', 'parquet']:
                raise ExportError(f"Unsupported export format: {format}")
            
            # Generate output path
            output_path = self.output_dir / f"{output_filename}.{format.lower()}"
            
            # Export based on format
            if format.lower() == 'jsonl':
                record_count = self._export_jsonl(data, output_path, include_metadata)
            elif format.lower() == 'csv':
                record_count = self._export_csv(data, output_path, include_metadata)
            elif format.lower() == 'parquet':
                record_count = self._export_parquet(data, output_path, include_metadata)
            
            # Get file size
            file_size = output_path.stat().st_size
            
            logger.info(f"Exported {record_count} records to {output_path}")
            
            return ExportResult(
                success=True,
                output_path=str(output_path),
                format=format.lower(),
                record_count=record_count,
                file_size_bytes=file_size,
                errors=errors,
                export_time=datetime.now().isoformat()
            )
            
        except Exception as e:
            error_msg = f"Export failed: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
            
            return ExportResult(
                success=False,
                output_path="",
                format=format.lower(),
                record_count=0,
                file_size_bytes=0,
                errors=errors,
                export_time=datetime.now().isoformat()
            )
    
    def _export_jsonl(
        self, 
        data: List[Dict[str, Any]], 
        output_path: Path,
        include_metadata: bool
    ) -> int:
        """Export data in JSONL format."""
        record_count = 0
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for record in data:
                if not include_metadata:
                    # Remove metadata fields for cleaner training data
                    record = self._clean_record(record)
                
                json.dump(record, f, ensure_ascii=False)
                f.write('\n')
                record_count += 1
        
        return record_count
    
    def _export_csv(
        self, 
        data: List[Dict[str, Any]], 
        output_path: Path,
        include_metadata: bool
    ) -> int:
        """Export data in CSV format."""
        if not data:
            return 0
        
        # Flatten nested dictionaries for CSV
        flattened_data = []
        for record in data:
            if not include_metadata:
                record = self._clean_record(record)
            flattened_data.append(self._flatten_dict(record))
        
        # Get all possible fieldnames
        fieldnames = set()
        for record in flattened_data:
            fieldnames.update(record.keys())
        fieldnames = sorted(list(fieldnames))
        
        record_count = 0
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for record in flattened_data:
                writer.writerow(record)
                record_count += 1
        
        return record_count
    
    def _export_parquet(
        self, 
        data: List[Dict[str, Any]], 
        output_path: Path,
        include_metadata: bool
    ) -> int:
        """Export data in Parquet format."""
        if not PANDAS_AVAILABLE:
            raise ExportError("pandas is required for Parquet export. Install with: pip install pandas")
        
        if not data:
            return 0
        
        # Prepare data for DataFrame
        processed_data = []
        for record in data:
            if not include_metadata:
                record = self._clean_record(record)
            processed_data.append(self._flatten_dict(record))
        
        # Create DataFrame and export
        df = pd.DataFrame(processed_data)
        df.to_parquet(output_path, index=False)
        
        return len(processed_data)
    
    def generate_instruction_pairs(
        self,
        metadata_samples: List[SaidataMetadata],
        instruction_templates: Optional[List[str]] = None
    ) -> List[InstructionPair]:
        """
        Generate instruction-response pairs from saidata metadata samples.
        
        Args:
            metadata_samples: List of SaidataMetadata objects
            instruction_templates: Custom instruction templates
            
        Returns:
            List of InstructionPair objects
        """
        if instruction_templates is None:
            instruction_templates = self._get_default_instruction_templates()
        
        pairs = []
        
        for metadata in metadata_samples:
            for template in instruction_templates:
                try:
                    pair = self._create_instruction_pair(metadata, template)
                    if pair:
                        pairs.append(pair)
                except Exception as e:
                    logger.warning(f"Failed to create instruction pair: {e}")
                    continue
        
        return pairs
    
    def _create_instruction_pair(
        self, 
        metadata: SaidataMetadata, 
        template: str
    ) -> Optional[InstructionPair]:
        """Create a single instruction pair from metadata and template."""
        metadata_dict = metadata.to_dict() if hasattr(metadata, 'to_dict') else asdict(metadata)
        
        # Extract software name for context
        software_name = self._extract_software_name(metadata_dict)
        if not software_name:
            return None
        
        # Generate instruction based on template
        if template == "generate_metadata":
            instruction = "Generate saidata YAML metadata for the given software package."
            input_text = f"Software: {software_name}"
            output = self._format_metadata_output(metadata_dict)
            
        elif template == "enhance_description":
            instruction = "Enhance the description for this software package based on its metadata."
            input_text = self._format_basic_info(metadata_dict)
            output = metadata_dict.get('description', '')
            
        elif template == "categorize_software":
            instruction = "Categorize this software package based on its metadata."
            input_text = self._format_basic_info(metadata_dict)
            output = self._format_category_output(metadata_dict.get('category', {}))
            
        elif template == "extract_urls":
            instruction = "Extract and format URLs for this software package."
            input_text = f"Software: {software_name}\nPackages: {metadata_dict.get('packages', {})}"
            output = self._format_urls_output(metadata_dict.get('urls', {}))
            
        else:
            return None
        
        if not output or not output.strip():
            return None
        
        return InstructionPair(
            instruction=instruction,
            input=input_text,
            output=output,
            metadata={
                "software_name": software_name,
                "template": template,
                "has_packages": bool(metadata_dict.get('packages')),
                "has_urls": bool(metadata_dict.get('urls')),
                "has_description": bool(metadata_dict.get('description')),
            },
            confidence_score=self._calculate_confidence_score(metadata_dict),
            source="saidata_metadata",
            timestamp=datetime.now().isoformat()
        )
    
    def _get_default_instruction_templates(self) -> List[str]:
        """Get default instruction templates."""
        return [
            "generate_metadata",
            "enhance_description", 
            "categorize_software",
            "extract_urls"
        ]
    
    def _extract_software_name(self, metadata: Dict[str, Any]) -> Optional[str]:
        """Extract software name from metadata."""
        # Try to get from packages
        packages = metadata.get('packages', {})
        if packages:
            # Return first package name
            return list(packages.keys())[0]
        
        # Try to get from description or other fields
        description = metadata.get('description', '')
        if description:
            # Simple heuristic to extract name from description
            words = description.split()
            if words:
                return words[0]
        
        return None
    
    def _format_metadata_output(self, metadata: Dict[str, Any]) -> str:
        """Format metadata as YAML-like output."""
        import yaml
        return yaml.dump(metadata, default_flow_style=False, sort_keys=True)
    
    def _format_basic_info(self, metadata: Dict[str, Any]) -> str:
        """Format basic software info for input."""
        info_parts = []
        
        if metadata.get('packages'):
            packages = list(metadata['packages'].keys())
            info_parts.append(f"Packages: {', '.join(packages)}")
        
        if metadata.get('description'):
            info_parts.append(f"Description: {metadata['description']}")
        
        if metadata.get('category'):
            category = metadata['category']
            if isinstance(category, dict) and category.get('default'):
                info_parts.append(f"Category: {category['default']}")
        
        return '\n'.join(info_parts)
    
    def _format_category_output(self, category: Dict[str, Any]) -> str:
        """Format category information."""
        if not category:
            return ""
        
        parts = []
        if category.get('default'):
            parts.append(f"Primary: {category['default']}")
        if category.get('sub'):
            parts.append(f"Secondary: {category['sub']}")
        if category.get('tags'):
            parts.append(f"Tags: {', '.join(category['tags'])}")
        
        return '\n'.join(parts)
    
    def _format_urls_output(self, urls: Dict[str, Any]) -> str:
        """Format URLs information."""
        if not urls:
            return ""
        
        formatted_urls = []
        for key, value in urls.items():
            if value:
                formatted_urls.append(f"{key}: {value}")
        
        return '\n'.join(formatted_urls)
    
    def _calculate_confidence_score(self, metadata: Dict[str, Any]) -> float:
        """Calculate confidence score for metadata quality."""
        score = 0.0
        total_fields = 0
        
        # Check presence of key fields
        key_fields = ['packages', 'description', 'urls', 'category', 'license']
        for field in key_fields:
            total_fields += 1
            if metadata.get(field):
                if field == 'packages' and isinstance(metadata[field], dict):
                    score += 1.0 if metadata[field] else 0.5
                elif field == 'urls' and isinstance(metadata[field], dict):
                    url_count = sum(1 for v in metadata[field].values() if v)
                    score += min(1.0, url_count / 3)  # Normalize by expected URL count
                else:
                    score += 1.0
        
        return score / total_fields if total_fields > 0 else 0.0
    
    def _clean_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Remove metadata fields for cleaner training data."""
        cleaned = record.copy()
        
        # Remove common metadata fields
        metadata_fields = ['timestamp', 'source', 'confidence_score', 'metadata']
        for field in metadata_fields:
            cleaned.pop(field, None)
        
        return cleaned
    
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
        """Flatten nested dictionary for CSV export."""
        items = []
        
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # Convert lists to comma-separated strings
                items.append((new_key, ', '.join(str(item) for item in v)))
            else:
                items.append((new_key, v))
        
        return dict(items)
    
    def export_instruction_pairs(
        self,
        pairs: List[InstructionPair],
        format: str,
        output_filename: str
    ) -> ExportResult:
        """
        Export instruction pairs in the specified format.
        
        Args:
            pairs: List of InstructionPair objects
            format: Export format ('jsonl', 'csv', 'parquet')
            output_filename: Name of output file
            
        Returns:
            ExportResult with export details
        """
        # Convert pairs to dictionaries
        data = [pair.to_dict() for pair in pairs]
        
        return self.export_training_data(
            data=data,
            format=format,
            output_filename=output_filename,
            include_metadata=True
        )