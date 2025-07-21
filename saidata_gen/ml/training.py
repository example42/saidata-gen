"""
Model fine-tuning and training functionality.

This module provides the ModelTrainer class for fine-tuning models
with HuggingFace Transformers integration, training pipelines,
and model serving capabilities.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime

try:
    import torch
    import transformers
    from transformers import (
        AutoTokenizer, AutoModelForCausalLM, AutoModelForSeq2SeqLM,
        TrainingArguments, Trainer, DataCollatorForSeq2Seq,
        EarlyStoppingCallback
    )
    from datasets import Dataset
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    # Create dummy classes for type hints when transformers is not available
    torch = None
    transformers = None
    
    class Dataset:
        pass
    
    class AutoTokenizer:
        pass
    
    class AutoModelForCausalLM:
        pass
    
    class AutoModelForSeq2SeqLM:
        pass
    
    class TrainingArguments:
        pass
    
    class Trainer:
        pass
    
    class DataCollatorForSeq2Seq:
        pass
    
    class EarlyStoppingCallback:
        pass

from .export import InstructionPair
from ..core.exceptions import SaidataGenError


logger = logging.getLogger(__name__)


class TrainingError(SaidataGenError):
    """Raised when model training fails."""
    pass


@dataclass
class ModelConfig:
    """Configuration for model training."""
    model_name: str = "microsoft/DialoGPT-small"
    model_type: str = "causal_lm"  # "causal_lm" or "seq2seq"
    max_length: int = 512
    learning_rate: float = 5e-5
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 4
    per_device_eval_batch_size: int = 4
    warmup_steps: int = 100
    weight_decay: float = 0.01
    logging_steps: int = 10
    eval_steps: int = 500
    save_steps: int = 1000
    evaluation_strategy: str = "steps"
    save_strategy: str = "steps"
    load_best_model_at_end: bool = True
    metric_for_best_model: str = "eval_loss"
    greater_is_better: bool = False
    early_stopping_patience: int = 3
    gradient_accumulation_steps: int = 1
    fp16: bool = False
    dataloader_num_workers: int = 0
    remove_unused_columns: bool = False
    
    def to_training_args(self, output_dir: str) -> 'TrainingArguments':
        """Convert to HuggingFace TrainingArguments."""
        if not TRANSFORMERS_AVAILABLE:
            raise TrainingError("transformers library is required for training")
        
        return TrainingArguments(
            output_dir=output_dir,
            learning_rate=self.learning_rate,
            num_train_epochs=self.num_train_epochs,
            per_device_train_batch_size=self.per_device_train_batch_size,
            per_device_eval_batch_size=self.per_device_eval_batch_size,
            warmup_steps=self.warmup_steps,
            weight_decay=self.weight_decay,
            logging_steps=self.logging_steps,
            eval_steps=self.eval_steps,
            save_steps=self.save_steps,
            evaluation_strategy=self.evaluation_strategy,
            save_strategy=self.save_strategy,
            load_best_model_at_end=self.load_best_model_at_end,
            metric_for_best_model=self.metric_for_best_model,
            greater_is_better=self.greater_is_better,
            gradient_accumulation_steps=self.gradient_accumulation_steps,
            fp16=self.fp16,
            dataloader_num_workers=self.dataloader_num_workers,
            remove_unused_columns=self.remove_unused_columns,
            report_to=[]  # Disable wandb/tensorboard by default
        )


@dataclass
class TrainingResult:
    """Result of model training."""
    success: bool
    model_path: str
    training_loss: float
    eval_loss: Optional[float]
    training_time: float
    epochs_completed: int
    best_checkpoint: Optional[str]
    metrics: Dict[str, float]
    errors: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "model_path": self.model_path,
            "training_loss": self.training_loss,
            "eval_loss": self.eval_loss,
            "training_time": self.training_time,
            "epochs_completed": self.epochs_completed,
            "best_checkpoint": self.best_checkpoint,
            "metrics": self.metrics,
            "errors": self.errors
        }


@dataclass
class EvaluationResult:
    """Result of model evaluation."""
    success: bool
    metrics: Dict[str, float]
    predictions: List[str]
    references: List[str]
    evaluation_time: float
    errors: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "metrics": self.metrics,
            "predictions": self.predictions[:100],  # Limit for serialization
            "references": self.references[:100],
            "evaluation_time": self.evaluation_time,
            "errors": self.errors
        }


class ModelTrainer:
    """
    Model trainer with HuggingFace Transformers integration.
    
    Supports fine-tuning of language models for saidata metadata generation
    with comprehensive training pipelines and evaluation metrics.
    """
    
    def __init__(self, config: Optional[ModelConfig] = None):
        """
        Initialize the model trainer.
        
        Args:
            config: Model training configuration
        """
        if not TRANSFORMERS_AVAILABLE:
            raise TrainingError(
                "transformers library is required for training. "
                "Install with: pip install torch transformers datasets"
            )
        
        self.config = config or ModelConfig()
        self.tokenizer = None
        self.model = None
        self.trainer = None
        
    def prepare_model_and_tokenizer(self) -> None:
        """Load and prepare model and tokenizer."""
        try:
            logger.info(f"Loading tokenizer and model: {self.config.model_name}")
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
            
            # Add padding token if not present
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Load model based on type
            if self.config.model_type == "seq2seq":
                self.model = AutoModelForSeq2SeqLM.from_pretrained(self.config.model_name)
            else:  # causal_lm
                self.model = AutoModelForCausalLM.from_pretrained(self.config.model_name)
            
            # Resize token embeddings if needed
            self.model.resize_token_embeddings(len(self.tokenizer))
            
            logger.info("Model and tokenizer loaded successfully")
            
        except Exception as e:
            raise TrainingError(f"Failed to load model and tokenizer: {str(e)}")
    
    def prepare_dataset(
        self,
        train_samples: List[InstructionPair],
        eval_samples: Optional[List[InstructionPair]] = None
    ) -> Tuple[Dataset, Optional[Dataset]]:
        """
        Prepare training and evaluation datasets.
        
        Args:
            train_samples: Training instruction pairs
            eval_samples: Evaluation instruction pairs (optional)
            
        Returns:
            Tuple of (train_dataset, eval_dataset)
        """
        if self.tokenizer is None:
            raise TrainingError("Tokenizer not loaded. Call prepare_model_and_tokenizer() first.")
        
        # Prepare training dataset
        train_texts = self._format_samples_for_training(train_samples)
        train_encodings = self._tokenize_texts(train_texts)
        train_dataset = Dataset.from_dict(train_encodings)
        
        # Prepare evaluation dataset if provided
        eval_dataset = None
        if eval_samples:
            eval_texts = self._format_samples_for_training(eval_samples)
            eval_encodings = self._tokenize_texts(eval_texts)
            eval_dataset = Dataset.from_dict(eval_encodings)
        
        logger.info(f"Prepared datasets: train={len(train_dataset)}, eval={len(eval_dataset) if eval_dataset else 0}")
        return train_dataset, eval_dataset
    
    def fine_tune_model(
        self,
        train_samples: List[InstructionPair],
        eval_samples: Optional[List[InstructionPair]] = None,
        output_dir: Optional[str] = None
    ) -> TrainingResult:
        """
        Fine-tune the model on training data.
        
        Args:
            train_samples: Training instruction pairs
            eval_samples: Evaluation instruction pairs (optional)
            output_dir: Directory to save the fine-tuned model
            
        Returns:
            TrainingResult with training details
        """
        start_time = datetime.now()
        errors = []
        
        try:
            # Prepare output directory
            if output_dir is None:
                output_dir = tempfile.mkdtemp(prefix="saidata_model_")
            else:
                os.makedirs(output_dir, exist_ok=True)
            
            # Prepare model and tokenizer
            if self.model is None or self.tokenizer is None:
                self.prepare_model_and_tokenizer()
            
            # Prepare datasets
            train_dataset, eval_dataset = self.prepare_dataset(train_samples, eval_samples)
            
            # Create training arguments
            training_args = self.config.to_training_args(output_dir)
            
            # Create data collator
            if self.config.model_type == "seq2seq":
                data_collator = DataCollatorForSeq2Seq(
                    tokenizer=self.tokenizer,
                    model=self.model,
                    padding=True
                )
            else:
                data_collator = transformers.DataCollatorForLanguageModeling(
                    tokenizer=self.tokenizer,
                    mlm=False
                )
            
            # Create trainer
            callbacks = []
            if eval_dataset is not None and self.config.early_stopping_patience > 0:
                callbacks.append(EarlyStoppingCallback(
                    early_stopping_patience=self.config.early_stopping_patience
                ))
            
            self.trainer = Trainer(
                model=self.model,
                args=training_args,
                train_dataset=train_dataset,
                eval_dataset=eval_dataset,
                data_collator=data_collator,
                tokenizer=self.tokenizer,
                callbacks=callbacks
            )
            
            # Start training
            logger.info("Starting model fine-tuning...")
            train_result = self.trainer.train()
            
            # Save the final model
            self.trainer.save_model()
            self.tokenizer.save_pretrained(output_dir)
            
            # Calculate training time
            training_time = (datetime.now() - start_time).total_seconds()
            
            # Extract metrics
            metrics = train_result.metrics
            training_loss = metrics.get('train_loss', 0.0)
            eval_loss = metrics.get('eval_loss') if eval_dataset else None
            epochs_completed = int(metrics.get('epoch', 0))
            
            # Find best checkpoint
            best_checkpoint = None
            if hasattr(self.trainer.state, 'best_model_checkpoint'):
                best_checkpoint = self.trainer.state.best_model_checkpoint
            
            logger.info(f"Training completed successfully in {training_time:.2f} seconds")
            
            return TrainingResult(
                success=True,
                model_path=output_dir,
                training_loss=training_loss,
                eval_loss=eval_loss,
                training_time=training_time,
                epochs_completed=epochs_completed,
                best_checkpoint=best_checkpoint,
                metrics=metrics,
                errors=errors
            )
            
        except Exception as e:
            error_msg = f"Training failed: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
            
            training_time = (datetime.now() - start_time).total_seconds()
            
            return TrainingResult(
                success=False,
                model_path="",
                training_loss=0.0,
                eval_loss=None,
                training_time=training_time,
                epochs_completed=0,
                best_checkpoint=None,
                metrics={},
                errors=errors
            )
    
    def evaluate_model(
        self,
        eval_samples: List[InstructionPair],
        model_path: Optional[str] = None
    ) -> EvaluationResult:
        """
        Evaluate the model on evaluation data.
        
        Args:
            eval_samples: Evaluation instruction pairs
            model_path: Path to model (if None, uses current model)
            
        Returns:
            EvaluationResult with evaluation metrics
        """
        start_time = datetime.now()
        errors = []
        
        try:
            # Load model if path provided
            if model_path and model_path != getattr(self, '_current_model_path', None):
                self._load_model_from_path(model_path)
            
            if self.model is None or self.tokenizer is None:
                raise TrainingError("Model not loaded. Train or load a model first.")
            
            # Prepare evaluation dataset
            _, eval_dataset = self.prepare_dataset([], eval_samples)
            
            # Run evaluation
            logger.info("Starting model evaluation...")
            eval_result = self.trainer.evaluate(eval_dataset) if self.trainer else {}
            
            # Generate predictions for a sample of the data
            predictions, references = self._generate_predictions(eval_samples[:50])  # Limit for performance
            
            evaluation_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"Evaluation completed in {evaluation_time:.2f} seconds")
            
            return EvaluationResult(
                success=True,
                metrics=eval_result,
                predictions=predictions,
                references=references,
                evaluation_time=evaluation_time,
                errors=errors
            )
            
        except Exception as e:
            error_msg = f"Evaluation failed: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)
            
            evaluation_time = (datetime.now() - start_time).total_seconds()
            
            return EvaluationResult(
                success=False,
                metrics={},
                predictions=[],
                references=[],
                evaluation_time=evaluation_time,
                errors=errors
            )
    
    def generate_text(
        self,
        prompt: str,
        max_length: Optional[int] = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        do_sample: bool = True
    ) -> str:
        """
        Generate text using the fine-tuned model.
        
        Args:
            prompt: Input prompt
            max_length: Maximum generation length
            temperature: Sampling temperature
            top_p: Top-p sampling parameter
            do_sample: Whether to use sampling
            
        Returns:
            Generated text
        """
        if self.model is None or self.tokenizer is None:
            raise TrainingError("Model not loaded. Train or load a model first.")
        
        max_length = max_length or self.config.max_length
        
        # Tokenize input
        inputs = self.tokenizer.encode(prompt, return_tensors="pt")
        
        # Generate
        with torch.no_grad():
            outputs = self.model.generate(
                inputs,
                max_length=max_length,
                temperature=temperature,
                top_p=top_p,
                do_sample=do_sample,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id
            )
        
        # Decode output
        generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Remove the input prompt from the output
        if generated_text.startswith(prompt):
            generated_text = generated_text[len(prompt):].strip()
        
        return generated_text
    
    def save_model(self, output_path: str) -> None:
        """Save the current model and tokenizer."""
        if self.model is None or self.tokenizer is None:
            raise TrainingError("No model to save. Train or load a model first.")
        
        os.makedirs(output_path, exist_ok=True)
        self.model.save_pretrained(output_path)
        self.tokenizer.save_pretrained(output_path)
        
        # Save config
        config_path = Path(output_path) / "training_config.json"
        with open(config_path, 'w') as f:
            json.dump(self.config.__dict__, f, indent=2)
        
        logger.info(f"Model saved to {output_path}")
    
    def load_model(self, model_path: str) -> None:
        """Load a saved model and tokenizer."""
        self._load_model_from_path(model_path)
        self._current_model_path = model_path
    
    def _load_model_from_path(self, model_path: str) -> None:
        """Load model and tokenizer from path."""
        try:
            logger.info(f"Loading model from {model_path}")
            
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            
            if self.config.model_type == "seq2seq":
                self.model = AutoModelForSeq2SeqLM.from_pretrained(model_path)
            else:
                self.model = AutoModelForCausalLM.from_pretrained(model_path)
            
            # Load training config if available
            config_path = Path(model_path) / "training_config.json"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config_dict = json.load(f)
                    for key, value in config_dict.items():
                        if hasattr(self.config, key):
                            setattr(self.config, key, value)
            
            logger.info("Model loaded successfully")
            
        except Exception as e:
            raise TrainingError(f"Failed to load model from {model_path}: {str(e)}")
    
    def _format_samples_for_training(self, samples: List[InstructionPair]) -> List[str]:
        """Format instruction pairs for training."""
        formatted_texts = []
        
        for sample in samples:
            if self.config.model_type == "seq2seq":
                # For seq2seq models, use instruction + input as source, output as target
                source = f"{sample.instruction}\n\nInput: {sample.input}"
                target = sample.output
                formatted_text = f"<source>{source}</source><target>{target}</target>"
            else:
                # For causal LM, format as a conversation
                formatted_text = (
                    f"Instruction: {sample.instruction}\n"
                    f"Input: {sample.input}\n"
                    f"Output: {sample.output}"
                )
            
            formatted_texts.append(formatted_text)
        
        return formatted_texts
    
    def _tokenize_texts(self, texts: List[str]) -> Dict[str, List[List[int]]]:
        """Tokenize texts for training."""
        encodings = self.tokenizer(
            texts,
            truncation=True,
            padding=True,
            max_length=self.config.max_length,
            return_tensors="pt"
        )
        
        # Convert to lists for Dataset
        return {
            "input_ids": encodings["input_ids"].tolist(),
            "attention_mask": encodings["attention_mask"].tolist(),
            "labels": encodings["input_ids"].tolist()  # For causal LM
        }
    
    def _generate_predictions(
        self, 
        samples: List[InstructionPair]
    ) -> Tuple[List[str], List[str]]:
        """Generate predictions for evaluation samples."""
        predictions = []
        references = []
        
        for sample in samples:
            try:
                # Create prompt
                prompt = f"Instruction: {sample.instruction}\nInput: {sample.input}\nOutput:"
                
                # Generate prediction
                prediction = self.generate_text(
                    prompt,
                    max_length=256,
                    temperature=0.1,  # Low temperature for more deterministic output
                    do_sample=False
                )
                
                predictions.append(prediction)
                references.append(sample.output)
                
            except Exception as e:
                logger.warning(f"Failed to generate prediction: {e}")
                predictions.append("")
                references.append(sample.output)
        
        return predictions, references