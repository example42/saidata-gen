"""
Unit tests for ML model training functionality.
"""

import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from saidata_gen.ml.training import (
    ModelTrainer,
    ModelConfig,
    TrainingResult,
    EvaluationResult,
    TrainingError
)
from saidata_gen.ml.export import InstructionPair


class TestModelConfig:
    """Test ModelConfig dataclass."""
    
    def test_model_config_creation(self):
        """Test creating model config."""
        config = ModelConfig(
            model_name="test-model",
            learning_rate=1e-4,
            num_train_epochs=5
        )
        
        assert config.model_name == "test-model"
        assert config.learning_rate == 1e-4
        assert config.num_train_epochs == 5
        assert config.model_type == "causal_lm"  # default
    
    @patch('saidata_gen.ml.training.TRANSFORMERS_AVAILABLE', True)
    @patch('saidata_gen.ml.training.TrainingArguments')
    def test_to_training_args(self, mock_training_args):
        """Test converting to TrainingArguments."""
        config = ModelConfig(learning_rate=1e-4, num_train_epochs=3)
        
        config.to_training_args("/tmp/output")
        
        mock_training_args.assert_called_once()
        call_kwargs = mock_training_args.call_args[1]
        assert call_kwargs["output_dir"] == "/tmp/output"
        assert call_kwargs["learning_rate"] == 1e-4
        assert call_kwargs["num_train_epochs"] == 3
    
    @patch('saidata_gen.ml.training.TRANSFORMERS_AVAILABLE', False)
    def test_to_training_args_without_transformers(self):
        """Test error when transformers not available."""
        config = ModelConfig()
        
        with pytest.raises(TrainingError):
            config.to_training_args("/tmp/output")


