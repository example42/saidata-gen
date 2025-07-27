"""Main CLI entry point for saidata-gen."""

import os
import sys
import logging
from pathlib import Path
from typing import List, Optional

import click
import yaml
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.panel import Panel
from rich.syntax import Syntax

from ..core.engine import SaidataEngine
from ..core.interfaces import GenerationOptions, BatchOptions
from ..core.exceptions import SaidataGenError

# Initialize rich console for better output formatting
console = Console()


def setup_logging(verbose: bool = False):
    """Set up logging configuration."""
    # Check environment variable for log level override
    env_log_level = os.getenv('SAIDATA_GEN_LOG_LEVEL', '').upper()
    if env_log_level in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
        level = getattr(logging, env_log_level)
    else:
        level = logging.DEBUG if verbose else logging.INFO
    
    # Check environment variable for log format override
    log_format = os.getenv('SAIDATA_GEN_LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    logging.basicConfig(
        level=level,
        format=log_format
    )


def format_metadata_output(metadata, output_format: str = "yaml") -> str:
    """Format metadata for output."""
    # Convert dataclass to dict for serialization
    if hasattr(metadata, '__dict__'):
        from dataclasses import asdict
        metadata_dict = asdict(metadata)
    else:
        metadata_dict = metadata
    
    if output_format == "json":
        import json
        return json.dumps(metadata_dict, indent=2, default=str)
    else:
        return yaml.dump(metadata_dict, default_flow_style=False, sort_keys=False)


def save_metadata_to_file(metadata, file_path: Path, output_format: str = "yaml"):
    """Save metadata to file."""
    content = format_metadata_output(metadata, output_format)
    file_path.write_text(content)


def display_validation_result(result, file_path: str):
    """Display validation result with rich formatting."""
    if result.valid:
        console.print(f"✅ [green]{file_path}[/green] is valid")
    else:
        console.print(f"❌ [red]{file_path}[/red] has validation errors:")
        for issue in result.issues:
            level_color = {
                "error": "red",
                "warning": "yellow", 
                "info": "blue"
            }.get(issue.level.value, "white")
            console.print(f"  [{level_color}]{issue.level.value.upper()}[/{level_color}]: {issue.message}")
            if issue.path:
                console.print(f"    Path: {issue.path}")


def display_search_results(matches: List, query: str):
    """Display search results in a formatted table."""
    if not matches:
        console.print(f"[yellow]No packages found for:[/yellow] {query}")
        return
    
    table = Table(title=f"Search Results for '{query}'")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Provider", style="magenta")
    table.add_column("Version", style="green")
    table.add_column("Description", style="white")
    table.add_column("Score", style="yellow", justify="right")
    
    for match in matches:
        table.add_row(
            match.name,
            match.provider,
            match.version or "N/A",
            (match.description or "No description")[:50] + ("..." if len(match.description or "") > 50 else ""),
            f"{match.score:.2f}"
        )
    
    console.print(table)


def display_batch_results(results, show_details: bool = False):
    """Display batch processing results."""
    total = len(results.results)
    successful = sum(1 for r in results.results.values() if not isinstance(r, Exception))
    failed = total - successful
    
    # Summary panel
    summary_text = f"Total: {total}\nSuccessful: {successful}\nFailed: {failed}"
    if hasattr(results, 'summary') and results.summary:
        for key, value in results.summary.items():
            if key not in ['total', 'successful', 'failed']:
                summary_text += f"\n{key.title()}: {value}"
    
    console.print(Panel(summary_text, title="Batch Processing Summary", border_style="blue"))
    
    if show_details:
        # Show successful packages
        if successful > 0:
            console.print("\n[green]Successful packages:[/green]")
            for name, result in results.results.items():
                if not isinstance(result, Exception):
                    console.print(f"  ✅ {name}")
    
    if failed > 0:
        console.print("\n[red]Failed packages:[/red]")
        for name, result in results.results.items():
            if isinstance(result, Exception):
                console.print(f"  ❌ {name}: {str(result)}")
    
    # CI/CD friendly output
    if os.getenv('CI') or os.getenv('GITHUB_ACTIONS') or os.getenv('JENKINS_URL'):
        console.print(f"\n::set-output name=total::{total}")
        console.print(f"::set-output name=successful::{successful}")
        console.print(f"::set-output name=failed::{failed}")
        if failed > 0:
            console.print(f"::error::Batch processing failed for {failed} packages")


# Global options that apply to all commands
@click.group()
@click.option('--config', '-c', type=click.Path(), 
              default=lambda: os.getenv('SAIDATA_GEN_CONFIG'),
              help='Path to configuration file (env: SAIDATA_GEN_CONFIG)')
@click.option('--verbose', '-v', is_flag=True, 
              help='Enable verbose logging (env: SAIDATA_GEN_VERBOSE)')
@click.pass_context
def cli(ctx, config, verbose):
    """
    Generate, validate, and manage saidata YAML files.
    
    saidata-gen is a comprehensive tool for creating software metadata files
    that conform to the saidata-0.1.schema.json specification.
    
    \b
    Examples:
    
      # Generate metadata for nginx
      saidata-gen generate nginx
      
      # Generate with specific providers
      saidata-gen generate nginx --providers apt,brew,docker
      
      # Search for web servers
      saidata-gen search "web server"
      
      # Validate a metadata file
      saidata-gen validate nginx.yaml
      
      # Process multiple packages
      saidata-gen batch --input software_list.txt
    """
    ctx.ensure_object(dict)
    ctx.obj['config'] = config
    
    # Apply environment variable for verbose if not provided via CLI
    if not verbose and os.getenv('SAIDATA_GEN_VERBOSE', '').lower() in ['true', '1', 'yes']:
        verbose = True
    
    ctx.obj['verbose'] = verbose
    setup_logging(verbose)


@cli.command()
@click.argument('software_name')
@click.option('--providers', '-p', 
              default=lambda: os.getenv('SAIDATA_GEN_PROVIDERS'),
              help='Comma-separated list of providers (apt,brew,winget,npm,pypi,cargo,etc.) (env: SAIDATA_GEN_PROVIDERS)')
@click.option('--ai', is_flag=True, 
              help='Enable AI enhancement for metadata generation (env: SAIDATA_GEN_AI)')
@click.option('--ai-provider', default='openai', type=click.Choice(['openai', 'anthropic', 'local']), 
              help='AI provider to use for enhancement (env: SAIDATA_GEN_AI_PROVIDER)')
