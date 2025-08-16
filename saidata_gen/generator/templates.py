"""
Template engine for saidata metadata generation.

This module provides a template engine for applying defaults and provider-specific
configurations to saidata metadata, with support for variable substitution and
conditional logic.
"""

import os
import re
import logging
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Set, Callable

import yaml

from saidata_gen.core.interfaces import SaidataMetadata, PackageInfo, RepositoryData
from saidata_gen.core.cache import CacheManager, CacheConfig, CacheBackend


logger = logging.getLogger(__name__)


class TemplateEngine:
    """
    Template engine for applying defaults and provider-specific configurations.
    
    This class provides methods for loading templates, applying variable substitution,
    conditional logic, and merging templates with metadata.
    
    Features:
    - Variable substitution with ${var} and ${var | default} syntax
    - Conditional logic with $if:, $elif:, $else, $endif directives
    - Template inclusion with $include: directive
    - Provider-specific overrides with $provider_override: directive
    - Platform-specific sections with $platform: directive
    - Function calls with $function: directive
    """
    
    # Special template directives
    CONDITION_IF = "$if:"
    CONDITION_ELIF = "$elif:"
    CONDITION_ELSE = "$else"
    CONDITION_ENDIF = "$endif"
    INCLUDE_TEMPLATE = "$include:"
    PROVIDER_OVERRIDE = "$provider_override:"
    PLATFORM_SPECIFIC = "$platform:"
    FUNCTION_CALL = "$function:"
    LOOP_FOR = "$for:"
    LOOP_ENDFOR = "$endfor"
    
    def __init__(self, templates_dir: Optional[str] = None, cache_manager: Optional[CacheManager] = None):
        """
        Initialize the template engine.
        
        Args:
            templates_dir: Directory containing template files. If None, uses the default
                templates directory in the package.
            cache_manager: Cache manager for provider support decisions. If None, creates a default one.
        """
        if templates_dir is None:
            # Use the default templates directory in the package
            package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.templates_dir = os.path.join(package_dir, "templates")
        else:
            self.templates_dir = os.path.expanduser(templates_dir)
        
        # Validate templates directory path for security
        self.templates_dir = os.path.abspath(self.templates_dir)
        
        # Create the templates directory if it doesn't exist
        os.makedirs(self.templates_dir, exist_ok=True)
        
        # Initialize cache manager for provider support decisions
        if cache_manager is None:
            cache_config = CacheConfig(
                backend=CacheBackend.MEMORY,
                default_ttl=3600,  # 1 hour cache for provider support decisions
                max_size=1000
            )
            self.cache_manager = CacheManager(cache_config)
        else:
            self.cache_manager = cache_manager
        
        # Load the default template
        self.default_template = self._load_default_template()
        
        # Load provider-specific templates
        self.provider_templates = self._load_provider_templates()
        
        # Register built-in functions
        self.functions = {
            "lower": lambda s: s.lower() if isinstance(s, str) else str(s).lower(),
            "upper": lambda s: s.upper() if isinstance(s, str) else str(s).upper(),
            "capitalize": lambda s: s.capitalize() if isinstance(s, str) else str(s).capitalize(),
            "title": lambda s: s.title() if isinstance(s, str) else str(s).title(),
            "strip": lambda s: s.strip() if isinstance(s, str) else str(s).strip(),
            "len": lambda obj: len(obj) if hasattr(obj, "__len__") else 0,
            "join": lambda items, sep=",": sep.join(items) if isinstance(items, (list, tuple)) else str(items),
            "split": lambda s, sep=",": s.split(sep) if isinstance(s, str) else [s],
            "replace": lambda s, old, new: s.replace(old, new) if isinstance(s, str) else str(s),
            "format": lambda s, *args, **kwargs: s.format(*args, **kwargs) if isinstance(s, str) else str(s),
            "json": lambda obj: json.dumps(obj),
            "yaml": lambda obj: yaml.dump(obj, default_flow_style=False),
        }
    
    def _load_default_template(self) -> Dict[str, Any]:
        """
        Load the default template.
        
        Returns:
            Default template as a dictionary.
        """
        default_path = os.path.join(self.templates_dir, "defaults.yaml")
        
        # If the default template doesn't exist, create it with basic structure
        if not os.path.exists(default_path):
            self._create_default_template(default_path)
        
        try:
            with open(default_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load default template: {e}")
            return {}
    
    def _create_default_template(self, path: str) -> None:
        """
        Create a default template file.
        
        Args:
            path: Path to create the template at.
        """
        # Create a basic default template
        default_template = {
            "version": "0.1",
            "packages": {
                "default": {
                    "name": "$software_name",
                    "version": "latest"
                }
            },
            "services": {
                "default": {
                    "name": "$software_name"
                }
            },
            "directories": {
                "config": {
                    "path": "/etc/$software_name",
                    "owner": "root",
                    "group": "root",
                    "mode": "0755"
                }
            },
            "urls": {},
            "category": {
                "default": None,
                "sub": None,
                "tags": []
            },
            "platforms": []
        }
        
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Write the template to the file
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(default_template, f, default_flow_style=False)
    
    def _load_provider_templates(self) -> Dict[str, Dict[str, Any]]:
        """
        Load provider-specific templates, supporting both flat and hierarchical structures.
        
        Returns:
            Dictionary mapping provider names to their templates.
        """
        provider_templates = {}
        providers_dir = os.path.join(self.templates_dir, "providers")
        
        # Create the providers directory if it doesn't exist
        os.makedirs(providers_dir, exist_ok=True)
        
        # Load templates from the providers directory
        if os.path.exists(providers_dir):
            for item in os.listdir(providers_dir):
                item_path = os.path.join(providers_dir, item)
                
                # Handle flat structure (provider.yaml files)
                if os.path.isfile(item_path) and (item.endswith(".yaml") or item.endswith(".yml")):
                    provider_name = os.path.splitext(item)[0]
                    try:
                        with open(item_path, 'r', encoding='utf-8') as f:
                            provider_templates[provider_name] = yaml.safe_load(f) or {}
                        logger.debug(f"Loaded flat provider template: {provider_name}")
                    except Exception as e:
                        logger.error(f"Failed to load provider template {item}: {e}")
                
                # Handle hierarchical structure (provider/default.yaml directories)
                elif os.path.isdir(item_path):
                    provider_name = item
                    default_template_path = os.path.join(item_path, "default.yaml")
                    
                    if os.path.exists(default_template_path):
                        try:
                            with open(default_template_path, 'r', encoding='utf-8') as f:
                                provider_templates[provider_name] = yaml.safe_load(f) or {}
                            logger.debug(f"Loaded hierarchical provider template: {provider_name}")
                        except Exception as e:
                            logger.error(f"Failed to load hierarchical provider template {default_template_path}: {e}")
                    else:
                        logger.warning(f"Hierarchical provider directory {item_path} found but no default.yaml")
        
        logger.info(f"Loaded {len(provider_templates)} provider templates")
        return provider_templates
    
    def register_function(self, name: str, func: Callable) -> None:
        """
        Register a custom function for use in templates.
        
        Args:
            name: Name of the function to register.
            func: Function to register.
        """
        self.functions[name] = func
    
    def apply_template(
        self,
        software_name: str,
        metadata: Optional[Dict[str, Any]] = None,
        providers: Optional[List[str]] = None,
        platforms: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Apply templates to metadata.
        
        Args:
            software_name: Name of the software.
            metadata: Existing metadata to apply templates to. If None, starts with an empty dict.
            providers: List of providers to apply templates for. If None, applies all available provider templates.
            platforms: List of platforms to apply platform-specific templates for.
            context: Additional context variables for template rendering.
            
        Returns:
            Metadata with templates applied.
        """
        # Initialize context with software name and providers
        full_context = {
            "software_name": software_name,
            "providers": providers or list(self.provider_templates.keys()),
            "platforms": platforms or []
        }
        
        # Add additional context variables
        if context:
            full_context.update(context)
        
        # Start with the default template
        result = self._deep_copy(self.default_template)
        
        # Process conditional logic and variable substitution in the default template
        result = self._process_template(result, full_context)
        
        # Apply provider-specific templates
        if providers:
            for provider in providers:
                if provider in self.provider_templates:
                    # Update context with current provider
                    provider_context = full_context.copy()
                    provider_context["current_provider"] = provider
                    
                    provider_template = self._deep_copy(self.provider_templates[provider])
                    provider_template = self._process_template(provider_template, provider_context)
                    
                    # Apply provider overrides
                    result = self._apply_provider_overrides(result, provider_template, provider)
                    
                    # Merge the processed provider template
                    result = self._deep_merge(result, provider_template)
        
        # Apply the existing metadata on top
        if metadata:
            result = self._deep_merge(result, metadata)
        
        # Process includes after merging
        result = self._process_includes(result, full_context)
        
        return result
    
    def _process_template(self, data: Any, context: Dict[str, Any]) -> Any:
        """
        Process a template with conditional logic and variable substitution.
        
        Args:
            data: Template data to process.
            context: Context for variable substitution and condition evaluation.
            
        Returns:
            Processed template data.
        """
        # First pass: Process conditional directives
        data = self._process_conditionals(data, context)
        
        # Second pass: Process loops
        data = self._process_loops(data, context)
        
        # Third pass: Process function calls
        data = self._process_functions(data, context)
        
        # Fourth pass: Substitute variables
        data = self._substitute_variables(data, context)
        
        return data
    
    def _process_conditionals(self, data: Any, context: Dict[str, Any]) -> Any:
        """
        Process conditional directives in the template.
        
        Args:
            data: Template data to process.
            context: Context for condition evaluation.
            
        Returns:
            Processed template data with conditionals evaluated.
        """
        if isinstance(data, dict):
            result = {}
            skip_until = None
            condition_met = False
            
            # Process dictionary keys in order to handle conditionals
            for key, value in data.items():
                # Skip keys until the matching endif if we're in a skipped conditional block
                if skip_until == self.CONDITION_ENDIF and key != self.CONDITION_ENDIF:
                    continue
                
                # Reset skip_until when we reach the endif
                if key == self.CONDITION_ENDIF:
                    skip_until = None
                    condition_met = False
                    continue
                
                # Process if condition
                if key.startswith(self.CONDITION_IF):
                    condition = key[len(self.CONDITION_IF):].strip()
                    condition_result = self.evaluate_condition(condition, context)
                    
                    if condition_result:
                        # Condition is true, include the nested content
                        condition_met = True
                        nested_result = self._process_conditionals(value, context)
                        if nested_result is not None:
                            if isinstance(nested_result, dict):
                                result.update(nested_result)
                            else:
                                # If the value is not a dict, store it under a generated key
                                result[f"_conditional_result_{len(result)}"] = nested_result
                    else:
                        # Condition is false, skip until elif, else, or endif
                        skip_until = self.CONDITION_ENDIF
                    continue
                
                # Process elif condition
                if key.startswith(self.CONDITION_ELIF):
                    if condition_met:
                        # Previous condition was met, skip this block
                        continue
                    
                    condition = key[len(self.CONDITION_ELIF):].strip()
                    condition_result = self.evaluate_condition(condition, context)
                    
                    if condition_result:
                        # Condition is true, include the nested content
                        condition_met = True
                        skip_until = None
                        nested_result = self._process_conditionals(value, context)
                        if nested_result is not None:
                            if isinstance(nested_result, dict):
                                result.update(nested_result)
                            else:
                                result[f"_conditional_result_{len(result)}"] = nested_result
                    continue
                
                # Process else condition
                if key == self.CONDITION_ELSE:
                    if condition_met:
                        # Previous condition was met, skip this block
                        continue
                    
                    # No previous condition was met, include the else block
                    condition_met = True
                    skip_until = None
                    nested_result = self._process_conditionals(value, context)
                    if nested_result is not None:
                        if isinstance(nested_result, dict):
                            result.update(nested_result)
                        else:
                            result[f"_conditional_result_{len(result)}"] = nested_result
                    continue
                
                # Process platform-specific directives
                if key.startswith(self.PLATFORM_SPECIFIC):
                    platform = key[len(self.PLATFORM_SPECIFIC):].strip()
                    if platform in context.get("platforms", []):
                        # Platform matches, include the nested content
                        nested_result = self._process_conditionals(value, context)
                        if nested_result is not None:
                            if isinstance(nested_result, dict):
                                result.update(nested_result)
                            else:
                                result[f"_platform_{platform}"] = nested_result
                    continue
                
                # Process normal key-value pairs
                if isinstance(value, (dict, list)):
                    result[key] = self._process_conditionals(value, context)
                else:
                    result[key] = value
            
            return result
        elif isinstance(data, list):
            # Process each item in the list
            return [self._process_conditionals(item, context) for item in data]
        else:
            # Return primitive values as-is
            return data
    
    def _process_loops(self, data: Any, context: Dict[str, Any]) -> Any:
        """
        Process loop directives in the template.
        
        Args:
            data: Template data to process.
            context: Context for loop evaluation.
            
        Returns:
            Processed template data with loops expanded.
        """
        if isinstance(data, dict):
            result = {}
            skip_until = None
            loop_vars = {}
            
            # Process dictionary keys in order to handle loops
            keys = list(data.keys())
            i = 0
            while i < len(keys):
                key = keys[i]
                value = data[key]
                
                # Skip keys until the matching endfor if we're in a skipped loop block
                if skip_until == self.LOOP_ENDFOR and key != self.LOOP_ENDFOR:
                    i += 1
                    continue
                
                # Reset skip_until when we reach the endfor
                if key == self.LOOP_ENDFOR:
                    skip_until = None
                    loop_vars = {}
                    i += 1
                    continue
                
                # Process for loop
                if key.startswith(self.LOOP_FOR):
                    # Extract loop variables and iterable
                    loop_def = key[len(self.LOOP_FOR):].strip()
                    match = re.match(r'(\w+)\s+in\s+(.+)', loop_def)
                    
                    if match:
                        var_name = match.group(1)
                        iterable_expr = match.group(2)
                        
                        # Get the iterable from the context
                        iterable = self._get_nested_value(context, iterable_expr)
                        
                        if iterable and isinstance(iterable, (list, tuple, dict)):
                            # Process the loop body for each item in the iterable
                            loop_body = value
                            
                            if isinstance(iterable, dict):
                                iterable = iterable.items()
                            
                            for item in iterable:
                                # Update context with loop variable
                                loop_context = context.copy()
                                loop_context[var_name] = item
                                
                                # Process the loop body with the updated context
                                # Note: We need to process the loop body completely, including variable substitution
                                processed_body = self._deep_copy(loop_body)
                                processed_body = self._process_conditionals(processed_body, loop_context)
                                processed_body = self._process_loops(processed_body, loop_context)
                                processed_body = self._process_functions(processed_body, loop_context)
                                processed_body = self._substitute_variables(processed_body, loop_context)
                                
                                # Merge the processed body into the result
                                if isinstance(processed_body, dict):
                                    result.update(processed_body)
                                elif isinstance(processed_body, list):
                                    if not isinstance(result, list):
                                        result = []
                                    result.extend(processed_body)
                                else:
                                    result[f"_loop_result_{len(result)}"] = processed_body
                    
                    # Don't skip to endfor - this is a single key-value loop
                    i += 1
                    continue
                
                # Process normal key-value pairs
                if isinstance(value, (dict, list)):
                    result[key] = self._process_loops(value, context)
                else:
                    result[key] = value
                
                i += 1
            
            return result
        elif isinstance(data, list):
            # Process each item in the list
            return [self._process_loops(item, context) for item in data]
        else:
            # Return primitive values as-is
            return data
    
    def _process_functions(self, data: Any, context: Dict[str, Any]) -> Any:
        """
        Process function call directives in the template.
        
        Args:
            data: Template data to process.
            context: Context for function evaluation.
            
        Returns:
            Processed template data with function calls evaluated.
        """
        if isinstance(data, dict):
            result = {}
            
            # Process dictionary keys in order to handle function calls
            for key, value in data.items():
                # Process function call directives
                if key.startswith(self.FUNCTION_CALL):
                    # Extract function name and arguments
                    func_def = key[len(self.FUNCTION_CALL):].strip()
                    match = re.match(r'(\w+)(?:\((.*)\))?', func_def)
                    
                    if match:
                        func_name = match.group(1)
                        args_str = match.group(2) or ""
                        
                        # Parse arguments
                        args = []
                        kwargs = {}
                        
                        if args_str:
                            # Simple argument parsing (this could be enhanced)
                            for arg in args_str.split(','):
                                arg = arg.strip()
                                if '=' in arg:
                                    k, v = arg.split('=', 1)
                                    kwargs[k.strip()] = self._parse_value(v.strip(), context)
                                else:
                                    # Parse the argument value from context
                                    parsed_arg = self._get_nested_value(context, arg) if arg in context or '.' in arg else self._parse_value(arg, context)
                                    args.append(parsed_arg)
                        
                        # Call the function
                        if func_name in self.functions:
                            try:
                                # Process the value as arguments to the function
                                if isinstance(value, dict):
                                    # If value is a dict, use it as kwargs
                                    for k, v in value.items():
                                        kwargs[k] = self._parse_value(v, context)
                                elif isinstance(value, list):
                                    # If value is a list, use it as args
                                    args.extend([self._parse_value(v, context) for v in value])
                                elif isinstance(value, str):
                                    # If value is a string, use it as the result key
                                    result_key = value
                                else:
                                    # Otherwise, use it as a single arg
                                    args.append(self._parse_value(value, context))
                                
                                # Call the function
                                func_result = self.functions[func_name](*args, **kwargs)
                                
                                # Add the result to the output
                                if isinstance(func_result, dict):
                                    result.update(func_result)
                                elif isinstance(value, str):
                                    # Use the value as the key for the result
                                    result[value] = func_result
                                else:
                                    result[f"_function_result_{len(result)}"] = func_result
                            except Exception as e:
                                logger.error(f"Error calling function {func_name}: {e}")
                                result[f"_function_error_{len(result)}"] = str(e)
                    continue
                
                # Process normal key-value pairs
                if isinstance(value, (dict, list)):
                    result[key] = self._process_functions(value, context)
                else:
                    result[key] = value
            
            return result
        elif isinstance(data, list):
            # Process each item in the list
            return [self._process_functions(item, context) for item in data]
        else:
            # Return primitive values as-is
            return data
    
    def _parse_value(self, value: Any, context: Dict[str, Any]) -> Any:
        """
        Parse a value from a template, resolving variables and expressions.
        
        Args:
            value: Value to parse.
            context: Context for variable resolution.
            
        Returns:
            Parsed value.
        """
        if isinstance(value, str):
            # Check if it's a variable reference
            if value.startswith('$') and value[1:] in context:
                return context[value[1:]]
            
            # Check if it's a string literal
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                return value[1:-1]
            
            # Check if it's a number
            try:
                if '.' in value:
                    return float(value)
                else:
                    return int(value)
            except ValueError:
                pass
            
            # Check if it's a boolean
            if value.lower() == 'true':
                return True
            if value.lower() == 'false':
                return False
            
            # Check if it's None/null
            if value.lower() == 'none' or value.lower() == 'null':
                return None
            
            # Otherwise, return as is
            return value
        else:
            return value
    
    # Compile regex patterns once at class level for performance
    _VARIABLE_PATTERN = re.compile(r'\${([^}]+)}')
    _JINJA_PATTERN = re.compile(r'\{\{\s*([^}]+?)\s*\}\}')
    
    def _substitute_variables(self, data: Any, context: Dict[str, Any]) -> Any:
        """
        Substitute variables in data.
        
        Args:
            data: Data to substitute variables in.
            context: Dictionary with variables for substitution.
            
        Returns:
            Data with variables substituted.
        """
        if isinstance(data, str):
            result = data
            
            # Early return if no variables to substitute
            if '$' not in result and '{' not in result:
                return result
            
            # Substitute simple variables like $variable_name
            for var_name, var_value in context.items():
                if isinstance(var_value, (str, int, float, bool)):
                    var_placeholder = f"${var_name}"
                    if var_placeholder in result:
                        result = result.replace(var_placeholder, str(var_value))
            
            # Substitute complex expressions like ${variable.path | default_value}
            matches = self._VARIABLE_PATTERN.findall(result)
            
            for match in matches:
                if '|' in match:
                    # Handle expressions with default values
                    expr, default = match.split('|', 1)
                    expr = expr.strip()
                    default = default.strip()
                    
                    value = self._get_nested_value(context, expr)
                    if value is None:
                        value = default
                else:
                    # Handle simple variable paths
                    expr = match.strip()
                    value = self._get_nested_value(context, expr)
                
                if value is not None:
                    result = result.replace(f"${{{match}}}", str(value))
            
            # Also handle Jinja2-style {{ variable }} syntax
            def replace_jinja_var(match):
                var_expr = match.group(1).strip()
                if '|' in var_expr:
                    # Handle expressions with default values
                    expr, default = var_expr.split('|', 1)
                    expr = expr.strip()
                    default = default.strip()
                    
                    value = self._get_nested_value(context, expr)
                    if value is None:
                        value = default
                else:
                    # Handle simple variable paths
                    value = self._get_nested_value(context, var_expr)
                
                return str(value) if value is not None else match.group(0)
            
            result = self._JINJA_PATTERN.sub(replace_jinja_var, result)
            
            return result
        elif isinstance(data, dict):
            # Recursively substitute variables in dictionaries (both keys and values)
            result = {}
            for k, v in data.items():
                # Substitute variables in both key and value
                new_key = self._substitute_variables(k, context) if isinstance(k, str) else k
                new_value = self._substitute_variables(v, context)
                result[new_key] = new_value
            return result
        elif isinstance(data, list):
            # Recursively substitute variables in lists
            return [self._substitute_variables(item, context) for item in data]
        else:
            # Return other types as-is
            return data
    
    def _apply_provider_overrides(
        self, 
        base: Dict[str, Any], 
        provider_template: Dict[str, Any],
        provider: str
    ) -> Dict[str, Any]:
        """
        Apply provider-specific overrides to the base template.
        
        Args:
            base: Base template to apply overrides to.
            provider_template: Provider template with override directives.
            provider: Current provider name.
            
        Returns:
            Base template with provider overrides applied.
        """
        result = self._deep_copy(base)
        
        # Find and process provider override directives
        overrides = {}
        keys_to_remove = []
        
        for key, value in provider_template.items():
            if key.startswith(self.PROVIDER_OVERRIDE):
                # Extract the path to override
                path = key[len(self.PROVIDER_OVERRIDE):].strip()
                keys_to_remove.append(key)
                
                # Store the override value
                overrides[path] = value
        
        # Remove override directives from the provider template
        for key in keys_to_remove:
            del provider_template[key]
        
        # Apply the overrides to the base template
        for path, value in overrides.items():
            parts = path.split('.')
            current = result
            
            # Navigate to the parent of the target path
            for i, part in enumerate(parts[:-1]):
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Set the value at the target path
            if parts[-1] in current and isinstance(current[parts[-1]], dict) and isinstance(value, dict):
                # Merge dictionaries
                current[parts[-1]] = self._deep_merge(current[parts[-1]], value)
            else:
                # Replace or add the value
                current[parts[-1]] = self._deep_copy(value)
        
        return result
    
    def _process_includes(self, data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process include directives in the template.
        
        Args:
            data: Template data to process.
            context: Context for template processing.
            
        Returns:
            Processed template data with includes resolved.
        """
        result = self._deep_copy(data)
        includes_processed = set()  # Track processed includes to prevent infinite recursion
        
        def process_includes_recursive(data_dict, path=""):
            if not isinstance(data_dict, dict):
                return data_dict
            
            result_dict = {}
            for key, value in data_dict.items():
                if key.startswith(self.INCLUDE_TEMPLATE):
                    # Extract the template name to include
                    template_name = key[len(self.INCLUDE_TEMPLATE):].strip()
                    full_path = f"{path}.{template_name}" if path else template_name
                    
                    # Prevent infinite recursion
                    if full_path in includes_processed:
                        logger.warning(f"Circular include detected: {full_path}")
                        continue
                    
                    includes_processed.add(full_path)
                    
                    # Load the included template
                    included_template = self._load_included_template(template_name)
                    if included_template:
                        # Process the included template
                        processed_template = self._process_template(included_template, context)
                        
                        # Merge with any override values provided
                        if isinstance(value, dict):
                            processed_template = self._deep_merge(processed_template, value)
                        
                        # Merge the processed template into the result
                        result_dict = self._deep_merge(result_dict, processed_template)
                else:
                    # Process normal key-value pairs
                    if isinstance(value, dict):
                        result_dict[key] = process_includes_recursive(value, f"{path}.{key}" if path else key)
                    elif isinstance(value, list):
                        result_dict[key] = [
                            process_includes_recursive(item, f"{path}.{key}[{i}]") if isinstance(item, dict) else item
                            for i, item in enumerate(value)
                        ]
                    else:
                        result_dict[key] = value
            
            return result_dict
        
        return process_includes_recursive(result)
    
    def _load_included_template(self, template_name: str) -> Dict[str, Any]:
        """
        Load an included template by name.
        
        Args:
            template_name: Name of the template to include.
            
        Returns:
            Loaded template as a dictionary.
        """
        # Check if it's a provider template
        if template_name in self.provider_templates:
            return self._deep_copy(self.provider_templates[template_name])
        
        # Check if it's a custom template in the templates directory
        template_path = os.path.join(self.templates_dir, f"{template_name}.yaml")
        if os.path.exists(template_path):
            try:
                with open(template_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Failed to load included template {template_name}: {e}")
        
        logger.warning(f"Included template not found: {template_name}")
        return {}
    
    def _deep_merge(self, base: Dict[str, Any], overlay: Dict[str, Any], _depth: int = 0) -> Dict[str, Any]:
        """
        Enhanced deep merge with null removal, override precedence, and type-safe merging.
        
        This method handles merging of different data types properly:
        - Dictionaries are merged recursively
        - Lists are replaced (not merged) to allow complete override
        - Primitive values are replaced
        - Null values in overlay remove the key from base
        - Keys that match defaults exactly are skipped to avoid redundancy
        - Type-safe merging ensures data integrity
        
        Args:
            base: Base dictionary.
            overlay: Dictionary to overlay on top of the base.
            _depth: Internal recursion depth counter for security.
            
        Returns:
            Merged dictionary with proper type handling and null removal.
            
        Raises:
            ValueError: If recursion depth exceeds maximum allowed depth.
        """
        # Prevent stack overflow attacks
        MAX_RECURSION_DEPTH = 100
        if _depth > MAX_RECURSION_DEPTH:
            raise ValueError(f"Template merge recursion depth exceeded maximum of {MAX_RECURSION_DEPTH}")
        
        # Validate inputs
        if not isinstance(base, dict) or not isinstance(overlay, dict):
            raise TypeError("Both base and overlay must be dictionaries")
        result = self._deep_copy(base)
        
        for key, value in overlay.items():
            # Handle null values - remove key from result
            if value is None:
                result.pop(key, None)
                continue
            
            # Skip keys that match defaults exactly to avoid redundancy
            if key in result and self._values_equal(result[key], value):
                continue
            
            # Type-safe merging based on data types
            if key in result:
                base_value = result[key]
                
                # Both are dictionaries - merge recursively
                if isinstance(base_value, dict) and isinstance(value, dict):
                    result[key] = self._deep_merge(base_value, value, _depth + 1)
                # Both are lists - validate types and replace
                elif isinstance(base_value, list) and isinstance(value, list):
                    if self._validate_list_merge(base_value, value):
                        result[key] = value if isinstance(value, (str, int, float, bool, type(None))) else self._deep_copy(value)
                    else:
                        logger.warning(f"Type mismatch in list merge for key '{key}', replacing with overlay value")
                        result[key] = value if isinstance(value, (str, int, float, bool, type(None))) else self._deep_copy(value)
                # Type mismatch - validate and replace
                elif type(base_value) != type(value):
                    if self._validate_type_override(key, base_value, value):
                        result[key] = value if isinstance(value, (str, int, float, bool, type(None))) else self._deep_copy(value)
                    else:
                        logger.warning(f"Invalid type override for key '{key}': {type(base_value).__name__} -> {type(value).__name__}")
                        result[key] = value if isinstance(value, (str, int, float, bool, type(None))) else self._deep_copy(value)
                else:
                    # Same types - replace (optimize for primitives)
                    result[key] = value if isinstance(value, (str, int, float, bool, type(None))) else self._deep_copy(value)
            else:
                # New key - add with validation
                if self._validate_new_key(key, value):
                    result[key] = value if isinstance(value, (str, int, float, bool, type(None))) else self._deep_copy(value)
        
        # Remove null values from the final result
        result = self._remove_null_values(result)
        
        return result
    
    def _deep_copy(self, data: Any) -> Any:
        """
        Deep copy data.
        
        Args:
            data: Data to copy.
            
        Returns:
            Deep copy of the data.
        """
        if isinstance(data, dict):
            return {k: self._deep_copy(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._deep_copy(item) for item in data]
        else:
            return data
    
    def _values_equal(self, value1: Any, value2: Any) -> bool:
        """
        Compare two values for equality, handling nested structures.
        
        Args:
            value1: First value to compare.
            value2: Second value to compare.
            
        Returns:
            True if values are equal, False otherwise.
        """
        # Handle None values
        if value1 is None and value2 is None:
            return True
        if value1 is None or value2 is None:
            return False
        
        # Handle different types
        if type(value1) != type(value2):
            return False
        
        # Handle dictionaries
        if isinstance(value1, dict):
            if set(value1.keys()) != set(value2.keys()):
                return False
            return all(self._values_equal(value1[k], value2[k]) for k in value1.keys())
        
        # Handle lists
        if isinstance(value1, list):
            if len(value1) != len(value2):
                return False
            return all(self._values_equal(v1, v2) for v1, v2 in zip(value1, value2))
        
        # Handle primitive types
        return value1 == value2
    
    def _validate_list_merge(self, base_list: List[Any], overlay_list: List[Any]) -> bool:
        """
        Validate that list merge is type-safe.
        
        Args:
            base_list: Base list.
            overlay_list: Overlay list.
            
        Returns:
            True if merge is valid, False otherwise.
        """
        # Empty lists are always valid
        if not base_list or not overlay_list:
            return True
        
        # Check if list items have compatible types
        base_types = {type(item) for item in base_list if item is not None}
        overlay_types = {type(item) for item in overlay_list if item is not None}
        
        # If both lists contain only None values, it's valid
        if not base_types and not overlay_types:
            return True
        
        # If one list has types and the other doesn't, it's valid (replacing empty with content)
        if not base_types or not overlay_types:
            return True
        
        # Check for compatible types (allow string/int mixing, etc.)
        compatible_types = {str, int, float, bool}
        if base_types.issubset(compatible_types) and overlay_types.issubset(compatible_types):
            return True
        
        # Check if types are exactly the same
        return base_types == overlay_types
    
    def _validate_type_override(self, key: str, base_value: Any, overlay_value: Any) -> bool:
        """
        Validate that type override is allowed.
        
        Args:
            key: Key being overridden.
            base_value: Base value.
            overlay_value: Overlay value.
            
        Returns:
            True if override is valid, False otherwise.
        """
        # Allow None to override any type (removal)
        if overlay_value is None:
            return True
        
        # Allow any type to override None (addition)
        if base_value is None:
            return True
        
        # Allow compatible primitive type conversions
        compatible_primitives = {str, int, float, bool}
        if (type(base_value) in compatible_primitives and 
            type(overlay_value) in compatible_primitives):
            return True
        
        # Allow list to dict conversion for certain keys (like packages)
        if key in ['packages', 'services', 'directories'] and isinstance(overlay_value, dict):
            return True
        
        # Allow dict to list conversion for certain keys (like platforms, tags)
        if key in ['platforms', 'tags', 'categories'] and isinstance(overlay_value, list):
            return True
        
        # Log warning for other type changes but allow them
        logger.debug(f"Type override for key '{key}': {type(base_value).__name__} -> {type(overlay_value).__name__}")
        return True
    
    def _validate_new_key(self, key: str, value: Any) -> bool:
        """
        Validate that a new key is allowed.
        
        Args:
            key: Key being added.
            value: Value being added.
            
        Returns:
            True if key is valid, False otherwise.
        """
        # Input validation
        if not isinstance(key, str):
            logger.warning(f"Rejecting non-string key: {type(key).__name__}")
            return False
        
        # Reject keys that start with underscore (reserved for internal use)
        if key.startswith('_'):
            logger.warning(f"Rejecting key '{key}' - keys starting with underscore are reserved")
            return False
        
        # Reject keys with dangerous characters
        if any(char in key for char in ['..', '/', '\\', '\x00']):
            logger.warning(f"Rejecting key '{key}' - contains dangerous characters")
            return False
        
        # Reject None values for new keys
        if value is None:
            logger.debug(f"Rejecting new key '{key}' with None value")
            return False
        
        # Reject excessively long keys
        if len(key) > 256:
            logger.warning(f"Rejecting key '{key}' - exceeds maximum length of 256 characters")
            return False
        
        # All other keys are valid
        return True
    
    def evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """
        Evaluate a condition in the context.
        
        Args:
            condition: Condition to evaluate.
            context: Context to evaluate the condition in.
            
        Returns:
            Result of the condition evaluation.
        """
        condition = condition.strip()
        
        # Handle complex conditions with AND/OR operators
        if " and " in condition.lower():
            parts = condition.split(" and ", 1)
            return self.evaluate_condition(parts[0], context) and self.evaluate_condition(parts[1], context)
        
        if " or " in condition.lower():
            parts = condition.split(" or ", 1)
            return self.evaluate_condition(parts[0], context) or self.evaluate_condition(parts[1], context)
        
        # Handle negation
        if condition.lower().startswith("not "):
            return not self.evaluate_condition(condition[4:], context)
        
        # Handle parentheses
        if condition.startswith("(") and condition.endswith(")"):
            return self.evaluate_condition(condition[1:-1], context)
        
        # Handle comparison operators
        if "==" in condition:
            var_name, value = condition.split("==", 1)
            var_name = var_name.strip()
            value = value.strip()
            
            # Get the variable value from the context
            var_value = self._get_nested_value(context, var_name)
            
            # Handle string literals
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            
            # Compare as strings
            return str(var_value) == value
        
        elif "!=" in condition:
            var_name, value = condition.split("!=", 1)
            var_name = var_name.strip()
            value = value.strip()
            
            # Get the variable value from the context
            var_value = self._get_nested_value(context, var_name)
            
            # Handle string literals
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            
            # Compare as strings
            return str(var_value) != value
        
        elif " not in " in condition:
            var_name, value = condition.split(" not in ", 1)
            var_name = var_name.strip()
            value = value.strip()
            
            # Get the variable value from the context
            var_value = self._get_nested_value(context, var_name)
            
            # Handle list literals - use ast.literal_eval for safety
            if value.startswith("[") and value.endswith("]"):
                try:
                    import ast
                    value_list = ast.literal_eval(value)
                    return var_value not in value_list
                except (ValueError, SyntaxError) as e:
                    logger.error(f"Failed to evaluate list in condition: {e}")
                    return False
            
            # Handle context variables
            value_list = self._get_nested_value(context, value)
            if isinstance(value_list, (list, tuple, set)):
                return var_value not in value_list
            
            # If value_list is not a list or is None, return False
            # (we can't determine membership in a non-existent list)
            return False
        
        elif " in " in condition:
            var_name, value = condition.split(" in ", 1)
            var_name = var_name.strip()
            value = value.strip()
            
            # Get the variable value from the context
            var_value = self._get_nested_value(context, var_name)
            
            # Handle list literals - use ast.literal_eval for safety
            if value.startswith("[") and value.endswith("]"):
                try:
                    import ast
                    value_list = ast.literal_eval(value)
                    return var_value in value_list
                except (ValueError, SyntaxError) as e:
                    logger.error(f"Failed to evaluate list in condition: {e}")
                    return False
            
            # Handle context variables
            value_list = self._get_nested_value(context, value)
            if isinstance(value_list, (list, tuple, set)):
                return var_value in value_list
            
            return False
        
        # Handle existence check
        if condition.startswith("exists "):
            var_name = condition[7:].strip()
            var_value = self._get_nested_value(context, var_name)
            return var_value is not None
        
        # Handle boolean values
        if condition.lower() == "true":
            return True
        
        if condition.lower() == "false":
            return False
        
        # Handle variable as boolean
        var_value = self._get_nested_value(context, condition)
        if var_value is not None:
            if isinstance(var_value, bool):
                return var_value
            if isinstance(var_value, (int, float)):
                return bool(var_value)
            if isinstance(var_value, str):
                return var_value.lower() == "true"
            if isinstance(var_value, (list, dict)):
                return bool(var_value)
        
        # Unknown condition format
        logger.warning(f"Unknown condition format: {condition}")
        return False
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """
        Get a nested value from a dictionary using a dot-separated path.
        
        Args:
            data: Dictionary to get the value from.
            path: Dot-separated path to the value.
            
        Returns:
            Value at the path, or None if not found.
        """
        if not path:
            return None
        
        parts = path.split(".")
        current = data
        
        for part in parts:
            # Handle array indexing
            if "[" in part and part.endswith("]"):
                array_name, index_str = part.split("[", 1)
                index = int(index_str[:-1])
                
                if array_name in current and isinstance(current[array_name], list):
                    if 0 <= index < len(current[array_name]):
                        current = current[array_name][index]
                    else:
                        return None
                else:
                    return None
            elif isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        return current
    

    
    def _remove_null_values(self, data: Any) -> Any:
        """
        Remove null values and empty structures from data.
        
        Args:
            data: Data to clean up.
            
        Returns:
            Data with null values and empty structures removed.
        """
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                cleaned_value = self._remove_null_values(value)
                if cleaned_value is not None:
                    if isinstance(cleaned_value, (dict, list)) and not cleaned_value:
                        # Skip empty dicts and lists
                        continue
                    result[key] = cleaned_value
            return result
        elif isinstance(data, list):
            result = []
            for item in data:
                cleaned_item = self._remove_null_values(item)
                if cleaned_item is not None:
                    result.append(cleaned_item)
            return result
        else:
            return data
    
    def merge_with_defaults(
        self, 
        defaults: Dict[str, Any], 
        provider_overrides: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge provider overrides with defaults, handling null removal and override precedence.
        
        This method properly merges provider-specific overrides with the default
        configuration, ensuring that:
        - Provider overrides take precedence over defaults
        - Null values are removed from the final configuration
        - The merge is type-safe for different data types
        - Keys that match defaults exactly are skipped to avoid redundancy
        - Final configuration is validated for correctness
        
        Args:
            defaults: Base defaults configuration
            provider_overrides: Provider-specific overrides
            
        Returns:
            Merged configuration with nulls removed and proper precedence
        """
        logger.debug("Merging provider overrides with defaults")
        
        # Validate input parameters
        if not isinstance(defaults, dict):
            raise ValueError("Defaults must be a dictionary")
        if not isinstance(provider_overrides, dict):
            raise ValueError("Provider overrides must be a dictionary")
        
        # Handle unsupported providers
        if provider_overrides.get("supported") is False:
            return provider_overrides
        
        # Start with a deep copy of defaults
        result = self._deep_copy(defaults)
        
        # Apply provider overrides using the enhanced deep merge
        result = self._deep_merge(result, provider_overrides)
        
        # Validate the merged configuration
        if not self._validate_merged_configuration(result):
            logger.warning("Merged configuration failed validation")
        
        return result
    
    def is_provider_supported(
        self, 
        software_name: str, 
        provider: str, 
        repository_data: Optional[Union[Dict[str, Any], RepositoryData, PackageInfo, List[PackageInfo]]] = None
    ) -> bool:
        """
        Determine if a provider supports the given software.
        
        This method checks multiple sources to determine provider support with caching:
        1. Cache lookup for previous decisions
        2. Repository data (if available) - most authoritative
        3. Provider template existence and configuration
        4. Explicit supported: false in template
        5. Fallback logic for unknown cases
        
        Args:
            software_name: Name of the software
            provider: Provider name
            repository_data: Data fetched from provider repository (optional)
                Can be Dict, RepositoryData, PackageInfo, or List[PackageInfo]
            
        Returns:
            True if provider supports the software, False otherwise
        """
        # Generate cache key for this provider support decision
        # Include repository data status in cache key to avoid conflicts
        repo_status = "none" if repository_data is None else ("empty" if not repository_data else "present")
        cache_key = f"provider_support:{provider}:{software_name}:{repo_status}"
        
        # Check cache first (unless we have fresh repository data)
        if repository_data is None:
            cached_result = self.cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Using cached provider support decision for {provider}:{software_name} = {cached_result}")
                return cached_result
        
        logger.debug(f"Checking if {provider} supports {software_name}")
        
        # Check repository data first (most authoritative)
        support_from_repo = self._check_repository_support(software_name, provider, repository_data)
        if support_from_repo is not None:
            # Cache the result and return
            self.cache_manager.put(cache_key, support_from_repo, ttl=3600)  # Cache for 1 hour
            return support_from_repo
        
        # Check provider template
        provider_template = self._load_provider_template(provider)
        if not provider_template:
            logger.debug(f"No template found for provider {provider}")
            # Cache negative result for shorter time to allow for template additions
            self.cache_manager.put(cache_key, False, ttl=300)  # Cache for 5 minutes
            return False
        
        # Check for explicit supported: false in template
        if provider_template.get("supported") is False:
            logger.debug(f"Provider {provider} explicitly marked as unsupported")
            self.cache_manager.put(cache_key, False, ttl=3600)
            return False
        
        # Apply fallback logic based on provider type and software characteristics
        fallback_result = self._apply_fallback_support_logic(software_name, provider, provider_template)
        
        # Cache the fallback result for a shorter time since it's less certain
        self.cache_manager.put(cache_key, fallback_result, ttl=1800)  # Cache for 30 minutes
        
        logger.debug(f"Provider {provider} support for {software_name} determined by fallback logic: {fallback_result}")
        return fallback_result
    
    def _check_repository_support(
        self, 
        software_name: str, 
        provider: str, 
        repository_data: Optional[Union[Dict[str, Any], RepositoryData, PackageInfo, List[PackageInfo]]]
    ) -> Optional[bool]:
        """
        Check if provider repository contains the software.
        
        Args:
            software_name: Name of the software
            provider: Provider name
            repository_data: Repository data in various formats
            
        Returns:
            True if supported, False if not supported, None if inconclusive
        """
        if repository_data is None:
            return None
        
        # Handle different repository data formats
        if isinstance(repository_data, list):
            # List of PackageInfo objects
            if repository_data:  # Non-empty list means supported
                logger.debug(f"Repository data (list) found for {software_name} on {provider}")
                return True
            else:  # Empty list means not found
                logger.debug(f"Empty repository data (list) for {software_name} on {provider}")
                return False
        
        elif isinstance(repository_data, PackageInfo):
            # Single PackageInfo object
            if repository_data.name and repository_data.provider == provider:
                logger.debug(f"Repository data (PackageInfo) found for {software_name} on {provider}")
                return True
            else:
                logger.debug(f"Invalid PackageInfo for {software_name} on {provider}")
                return False
        
        elif isinstance(repository_data, RepositoryData):
            # RepositoryData object
            if repository_data.packages and software_name in repository_data.packages:
                logger.debug(f"Repository data (RepositoryData) found for {software_name} on {provider}")
                return True
            elif repository_data.packages:  # Has packages but not this one
                logger.debug(f"Software {software_name} not found in {provider} repository")
                return False
            else:
                logger.debug(f"Empty repository data (RepositoryData) for {provider}")
                return None
        
        elif isinstance(repository_data, dict):
            # Dictionary format
            if repository_data:  # Non-empty dict means supported
                # Check if it contains package information
                if any(key in repository_data for key in ['name', 'version', 'description', 'packages']):
                    logger.debug(f"Repository data (dict) found for {software_name} on {provider}")
                    return True
                else:
                    logger.debug(f"Repository data (dict) exists but lacks package info for {software_name} on {provider}")
                    return None
            else:  # Empty dict is inconclusive, fall back to template check
                logger.debug(f"Empty repository data (dict) for {software_name} on {provider}")
                return None
        
        # Unknown format
        logger.warning(f"Unknown repository data format for {software_name} on {provider}: {type(repository_data)}")
        return None
    
    def _apply_fallback_support_logic(
        self, 
        software_name: str, 
        provider: str, 
        provider_template: Dict[str, Any]
    ) -> bool:
        """
        Apply fallback logic for determining provider support when repository data is unavailable.
        
        This method uses heuristics based on:
        - Provider type and typical software support patterns
        - Software name patterns and common package naming conventions
        - Provider template configuration hints
        
        Args:
            software_name: Name of the software
            provider: Provider name
            provider_template: Provider template configuration
            
        Returns:
            True if provider likely supports the software, False otherwise
        """
        logger.debug(f"Applying fallback logic for {provider}:{software_name}")
        
        # Provider-specific fallback logic
        provider_lower = provider.lower()
        software_lower = software_name.lower()
        
        # Language-specific package managers
        if provider_lower in ['npm', 'yarn', 'pnpm']:
            # Node.js packages - very broad support
            if any(keyword in software_lower for keyword in ['node', 'js', 'javascript', 'react', 'vue', 'angular']):
                return True
            # Many general tools are also available on npm
            return True  # Default to supported for npm due to broad ecosystem
        
        elif provider_lower in ['pypi', 'pip']:
            # Python packages
            if any(keyword in software_lower for keyword in ['python', 'py', 'django', 'flask', 'pandas']):
                return True
            # Many general tools have Python packages
            return True  # Default to supported for PyPI due to broad ecosystem
        
        elif provider_lower in ['cargo']:
            # Rust packages
            if any(keyword in software_lower for keyword in ['rust', 'rs']):
                return True
            # Rust ecosystem is smaller but growing
            return False  # Default to not supported unless explicitly known
        
        elif provider_lower in ['gem', 'rubygems']:
            # Ruby packages
            if any(keyword in software_lower for keyword in ['ruby', 'rb', 'rails']):
                return True
            return False  # Ruby ecosystem is more specialized
        
        elif provider_lower in ['nuget']:
            # .NET packages
            if any(keyword in software_lower for keyword in ['net', 'dotnet', 'csharp', 'c#']):
                return True
            return False  # .NET ecosystem is more specialized
        
        elif provider_lower in ['maven', 'gradle']:
            # Java packages
            if any(keyword in software_lower for keyword in ['java', 'jvm', 'scala', 'kotlin']):
                return True
            return False  # Java ecosystem is more specialized
        
        elif provider_lower in ['composer']:
            # PHP packages
            if any(keyword in software_lower for keyword in ['php', 'laravel', 'symfony']):
                return True
            return False  # PHP ecosystem is more specialized
        
        elif provider_lower in ['go', 'golang']:
            # Go modules
            if any(keyword in software_lower for keyword in ['go', 'golang']):
                return True
            return False  # Go ecosystem is more specialized
        
        # System package managers
        elif provider_lower in ['apt', 'dpkg']:
            # Debian/Ubuntu packages - broad system software support
            if any(keyword in software_lower for keyword in ['lib', 'dev', 'server', 'daemon', 'tool']):
                return True
            return True  # Default to supported for system packages
        
        elif provider_lower in ['yum', 'dnf', 'rpm']:
            # Red Hat/Fedora packages - broad system software support
            if any(keyword in software_lower for keyword in ['lib', 'dev', 'server', 'daemon', 'tool']):
                return True
            return True  # Default to supported for system packages
        
        elif provider_lower in ['zypper']:
            # SUSE packages
            return True  # Default to supported for system packages
        
        elif provider_lower in ['pacman']:
            # Arch Linux packages - very broad support
            return True  # Arch has extensive package availability
        
        elif provider_lower in ['apk']:
            # Alpine Linux packages - minimal but covers essentials
            if any(keyword in software_lower for keyword in ['lib', 'dev', 'server', 'daemon']):
                return True
            return False  # Alpine focuses on minimal packages
        
        elif provider_lower in ['brew', 'homebrew']:
            # macOS/Linux Homebrew - broad support for development tools
            return True  # Homebrew has very broad package support
        
        elif provider_lower in ['winget']:
            # Windows Package Manager - growing ecosystem
            if any(keyword in software_lower for keyword in ['windows', 'win', 'microsoft']):
                return True
            return True  # Default to supported as winget is expanding rapidly
        
        elif provider_lower in ['choco', 'chocolatey']:
            # Chocolatey - broad Windows software support
            return True  # Chocolatey has extensive Windows software
        
        elif provider_lower in ['scoop']:
            # Scoop - focuses on command-line tools
            if any(keyword in software_lower for keyword in ['cli', 'tool', 'dev', 'git']):
                return True
            return False  # Scoop is more specialized
        
        # Container and orchestration
        elif provider_lower in ['docker']:
            # Docker Hub - extremely broad support
            return True  # Docker Hub has containers for almost everything
        
        elif provider_lower in ['helm']:
            # Kubernetes Helm charts
            if any(keyword in software_lower for keyword in ['k8s', 'kubernetes', 'server', 'database', 'web']):
                return True
            return False  # Helm is specialized for Kubernetes deployments
        
        # Universal package managers
        elif provider_lower in ['snap', 'snapcraft']:
            # Ubuntu Snap packages
            if any(keyword in software_lower for keyword in ['app', 'desktop', 'server', 'tool']):
                return True
            return True  # Snap aims for broad application support
        
        elif provider_lower in ['flatpak']:
            # Flatpak applications
            if any(keyword in software_lower for keyword in ['app', 'desktop', 'gui']):
                return True
            return False  # Flatpak focuses on desktop applications
        
        # Specialized package managers
        elif provider_lower in ['nix', 'nixpkgs']:
            # Nix packages - very comprehensive
            return True  # Nix has extensive package collection
        
        elif provider_lower in ['guix']:
            # GNU Guix packages
            if any(keyword in software_lower for keyword in ['gnu', 'free', 'lib']):
                return True
            return False  # Guix focuses on free software
        
        elif provider_lower in ['spack']:
            # Spack - HPC packages
            if any(keyword in software_lower for keyword in ['hpc', 'scientific', 'compute', 'mpi']):
                return True
            return False  # Spack is specialized for HPC
        
        # If we have a template but no specific logic, assume supported
        # This is because having a template suggests the provider is relevant
        if provider_template:
            logger.debug(f"Fallback: assuming {provider} supports {software_name} due to template existence")
            return True
        
        # Final fallback - assume not supported
        logger.debug(f"Fallback: assuming {provider} does not support {software_name}")
        return False
    
    def _load_provider_template(self, provider: str) -> Dict[str, Any]:
        """
        Load provider template, supporting both hierarchical and flat structures.
        
        Args:
            provider: Provider name
            
        Returns:
            Provider template as dictionary, or empty dict if not found
        """
        # First check if it's already loaded in provider_templates (flat structure)
        if provider in self.provider_templates:
            return self._deep_copy(self.provider_templates[provider])
        
        # Check for hierarchical structure (provider/default.yaml)
        hierarchical_path = os.path.join(self.templates_dir, "providers", provider, "default.yaml")
        if os.path.exists(hierarchical_path):
            try:
                with open(hierarchical_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Failed to load hierarchical provider template {hierarchical_path}: {e}")
        
        # Check for flat structure (provider.yaml)
        flat_path = os.path.join(self.templates_dir, "providers", f"{provider}.yaml")
        if os.path.exists(flat_path):
            try:
                with open(flat_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Failed to load flat provider template {flat_path}: {e}")
        
        logger.warning(f"Provider template not found for {provider}")
        return {}
    
    def clear_provider_support_cache(self, software_name: Optional[str] = None, provider: Optional[str] = None) -> int:
        """
        Clear cached provider support decisions.
        
        Args:
            software_name: If specified, only clear cache for this software
            provider: If specified, only clear cache for this provider
            
        Returns:
            Number of cache entries cleared
        """
        if software_name and provider:
            # Clear all cache entries for this specific provider:software combination
            pattern = f"provider_support:{provider}:{software_name}:*"
            cleared = self.cache_manager.invalidate_pattern(pattern)
            logger.debug(f"Cleared {cleared} provider support cache entries for {provider}:{software_name}")
            return cleared
        elif software_name:
            # Clear all entries for a specific software
            pattern = f"provider_support:*:{software_name}:*"
            cleared = self.cache_manager.invalidate_pattern(pattern)
            logger.debug(f"Cleared {cleared} provider support cache entries for software {software_name}")
            return cleared
        elif provider:
            # Clear all entries for a specific provider
            pattern = f"provider_support:{provider}:*"
            cleared = self.cache_manager.invalidate_pattern(pattern)
            logger.debug(f"Cleared {cleared} provider support cache entries for provider {provider}")
            return cleared
        else:
            # Clear all provider support cache entries
            pattern = "provider_support:*"
            cleared = self.cache_manager.invalidate_pattern(pattern)
            logger.debug(f"Cleared {cleared} provider support cache entries")
            return cleared
    
    def get_provider_support_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the provider support cache.
        
        Returns:
            Dictionary with cache statistics
        """
        return self.cache_manager.get_info()
    
    def _enhanced_deep_merge(self, base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhanced deep merge with proper type handling and override precedence.
        
        This method handles merging of different data types properly:
        - Dictionaries are merged recursively
        - Lists are replaced (not merged) to allow complete override
        - Primitive values are replaced
        - Null values in overlay remove the key from base
        
        Args:
            base: Base dictionary
            overlay: Dictionary to overlay on top of the base
            
        Returns:
            Merged dictionary with proper type handling
        """
        result = self._deep_copy(base)
        
        for key, value in overlay.items():
            if value is None:
                # Null values in overlay remove the key from result
                result.pop(key, None)
            elif key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge dictionaries
                result[key] = self._enhanced_deep_merge(result[key], value)
            else:
                # Replace or add the value (handles lists, primitives, etc.)
                result[key] = self._deep_copy(value)
        
        return result
    
    def _remove_null_values(self, data: Any) -> Any:
        """
        Remove null values and empty structures from data recursively.
        
        This method cleans up the configuration by removing:
        - Keys with None/null values
        - Empty dictionaries
        - Empty lists (optional, based on context)
        
        Args:
            data: Data to clean up
            
        Returns:
            Cleaned data with null values removed
        """
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                # Skip null values
                if value is None:
                    continue
                
                # Recursively clean nested structures
                cleaned_value = self._remove_null_values(value)
                
                # Skip empty dictionaries (but keep empty lists as they might be meaningful)
                if isinstance(cleaned_value, dict) and not cleaned_value:
                    continue
                
                result[key] = cleaned_value
            
            return result
        elif isinstance(data, list):
            # Clean list items but preserve the list structure
            result = []
            for item in data:
                cleaned_item = self._remove_null_values(item)
                # Only skip None items, keep other falsy values like empty strings or 0
                if cleaned_item is not None:
                    result.append(cleaned_item)
            return result
        else:
            # Return primitive values as-is (including empty strings, 0, False)
            return data
    
    def _validate_merged_configuration(self, config: Dict[str, Any]) -> bool:
        """
        Validate that a merged configuration is valid.
        
        Args:
            config: Configuration to validate.
            
        Returns:
            True if configuration is valid, False otherwise.
        """
        try:
            # Check required fields
            if "version" not in config:
                logger.error("Configuration missing required 'version' field")
                return False
            
            # Validate version format
            version = config.get("version")
            if not isinstance(version, str) or not re.match(r'^\d+\.\d+$', version):
                logger.error(f"Invalid version format: {version}")
                return False
            
            # Validate packages structure if present
            if "packages" in config:
                if not self._validate_packages_structure(config["packages"]):
                    return False
            
            # Validate services structure if present
            if "services" in config:
                if not self._validate_services_structure(config["services"]):
                    return False
            
            # Validate directories structure if present
            if "directories" in config:
                if not self._validate_directories_structure(config["directories"]):
                    return False
            
            # Validate URLs structure if present
            if "urls" in config:
                if not self._validate_urls_structure(config["urls"]):
                    return False
            
            # Validate platforms if present
            if "platforms" in config:
                if not self._validate_platforms_structure(config["platforms"]):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating configuration: {e}")
            return False
    
    def _validate_packages_structure(self, packages: Any) -> bool:
        """Validate packages structure."""
        if not isinstance(packages, dict):
            logger.error("Packages must be a dictionary")
            return False
        
        for key, package in packages.items():
            if not isinstance(package, dict):
                logger.error(f"Package '{key}' must be a dictionary")
                return False
            
            # Validate required package fields
            if "name" not in package:
                logger.error(f"Package '{key}' missing required 'name' field")
                return False
        
        return True
    
    def _validate_services_structure(self, services: Any) -> bool:
        """Validate services structure."""
        if not isinstance(services, dict):
            logger.error("Services must be a dictionary")
            return False
        
        for key, service in services.items():
            if not isinstance(service, dict):
                logger.error(f"Service '{key}' must be a dictionary")
                return False
        
        return True
    
    def _validate_directories_structure(self, directories: Any) -> bool:
        """Validate directories structure."""
        if not isinstance(directories, dict):
            logger.error("Directories must be a dictionary")
            return False
        
        for key, directory in directories.items():
            if not isinstance(directory, dict):
                logger.error(f"Directory '{key}' must be a dictionary")
                return False
            
            # Validate path field if present
            if "path" in directory and not isinstance(directory["path"], str):
                logger.error(f"Directory '{key}' path must be a string")
                return False
        
        return True
    
    def _validate_urls_structure(self, urls: Any) -> bool:
        """Validate URLs structure."""
        if not isinstance(urls, dict):
            logger.error("URLs must be a dictionary")
            return False
        
        for key, url in urls.items():
            if url is not None and not isinstance(url, str):
                logger.error(f"URL '{key}' must be a string or null")
                return False
        
        return True
    
    def _validate_platforms_structure(self, platforms: Any) -> bool:
        """Validate platforms structure."""
        if not isinstance(platforms, list):
            logger.error("Platforms must be a list")
            return False
        
        for platform in platforms:
            if not isinstance(platform, str):
                logger.error(f"Platform '{platform}' must be a string")
                return False
        
        return True
    
    def apply_provider_overrides_only(
        self, 
        software_name: str, 
        provider: str, 
        repository_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate provider-specific configuration containing only overrides.
        
        This method creates a configuration that contains only the settings that
        differ from the defaults for a specific provider.
        
        Args:
            software_name: Name of the software to generate overrides for.
            provider: Provider name (e.g., 'apt', 'brew', 'winget').
            repository_data: Optional repository data to determine provider support.
            
        Returns:
            Dictionary containing only provider-specific overrides and metadata.
        """
        # Check if provider is supported
        is_supported = self.is_provider_supported(software_name, provider, repository_data)
        
        # Start with base metadata structure
        result = {
            "version": "0.1"
        }
        
        # Only add supported field if it's false
        if not is_supported:
            result["supported"] = False
            return result
        
        # Get provider template if it exists
        if provider in self.provider_templates:
            provider_template = self._deep_copy(self.provider_templates[provider])
            
            # Process the provider template with context
            context = {
                "software_name": software_name,
                "current_provider": provider,
                "providers": [provider],
                "platforms": []
            }
            
            # Add repository data to context if available
            if repository_data:
                context.update(repository_data)
            
            # Process the template
            processed_template = self._process_template(provider_template, context)
            
            # Remove null values and empty structures
            processed_template = self._remove_null_values(processed_template)
            
            # Merge with result
            result = self._deep_merge(result, processed_template)
        
        return result

    def _filter_overrides_only(
        self, 
        provider_config: Dict[str, Any], 
        defaults: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Filter provider configuration to contain only overrides that differ from defaults.
        
        Args:
            provider_config: Full provider configuration
            defaults: Default configuration to compare against
            context: Template context for processing defaults
            
        Returns:
            Configuration containing only meaningful overrides
        """
        # Process defaults with the same context to ensure fair comparison
        processed_defaults = self._process_template(self._deep_copy(defaults), context)
        processed_defaults = self._remove_null_values(processed_defaults)
        
        # Start with version and supported status
        result = {
            "version": provider_config.get("version", "0.1")
        }
        
        # Check if explicitly marked as unsupported
        if provider_config.get("supported") is False:
            result["supported"] = False
            return result
        
        # Recursively compare and extract only differences
        overrides = self._extract_deep_differences(provider_config, processed_defaults, is_top_level=True)
        
        # Merge the overrides into the result (excluding version which is already handled)
        for key, value in overrides.items():
            if key != "version":
                result[key] = value
        
        return result
    
    def _extract_deep_differences(
        self, 
        provider_config: Dict[str, Any], 
        defaults: Dict[str, Any],
        is_top_level: bool = True
    ) -> Dict[str, Any]:
        """
        Extract deep differences between provider config and defaults.
        
        Args:
            provider_config: Provider configuration
            defaults: Default configuration
            is_top_level: Whether this is the top-level call (to handle version field)
            
        Returns:
            Dictionary containing only the differences
        """
        differences = {}
        
        for key, value in provider_config.items():
            # Only skip version at the top level
            if key == "version" and is_top_level:
                continue  # Version is handled separately
            
            # Always include supported field if present and not default (only at top level)
            if key == "supported" and is_top_level:
                if value is not True:  # Only include if not the default True
                    differences[key] = value
                continue
            
            default_value = defaults.get(key)
            
            if isinstance(value, dict) and isinstance(default_value, dict):
                # Recursively compare nested dictionaries
                nested_differences = self._extract_deep_differences(value, default_value, is_top_level=False)
                if nested_differences:
                    differences[key] = nested_differences
            elif not self._values_equal(value, default_value):
                # Value differs from default, include it
                differences[key] = self._deep_copy(value)
            elif key not in defaults:
                # Key doesn't exist in defaults, include it
                differences[key] = self._deep_copy(value)
        
        return differences