class TestTrainingResult:
    """Test TrainingResult dataclass."""
    
    def test_training_result_creation(self):
        """Test creating training result."""
        result = TrainingResult(
            success=True,
            model_path="/path/to/model",
            training_loss=0.5,
            eval_loss=0.6,
            training_time=120.0,
            epochs_completed=3,
            best_checkpoint="/path/to/checkpoint",
            metrics={"accuracy": 0.85},
            errors=[]
        )
        
        assert result.success is True
        assert result.model_path == "/path/to/model"
        assert result.training_loss == 0.5
        assert result.metrics["accuracy"] == 0.85
    
    def test_training_result_to_dict(self):
        """Test converting result to dictionary."""
        result = TrainingResult(
            success=True,
            model_path="/path/to/model",
            training_loss=0.5,
            eval_loss=None,
            training_time=120.0,
            epochs_completed=3,
            best_checkpoint=None,
            metrics={},
            errors=[]
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["success"] is True
        assert result_dict["model_path"] == "/path/to/model"
        assert result_dict["training_loss"] == 0.5
        assert result_dict["eval_loss"] is None


class TestEvaluationResult:
    """Test EvaluationResult dataclass."""
    
    def test_evaluation_result_creation(self):
        """Test creating evaluation result."""
        result = EvaluationResult(
            success=True,
            metrics={"perplexity": 15.2},
            predictions=["pred1", "pred2"],
            references=["ref1", "ref2"],
            evaluation_time=30.0,
            errors=[]
        )
        
        assert result.success is True
        assert result.metrics["perplexity"] == 15.2
        assert len(result.predictions) == 2
    
    def test_evaluation_result_to_dict(self):
        """Test converting result to dictionary."""
        # Create result with many predictions to test truncation
        predictions = [f"pred{i}" for i in range(150)]
        references = [f"ref{i}" for i in range(150)]
        
        result = EvaluationResult(
            success=True,
            metrics={},
            predictions=predictions,
            references=references,
            evaluation_time=30.0,
            errors=[]
        )
        
        result_dict = result.to_dict()
        
        # Should truncate to 100 items
        assert len(result_dict["predictions"]) == 100
        assert len(result_dict["references"]) == 100


class TestModelTrainer:
    """Test ModelTrainer class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = ModelConfig(
            model_name="microsoft/DialoGPT-small",
            num_train_epochs=1,
            per_device_train_batch_size=1
        )
        
        self.sample_data = [
            InstructionPair(
                instruction="Generate metadata",
                input="Software: nginx",
                output="version: 0.1\npackages:\n  apt:\n    name: nginx",
                confidence_score=0.9
            ),
            InstructionPair(
                instruction="Categorize software",
                input="Software: apache",
                output="Web Server",
                confidence_score=0.8
            )
        ]
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    @patch('saidata_gen.ml.training.TRANSFORMERS_AVAILABLE', False)
    def test_trainer_init_without_transformers(self):
        """Test trainer initialization without transformers."""
        with pytest.raises(TrainingError):
            ModelTrainer(self.config)
    
    @patch('saidata_gen.ml.training.TRANSFORMERS_AVAILABLE', True)
    def test_trainer_initialization(self):
        """Test trainer initialization."""
        trainer = ModelTrainer(self.config)
        
        assert trainer.config.model_name == "microsoft/DialoGPT-small"
        assert trainer.tokenizer is None
        assert trainer.model is None
        assert trainer.trainer is None
    
    @patch('saidata_gen.ml.training.TRANSFORMERS_AVAILABLE', True)
    @patch('saidata_gen.ml.training.AutoTokenizer')
    @patch('saidata_gen.ml.training.AutoModelForCausalLM')
    def test_prepare_model_and_tokenizer(self, mock_model_class, mock_tokenizer_class):
        """Test preparing model and tokenizer."""
        # Mock tokenizer
        mock_tokenizer = Mock()
        mock_tokenizer.pad_token = None
        mock_tokenizer.eos_token = "<eos>"
        mock_tokenizer_class.from_pretrained.return_value = mock_tokenizer
        
        # Mock model
        mock_model = Mock()
        mock_model_class.from_pretrained.return_value = mock_model
        
        trainer = ModelTrainer(self.config)
        trainer.prepare_model_and_tokenizer()
        
        assert trainer.tokenizer == mock_tokenizer
        assert trainer.model == mock_model
        assert trainer.tokenizer.pad_token == "<eos>"
        mock_model.resize_token_embeddings.assert_called_once()
    
    @patch('saidata_gen.ml.training.TRANSFORMERS_AVAILABLE', True)
    @patch('saidata_gen.ml.training.AutoTokenizer')
    @patch('saidata_gen.ml.training.AutoModelForSeq2SeqLM')
    def test_prepare_seq2seq_model(self, mock_model_class, mock_tokenizer_class):
        """Test preparing seq2seq model."""
        config = ModelConfig(model_type="seq2seq")
        
        # Mock tokenizer and model
        mock_tokenizer = Mock()
        mock_tokenizer.pad_token = "<pad>"
        mock_tokenizer_class.from_pretrained.return_value = mock_tokenizer
        
        mock_model = Mock()
        mock_model_class.from_pretrained.return_value = mock_model
        
        trainer = ModelTrainer(config)
        trainer.prepare_model_and_tokenizer()
        
        mock_model_class.from_pretrained.assert_called_once()
        assert trainer.model == mock_model
    
    @patch('saidata_gen.ml.training.TRANSFORMERS_AVAILABLE', True)
    def test_prepare_dataset(self):
        """Test preparing training dataset."""
        trainer = ModelTrainer(self.config)
        
        # Mock tokenizer
        mock_tokenizer = Mock()
        mock_encodings = Mock()
        mock_encodings.__getitem__ = Mock(side_effect=lambda key: {
            "input_ids": Mock(tolist=Mock(return_value=[[1, 2, 3], [4, 5, 6]])),
            "attention_mask": Mock(tolist=Mock(return_value=[[1, 1, 1], [1, 1, 1]]))
        }[key])
        mock_tokenizer.return_value = mock_encodings
        trainer.tokenizer = mock_tokenizer
        
        with patch('saidata_gen.ml.training.Dataset') as mock_dataset_class:
            mock_dataset = Mock()
            mock_dataset.__len__ = Mock(return_value=2)
            mock_dataset_class.from_dict.return_value = mock_dataset
            
            train_dataset, eval_dataset = trainer.prepare_dataset(self.sample_data)
            
            assert train_dataset == mock_dataset
            assert eval_dataset is None
            mock_dataset_class.from_dict.assert_called_once()
    
    @patch('saidata_gen.ml.training.TRANSFORMERS_AVAILABLE', True)
    def test_prepare_dataset_without_tokenizer(self):
        """Test preparing dataset without tokenizer."""
        trainer = ModelTrainer(self.config)
        
        with pytest.raises(TrainingError):
            trainer.prepare_dataset(self.sample_data)
    
    @patch('saidata_gen.ml.training.TRANSFORMERS_AVAILABLE', True)
    def test_format_samples_for_training_causal_lm(self):
        """Test formatting samples for causal LM training."""
        trainer = ModelTrainer(self.config)
        
        formatted_texts = trainer._format_samples_for_training(self.sample_data)
        
        assert len(formatted_texts) == 2
        assert "Instruction: Generate metadata" in formatted_texts[0]
        assert "Input: Software: nginx" in formatted_texts[0]
        assert "Output: version: 0.1" in formatted_texts[0]
    
    @patch('saidata_gen.ml.training.TRANSFORMERS_AVAILABLE', True)
    def test_format_samples_for_training_seq2seq(self):
        """Test formatting samples for seq2seq training."""
        config = ModelConfig(model_type="seq2seq")
        trainer = ModelTrainer(config)
        
        formatted_texts = trainer._format_samples_for_training(self.sample_data)
        
        assert len(formatted_texts) == 2
        assert "<source>" in formatted_texts[0]
        assert "<target>" in formatted_texts[0]
        assert "Generate metadata" in formatted_texts[0]
    
    @patch('saidata_gen.ml.training.TRANSFORMERS_AVAILABLE', True)
    def test_tokenize_texts(self):
        """Test tokenizing texts."""
        trainer = ModelTrainer(self.config)
        
        # Mock tokenizer
        mock_tokenizer = Mock()
        mock_encodings = Mock()
        mock_input_ids = Mock()
        mock_input_ids.tolist.return_value = [[1, 2, 3], [4, 5, 6]]
        mock_attention_mask = Mock()
        mock_attention_mask.tolist.return_value = [[1, 1, 1], [1, 1, 1]]
        
        mock_encodings.__getitem__ = Mock(side_effect=lambda key: {
            "input_ids": mock_input_ids,
            "attention_mask": mock_attention_mask
        }[key])
        mock_tokenizer.return_value = mock_encodings
        trainer.tokenizer = mock_tokenizer
        
        texts = ["text1", "text2"]
        encodings = trainer._tokenize_texts(texts)
        
        assert "input_ids" in encodings
        assert "attention_mask" in encodings
        assert "labels" in encodings
        mock_tokenizer.assert_called_once()
    
    @patch('saidata_gen.ml.training.TRANSFORMERS_AVAILABLE', True)
    @patch('saidata_gen.ml.training.Trainer')
    @patch('saidata_gen.ml.training.Dataset')
    def test_fine_tune_model_success(self, mock_dataset_class, mock_trainer_class):
        """Test successful model fine-tuning."""
        trainer = ModelTrainer(self.config)
        
        # Mock components
        trainer.tokenizer = Mock()
        trainer.model = Mock()
        
        # Mock dataset
        mock_dataset = Mock()
        mock_dataset.__len__ = Mock(return_value=2)
        mock_dataset_class.from_dict.return_value = mock_dataset
        
        # Mock trainer
        mock_hf_trainer = Mock()
        mock_train_result = Mock()
        mock_train_result.metrics = {
            'train_loss': 0.5,
            'epoch': 1.0
        }
        mock_hf_trainer.train.return_value = mock_train_result
        mock_hf_trainer.save_model.return_value = None
        mock_trainer_class.return_value = mock_hf_trainer
        
        # Mock tokenizer methods
        trainer.tokenizer.return_value = {
            "input_ids": [[1, 2], [3, 4]],
            "attention_mask": [[1, 1], [1, 1]]
        }
        trainer.tokenizer.save_pretrained.return_value = None
        
        result = trainer.fine_tune_model(
            train_samples=self.sample_data,
            output_dir=self.temp_dir
        )
        
        assert result.success is True
        assert result.training_loss == 0.5
        assert result.epochs_completed == 1
        assert result.model_path == self.temp_dir
        mock_hf_trainer.train.assert_called_once()
        mock_hf_trainer.save_model.assert_called_once()
    
    @patch('saidata_gen.ml.training.TRANSFORMERS_AVAILABLE', True)
    def test_fine_tune_model_failure(self):
        """Test model fine-tuning failure."""
        trainer = ModelTrainer(self.config)
        
        # Don't prepare model/tokenizer to cause failure
        result = trainer.fine_tune_model(
            train_samples=self.sample_data,
            output_dir=self.temp_dir
        )
        
        assert result.success is False
        assert len(result.errors) > 0
        assert "Training failed" in result.errors[0]
    
    @patch('saidata_gen.ml.training.TRANSFORMERS_AVAILABLE', True)
    def test_generate_text(self):
        """Test text generation."""
        trainer = ModelTrainer(self.config)
        
        # Mock tokenizer and model
        mock_tokenizer = Mock()
        mock_tokenizer.encode.return_value = [1, 2, 3]
        mock_tokenizer.decode.return_value = "Generated text"
        mock_tokenizer.pad_token_id = 0
        mock_tokenizer.eos_token_id = 1
        trainer.tokenizer = mock_tokenizer
        
        mock_model = Mock()
        mock_outputs = Mock()
        mock_outputs.__getitem__ = Mock(return_value=[1, 2, 3, 4, 5])
        mock_model.generate.return_value = [mock_outputs]
        trainer.model = mock_model
        
        with patch('torch.no_grad'):
            result = trainer.generate_text("Test prompt")
        
        assert result == "Generated text"
        mock_model.generate.assert_called_once()
        mock_tokenizer.decode.assert_called_once()
    
    @patch('saidata_gen.ml.training.TRANSFORMERS_AVAILABLE', True)
    def test_generate_text_without_model(self):
        """Test text generation without model."""
        trainer = ModelTrainer(self.config)
        
        with pytest.raises(TrainingError):
            trainer.generate_text("Test prompt")
    
    @patch('saidata_gen.ml.training.TRANSFORMERS_AVAILABLE', True)
    def test_save_model(self):
        """Test saving model."""
        trainer = ModelTrainer(self.config)
        
        # Mock model and tokenizer
        mock_model = Mock()
        mock_tokenizer = Mock()
        trainer.model = mock_model
        trainer.tokenizer = mock_tokenizer
        
        output_path = str(Path(self.temp_dir) / "saved_model")
        trainer.save_model(output_path)
        
        mock_model.save_pretrained.assert_called_once_with(output_path)
        mock_tokenizer.save_pretrained.assert_called_once_with(output_path)
        
        # Check config file was created
        config_file = Path(output_path) / "training_config.json"
        assert config_file.exists()
    
    @patch('saidata_gen.ml.training.TRANSFORMERS_AVAILABLE', True)
    def test_save_model_without_model(self):
        """Test saving model without model loaded."""
        trainer = ModelTrainer(self.config)
        
        with pytest.raises(TrainingError):
            trainer.save_model(self.temp_dir)
    
    @patch('saidata_gen.ml.training.TRANSFORMERS_AVAILABLE', True)
    @patch('saidata_gen.ml.training.AutoTokenizer')
    @patch('saidata_gen.ml.training.AutoModelForCausalLM')
    def test_load_model(self, mock_model_class, mock_tokenizer_class):
        """Test loading model."""
        # Create a config file
        config_file = Path(self.temp_dir) / "training_config.json"
        config_file.write_text('{"learning_rate": 1e-4}')
        
        # Mock tokenizer and model
        mock_tokenizer = Mock()
        mock_model = Mock()
        mock_tokenizer_class.from_pretrained.return_value = mock_tokenizer
        mock_model_class.from_pretrained.return_value = mock_model
        
        trainer = ModelTrainer(self.config)
        trainer.load_model(self.temp_dir)
        
        assert trainer.tokenizer == mock_tokenizer
        assert trainer.model == mock_model
        assert trainer.config.learning_rate == 1e-4  # Should be updated from config file
    
    @patch('saidata_gen.ml.training.TRANSFORMERS_AVAILABLE', True)
    def test_generate_predictions(self):
        """Test generating predictions for evaluation."""
        trainer = ModelTrainer(self.config)
        
        # Mock generate_text method
        trainer.generate_text = Mock(side_effect=["prediction1", "prediction2"])
        
        predictions, references = trainer._generate_predictions(self.sample_data)
        
        assert len(predictions) == 2
        assert len(references) == 2
        assert predictions[0] == "prediction1"
        assert references[0] == self.sample_data[0].output
        assert trainer.generate_text.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__])