@click.option('--use-rag', is_flag=True, 
              help='Use RAG for enhanced metadata generation (deprecated: use --ai) (env: SAIDATA_GEN_USE_RAG)')
@click.option('--rag-provider', default='openai', type=click.Choice(['openai', 'anthropic', 'local']), 
              help='RAG provider to use (deprecated: use --ai-provider) (env: SAIDATA_GEN_RAG_PROVIDER)')
@click.option('--no-validate', is_flag=True, 
              default=lambda: os.getenv('SAIDATA_GEN_NO_VALIDATE', '').lower() in ['true', '1', 'yes'],
              help='Skip schema validation (env: SAIDATA_GEN_NO_VALIDATE)')
@click.option('--format', '-f', default='yaml', type=click.Choice(['yaml', 'json']), 
              help='Output format')
@click.option('--output', '-o', type=click.Path(), 
              default=lambda: os.getenv('SAIDATA_GEN_OUTPUT'),
              help='Output file path (env: SAIDATA_GEN_OUTPUT)')
@click.option('--confidence-threshold', default=0.7, type=float, 
              help='Minimum confidence threshold for generated data (env: SAIDATA_GEN_CONFIDENCE_THRESHOLD)')
@click.option('--directory-structure', is_flag=True,
              help='Generate software-specific directory structure with defaults.yaml and provider overrides')
@click.option('--comprehensive', is_flag=True,
              help='Generate comprehensive metadata file with all provider information merged')
@click.pass_context
def generate(ctx, software_name, providers, ai, ai_provider, use_rag, rag_provider, no_validate, format, output, confidence_threshold, directory_structure, comprehensive):
    """
    Generate metadata for a software package.
    
    This command generates comprehensive saidata YAML metadata for the specified
    software by gathering information from multiple package repositories and sources.
    
    AI Enhancement:
      The --ai flag enables AI-powered metadata enhancement using LLMs to fill
      missing fields and improve data quality. AI enhancement works by:
      - Identifying missing or incomplete metadata fields
      - Using LLMs to generate descriptions, categorizations, and URLs
      - Merging AI-generated data with repository data (repository data takes precedence)
      - Providing confidence scores for AI-enhanced fields
    
    Environment Variables:
      SAIDATA_GEN_AI: Enable AI enhancement by default (true/false)
      SAIDATA_GEN_AI_PROVIDER: Default AI provider (openai/anthropic/local)
      SAIDATA_GEN_PROVIDERS: Default providers list
      SAIDATA_GEN_OUTPUT: Default output file path
      SAIDATA_GEN_NO_VALIDATE: Skip validation by default (true/false)
      SAIDATA_GEN_FORMAT: Default output format (yaml/json)
      SAIDATA_GEN_CONFIDENCE_THRESHOLD: Default confidence threshold (0.0-1.0)
    
    Examples:
    
      # Basic generation
      saidata-gen generate nginx
      
      # Use specific providers
      saidata-gen generate nginx --providers apt,brew,docker
      
      # Generate with AI enhancement
      saidata-gen generate nginx --ai --ai-provider openai
      
      # Generate with AI using Anthropic
      saidata-gen generate nginx --ai --ai-provider anthropic
      
      # Generate with local AI model
      saidata-gen generate nginx --ai --ai-provider local
      
      # Save to specific file
      saidata-gen generate nginx --output nginx.yaml
      
      # Generate as JSON with AI enhancement
      saidata-gen generate nginx --format json --ai
      
      # Generate directory structure with provider overrides
      saidata-gen generate nginx --directory-structure
      
      # Generate directory structure in specific location
      saidata-gen generate nginx --directory-structure --output ./generated/
      
      # Generate comprehensive metadata file with all provider info
      saidata-gen generate nginx --comprehensive
      
      # Generate comprehensive file with specific name
      saidata-gen generate nginx --comprehensive --output nginx_full.yaml
      
      # Use environment variables
      export SAIDATA_GEN_AI=true
      export SAIDATA_GEN_AI_PROVIDER=anthropic
      saidata-gen generate nginx
    """
    try:
        # Apply environment variable defaults only if not provided via CLI
        if not providers and os.getenv('SAIDATA_GEN_PROVIDERS'):
            providers = os.getenv('SAIDATA_GEN_PROVIDERS')
        
        # Handle AI enhancement options with environment variables
        if not ai and os.getenv('SAIDATA_GEN_AI', '').lower() in ['true', '1', 'yes']:
            ai = True
        if ai_provider == 'openai' and os.getenv('SAIDATA_GEN_AI_PROVIDER'):
            ai_provider = os.getenv('SAIDATA_GEN_AI_PROVIDER')
        
        # Backward compatibility: handle deprecated RAG options
        if not use_rag and os.getenv('SAIDATA_GEN_USE_RAG', '').lower() in ['true', '1', 'yes']:
            use_rag = True
        if rag_provider == 'openai' and os.getenv('SAIDATA_GEN_RAG_PROVIDER'):
            rag_provider = os.getenv('SAIDATA_GEN_RAG_PROVIDER')
        
        # If deprecated RAG options are used, map them to new AI options
        if use_rag and not ai:
            ai = True
            console.print("[yellow]Warning: --use-rag is deprecated, use --ai instead[/yellow]")
        if use_rag and ai_provider == 'openai' and rag_provider != 'openai':
            ai_provider = rag_provider
            console.print("[yellow]Warning: --rag-provider is deprecated, use --ai-provider instead[/yellow]")
        
        # Use Click context to check if format was provided explicitly
        if ctx.get_parameter_source('format') == click.core.ParameterSource.DEFAULT and os.getenv('SAIDATA_GEN_FORMAT'):
            format = os.getenv('SAIDATA_GEN_FORMAT')
        if not output and os.getenv('SAIDATA_GEN_OUTPUT'):
            output = os.getenv('SAIDATA_GEN_OUTPUT')
        if confidence_threshold == 0.7 and os.getenv('SAIDATA_GEN_CONFIDENCE_THRESHOLD'):
            confidence_threshold = float(os.getenv('SAIDATA_GEN_CONFIDENCE_THRESHOLD'))
        
        engine = SaidataEngine(config_path=ctx.obj['config'])
        
        # Determine provider list - validate if specified, discover if not
        if providers:
            provider_list = providers.split(',')
            console.print(f"Validating {len(provider_list)} specified providers...")
            available_providers = engine.get_available_providers()
            invalid_providers = []
            
            for provider in provider_list:
                if provider not in available_providers:
                    invalid_providers.append(provider)
                elif not available_providers[provider].get('has_template', False):
                    console.print(f"[yellow]Warning:[/yellow] Provider '{provider}' has no template available")
            
            if invalid_providers:
                console.print(f"[red]Error:[/red] Invalid providers specified: {', '.join(invalid_providers)}")
                console.print("Use 'saidata-gen list-providers' to see available providers")
                sys.exit(1)
            
            console.print(f"✓ All {len(provider_list)} providers are valid")
        else:
            # Auto-discover available providers
            provider_list = engine.get_default_providers()
            console.print(f"Auto-discovered {len(provider_list)} available providers")
            if ctx.obj['verbose']:
                console.print(f"Using providers: {', '.join(provider_list)}")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Generating metadata for {software_name}...", total=None)
            
            options = GenerationOptions(
                providers=provider_list,
                use_rag=ai,  # Map new AI flag to use_rag for backward compatibility
                rag_provider=ai_provider,  # Map new AI provider to rag_provider
                validate_schema=not no_validate,
                output_format=format,
                confidence_threshold=confidence_threshold
            )
            
            if directory_structure:
                # Generate directory structure
                output_dir = output or str(Path.cwd())
                result = engine.generate_metadata_with_directory_structure(software_name, output_dir, options)
                progress.update(task, completed=True)
                
                # Display results
                console.print(f"✅ Directory structure generated at: [cyan]{result['software_dir']}[/cyan]")
                console.print(f"   📄 Defaults file: [green]{result['defaults_file']}[/green]")
                
                if result['provider_files']:
                    console.print(f"   📁 Provider files ({len(result['provider_files'])}):")
                    for provider, file_path in result['provider_files'].items():
                        console.print(f"      - {provider}: [blue]{file_path}[/blue]")
                else:
                    console.print("   📁 No provider override files generated")
                
                if result.get('skipped_providers'):
                    console.print(f"   ⏭️  Skipped providers ({len(result['skipped_providers'])}):")
                    for provider, reason in result['skipped_providers'].items():
                        console.print(f"      - {provider}: [yellow]{reason}[/yellow]")
                
                # Display validation result if validation was performed
                if result.get('validation_result') and not no_validate:
                    display_validation_result(result['validation_result'], result['defaults_file'])
                
                # Display confidence scores if available
                if result.get('confidence_scores'):
                    console.print("\n[bold]Confidence Scores:[/bold]")
                    for field, score in result['confidence_scores'].items():
                        color = "green" if score >= 0.8 else "yellow" if score >= 0.6 else "red"
                        console.print(f"  {field}: [{color}]{score:.2f}[/{color}]")
            elif comprehensive:
                # Generate comprehensive metadata file
                output_path = output or f"{software_name}_comprehensive.yaml"
                result = engine.generate_comprehensive_metadata_file(software_name, output_path, options)
                progress.update(task, completed=True)
                
                # Display results
                console.print(f"✅ Comprehensive metadata generated: [cyan]{result['comprehensive_file']}[/cyan]")
                console.print(f"   📊 Providers processed: [green]{result['provider_count']}[/green]")
                
                # Display validation result if validation was performed
                if result.get('validation_result') and not no_validate:
                    display_validation_result(result['validation_result'], result['comprehensive_file'])
                
                # Display confidence scores if available
                if result.get('confidence_scores'):
                    console.print("\n[bold]Confidence Scores:[/bold]")
                    for field, score in result['confidence_scores'].items():
                        color = "green" if score >= 0.8 else "yellow" if score >= 0.6 else "red"
                        console.print(f"  {field}: [{color}]{score:.2f}[/{color}]")
            else:
                # Generate single metadata file (existing behavior)
                result = engine.generate_metadata(software_name, options)
                progress.update(task, completed=True)
                
                # Handle output
                if output:
                    output_path = Path(output)
                    save_metadata_to_file(result.metadata, output_path, format)
                    console.print(f"✅ Metadata generated and saved to: [cyan]{output_path}[/cyan]")
                else:
                    # Display to stdout with syntax highlighting
                    content = format_metadata_output(result.metadata, format)
                    syntax = Syntax(content, format, theme="monokai", line_numbers=True)
                    console.print(Panel(syntax, title=f"Generated Metadata for {software_name}", border_style="green"))
                
                # Display validation result if validation was performed
                if result.validation_result and not no_validate:
                    display_validation_result(result.validation_result, output or f"{software_name}.{format}")
                
                # Display confidence scores if available
                if result.confidence_scores:
                    console.print("\n[bold]Confidence Scores:[/bold]")
                    for field, score in result.confidence_scores.items():
                        color = "green" if score >= 0.8 else "yellow" if score >= 0.6 else "red"
                        console.print(f"  {field}: [{color}]{score:.2f}[/{color}]")
        
    except SaidataGenError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        if ctx.obj['verbose']:
            console.print_exception()
        sys.exit(1)


