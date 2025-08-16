"""
AI Metadata Enhancer for saidata-gen.

This module provides the AIMetadataEnhancer class that uses various LLM providers
to enhance software metadata by filling missing fields and improving data quality.
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path
import hashlib
import base64

from saidata_gen.core.interfaces import RAGConfig
from saidata_gen.rag.engine import RAGEngine, EnhancementResult
from saidata_gen.rag.providers import LLMProvider, OpenAIProvider, AnthropicProvider, LocalModelProvider
from saidata_gen.rag.exceptions import RAGError, LLMProviderError, APIKeyError, RateLimitError


logger = logging.getLogger(__name__)


@dataclass
class AIEnhancementRequest:
    """Request for AI metadata enhancement."""
    software_name: str
    base_metadata: Dict[str, Any]
    missing_fields: List[str]
    provider: str = "openai"
    enhancement_types: List[str] = field(default_factory=lambda: ["description", "categorization", "field_completion"])


@dataclass
class AIEnhancementResult:
    """Result of AI metadata enhancement."""
    enhanced_metadata: Dict[str, Any]
    confidence_scores: Dict[str, float]
    sources_used: List[str]
    processing_time: float
    enhancement_metadata: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error_message: Optional[str] = None


@dataclass
class AIProviderConfig:
    """Configuration for AI providers."""
    provider: str
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 1000
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    rate_limit_requests_per_minute: int = 60
    rate_limit_tokens_per_minute: int = 90000
    enable_response_validation: bool = True
    api_key_env_var: Optional[str] = None


class APIKeyManager:
    """Secure API key management for AI providers."""
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize API key manager.
        
        Args:
            config_dir: Directory to store encrypted API keys. Defaults to ~/.saidata-gen
        """
        if config_dir is None:
            config_dir = os.path.expanduser("~/.saidata-gen")
        
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True, mode=0o700)  # Secure permissions
        self.keys_file = self.config_dir / "api_keys.json"
        
    def _get_encryption_key(self) -> bytes:
        """Get or create encryption key for API keys."""
        key_file = self.config_dir / ".key"
        
        if key_file.exists():
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            # Generate new key
            key = os.urandom(32)
            with open(key_file, 'wb') as f:
                f.write(key)
            key_file.chmod(0o600)  # Secure permissions
            return key
    
    def _encrypt_key(self, api_key: str) -> str:
        """Encrypt API key for secure storage."""
        try:
            from cryptography.fernet import Fernet
            key = base64.urlsafe_b64encode(self._get_encryption_key())
            fernet = Fernet(key)
            encrypted = fernet.encrypt(api_key.encode())
            return base64.b64encode(encrypted).decode()
        except ImportError:
            # Fallback to base64 encoding (less secure but doesn't require cryptography)
            logger.warning("cryptography library not available, using base64 encoding for API keys")
            return base64.b64encode(api_key.encode()).decode()
    
    def _decrypt_key(self, encrypted_key: str) -> str:
        """Decrypt API key from secure storage."""
        try:
            from cryptography.fernet import Fernet
            key = base64.urlsafe_b64encode(self._get_encryption_key())
            fernet = Fernet(key)
            encrypted_bytes = base64.b64decode(encrypted_key.encode())
            return fernet.decrypt(encrypted_bytes).decode()
        except ImportError:
            # Fallback to base64 decoding
            return base64.b64decode(encrypted_key.encode()).decode()
    
    def store_api_key(self, provider: str, api_key: str) -> None:
        """
        Store API key securely.
        
        Args:
            provider: AI provider name
            api_key: API key to store
        """
        keys_data = {}
        if self.keys_file.exists():
            with open(self.keys_file, 'r') as f:
                keys_data = json.load(f)
        
        keys_data[provider] = self._encrypt_key(api_key)
        
        with open(self.keys_file, 'w') as f:
            json.dump(keys_data, f)
        self.keys_file.chmod(0o600)  # Secure permissions
        
        logger.info(f"API key stored securely for provider: {provider}")
    
    def get_api_key(self, provider: str, env_var: Optional[str] = None) -> Optional[str]:
        """
        Get API key for provider.
        
        Args:
            provider: AI provider name
            env_var: Environment variable name to check first
            
        Returns:
            API key if found, None otherwise
        """
        # First check environment variable
        if env_var:
            env_key = os.getenv(env_var)
            if env_key:
                return env_key
        
        # Check default environment variables
        default_env_vars = {
            'openai': 'OPENAI_API_KEY',
            'anthropic': 'ANTHROPIC_API_KEY',
            'local': None
        }
        
        default_env_var = default_env_vars.get(provider)
        if default_env_var:
            env_key = os.getenv(default_env_var)
            if env_key:
                return env_key
        
        # Check stored keys
        if self.keys_file.exists():
            try:
                with open(self.keys_file, 'r') as f:
                    keys_data = json.load(f)
                
                if provider in keys_data:
                    return self._decrypt_key(keys_data[provider])
            except Exception as e:
                logger.error(f"Error reading stored API key for {provider}: {e}")
        
        return None
    
    def remove_api_key(self, provider: str) -> bool:
        """
        Remove stored API key for provider.
        
        Args:
            provider: AI provider name
            
        Returns:
            True if key was removed, False if not found
        """
        if not self.keys_file.exists():
            return False
        
        try:
            with open(self.keys_file, 'r') as f:
                keys_data = json.load(f)
            
            if provider in keys_data:
                del keys_data[provider]
                
                with open(self.keys_file, 'w') as f:
                    json.dump(keys_data, f)
                self.keys_file.chmod(0o600)
                
                logger.info(f"API key removed for provider: {provider}")
                return True
        except Exception as e:
            logger.error(f"Error removing API key for {provider}: {e}")
        
        return False
    
    def list_stored_providers(self) -> List[str]:
        """
        List providers with stored API keys.
        
        Returns:
            List of provider names
        """
        if not self.keys_file.exists():
            return []
        
        try:
            with open(self.keys_file, 'r') as f:
                keys_data = json.load(f)
            return list(keys_data.keys())
        except Exception as e:
            logger.error(f"Error listing stored providers: {e}")
            return []


