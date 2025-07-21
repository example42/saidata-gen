"""
RAG Engine for AI-enhanced metadata generation.
"""

import json
import re
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

from saidata_gen.core.interfaces import RAGConfig, SaidataMetadata, CategoryConfig
from .providers import LLMProvider, OpenAIProvider, AnthropicProvider, LocalModelProvider
from .exceptions import RAGError, PromptError, LLMProviderError


@dataclass
class EnhancementResult:
    """Result of metadata enhancement."""
    enhanced_data: Dict[str, Any]
    confidence_scores: Dict[str, float]
    sources: List[str]
    metadata: Dict[str, Any]


@dataclass
class CategoryInfo:
    """Information about software category."""
    default: str
    sub: Optional[str] = None
    tags: Optional[List[str]] = None
    confidence: float = 0.0


class PromptTemplate:
    """Template for generating prompts."""
    
    def __init__(self, template: str):
        """
        Initialize prompt template.
        
        Args:
            template: Template string with {variable} placeholders
        """
        self.template = template
        self._variables = self._extract_variables(template)
    
    def _extract_variables(self, template: str) -> List[str]:
        """Extract variable names from template."""
        return re.findall(r'\{(\w+)\}', template)
    
    def render(self, **kwargs) -> str:
        """
        Render template with provided variables.
        
        Args:
            **kwargs: Variables to substitute in template
            
        Returns:
            Rendered template string
            
        Raises:
            PromptError: If required variables are missing
        """
        missing_vars = set(self._variables) - set(kwargs.keys())
        if missing_vars:
            raise PromptError(f"Missing template variables: {missing_vars}")
        
        try:
            return self.template.format(**kwargs)
        except KeyError as e:
            raise PromptError(f"Template rendering failed: {e}")
    
    @property
    def variables(self) -> List[str]:
        """Get list of template variables."""
        return self._variables.copy()