@cli.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--detailed', '-d', is_flag=True, help='Show detailed validation information')
@click.pass_context
def validate(ctx, file_path, detailed):
    """
    Validate a metadata file against the saidata schema.
    
    This command validates YAML or JSON metadata files to ensure they conform
    to the saidata-0.1.schema.json specification.
    
    Examples:
    
      # Basic validation
      saidata-gen validate nginx.yaml
      
      # Detailed validation output
      saidata-gen validate nginx.yaml --detailed
    """
    try:
        engine = SaidataEngine(config_path=ctx.obj['config'])
        result = engine.validate_metadata(file_path)
        
        display_validation_result(result, file_path)
        
        if detailed and result.issues:
            console.print("\n[bold]Detailed Issues:[/bold]")
            for i, issue in enumerate(result.issues, 1):
                console.print(f"\n{i}. {issue.message}")
                if issue.path:
                    console.print(f"   Field path: {issue.path}")
                if issue.schema_path:
                    console.print(f"   Schema path: {issue.schema_path}")
        
        sys.exit(0 if result.valid else 1)
        
    except SaidataGenError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        if ctx.obj['verbose']:
            console.print_exception()
        sys.exit(1)


@cli.command()
@click.argument('directory_path', type=click.Path(exists=True))
@click.option('--cleanup', is_flag=True, help='Remove empty or redundant provider files')
@click.option('--format', 'format_files', is_flag=True, help='Ensure formatting consistency')
@click.option('--detailed', '-d', is_flag=True, help='Show detailed validation information')
@click.pass_context
def validate_structure(ctx, directory_path, cleanup, format_files, detailed):
    """
    Validate a generated directory structure.
    
    This command validates directory structures created with --directory-structure
    and optionally performs cleanup and formatting operations.
    
    Examples:
    
      # Basic validation
      saidata-gen validate-structure nginx/
      
      # Validate with cleanup and formatting
      saidata-gen validate-structure nginx/ --cleanup --format
      
      # Detailed validation output
      saidata-gen validate-structure nginx/ --detailed
    """
    try:
        engine = SaidataEngine(config_path=ctx.obj['config'])
        result = engine.validate_and_cleanup_directory_structure(
            directory_path, 
            cleanup=cleanup, 
            format_files=format_files
        )
        
        # Display validation results
        validation = result["validation"]
        if validation["valid"]:
            console.print(f"✅ [green]Directory structure is valid[/green]: {directory_path}")
        else:
            console.print(f"❌ [red]Directory structure has issues[/red]: {directory_path}")
        
        if validation["issues"]:
            console.print("\n[red]Issues found:[/red]")
            for issue in validation["issues"]:
                console.print(f"  • {issue}")
        
        if validation["warnings"]:
            console.print("\n[yellow]Warnings:[/yellow]")
            for warning in validation["warnings"]:
                console.print(f"  • {warning}")
        
        # Display cleanup results
        if cleanup and result["cleanup"]:
            cleanup_result = result["cleanup"]
            if cleanup_result["removed_files"]:
                console.print(f"\n🧹 [blue]Cleanup completed[/blue]: removed {len(cleanup_result['removed_files'])} files")
                if detailed:
                    for removed_file in cleanup_result["removed_files"]:
                        console.print(f"  - Removed: {removed_file}")
            
            if cleanup_result["errors"]:
                console.print("\n[red]Cleanup errors:[/red]")
                for error in cleanup_result["errors"]:
                    console.print(f"  • {error}")
        
        # Display formatting results
        if format_files and result["formatting"]:
            formatting_result = result["formatting"]
            if formatting_result["formatted_files"]:
                console.print(f"\n📝 [blue]Formatting completed[/blue]: formatted {len(formatting_result['formatted_files'])} files")
                if detailed:
                    for formatted_file in formatting_result["formatted_files"]:
                        console.print(f"  - Formatted: {formatted_file}")
            
            if formatting_result["errors"]:
                console.print("\n[red]Formatting errors:[/red]")
                for error in formatting_result["errors"]:
                    console.print(f"  • {error}")
        
        sys.exit(0 if validation["valid"] else 1)
        
    except SaidataGenError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        if ctx.obj['verbose']:
            console.print_exception()
        sys.exit(1)


