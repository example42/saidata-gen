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
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Set, Callable

import yaml

from saidata_gen.core.interfaces import SaidataMetadata


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
    
    def __init__(self, templates_dir: Optional[str] = None):
        """
        Initialize the template engine.
        
        Args:
            templates_dir: Directory containing template files. If None, uses the default
                templates directory in the package.
        """
        if templates_dir is None:
            # Use the default templates directory in the package
            package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.templates_dir = os.path.join(package_dir, "templates")
        else:
            self.templates_dir = os.path.expanduser(templates_dir)
        
        # Create the templates directory if it doesn't exist
        os.makedirs(self.templates_dir, exist_ok=True)
        
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
        Load provider-specific templates.
        
        Returns:
            Dictionary mapping provider names to their templates.
        """
        provider_templates = {}
        providers_dir = os.path.join(self.templates_dir, "providers")
        
        # Create the providers directory if it doesn't exist
        os.makedirs(providers_dir, exist_ok=True)
        
        # Load templates from the providers directory
        if os.path.exists(providers_dir):
            for filename in os.listdir(providers_dir):
                if filename.endswith(".yaml") or filename.endswith(".yml"):
                    provider_name = os.path.splitext(filename)[0]
                    try:
                        with open(os.path.join(providers_dir, filename), 'r', encoding='utf-8') as f:
                            provider_templates[provider_name] = yaml.safe_load(f) or {}
                    except Exception as e:
                        logger.error(f"Failed to load provider template {filename}: {e}")
        
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
                                processed_body = self._process_template(self._deep_copy(loop_body), loop_context)
                                
                                # Merge the processed body into the result
                                if isinstance(processed_body, dict):
                                    result.update(processed_body)
                                elif isinstance(processed_body, list):
                                    if not isinstance(result, list):
                                        result = []
                                    result.extend(processed_body)
                                else:
                                    result[f"_loop_result_{len(result)}"] = processed_body
                    
                    # Skip to the endfor
                    skip_until = self.LOOP_ENDFOR
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
                                    args.append(self._parse_value(arg, context))
                        
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
                                else:
                                    # Otherwise, use it as a single arg
                                    args.append(self._parse_value(value, context))
                                
                                # Call the function
                                func_result = self.functions[func_name](*args, **kwargs)
                                
                                # Add the result to the output
                                if isinstance(func_result, dict):
                                    result.update(func_result)
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
            # Substitute simple variables like $variable_name
            result = data
            for var_name, var_value in context.items():
                if isinstance(var_value, (str, int, float, bool)):
                    result = result.replace(f"${var_name}", str(var_value))
            
            # Substitute complex expressions like ${variable.path | default_value}
            pattern = r'\${([^}]+)}'
            matches = re.findall(pattern, result)
            
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
            
            return result
        elif isinstance(data, dict):
            # Recursively substitute variables in dictionaries
            return {k: self._substitute_variables(v, context) for k, v in data.items()}
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
    
    def _deep_merge(self, base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries.
        
        Args:
            base: Base dictionary.
            overlay: Dictionary to overlay on top of the base.
            
        Returns:
            Merged dictionary.
        """
        result = self._deep_copy(base)
        
        for key, value in overlay.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge dictionaries
                result[key] = self._deep_merge(result[key], value)
            else:
                # Replace or add the value
                result[key] = self._deep_copy(value)
        
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
        
        elif " in " in condition:
            var_name, value = condition.split(" in ", 1)
            var_name = var_name.strip()
            value = value.strip()
            
            # Get the variable value from the context
            var_value = self._get_nested_value(context, var_name)
            
            # Handle list literals
            if value.startswith("[") and value.endswith("]"):
                try:
                    value_list = eval(value)
                    return var_value in value_list
                except Exception as e:
                    logger.error(f"Failed to evaluate list in condition: {e}")
                    return False
            
            # Handle context variables
            value_list = self._get_nested_value(context, value)
            if isinstance(value_list, (list, tuple, set)):
                return var_value in value_list
            
            return False
        
        elif " not in " in condition:
            var_name, value = condition.split(" not in ", 1)
            var_name = var_name.strip()
            value = value.strip()
            
            # Get the variable value from the context
            var_value = self._get_nested_value(context, var_name)
            
            # Handle list literals
            if value.startswith("[") and value.endswith("]"):
                try:
                    value_list = eval(value)
                    return var_value not in value_list
                except Exception as e:
                    logger.error(f"Failed to evaluate list in condition: {e}")
                    return False
            
            # Handle context variables
            value_list = self._get_nested_value(context, value)
            if isinstance(value_list, (list, tuple, set)):
                return var_value not in value_list
            
            # If value_list is not a list or is None, the condition is true
            # (since anything not in a non-existent list is true)
            return True
        
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