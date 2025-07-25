"""
Unit tests for ML training data export functionality.
"""

import json
import csv
import tempfile
import shutil
import sys
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from saidata_gen.ml.export import (
    TrainingDataExporter,
    InstructionPair,
    ExportResult,
    ExportError
)
from saidata_gen.core.models import EnhancedSaidataMetadata as SaidataMetadata


class TestInstructionPair:
    """Test InstructionPair dataclass."""
    
    def test_instruction_pair_creation(self):
        """Test creating an instruction pair."""
        pair = InstructionPair(
            instruction="Generate metadata",
            input="Software: nginx",
            output="version: 0.1\npackages:\n  apt:\n    name: nginx",
            confidence_score=0.8
        )
        
        assert pair.instruction == "Generate metadata"
        assert pair.input == "Software: nginx"
        assert pair.confidence_score == 0.8
    
    def test_instruction_pair_to_dict(self):
        """Test converting instruction pair to dictionary."""
        pair = InstructionPair(
            instruction="Test instruction",
            input="Test input",
            output="Test output",
            metadata={"test": "value"}
        )
        
        result = pair.to_dict()
        
        assert result["instruction"] == "Test instruction"
        assert result["input"] == "Test input"
        assert result["output"] == "Test output"
        assert result["metadata"] == {"test": "value"}