@cli.command()
@click.argument('query')
@click.option('--providers', '-p', help='Comma-separated list of providers to search')
@click.option('--limit', '-l', default=20, help='Maximum number of results to display')
@click.option('--min-score', default=0.0, type=float, help='Minimum match score threshold')
@click.pass_context
def search(ctx, query, providers, limit, min_score):
    """
    Search for software packages across multiple repositories.
    
    This command searches for software packages using fuzzy matching across
    multiple package repositories and displays detailed results.
    
    Examples:
    
      # Basic search
      saidata-gen search "web server"
      
      # Search specific providers
      saidata-gen search nginx --providers apt,brew
      
      # Limit results and set minimum score
      saidata-gen search python --limit 10 --min-score 0.5
    """
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Searching for '{query}'...", total=None)
            
            engine = SaidataEngine(config_path=ctx.obj['config'])
            matches = engine.search_software(query)
            progress.update(task, completed=True)
        
        # Filter results
        if providers:
            provider_list = providers.split(',')
            matches = [m for m in matches if m.provider in provider_list]
        
        matches = [m for m in matches if m.score >= min_score]
        matches = matches[:limit]
        
        display_search_results(matches, query)
        
    except SaidataGenError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        if ctx.obj['verbose']:
            console.print_exception()
        sys.exit(1)


@cli.command()
@click.option('--input', '-i', required=True, type=click.Path(exists=True), 
              default=lambda: os.getenv('SAIDATA_GEN_BATCH_INPUT'),
              help='Input file with software names (one per line) (env: SAIDATA_GEN_BATCH_INPUT)')
@click.option('--output', '-o', type=click.Path(), 
              default=lambda: os.getenv('SAIDATA_GEN_BATCH_OUTPUT'),
              help='Output directory for generated files (env: SAIDATA_GEN_BATCH_OUTPUT)')
@click.option('--providers', '-p', 
              default=lambda: os.getenv('SAIDATA_GEN_PROVIDERS'),
              help='Comma-separated list of providers to use (env: SAIDATA_GEN_PROVIDERS)')
@click.option('--ai', is_flag=True, 
              help='Enable AI enhancement for metadata generation (env: SAIDATA_GEN_AI)')
@click.option('--ai-provider', default='openai', type=click.Choice(['openai', 'anthropic', 'local']),
              help='AI provider to use for enhancement (env: SAIDATA_GEN_AI_PROVIDER)')
@click.option('--use-rag', is_flag=True, 
              default=lambda: os.getenv('SAIDATA_GEN_USE_RAG', '').lower() in ['true', '1', 'yes'],
              help='Use RAG for enhanced generation (deprecated: use --ai) (env: SAIDATA_GEN_USE_RAG)')
@click.option('--rag-provider', default='openai', type=click.Choice(['openai', 'anthropic', 'local']),
              help='RAG provider to use (deprecated: use --ai-provider) (env: SAIDATA_GEN_RAG_PROVIDER)')
@click.option('--no-validate', is_flag=True, 
              default=lambda: os.getenv('SAIDATA_GEN_NO_VALIDATE', '').lower() in ['true', '1', 'yes'],
              help='Skip schema validation (env: SAIDATA_GEN_NO_VALIDATE)')
@click.option('--format', '-f', default='yaml', type=click.Choice(['yaml', 'json']),
              help='Output format (env: SAIDATA_GEN_FORMAT)')
@click.option('--max-concurrent', default=5, type=int,
              help='Maximum concurrent processing (env: SAIDATA_GEN_MAX_CONCURRENT)')
@click.option('--continue-on-error/--no-continue-on-error', default=True, 
              help='Continue processing even if some packages fail (env: SAIDATA_GEN_CONTINUE_ON_ERROR)')
@click.option('--progress-format', default='rich', type=click.Choice(['rich', 'simple', 'json']),
              help='Progress reporting format (env: SAIDATA_GEN_PROGRESS_FORMAT)')