class RateLimiter:
    """Rate limiter for AI API calls."""
    
    def __init__(self, requests_per_minute: int = 60, tokens_per_minute: int = 90000):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum requests per minute
            tokens_per_minute: Maximum tokens per minute
        """
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.request_times = []
        self.token_usage = []
        
    def can_make_request(self, estimated_tokens: int = 1000) -> Tuple[bool, Optional[float]]:
        """
        Check if a request can be made within rate limits.
        
        Args:
            estimated_tokens: Estimated tokens for the request
            
        Returns:
            Tuple of (can_make_request, wait_time_seconds)
        """
        now = time.time()
        minute_ago = now - 60
        
        # Clean old entries
        self.request_times = [t for t in self.request_times if t > minute_ago]
        self.token_usage = [(t, tokens) for t, tokens in self.token_usage if t > minute_ago]
        
        # Check request rate limit
        if len(self.request_times) >= self.requests_per_minute:
            wait_time = 60 - (now - self.request_times[0])
            return False, wait_time
        
        # Check token rate limit
        current_tokens = sum(tokens for _, tokens in self.token_usage)
        if current_tokens + estimated_tokens > self.tokens_per_minute:
            # Find when enough tokens will be available
            needed_tokens = current_tokens + estimated_tokens - self.tokens_per_minute
            for t, tokens in sorted(self.token_usage):
                needed_tokens -= tokens
                if needed_tokens <= 0:
                    wait_time = 60 - (now - t)
                    return False, wait_time
            
            # If we can't find enough tokens, wait for the oldest entry
            if self.token_usage:
                wait_time = 60 - (now - self.token_usage[0][0])
                return False, wait_time
        
        return True, None
    
    def record_request(self, tokens_used: int = 1000) -> None:
        """
        Record a successful request.
        
        Args:
            tokens_used: Number of tokens used in the request
        """
        now = time.time()
        self.request_times.append(now)
        self.token_usage.append((now, tokens_used))


class ResponseValidator:
    """Validator for AI responses to ensure data quality."""
    
    @staticmethod
    def validate_json_response(response: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Validate JSON response from AI.
        
        Args:
            response: Response string from AI
            
        Returns:
            Tuple of (is_valid, parsed_data, error_message)
        """
        try:
            # Try to parse as JSON
            data = json.loads(response.strip())
            return True, data, None
        except json.JSONDecodeError as e:
            return False, None, f"Invalid JSON: {e}"
    
    @staticmethod
    def validate_description(description: str) -> Tuple[bool, Optional[str]]:
        """
        Validate AI-generated description.
        
        Args:
            description: Description to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not description or not description.strip():
            return False, "Description is empty"
        
        if len(description) < 10:
            return False, "Description is too short"
        
        if len(description) > 1000:
            return False, "Description is too long"
        
        # Check for common AI artifacts
        artifacts = [
            "I cannot", "I don't know", "As an AI", "I'm sorry",
            "I apologize", "I'm not able", "I can't provide"
        ]
        
        for artifact in artifacts:
            if artifact.lower() in description.lower():
                return False, f"Description contains AI artifact: {artifact}"
        
        return True, None
    
    @staticmethod
    def validate_category(category_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate AI-generated category data.
        
        Args:
            category_data: Category data to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(category_data, dict):
            return False, "Category data must be a dictionary"
        
        if 'default' not in category_data:
            return False, "Category data must have 'default' field"
        
        default_category = category_data['default']
        if not isinstance(default_category, str) or not default_category.strip():
            return False, "Default category must be a non-empty string"
        
        # Validate against known categories
        valid_categories = {
            'development', 'system', 'network', 'security', 'multimedia',
            'productivity', 'database', 'web', 'mobile', 'desktop',
            'server', 'cli', 'library', 'framework', 'tool', 'utility'
        }
        
        if default_category.lower() not in valid_categories:
            logger.warning(f"Unknown category: {default_category}")
        
        # Validate confidence if present
        if 'confidence' in category_data:
            confidence = category_data['confidence']
            if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                return False, "Confidence must be a number between 0 and 1"
        
        return True, None
    
    @staticmethod
    def validate_field_completion(field_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate AI-generated field completion data.
        
        Args:
            field_data: Field completion data to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(field_data, dict):
            return False, "Field data must be a dictionary"
        
        # Validate URLs if present
        url_fields = ['website', 'source', 'documentation', 'support', 'download', 'changelog', 'icon']
        for field in url_fields:
            if field in field_data:
                url = field_data[field]
                if url and not isinstance(url, str):
                    return False, f"URL field '{field}' must be a string"
                if url and not (url.startswith('http://') or url.startswith('https://')):
                    return False, f"URL field '{field}' must be a valid HTTP/HTTPS URL"
        
        # Validate platforms if present
        if 'platforms' in field_data:
            platforms = field_data['platforms']
            if not isinstance(platforms, list):
                return False, "Platforms must be a list"
            
            valid_platforms = {'linux', 'windows', 'macos', 'freebsd', 'openbsd', 'netbsd', 'solaris'}
            for platform in platforms:
                if not isinstance(platform, str) or platform.lower() not in valid_platforms:
                    logger.warning(f"Unknown platform: {platform}")
        
        return True, None


class AIMetadataEnhancer:
    """
    AI Metadata Enhancer for filling missing fields using AI.
    
    This class provides capabilities for enhancing software metadata using
    various LLM providers including OpenAI, Anthropic, and local models.
    """
    
    # Default configurations for different providers
    DEFAULT_CONFIGS = {
        "openai": AIProviderConfig(
            provider="openai",
            model="gpt-3.5-turbo",
            temperature=0.1,
            max_tokens=1000
        ),
        "anthropic": AIProviderConfig(
            provider="anthropic", 
            model="claude-3-haiku-20240307",
            temperature=0.1,
            max_tokens=1000
        ),
        "local": AIProviderConfig(
            provider="local",
            model="llama2",
            base_url="http://localhost:11434",
            temperature=0.1,
            max_tokens=1000
        )
    }
    
    # Fields that are commonly missing and can be enhanced by AI
    ENHANCEABLE_FIELDS = {
        "description": "Software description",
        "license": "Software license",
        "urls.website": "Official website URL",
        "urls.source": "Source code repository URL", 
        "urls.documentation": "Documentation URL",
        "urls.support": "Support/help URL",
        "urls.download": "Download URL",
        "urls.changelog": "Changelog URL",
        "urls.icon": "Icon/logo URL",
        "category.default": "Primary software category",
        "category.sub": "Software subcategory",
        "category.tags": "Software tags",
        "platforms": "Supported platforms",
        "language": "Primary programming language"
    }
    
    def __init__(self, provider: str = "openai", config: Optional[AIProviderConfig] = None):
        """
        Initialize AI metadata enhancer.
        
        Args:
            provider: AI provider to use (openai, anthropic, local)
            config: Custom provider configuration
        """
        self.provider = provider
        self.config = config or self.DEFAULT_CONFIGS.get(provider, self.DEFAULT_CONFIGS["openai"])
        self._rag_engine = None
        self._provider_instance = None
        
        # Initialize management components
        self.api_key_manager = APIKeyManager()
        self.rate_limiter = RateLimiter(
            requests_per_minute=self.config.rate_limit_requests_per_minute,
            tokens_per_minute=self.config.rate_limit_tokens_per_minute
        )
        self.response_validator = ResponseValidator()
        
        # Get API key from manager if not provided in config
        if not self.config.api_key:
            self.config.api_key = self.api_key_manager.get_api_key(
                provider, self.config.api_key_env_var
            )
        
        logger.info(f"Initialized AIMetadataEnhancer with provider: {provider}")
    
    def _get_rag_engine(self) -> RAGEngine:
        """Get RAG engine instance with lazy initialization."""
        if self._rag_engine is None:
            rag_config = RAGConfig(
                provider=self.config.provider,
                model=self.config.model,
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            self._rag_engine = RAGEngine(rag_config)
        return self._rag_engine
    
    def _get_provider_instance(self) -> LLMProvider:
        """Get LLM provider instance with lazy initialization."""
        if self._provider_instance is None:
            if self.config.provider == "openai":
                self._provider_instance = OpenAIProvider(
                    model=self.config.model,
                    api_key=self.config.api_key,
                    base_url=self.config.base_url
                )
            elif self.config.provider == "anthropic":
                self._provider_instance = AnthropicProvider(
                    model=self.config.model,
                    api_key=self.config.api_key,
                    base_url=self.config.base_url
                )
            elif self.config.provider == "local":
                self._provider_instance = LocalModelProvider(
                    model=self.config.model,
                    api_key=self.config.api_key,
                    base_url=self.config.base_url or "http://localhost:11434"
                )
            else:
                raise ValueError(f"Unsupported AI provider: {self.config.provider}")
        
        return self._provider_instance
    
    def get_missing_fields(self, metadata: Dict[str, Any]) -> List[str]:
        """
        Identify fields that are missing or have null values.
        
        Args:
            metadata: Metadata to analyze
            
        Returns:
            List of missing field paths
        """
        missing_fields = []
        
        for field_path, description in self.ENHANCEABLE_FIELDS.items():
            if self._is_field_missing(metadata, field_path):
                missing_fields.append(field_path)
        
        logger.debug(f"Identified {len(missing_fields)} missing fields: {missing_fields}")
        return missing_fields
    
    def _is_field_missing(self, metadata: Dict[str, Any], field_path: str) -> bool:
        """
        Check if a field is missing or empty.
        
        Args:
            metadata: Metadata dictionary
            field_path: Dot-separated field path (e.g., "urls.website")
            
        Returns:
            True if field is missing or empty, False otherwise
        """
        try:
            parts = field_path.split('.')
            current = metadata
            
            for part in parts:
                if not isinstance(current, dict) or part not in current:
                    return True
                current = current[part]
            
            # Check if value is empty, None, or whitespace-only string
            if current is None:
                return True
            if isinstance(current, str) and not current.strip():
                return True
            if isinstance(current, list) and not current:
                return True
            if isinstance(current, dict) and not current:
                return True
            
            return False
            
        except (KeyError, TypeError, AttributeError):
            return True
    
    def _set_field_value(self, metadata: Dict[str, Any], field_path: str, value: Any) -> None:
        """
        Set a field value using dot notation.
        
        Args:
            metadata: Metadata dictionary to modify
            field_path: Dot-separated field path
            value: Value to set
        """
        parts = field_path.split('.')
        current = metadata
        
        # Navigate to the parent of the target field
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        # Set the final value
        current[parts[-1]] = value
    
    def enhance_metadata(
        self,
        software_name: str,
        base_metadata: Dict[str, Any],
        enhancement_types: Optional[List[str]] = None
    ) -> AIEnhancementResult:
        """
        Enhance metadata using AI for missing fields.
        
        Args:
            software_name: Name of the software
            base_metadata: Base metadata from repositories
            enhancement_types: Types of enhancement to apply
            
        Returns:
            AIEnhancementResult with enhanced metadata
        """
        start_time = time.time()
        
        if enhancement_types is None:
            enhancement_types = ["description", "categorization", "field_completion"]
        
        # Check if AI provider is available
        if not self.is_available():
            logger.warning(f"AI provider {self.provider} is not available")
            return AIEnhancementResult(
                enhanced_metadata=base_metadata.copy(),
                confidence_scores={},
                sources_used=[],
                processing_time=time.time() - start_time,
                success=False,
                error_message=f"AI provider {self.provider} is not available"
            )
        
        # Perform enhancement with retry logic
        return self._enhance_with_retry(
            software_name=software_name,
            base_metadata=base_metadata,
            enhancement_types=enhancement_types,
            start_time=start_time
        )
    
    def _enhance_with_retry(
        self,
        software_name: str,
        base_metadata: Dict[str, Any],
        enhancement_types: List[str],
        start_time: float
    ) -> AIEnhancementResult:
        """
        Enhance metadata with retry logic and rate limiting.
        
        Args:
            software_name: Name of the software
            base_metadata: Base metadata from repositories
            enhancement_types: Types of enhancement to apply
            start_time: Start time for processing time calculation
            
        Returns:
            AIEnhancementResult with enhanced metadata
        """
        last_error = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                # Check rate limits before making request
                estimated_tokens = self._estimate_tokens(base_metadata, enhancement_types)
                can_proceed, wait_time = self.rate_limiter.can_make_request(estimated_tokens)
                
                if not can_proceed and wait_time:
                    if attempt < self.config.max_retries:
                        logger.info(f"Rate limit reached, waiting {wait_time:.1f}s before retry")
                        time.sleep(wait_time)
                        continue
                    else:
                        return AIEnhancementResult(
                            enhanced_metadata=base_metadata.copy(),
                            confidence_scores={},
                            sources_used=[],
                            processing_time=time.time() - start_time,
                            success=False,
                            error_message="Rate limit exceeded and max retries reached"
                        )
                
                # Get RAG engine and perform enhancement
                rag_engine = self._get_rag_engine()
                
                # Perform RAG-based enhancement
                enhancement_result = rag_engine.enhance_metadata(
                    software_name=software_name,
                    metadata=base_metadata,
                    enhancement_types=enhancement_types
                )
                
                # Record successful request
                actual_tokens = self._calculate_actual_tokens(enhancement_result)
                self.rate_limiter.record_request(actual_tokens)
                
                # Validate response if enabled
                if self.config.enable_response_validation:
                    validation_result = self._validate_enhancement_result(enhancement_result)
                    if not validation_result.success:
                        logger.warning(f"Response validation failed: {validation_result.error_message}")
                        # Continue with unvalidated result but log warning
                
                processing_time = time.time() - start_time
                
                logger.info(
                    f"Successfully enhanced metadata for {software_name} "
                    f"in {processing_time:.2f}s using {self.provider} (attempt {attempt + 1})"
                )
                
                return AIEnhancementResult(
                    enhanced_metadata=enhancement_result.enhanced_data,
                    confidence_scores=enhancement_result.confidence_scores,
                    sources_used=enhancement_result.sources,
                    processing_time=processing_time,
                    enhancement_metadata=enhancement_result.metadata,
                    success=True
                )
                
            except RateLimitError as e:
                last_error = e
                if attempt < self.config.max_retries:
                    wait_time = self.config.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(f"Rate limit error, waiting {wait_time:.1f}s before retry (attempt {attempt + 1})")
                    time.sleep(wait_time)
                    continue
                else:
                    break
                    
            except RAGError as e:
                last_error = e
                if attempt < self.config.max_retries:
                    wait_time = self.config.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(f"RAG error, retrying in {wait_time:.1f}s (attempt {attempt + 1}): {e}")
                    time.sleep(wait_time)
                    continue
                else:
                    break
                    
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error during AI enhancement (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries:
                    wait_time = self.config.retry_delay * (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                else:
                    break
        
        # All retries failed
        processing_time = time.time() - start_time
        error_message = f"Enhancement failed after {self.config.max_retries + 1} attempts: {last_error}"
        
        logger.error(f"AI enhancement failed for {software_name}: {error_message}")
        
        return AIEnhancementResult(
            enhanced_metadata=base_metadata.copy(),
            confidence_scores={},
            sources_used=[],
            processing_time=processing_time,
            success=False,
            error_message=error_message
        )
    
    def _estimate_tokens(self, metadata: Dict[str, Any], enhancement_types: List[str]) -> int:
        """
        Estimate tokens needed for enhancement request.
        
        Args:
            metadata: Base metadata
            enhancement_types: Types of enhancement
            
        Returns:
            Estimated token count
        """
        # Rough estimation based on metadata size and enhancement types
        base_tokens = len(json.dumps(metadata)) // 4  # Rough token estimation
        enhancement_tokens = len(enhancement_types) * 200  # Tokens per enhancement type
        response_tokens = 500  # Estimated response tokens
        
        return base_tokens + enhancement_tokens + response_tokens
    
    def _calculate_actual_tokens(self, result: EnhancementResult) -> int:
        """
        Calculate actual tokens used from enhancement result.
        
        Args:
            result: Enhancement result
            
        Returns:
            Actual token count
        """
        # This would ideally come from the LLM provider response
        # For now, estimate based on result size
        return len(json.dumps(result.enhanced_data)) // 4 + 500
    
    def _validate_enhancement_result(self, result: EnhancementResult) -> AIEnhancementResult:
        """
        Validate enhancement result for data quality.
        
        Args:
            result: Enhancement result to validate
            
        Returns:
            Validation result
        """
        try:
            enhanced_data = result.enhanced_data
            
            # Validate description if present
            if 'description' in enhanced_data:
                is_valid, error = self.response_validator.validate_description(enhanced_data['description'])
                if not is_valid:
                    return AIEnhancementResult(
                        enhanced_metadata={},
                        confidence_scores={},
                        sources_used=[],
                        processing_time=0,
                        success=False,
                        error_message=f"Description validation failed: {error}"
                    )
            
            # Validate category if present
            if 'category' in enhanced_data:
                is_valid, error = self.response_validator.validate_category(enhanced_data['category'])
                if not is_valid:
                    return AIEnhancementResult(
                        enhanced_metadata={},
                        confidence_scores={},
                        sources_used=[],
                        processing_time=0,
                        success=False,
                        error_message=f"Category validation failed: {error}"
                    )
            
            # Validate field completion
            is_valid, error = self.response_validator.validate_field_completion(enhanced_data)
            if not is_valid:
                return AIEnhancementResult(
                    enhanced_metadata={},
                    confidence_scores={},
                    sources_used=[],
                    processing_time=0,
                    success=False,
                    error_message=f"Field validation failed: {error}"
                )
            
            return AIEnhancementResult(
                enhanced_metadata=enhanced_data,
                confidence_scores={},
                sources_used=[],
                processing_time=0,
                success=True
            )
            
        except Exception as e:
            return AIEnhancementResult(
                enhanced_metadata={},
                confidence_scores={},
                sources_used=[],
                processing_time=0,
                success=False,
                error_message=f"Validation error: {e}"
            )
    
    def enhance_specific_fields(
        self,
        software_name: str,
        base_metadata: Dict[str, Any],
        target_fields: List[str]
    ) -> AIEnhancementResult:
        """
        Enhance specific metadata fields using AI.
        
        Args:
            software_name: Name of the software
            base_metadata: Base metadata from repositories
            target_fields: Specific fields to enhance
            
        Returns:
            AIEnhancementResult with enhanced metadata
        """
        start_time = time.time()
        
        try:
            # Filter target fields to only enhanceable ones
            valid_fields = [f for f in target_fields if f in self.ENHANCEABLE_FIELDS]
            if not valid_fields:
                logger.warning(f"No valid enhanceable fields specified: {target_fields}")
                return AIEnhancementResult(
                    enhanced_metadata=base_metadata.copy(),
                    confidence_scores={},
                    sources_used=[],
                    processing_time=time.time() - start_time,
                    success=False,
                    error_message="No valid enhanceable fields specified"
                )
            
            # Check which fields are actually missing
            missing_fields = [f for f in valid_fields if self._is_field_missing(base_metadata, f)]
            if not missing_fields:
                logger.info(f"All specified fields already have values: {target_fields}")
                return AIEnhancementResult(
                    enhanced_metadata=base_metadata.copy(),
                    confidence_scores={},
                    sources_used=[],
                    processing_time=time.time() - start_time,
                    success=True
                )
            
            # Use field completion enhancement type
            return self.enhance_metadata(
                software_name=software_name,
                base_metadata=base_metadata,
                enhancement_types=["field_completion"]
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error enhancing specific fields for {software_name}: {e}")
            
            return AIEnhancementResult(
                enhanced_metadata=base_metadata.copy(),
                confidence_scores={},
                sources_used=[],
                processing_time=processing_time,
                success=False,
                error_message=str(e)
            )
    
    def is_available(self) -> bool:
        """
        Check if the AI provider is available.
        
        Returns:
            True if AI provider is available, False otherwise
        """
        try:
            provider = self._get_provider_instance()
            return provider.is_available()
        except Exception as e:
            logger.debug(f"AI provider {self.provider} not available: {e}")
            return False
    
    def get_supported_providers(self) -> List[str]:
        """
        Get list of supported AI providers.
        
        Returns:
            List of supported provider names
        """
        return list(self.DEFAULT_CONFIGS.keys())
    
    def validate_configuration(self) -> Tuple[bool, Optional[str]]:
        """
        Validate the current AI provider configuration.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check if provider is supported
            if self.provider not in self.DEFAULT_CONFIGS:
                return False, f"Unsupported provider: {self.provider}"
            
            # Check if required configuration is present
            if self.config.provider in ["openai", "anthropic"] and not self.config.api_key:
                return False, f"API key required for {self.config.provider}"
            
            # Try to create provider instance
            provider = self._get_provider_instance()
            
            # Check if provider is available
            if not provider.is_available():
                return False, f"Provider {self.provider} is not available"
            
            return True, None
            
        except APIKeyError as e:
            return False, f"API key error: {e}"
        except Exception as e:
            return False, f"Configuration error: {e}"
    
    def get_enhancement_statistics(self, results: List[AIEnhancementResult]) -> Dict[str, Any]:
        """
        Generate statistics from multiple enhancement results.
        
        Args:
            results: List of enhancement results
            
        Returns:
            Dictionary with enhancement statistics
        """
        if not results:
            return {}
        
        total_results = len(results)
        successful_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]
        
        # Calculate timing statistics
        processing_times = [r.processing_time for r in results]
        avg_processing_time = sum(processing_times) / len(processing_times)
        
        # Calculate confidence statistics
        all_confidence_scores = []
        for result in successful_results:
            all_confidence_scores.extend(result.confidence_scores.values())
        
        avg_confidence = sum(all_confidence_scores) / len(all_confidence_scores) if all_confidence_scores else 0.0
        
        # Count enhancement types used
        sources_used = {}
        for result in successful_results:
            for source in result.sources_used:
                sources_used[source] = sources_used.get(source, 0) + 1
        
        return {
            "total_requests": total_results,
            "successful_requests": len(successful_results),
            "failed_requests": len(failed_results),
            "success_rate": len(successful_results) / total_results,
            "average_processing_time": avg_processing_time,
            "average_confidence_score": avg_confidence,
            "enhancement_types_used": sources_used,
            "provider": self.provider,
            "model": self.config.model
        }
    
    def create_enhancement_request(
        self,
        software_name: str,
        base_metadata: Dict[str, Any],
        provider: Optional[str] = None,
        enhancement_types: Optional[List[str]] = None
    ) -> AIEnhancementRequest:
        """
        Create an AI enhancement request.
        
        Args:
            software_name: Name of the software
            base_metadata: Base metadata from repositories
            provider: AI provider to use (defaults to current provider)
            enhancement_types: Types of enhancement to apply
            
        Returns:
            AIEnhancementRequest object
        """
        missing_fields = self.get_missing_fields(base_metadata)
        
        return AIEnhancementRequest(
            software_name=software_name,
            base_metadata=base_metadata,
            missing_fields=missing_fields,
            provider=provider or self.provider,
            enhancement_types=enhancement_types or ["description", "categorization", "field_completion"]
        )
    
    def store_api_key(self, api_key: str) -> None:
        """
        Store API key securely for the current provider.
        
        Args:
            api_key: API key to store
        """
        self.api_key_manager.store_api_key(self.provider, api_key)
        self.config.api_key = api_key
    
    def remove_api_key(self) -> bool:
        """
        Remove stored API key for the current provider.
        
        Returns:
            True if key was removed, False if not found
        """
        result = self.api_key_manager.remove_api_key(self.provider)
        if result:
            self.config.api_key = None
        return result
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        Get current rate limit status.
        
        Returns:
            Dictionary with rate limit information
        """
        now = time.time()
        minute_ago = now - 60
        
        # Count recent requests and tokens
        recent_requests = len([t for t in self.rate_limiter.request_times if t > minute_ago])
        recent_tokens = sum(tokens for t, tokens in self.rate_limiter.token_usage if t > minute_ago)
        
        return {
            "requests_per_minute_limit": self.config.rate_limit_requests_per_minute,
            "tokens_per_minute_limit": self.config.rate_limit_tokens_per_minute,
            "recent_requests": recent_requests,
            "recent_tokens": recent_tokens,
            "requests_remaining": max(0, self.config.rate_limit_requests_per_minute - recent_requests),
            "tokens_remaining": max(0, self.config.rate_limit_tokens_per_minute - recent_tokens)
        }
    
    def update_rate_limits(self, requests_per_minute: int, tokens_per_minute: int) -> None:
        """
        Update rate limits for the current provider.
        
        Args:
            requests_per_minute: New requests per minute limit
            tokens_per_minute: New tokens per minute limit
        """
        self.config.rate_limit_requests_per_minute = requests_per_minute
        self.config.rate_limit_tokens_per_minute = tokens_per_minute
        
        # Update rate limiter
        self.rate_limiter = RateLimiter(requests_per_minute, tokens_per_minute)
        
        logger.info(f"Updated rate limits: {requests_per_minute} req/min, {tokens_per_minute} tokens/min")
    
    def get_provider_config(self) -> Dict[str, Any]:
        """
        Get current provider configuration (without sensitive data).
        
        Returns:
            Dictionary with provider configuration
        """
        config_dict = {
            "provider": self.config.provider,
            "model": self.config.model,
            "base_url": self.config.base_url,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "timeout": self.config.timeout,
            "max_retries": self.config.max_retries,
            "retry_delay": self.config.retry_delay,
            "rate_limit_requests_per_minute": self.config.rate_limit_requests_per_minute,
            "rate_limit_tokens_per_minute": self.config.rate_limit_tokens_per_minute,
            "enable_response_validation": self.config.enable_response_validation,
            "has_api_key": bool(self.config.api_key)
        }
        
        return config_dict
    
    @classmethod
    def create_provider_config(
        cls,
        provider: str,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs
    ) -> AIProviderConfig:
        """
        Create a provider configuration with defaults.
        
        Args:
            provider: AI provider name
            model: Model name (uses default if not specified)
            api_key: API key
            **kwargs: Additional configuration options
            
        Returns:
            AIProviderConfig object
        """
        # Start with default config
        default_config = cls.DEFAULT_CONFIGS.get(provider)
        if not default_config:
            raise ValueError(f"Unsupported provider: {provider}")
        
        # Override with provided values
        config_dict = {
            "provider": provider,
            "model": model or default_config.model,
            "api_key": api_key,
            "base_url": kwargs.get("base_url", default_config.base_url),
            "temperature": kwargs.get("temperature", default_config.temperature),
            "max_tokens": kwargs.get("max_tokens", default_config.max_tokens),
            "timeout": kwargs.get("timeout", 30),
            "max_retries": kwargs.get("max_retries", 3),
            "retry_delay": kwargs.get("retry_delay", 1.0),
            "rate_limit_requests_per_minute": kwargs.get("rate_limit_requests_per_minute", 60),
            "rate_limit_tokens_per_minute": kwargs.get("rate_limit_tokens_per_minute", 90000),
            "enable_response_validation": kwargs.get("enable_response_validation", True),
            "api_key_env_var": kwargs.get("api_key_env_var")
        }
        
        return AIProviderConfig(**config_dict)