class RAGEngine:
    """
    RAG Engine for AI-enhanced metadata generation.
    
    Provides capabilities for enhancing software metadata using Large Language Models
    including description enhancement, categorization, and missing field completion.
    """
    
    # Prompt templates for different enhancement tasks
    DESCRIPTION_TEMPLATE = PromptTemplate("""
You are a software documentation expert. Given the following information about a software package, 
write a clear, concise, and informative description (2-3 sentences maximum).

Software Name: {software_name}
Package Manager: {provider}
Version: {version}
Existing Description: {existing_description}
Additional Context: {context}

Focus on:
- What the software does (primary purpose)
- Key features or capabilities
- Target audience or use cases

Provide only the description text, no additional formatting or explanations.
""")
    
    CATEGORIZATION_TEMPLATE = PromptTemplate("""
You are a software categorization expert. Analyze the following software and provide categorization information.

Software Name: {software_name}
Description: {description}
Package Manager: {provider}
Additional Context: {context}

Provide your response as a JSON object with the following structure:
{{
    "default": "primary_category",
    "sub": "subcategory_if_applicable",
    "tags": ["tag1", "tag2", "tag3"],
    "confidence": 0.85
}}

Common categories include: development, system, network, security, multimedia, productivity, 
database, web, mobile, desktop, server, cli, library, framework, tool, utility.

Provide only the JSON response, no additional text.
""")
    
    FIELD_COMPLETION_TEMPLATE = PromptTemplate("""
You are a software metadata expert. Given the following software information, 
help complete missing fields with accurate information.

Software Name: {software_name}
Current Metadata: {current_metadata}
Missing Fields: {missing_fields}
Additional Context: {context}

For each missing field, provide the most accurate information you can determine.
If you cannot determine accurate information for a field, use null.

Provide your response as a JSON object with only the missing fields:
{{
    "field_name": "value_or_null",
    "another_field": "value_or_null"
}}

Common fields include: license, homepage, source_url, documentation_url, 
support_url, download_url, changelog_url, icon_url, platforms, language.

Provide only the JSON response, no additional text.
""")
    
    def __init__(self, config: RAGConfig):
        """
        Initialize RAG engine.
        
        Args:
            config: RAG configuration
        """
        self.config = config
        self._provider = None
        
    def _get_provider(self) -> LLMProvider:
        """Get LLM provider instance."""
        if self._provider is None:
            if self.config.provider == "openai":
                self._provider = OpenAIProvider(
                    model=self.config.model,
                    api_key=self.config.api_key,
                    base_url=self.config.base_url
                )
            elif self.config.provider == "anthropic":
                self._provider = AnthropicProvider(
                    model=self.config.model,
                    api_key=self.config.api_key,
                    base_url=self.config.base_url
                )
            elif self.config.provider == "local":
                self._provider = LocalModelProvider(
                    model=self.config.model,
                    api_key=self.config.api_key,
                    base_url=self.config.base_url or "http://localhost:11434"
                )
            else:
                raise RAGError(f"Unsupported RAG provider: {self.config.provider}")
        
        return self._provider
    
    def enhance_description(self, software_name: str, basic_info: Dict[str, Any]) -> str:
        """
        Enhance software description using RAG.
        
        Args:
            software_name: Name of the software
            basic_info: Basic information about the software
            
        Returns:
            Enhanced description string
            
        Raises:
            RAGError: If enhancement fails
        """
        try:
            provider = self._get_provider()
            
            # Prepare context information
            context_parts = []
            if basic_info.get('packages'):
                context_parts.append(f"Available in package managers: {', '.join(basic_info['packages'].keys())}")
            if basic_info.get('license'):
                context_parts.append(f"License: {basic_info['license']}")
            if basic_info.get('platforms'):
                context_parts.append(f"Platforms: {', '.join(basic_info['platforms'])}")
            
            context = "; ".join(context_parts) if context_parts else "No additional context available"
            
            # Render prompt
            prompt = self.DESCRIPTION_TEMPLATE.render(
                software_name=software_name,
                provider=basic_info.get('provider', 'unknown'),
                version=basic_info.get('version', 'unknown'),
                existing_description=basic_info.get('description', 'No existing description'),
                context=context
            )
            
            # Generate enhanced description
            response = provider.generate(
                prompt=prompt,
                temperature=self.config.temperature,
                max_tokens=min(self.config.max_tokens, 200)  # Descriptions should be concise
            )
            
            return response.content.strip()
            
        except Exception as e:
            raise RAGError(f"Failed to enhance description for {software_name}: {e}")
    
    def categorize_software(self, software_info: Dict[str, Any]) -> CategoryInfo:
        """
        Categorize software using LLM analysis.
        
        Args:
            software_info: Information about the software
            
        Returns:
            CategoryInfo with categorization details
            
        Raises:
            RAGError: If categorization fails
        """
        try:
            provider = self._get_provider()
            
            # Prepare context information
            context_parts = []
            if software_info.get('packages'):
                context_parts.append(f"Package managers: {', '.join(software_info['packages'].keys())}")
            if software_info.get('license'):
                context_parts.append(f"License: {software_info['license']}")
            if software_info.get('platforms'):
                context_parts.append(f"Platforms: {', '.join(software_info['platforms'])}")
            if software_info.get('urls', {}).get('website'):
                context_parts.append(f"Website: {software_info['urls']['website']}")
            
            context = "; ".join(context_parts) if context_parts else "No additional context available"
            
            # Render prompt
            prompt = self.CATEGORIZATION_TEMPLATE.render(
                software_name=software_info.get('name', 'unknown'),
                description=software_info.get('description', 'No description available'),
                provider=software_info.get('provider', 'unknown'),
                context=context
            )
            
            # Generate categorization
            response = provider.generate(
                prompt=prompt,
                temperature=self.config.temperature,
                max_tokens=min(self.config.max_tokens, 300)
            )
            
            # Parse JSON response
            try:
                result = json.loads(response.content.strip())
                return CategoryInfo(
                    default=result.get('default', 'utility'),
                    sub=result.get('sub'),
                    tags=result.get('tags', []),
                    confidence=result.get('confidence', 0.5)
                )
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return CategoryInfo(
                    default='utility',
                    confidence=0.1
                )
                
        except Exception as e:
            raise RAGError(f"Failed to categorize software: {e}")
    
    def fill_missing_fields(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fill missing metadata fields using AI inference.
        
        Args:
            metadata: Current metadata dictionary
            
        Returns:
            Dictionary with filled missing fields
            
        Raises:
            RAGError: If field completion fails
        """
        try:
            provider = self._get_provider()
            
            # Identify missing fields
            expected_fields = [
                'license', 'urls.website', 'urls.source', 'urls.documentation',
                'urls.support', 'urls.download', 'urls.changelog', 'urls.icon',
                'platforms', 'language'
            ]
            
            missing_fields = []
            for field in expected_fields:
                if '.' in field:
                    # Handle nested fields
                    parts = field.split('.')
                    current = metadata
                    for part in parts:
                        if not isinstance(current, dict) or part not in current or not current[part]:
                            missing_fields.append(field)
                            break
                        current = current[part]
                else:
                    if field not in metadata or not metadata[field]:
                        missing_fields.append(field)
            
            if not missing_fields:
                return {}
            
            # Prepare context
            context_parts = []
            if metadata.get('description'):
                context_parts.append(f"Description: {metadata['description']}")
            if metadata.get('packages'):
                context_parts.append(f"Package managers: {', '.join(metadata['packages'].keys())}")
            if metadata.get('category', {}).get('default'):
                context_parts.append(f"Category: {metadata['category']['default']}")
            
            context = "; ".join(context_parts) if context_parts else "No additional context available"
            
            # Render prompt
            prompt = self.FIELD_COMPLETION_TEMPLATE.render(
                software_name=metadata.get('name', 'unknown'),
                current_metadata=json.dumps(metadata, indent=2),
                missing_fields=', '.join(missing_fields),
                context=context
            )
            
            # Generate field completions
            response = provider.generate(
                prompt=prompt,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            
            # Parse JSON response
            try:
                result = json.loads(response.content.strip())
                # Filter out null values
                return {k: v for k, v in result.items() if v is not None}
            except json.JSONDecodeError:
                # Return empty dict if JSON parsing fails
                return {}
                
        except Exception as e:
            raise RAGError(f"Failed to fill missing fields: {e}")
    
    def generate_confidence_scores(self, metadata: Dict[str, Any]) -> Dict[str, float]:
        """
        Generate confidence scores for metadata fields.
        
        Args:
            metadata: Metadata dictionary
            
        Returns:
            Dictionary mapping field names to confidence scores (0.0-1.0)
        """
        confidence_scores = {}
        
        # Basic heuristics for confidence scoring
        # These could be enhanced with more sophisticated analysis
        
        # Description confidence
        if metadata.get('description'):
            desc_len = len(metadata['description'])
            if desc_len > 100:
                confidence_scores['description'] = 0.9
            elif desc_len > 50:
                confidence_scores['description'] = 0.7
            else:
                confidence_scores['description'] = 0.5
        
        # Package information confidence
        if metadata.get('packages'):
            num_packages = len(metadata['packages'])
            confidence_scores['packages'] = min(0.9, 0.5 + (num_packages * 0.1))
        
        # URL confidence
        urls = metadata.get('urls', {})
        if urls:
            url_count = sum(1 for v in urls.values() if v)
            confidence_scores['urls'] = min(0.9, 0.3 + (url_count * 0.1))
        
        # Category confidence
        if metadata.get('category', {}).get('default'):
            confidence_scores['category'] = 0.8
        
        # License confidence
        if metadata.get('license'):
            confidence_scores['license'] = 0.8
        
        # Platform confidence
        if metadata.get('platforms'):
            confidence_scores['platforms'] = 0.7
        
        return confidence_scores
    
    def enhance_metadata(self, software_name: str, metadata: Dict[str, Any], 
                        enhancement_types: Optional[List[str]] = None) -> EnhancementResult:
        """
        Enhance metadata using multiple RAG capabilities.
        
        Args:
            software_name: Name of the software
            metadata: Current metadata
            enhancement_types: List of enhancement types to apply
                             (description, categorization, field_completion)
            
        Returns:
            EnhancementResult with enhanced metadata
            
        Raises:
            RAGError: If enhancement fails
        """
        if enhancement_types is None:
            enhancement_types = ['description', 'categorization', 'field_completion']
        
        enhanced_data = metadata.copy()
        sources = []
        enhancement_metadata = {}
        
        try:
            # Enhance description
            if 'description' in enhancement_types:
                if not enhanced_data.get('description') or len(enhanced_data['description']) < 50:
                    enhanced_description = self.enhance_description(software_name, enhanced_data)
                    enhanced_data['description'] = enhanced_description
                    sources.append('rag_description')
                    enhancement_metadata['description_enhanced'] = True
            
            # Enhance categorization
            if 'categorization' in enhancement_types:
                if not enhanced_data.get('category', {}).get('default'):
                    category_info = self.categorize_software(enhanced_data)
                    enhanced_data['category'] = {
                        'default': category_info.default,
                        'sub': category_info.sub,
                        'tags': category_info.tags
                    }
                    sources.append('rag_categorization')
                    enhancement_metadata['category_enhanced'] = True
                    enhancement_metadata['category_confidence'] = category_info.confidence
            
            # Fill missing fields
            if 'field_completion' in enhancement_types:
                missing_fields = self.fill_missing_fields(enhanced_data)
                if missing_fields:
                    # Merge missing fields into enhanced data
                    for field, value in missing_fields.items():
                        if '.' in field:
                            # Handle nested fields
                            parts = field.split('.')
                            current = enhanced_data
                            for part in parts[:-1]:
                                if part not in current:
                                    current[part] = {}
                                current = current[part]
                            current[parts[-1]] = value
                        else:
                            enhanced_data[field] = value
                    
                    sources.append('rag_field_completion')
                    enhancement_metadata['fields_completed'] = list(missing_fields.keys())
            
            # Generate confidence scores
            confidence_scores = self.generate_confidence_scores(enhanced_data)
            
            return EnhancementResult(
                enhanced_data=enhanced_data,
                confidence_scores=confidence_scores,
                sources=sources,
                metadata=enhancement_metadata
            )
            
        except Exception as e:
            raise RAGError(f"Failed to enhance metadata for {software_name}: {e}")
    
    def is_available(self) -> bool:
        """
        Check if RAG engine is available.
        
        Returns:
            True if RAG engine is available, False otherwise
        """
        try:
            provider = self._get_provider()
            return provider.is_available()
        except Exception:
            return False