@click.option('--fail-fast', is_flag=True, 
              help='Stop processing on first failure (opposite of --continue-on-error)')
@click.option('--dry-run', is_flag=True, help='Show what would be processed without actually doing it')
@click.option('--show-details', is_flag=True, help='Show detailed results including successful packages')
@click.pass_context
def batch(ctx, input, output, providers, ai, ai_provider, use_rag, rag_provider, no_validate, format, max_concurrent, 
          continue_on_error, progress_format, fail_fast, dry_run, show_details):
    """
    Process multiple software packages in batch.
    
    This command processes a list of software packages from a file and generates
    metadata for each one. It supports parallel processing and detailed progress reporting.
    
    AI Enhancement:
      The --ai flag enables AI-powered metadata enhancement for all packages in the batch.
      This can significantly improve metadata quality but may increase processing time.
    
    Environment Variables:
      SAIDATA_GEN_BATCH_INPUT: Default input file path
      SAIDATA_GEN_BATCH_OUTPUT: Default output directory
      SAIDATA_GEN_PROVIDERS: Default providers list
      SAIDATA_GEN_AI: Enable AI enhancement by default (true/false)
      SAIDATA_GEN_AI_PROVIDER: Default AI provider (openai/anthropic/local)
      SAIDATA_GEN_USE_RAG: Enable RAG by default (deprecated: use SAIDATA_GEN_AI)
      SAIDATA_GEN_MAX_CONCURRENT: Default concurrency level
      SAIDATA_GEN_PROGRESS_FORMAT: Progress format (rich/simple/json)
    
    Examples:
    
      # Basic batch processing
      saidata-gen batch --input software_list.txt
      
      # Save to specific directory
      saidata-gen batch --input software_list.txt --output ./generated/
      
      # Use specific providers with AI enhancement
      saidata-gen batch --input software_list.txt --providers apt,brew --ai
      
      # Use AI with specific provider
      saidata-gen batch --input software_list.txt --ai --ai-provider anthropic
      
      # Process with custom concurrency
      saidata-gen batch --input software_list.txt --max-concurrent 10
      
      # CI/CD friendly with JSON progress
      saidata-gen batch --input software_list.txt --progress-format json
    
    Input file format:
      Each line should contain one software name. Lines starting with # are ignored.
      
      Example:
        nginx
        apache2
        # This is a comment
        mysql-server
    """
    try:
        # Apply environment variable defaults
        if not input and os.getenv('SAIDATA_GEN_BATCH_INPUT'):
            input = os.getenv('SAIDATA_GEN_BATCH_INPUT')
        if not output and os.getenv('SAIDATA_GEN_BATCH_OUTPUT'):
            output = os.getenv('SAIDATA_GEN_BATCH_OUTPUT')
        if not providers and os.getenv('SAIDATA_GEN_PROVIDERS'):
            providers = os.getenv('SAIDATA_GEN_PROVIDERS')
        
        # Handle AI enhancement options with environment variables
        if not ai and os.getenv('SAIDATA_GEN_AI', '').lower() in ['true', '1', 'yes']:
            ai = True
        if ai_provider == 'openai' and os.getenv('SAIDATA_GEN_AI_PROVIDER'):
            ai_provider = os.getenv('SAIDATA_GEN_AI_PROVIDER')
        
        # Backward compatibility: handle deprecated RAG options
        if os.getenv('SAIDATA_GEN_RAG_PROVIDER'):
            rag_provider = os.getenv('SAIDATA_GEN_RAG_PROVIDER')
        
        # If deprecated RAG options are used, map them to new AI options
        if use_rag and not ai:
            ai = True
            console.print("[yellow]Warning: --use-rag is deprecated, use --ai instead[/yellow]")
        if use_rag and ai_provider == 'openai' and rag_provider != 'openai':
            ai_provider = rag_provider
            console.print("[yellow]Warning: --rag-provider is deprecated, use --ai-provider instead[/yellow]")
        
        if os.getenv('SAIDATA_GEN_FORMAT'):
            format = os.getenv('SAIDATA_GEN_FORMAT')
        if os.getenv('SAIDATA_GEN_MAX_CONCURRENT'):
            max_concurrent = int(os.getenv('SAIDATA_GEN_MAX_CONCURRENT'))
        if os.getenv('SAIDATA_GEN_PROGRESS_FORMAT'):
            progress_format = os.getenv('SAIDATA_GEN_PROGRESS_FORMAT')
        
        # Handle fail-fast option
        if fail_fast:
            continue_on_error = False
        
        # Read software list from file
        input_path = Path(input)
        software_list = []
        
        with open(input_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if line and not line.startswith('#'):
                    software_list.append(line)
        
        if not software_list:
            console.print("[red]Error:[/red] No software names found in input file")
            sys.exit(1)
        
        # Dry run mode
        if dry_run:
            console.print(f"[yellow]DRY RUN:[/yellow] Would process {len(software_list)} packages:")
            for pkg in software_list:
                console.print(f"  - {pkg}")
            console.print(f"\nOutput directory: {output or Path.cwd()}")
            console.print(f"Providers: {providers or 'all'}")
            console.print(f"Format: {format}")
            console.print(f"Max concurrent: {max_concurrent}")
            console.print(f"Continue on error: {continue_on_error}")
            return
        
        if progress_format != 'json':
            console.print(f"Found {len(software_list)} software packages to process")
        
        # Set up output directory
        output_dir = Path(output) if output else Path.cwd()
        if output:
            output_dir.mkdir(parents=True, exist_ok=True)
        
        engine = SaidataEngine(config_path=ctx.obj['config'])
        
        # Determine provider list - validate if specified, discover if not
        if providers:
            provider_list = providers.split(',')
            if progress_format != 'json':
                console.print(f"Validating {len(provider_list)} specified providers...")
            available_providers = engine.get_available_providers()
            invalid_providers = []
            
            for provider in provider_list:
                if provider not in available_providers:
                    invalid_providers.append(provider)
                elif not available_providers[provider].get('has_template', False):
                    if progress_format != 'json':
                        console.print(f"[yellow]Warning:[/yellow] Provider '{provider}' has no template available")
            
            if invalid_providers:
                if progress_format != 'json':
                    console.print(f"[red]Error:[/red] Invalid providers specified: {', '.join(invalid_providers)}")
                    console.print("Use 'saidata-gen list-providers' to see available providers")
                sys.exit(1)
            
            if progress_format != 'json':
                console.print(f"✓ All {len(provider_list)} providers are valid")
        else:
            # Auto-discover available providers
            provider_list = engine.get_default_providers()
            if progress_format != 'json':
                console.print(f"Auto-discovered {len(provider_list)} available providers")
        
        options = BatchOptions(
            output_dir=str(output_dir),
            providers=provider_list,
            use_rag=ai,  # Map new AI flag to use_rag for backward compatibility
            rag_provider=ai_provider,  # Map new AI provider to rag_provider
            validate_schema=not no_validate,
            output_format=format,
            max_concurrent=max_concurrent,
            continue_on_error=continue_on_error
        )
        
        # Progress reporting based on format
        if progress_format == 'json':
            # JSON progress for CI/CD - suppress other output
            import json
            
            progress_data = {
                "status": "started",
                "total": len(software_list),
                "processed": 0,
                "successful": 0,
                "failed": 0
            }
            print(json.dumps(progress_data))
            
            results = engine.batch_process(software_list, options)
            
            # Final JSON output
            successful = sum(1 for r in results.results.values() if not isinstance(r, Exception))
            failed = len(software_list) - successful
            final_data = {
                "status": "completed",
                "total": len(software_list),
                "processed": len(software_list),
                "successful": successful,
                "failed": failed,
                "results": {
                    name: "success" if not isinstance(result, Exception) else str(result)
                    for name, result in results.results.items()
                }
            }
            print(json.dumps(final_data))
            
        elif progress_format == 'simple':
            # Simple text progress for basic terminals
            console.print(f"Processing {len(software_list)} packages...")
            results = engine.batch_process(software_list, options)
            console.print("Processing complete.")
            
        else:
            # Rich progress (default)
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                console=console
            ) as progress:
                task = progress.add_task("Processing packages...", total=len(software_list))
                
                results = engine.batch_process(software_list, options)
                progress.update(task, completed=len(software_list))
        
        if progress_format != 'json':
            display_batch_results(results, show_details)
        
        # CI/CD exit codes
        failed_count = sum(1 for r in results.results.values() if isinstance(r, Exception))
        if failed_count > 0:
            if not continue_on_error:
                if progress_format != 'json':
                    console.print(f"[red]Exiting with error code 1 due to {failed_count} failures[/red]")
                sys.exit(1)
            else:
                if progress_format != 'json':
                    console.print(f"[yellow]Warning: {failed_count} packages failed but continuing due to --continue-on-error[/yellow]")
        
    except SaidataGenError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        if ctx.obj['verbose']:
            console.print_exception()
        sys.exit(1)