class TestTrainingDataExporter:
    """Test TrainingDataExporter class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.exporter = TrainingDataExporter(output_dir=self.temp_dir)
        
        # Sample training data
        self.sample_data = [
            {
                "instruction": "Generate metadata for nginx",
                "input": "Software: nginx",
                "output": "version: 0.1\npackages:\n  apt:\n    name: nginx",
                "confidence_score": 0.9
            },
            {
                "instruction": "Categorize software",
                "input": "Software: nginx\nDescription: Web server",
                "output": "Primary: Web Server\nTags: server, http",
                "confidence_score": 0.8
            }
        ]
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_exporter_initialization(self):
        """Test exporter initialization."""
        assert self.exporter.output_dir == Path(self.temp_dir)
        assert self.exporter.output_dir.exists()
    
    def test_export_jsonl_format(self):
        """Test exporting data in JSONL format."""
        result = self.exporter.export_training_data(
            data=self.sample_data,
            format="jsonl",
            output_filename="test_export"
        )
        
        assert result.success is True
        assert result.format == "jsonl"
        assert result.record_count == 2
        assert result.file_size_bytes > 0
        
        # Verify file contents
        output_path = Path(result.output_path)
        assert output_path.exists()
        
        with open(output_path, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 2
            
            # Parse first line
            first_record = json.loads(lines[0])
            assert first_record["instruction"] == "Generate metadata for nginx"
            assert first_record["confidence_score"] == 0.9
    
    def test_export_csv_format(self):
        """Test exporting data in CSV format."""
        result = self.exporter.export_training_data(
            data=self.sample_data,
            format="csv",
            output_filename="test_export"
        )
        
        assert result.success is True
        assert result.format == "csv"
        assert result.record_count == 2
        
        # Verify file contents
        output_path = Path(result.output_path)
        assert output_path.exists()
        
        with open(output_path, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2
            assert "instruction" in rows[0]
            assert "confidence_score" in rows[0]
    
    def test_export_parquet_format(self):
        """Test exporting data in Parquet format."""
        # Mock pandas module
        mock_pd = Mock()
        mock_df = Mock()
        mock_pd.DataFrame.return_value = mock_df
        mock_df.to_parquet.return_value = None
        
        with patch('saidata_gen.ml.export.PANDAS_AVAILABLE', True):
            with patch.dict('sys.modules', {'pandas': mock_pd}):
                # Import the module again to get the mocked pandas
                import importlib
                import saidata_gen.ml.export
                importlib.reload(saidata_gen.ml.export)
                
                # Create a mock file to simulate parquet output
                output_path = Path(self.temp_dir) / "test_export.parquet"
                output_path.write_text("mock parquet data")
                
                result = self.exporter.export_training_data(
                    data=self.sample_data,
                    format="parquet",
                    output_filename="test_export"
                )
                
                assert result.success is True
                assert result.format == "parquet"
                mock_pd.DataFrame.assert_called_once()
                mock_df.to_parquet.assert_called_once()
    
    @patch('saidata_gen.ml.export.PANDAS_AVAILABLE', False)
    def test_export_parquet_without_pandas(self):
        """Test parquet export fails without pandas."""
        result = self.exporter.export_training_data(
            data=self.sample_data,
            format="parquet",
            output_filename="test_export"
        )
        
        assert result.success is False
        assert "pandas is required" in result.errors[0]
    
    def test_export_unsupported_format(self):
        """Test export with unsupported format."""
        result = self.exporter.export_training_data(
            data=self.sample_data,
            format="xml",
            output_filename="test_export"
        )
        
        assert result.success is False
        assert "Unsupported export format" in result.errors[0]
    
    def test_export_empty_data(self):
        """Test export with empty data."""
        result = self.exporter.export_training_data(
            data=[],
            format="jsonl",
            output_filename="empty_export"
        )
        
        assert result.success is True
        assert result.record_count == 0
    
    def test_export_without_metadata(self):
        """Test export excluding metadata fields."""
        data_with_metadata = [
            {
                "instruction": "Test",
                "input": "Test input",
                "output": "Test output",
                "timestamp": "2023-01-01T00:00:00",
                "source": "test",
                "metadata": {"test": "value"}
            }
        ]
        
        result = self.exporter.export_training_data(
            data=data_with_metadata,
            format="jsonl",
            output_filename="clean_export",
            include_metadata=False
        )
        
        assert result.success is True
        
        # Verify metadata fields are removed
        with open(result.output_path, 'r') as f:
            record = json.loads(f.readline())
            assert "timestamp" not in record
            assert "source" not in record
            assert "metadata" not in record
            assert "instruction" in record  # Core fields should remain
    
    def test_generate_instruction_pairs(self):
        """Test generating instruction pairs from metadata."""
        # Create sample metadata
        metadata = SaidataMetadata(
            version="0.1",
            packages={"apt": {"name": "nginx"}},
            description="High-performance web server",
            urls={"website": "https://nginx.org"},
            category={"default": "Web Server", "tags": ["server", "http"]}
        )
        
        pairs = self.exporter.generate_instruction_pairs([metadata])
        
        assert len(pairs) > 0
        
        # Check that we have different types of instruction pairs
        instructions = [pair.instruction for pair in pairs]
        assert any("Generate saidata YAML" in inst for inst in instructions)
        assert any("Enhance the description" in inst for inst in instructions)
        assert any("Categorize this software" in inst for inst in instructions)
    
    def test_generate_instruction_pairs_with_custom_templates(self):
        """Test generating instruction pairs with custom templates."""
        metadata = SaidataMetadata(
            version="0.1",
            packages={"apt": {"name": "nginx"}},
            description="Web server"
        )
        
        custom_templates = ["generate_metadata", "enhance_description"]
        
        pairs = self.exporter.generate_instruction_pairs(
            [metadata], 
            instruction_templates=custom_templates
        )
        
        # Should only generate pairs for custom templates
        instructions = [pair.instruction for pair in pairs]
        assert len([inst for inst in instructions if "Generate saidata YAML" in inst]) > 0
        assert len([inst for inst in instructions if "Enhance the description" in inst]) > 0
        assert len([inst for inst in instructions if "Categorize this software" in inst]) == 0
    
    def test_export_instruction_pairs(self):
        """Test exporting instruction pairs."""
        pairs = [
            InstructionPair(
                instruction="Test instruction",
                input="Test input",
                output="Test output",
                confidence_score=0.8
            ),
            InstructionPair(
                instruction="Another instruction",
                input="Another input", 
                output="Another output",
                confidence_score=0.9
            )
        ]
        
        result = self.exporter.export_instruction_pairs(
            pairs=pairs,
            format="jsonl",
            output_filename="instruction_pairs"
        )
        
        assert result.success is True
        assert result.record_count == 2
        
        # Verify contents
        with open(result.output_path, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 2
            
            first_record = json.loads(lines[0])
            assert first_record["instruction"] == "Test instruction"
            assert first_record["confidence_score"] == 0.8
    
    def test_flatten_dict(self):
        """Test dictionary flattening for CSV export."""
        nested_dict = {
            "simple": "value",
            "nested": {
                "key1": "value1",
                "key2": "value2"
            },
            "list_field": ["item1", "item2"]
        }
        
        flattened = self.exporter._flatten_dict(nested_dict)
        
        assert flattened["simple"] == "value"
        assert flattened["nested_key1"] == "value1"
        assert flattened["nested_key2"] == "value2"
        assert flattened["list_field"] == "item1, item2"
    
    def test_calculate_confidence_score(self):
        """Test confidence score calculation."""
        # Complete metadata
        complete_metadata = {
            "packages": {"apt": {"name": "nginx"}},
            "description": "Web server",
            "urls": {"website": "https://nginx.org", "source": "https://github.com/nginx/nginx"},
            "category": {"default": "Web Server"},
            "license": "BSD-2-Clause"
        }
        
        score = self.exporter._calculate_confidence_score(complete_metadata)
        assert score > 0.8  # Should be high for complete metadata
        
        # Incomplete metadata
        incomplete_metadata = {
            "packages": {"apt": {"name": "nginx"}},
            "description": "Web server"
        }
        
        score = self.exporter._calculate_confidence_score(incomplete_metadata)
        assert score < 0.5  # Should be lower for incomplete metadata
    
    def test_extract_software_name(self):
        """Test software name extraction."""
        # From packages
        metadata_with_packages = {
            "packages": {"apt": {"name": "nginx"}, "brew": {"name": "nginx"}}
        }
        name = self.exporter._extract_software_name(metadata_with_packages)
        assert name in ["apt", "brew"]  # Should return one of the package keys
        
        # From description
        metadata_with_description = {
            "description": "nginx is a web server"
        }
        name = self.exporter._extract_software_name(metadata_with_description)
        assert name == "nginx"
        
        # Empty metadata
        empty_metadata = {}
        name = self.exporter._extract_software_name(empty_metadata)
        assert name is None


if __name__ == "__main__":
    pytest.main([__file__])