@cli.command()
@click.option('--show-templates', is_flag=True, help='Show which providers have templates available')
@click.option('--show-fetchers', is_flag=True, help='Show which providers have fetchers available')
@click.option('--format', '-f', default='table', type=click.Choice(['table', 'list', 'json']), 
              help='Output format')
@click.pass_context
def list_providers(ctx, show_templates, show_fetchers, format):
    """
    List all available providers.
    
    This command shows all available package managers and providers that
    saidata-gen can work with, including their status and capabilities.
    
    Examples:
    
      # List all providers
      saidata-gen list-providers
      
      # Show template availability
      saidata-gen list-providers --show-templates
      
      # Show fetcher availability
      saidata-gen list-providers --show-fetchers
      
      # Output as JSON
      saidata-gen list-providers --format json
    """
    try:
        engine = SaidataEngine(config_path=ctx.obj['config'])
        provider_info = engine.get_available_providers()
        
        if format == 'json':
            import json
            print(json.dumps(provider_info, indent=2))
            return
        
        if format == 'list':
            for provider in sorted(provider_info.keys()):
                console.print(provider)
            return
        
        # Table format (default)
        table = Table(title="Available Providers")
        table.add_column("Provider", style="cyan", no_wrap=True)
        table.add_column("Type", style="magenta")
        
        if show_templates:
            table.add_column("Template", style="green")
        if show_fetchers:
            table.add_column("Fetcher", style="blue")
        
        table.add_column("Description", style="white")
        
        for provider, info in sorted(provider_info.items()):
            row = [
                provider,
                info.get('type', 'Unknown')
            ]
            
            if show_templates:
                has_template = "✅" if info.get('has_template', False) else "❌"
                row.append(has_template)
            
            if show_fetchers:
                has_fetcher = "✅" if info.get('has_fetcher', False) else "❌"
                row.append(has_fetcher)
            
            row.append(info.get('description', 'No description available'))
            
            table.add_row(*row)
        
        console.print(table)
        
    except SaidataGenError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        if ctx.obj['verbose']:
            console.print_exception()
        sys.exit(1)


@cli.command()
@click.option('--providers', '-p', help='Comma-separated list of providers to fetch (default: all)')
@click.option('--cache-dir', type=click.Path(), help='Cache directory for repository data')
@click.option('--force-refresh', is_flag=True, help='Force refresh of cached data')
@click.option('--show-stats', is_flag=True, help='Show detailed statistics')
@click.pass_context
def fetch(ctx, providers, cache_dir, force_refresh, show_stats):
    """
    Fetch repository data from package managers.
    
    This command fetches and caches repository metadata from various package
    managers to improve subsequent metadata generation performance.
    
    Examples:
    
      # Fetch from all providers
      saidata-gen fetch
      
      # Fetch from specific providers
      saidata-gen fetch --providers apt,brew,winget
      
      # Force refresh cached data
      saidata-gen fetch --force-refresh
      
      # Show detailed statistics
      saidata-gen fetch --show-stats
    """
    try:
        provider_list = providers.split(',') if providers else []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Fetching repository data...", total=None)
            
            engine = SaidataEngine(config_path=ctx.obj['config'])
            results = engine.fetch_repository_data(provider_list)
            progress.update(task, completed=True)
        
        # Display results
        table = Table(title="Repository Fetch Results")
        table.add_column("Provider", style="cyan")
        table.add_column("Status", style="white")
        table.add_column("Details", style="white")
        
        for provider, success in results.providers.items():
            if success:
                status = "✅ Success"
                details = "Data fetched successfully"
                if results.cache_hits.get(provider):
                    details += " (cached)"
            else:
                status = "❌ Failed"
                details = results.errors.get(provider, "Unknown error")
            
            table.add_row(provider, status, details)
        
        console.print(table)
        
        if show_stats:
            console.print(f"\n[bold]Statistics:[/bold]")
            console.print(f"Total providers: {len(results.providers)}")
            console.print(f"Successful: {sum(results.providers.values())}")
            console.print(f"Failed: {len(results.providers) - sum(results.providers.values())}")
            console.print(f"Cache hits: {sum(results.cache_hits.values())}")
        
        # Exit with error if any fetches failed
        if not results.success:
            sys.exit(1)
        
    except SaidataGenError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        if ctx.obj['verbose']:
            console.print_exception()
        sys.exit(1)


def main() -> int:
    """Main CLI entry point."""
    try:
        cli(standalone_mode=False)
        return 0
    except click.ClickException as e:
        e.show()
        return e.exit_code
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        return 130
    except SystemExit as e:
        return e.code
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        return 1


@cli.group()
def config():
    """Configuration management commands."""
    pass


@config.command('init')
@click.option('--config-dir', type=click.Path(), default='~/.saidata-gen',
              help='Configuration directory')
@click.option('--force', is_flag=True, help='Overwrite existing configuration')
@click.pass_context
def config_init(ctx, config_dir, force):
    """Initialize saidata-gen configuration."""
    try:
        config_path = Path(config_dir).expanduser()
        config_file = config_path / 'config.yaml'
        
        if config_file.exists() and not force:
            console.print(f"[yellow]Configuration already exists at {config_file}[/yellow]")
            console.print("Use --force to overwrite")
            return
        
        # Create config directory
        config_path.mkdir(parents=True, exist_ok=True)
        
        # Create default configuration
        default_config = {
            'providers': {
                'apt': {'enabled': True, 'cache_ttl': 3600},
                'brew': {'enabled': True, 'cache_ttl': 3600},
                'winget': {'enabled': True, 'cache_ttl': 3600},
                'npm': {'enabled': True, 'cache_ttl': 3600},
                'pypi': {'enabled': True, 'cache_ttl': 3600},
                'cargo': {'enabled': True, 'cache_ttl': 3600},
            },
            'cache': {
                'directory': str(config_path / 'cache'),
                'default_ttl': 3600,
                'max_size': '1GB'
            },
            'output': {
                'default_format': 'yaml',
                'validate_schema': True
            },
            'rag': {
                'enabled': False,
                'provider': 'openai',
                'model': 'gpt-3.5-turbo',
                'temperature': 0.1,
                'max_tokens': 1000
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
        
        console.print(f"✅ Configuration initialized at [cyan]{config_file}[/cyan]")
        console.print("\nNext steps:")
        console.print("1. Edit the configuration file to customize settings")
        console.print("2. Set up RAG API keys if needed:")
        console.print("   saidata-gen config rag --provider openai --api-key YOUR_KEY")
        console.print("3. Test the configuration:")
        console.print("   saidata-gen config validate")
        
    except Exception as e:
        console.print(f"[red]Error initializing configuration:[/red] {e}")
        sys.exit(1)


@config.command('show')
@click.option('--section', help='Show specific configuration section')
@click.pass_context
def config_show(ctx, section):
    """Show current configuration."""
    try:
        config_path = ctx.obj.get('config')
        if not config_path:
            config_path = Path('~/.saidata-gen/config.yaml').expanduser()
        else:
            config_path = Path(config_path)
        
        if not config_path.exists():
            console.print(f"[red]Configuration file not found:[/red] {config_path}")
            console.print("Run 'saidata-gen config init' to create it")
            sys.exit(1)
        
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        if section:
            if section in config_data:
                config_data = {section: config_data[section]}
            else:
                console.print(f"[red]Section '{section}' not found in configuration[/red]")
                sys.exit(1)
        
        # Display configuration with syntax highlighting
        config_yaml = yaml.dump(config_data, default_flow_style=False, sort_keys=False)
        syntax = Syntax(config_yaml, "yaml", theme="monokai", line_numbers=True)
        console.print(Panel(syntax, title=f"Configuration: {config_path}", border_style="blue"))
        
    except Exception as e:
        console.print(f"[red]Error reading configuration:[/red] {e}")
        sys.exit(1)


@config.command('validate')
@click.pass_context
def config_validate(ctx):
    """Validate configuration file."""
    try:
        config_path = ctx.obj.get('config')
        if not config_path:
            config_path = Path('~/.saidata-gen/config.yaml').expanduser()
        else:
            config_path = Path(config_path)
        
        if not config_path.exists():
            console.print(f"[red]Configuration file not found:[/red] {config_path}")
            console.print("Run 'saidata-gen config init' to create it")
            sys.exit(1)
        
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Validate configuration structure
        required_sections = ['providers', 'cache', 'output']
        issues = []
        
        for section in required_sections:
            if section not in config_data:
                issues.append(f"Missing required section: {section}")
        
        # Validate providers section
        if 'providers' in config_data:
            for provider, settings in config_data['providers'].items():
                if not isinstance(settings, dict):
                    issues.append(f"Provider '{provider}' settings must be a dictionary")
                elif 'enabled' not in settings:
                    issues.append(f"Provider '{provider}' missing 'enabled' setting")
        
        # Validate cache section
        if 'cache' in config_data:
            cache_config = config_data['cache']
            if 'directory' not in cache_config:
                issues.append("Cache section missing 'directory' setting")
            if 'default_ttl' not in cache_config:
                issues.append("Cache section missing 'default_ttl' setting")
        
        if issues:
            console.print(f"[red]Configuration validation failed:[/red]")
            for issue in issues:
                console.print(f"  ❌ {issue}")
            sys.exit(1)
        else:
            console.print(f"✅ Configuration is valid: [cyan]{config_path}[/cyan]")
        
    except yaml.YAMLError as e:
        console.print(f"[red]YAML syntax error in configuration:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error validating configuration:[/red] {e}")
        sys.exit(1)


@config.command('rag')
@click.option('--provider', type=click.Choice(['openai', 'anthropic', 'local']),
              help='RAG provider to configure')
@click.option('--api-key', help='API key for the provider')
@click.option('--model', help='Model to use')
@click.option('--base-url', help='Base URL for local providers')
@click.option('--enable/--disable', default=None, help='Enable or disable RAG')
@click.option('--test', is_flag=True, help='Test the RAG configuration')
@click.pass_context
def config_rag(ctx, provider, api_key, model, base_url, enable, test):
    """Configure RAG (Retrieval-Augmented Generation) settings."""
    try:
        config_path = ctx.obj.get('config')
        if not config_path:
            config_path = Path('~/.saidata-gen/config.yaml').expanduser()
        else:
            config_path = Path(config_path)
        
        if not config_path.exists():
            console.print(f"[red]Configuration file not found:[/red] {config_path}")
            console.print("Run 'saidata-gen config init' to create it")
            sys.exit(1)
        
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Ensure RAG section exists
        if 'rag' not in config_data:
            config_data['rag'] = {}
        
        rag_config = config_data['rag']
        
        # Update RAG configuration
        if provider:
            rag_config['provider'] = provider
        if api_key:
            rag_config['api_key'] = api_key
        if model:
            rag_config['model'] = model
        if base_url:
            rag_config['base_url'] = base_url
        if enable is not None:
            rag_config['enabled'] = enable
        
        # Test RAG configuration if requested
        if test:
            console.print("Testing RAG configuration...")
            
            if not rag_config.get('enabled', False):
                console.print("[yellow]RAG is disabled in configuration[/yellow]")
                return
            
            provider_name = rag_config.get('provider', 'openai')
            
            if provider_name == 'openai':
                if not rag_config.get('api_key'):
                    console.print("[red]OpenAI API key not configured[/red]")
                    sys.exit(1)
                console.print("✅ OpenAI configuration looks valid")
                
            elif provider_name == 'anthropic':
                if not rag_config.get('api_key'):
                    console.print("[red]Anthropic API key not configured[/red]")
                    sys.exit(1)
                console.print("✅ Anthropic configuration looks valid")
                
            elif provider_name == 'local':
                if not rag_config.get('base_url'):
                    console.print("[red]Base URL not configured for local provider[/red]")
                    sys.exit(1)
                console.print("✅ Local provider configuration looks valid")
            
            console.print("Note: This is a basic configuration check. Actual API connectivity is tested during generation.")
        
        # Save updated configuration
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
        
        console.print(f"✅ RAG configuration updated in [cyan]{config_path}[/cyan]")
        
        # Show current RAG configuration
        rag_yaml = yaml.dump({'rag': rag_config}, default_flow_style=False)
        syntax = Syntax(rag_yaml, "yaml", theme="monokai")
        console.print(Panel(syntax, title="Current RAG Configuration", border_style="green"))
        
    except Exception as e:
        console.print(f"[red]Error configuring RAG:[/red] {e}")
        sys.exit(1)


@config.command('providers')
@click.option('--enable', help='Enable specific providers (comma-separated)')
@click.option('--disable', help='Disable specific providers (comma-separated)')
@click.option('--list', 'list_providers', is_flag=True, help='List all available providers')
@click.pass_context
def config_providers(ctx, enable, disable, list_providers):
    """Configure package repository providers."""
    try:
        if list_providers:
            # List all available providers
            available_providers = [
                'apt', 'brew', 'winget', 'scoop', 'choco', 'nuget',
                'npm', 'yarn', 'pypi', 'conda', 'cargo', 'gem',
                'composer', 'maven', 'gradle', 'docker', 'helm',
                'snap', 'flatpak', 'pacman', 'apk', 'portage',
                'xbps', 'slackpkg', 'opkg', 'emerge', 'guix',
                'nix', 'nixpkgs', 'spack', 'pkg'
            ]
            
            table = Table(title="Available Package Repository Providers")
            table.add_column("Provider", style="cyan")
            table.add_column("Description", style="white")
            
            descriptions = {
                'apt': 'Debian/Ubuntu APT packages',
                'brew': 'Homebrew packages (macOS/Linux)',
                'winget': 'Windows Package Manager',
                'scoop': 'Scoop packages (Windows)',
                'choco': 'Chocolatey packages (Windows)',
                'nuget': '.NET NuGet packages',
                'npm': 'Node.js npm packages',
                'yarn': 'Yarn packages',
                'pypi': 'Python PyPI packages',
                'conda': 'Anaconda/Miniconda packages',
                'cargo': 'Rust Cargo packages',
                'gem': 'Ruby Gems',
                'composer': 'PHP Composer packages',
                'maven': 'Java Maven packages',
                'gradle': 'Gradle dependencies',
                'docker': 'Docker Hub images',
                'helm': 'Kubernetes Helm charts',
                'snap': 'Ubuntu Snap packages',
                'flatpak': 'Flatpak applications',
                'pacman': 'Arch Linux packages',
                'apk': 'Alpine Linux packages',
                'portage': 'Gentoo Portage packages',
                'xbps': 'Void Linux packages',
                'slackpkg': 'Slackware packages',
                'opkg': 'Embedded Linux packages',
                'emerge': 'Gentoo emerge tool',
                'guix': 'GNU Guix packages',
                'nix': 'Nix packages',
                'nixpkgs': 'Nixpkgs collection',
                'spack': 'HPC Spack packages',
                'pkg': 'FreeBSD packages'
            }
            
            for provider in available_providers:
                table.add_row(provider, descriptions.get(provider, 'Package repository'))
            
            console.print(table)
            return
        
        config_path = ctx.obj.get('config')
        if not config_path:
            config_path = Path('~/.saidata-gen/config.yaml').expanduser()
        else:
            config_path = Path(config_path)
        
        if not config_path.exists():
            console.print(f"[red]Configuration file not found:[/red] {config_path}")
            console.print("Run 'saidata-gen config init' to create it")
            sys.exit(1)
        
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        # Ensure providers section exists
        if 'providers' not in config_data:
            config_data['providers'] = {}
        
        providers_config = config_data['providers']
        
        # Enable providers
        if enable:
            for provider in enable.split(','):
                provider = provider.strip()
                if provider not in providers_config:
                    providers_config[provider] = {}
                providers_config[provider]['enabled'] = True
                console.print(f"✅ Enabled provider: {provider}")
        
        # Disable providers
        if disable:
            for provider in disable.split(','):
                provider = provider.strip()
                if provider in providers_config:
                    providers_config[provider]['enabled'] = False
                    console.print(f"❌ Disabled provider: {provider}")
        
        # Save updated configuration
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
        
        console.print(f"✅ Provider configuration updated in [cyan]{config_path}[/cyan]")
        
        # Show current provider status
        if providers_config:
            table = Table(title="Provider Status")
            table.add_column("Provider", style="cyan")
            table.add_column("Status", style="white")
            table.add_column("Cache TTL", style="yellow")
            
            for provider, settings in providers_config.items():
                enabled = settings.get('enabled', False)
                status = "✅ Enabled" if enabled else "❌ Disabled"
                ttl = str(settings.get('cache_ttl', 'default'))
                table.add_row(provider, status, ttl)
            
            console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error configuring providers:[/red] {e}")
        sys.exit(1)


if __name__ == '__main__':
    sys.exit(main())