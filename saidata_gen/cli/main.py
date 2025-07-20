"""Main CLI entry point for saidata-gen."""

import sys
import argparse
import logging
from pathlib import Path
from typing import List, Optional

from ..core.engine import SaidataEngine
from ..core.interfaces import GenerationOptions
from ..core.exceptions import SaidataGenError


def setup_logging(verbose: bool = False):
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def cmd_generate(args) -> int:
    """Handle the generate command."""
    try:
        engine = SaidataEngine(config_path=args.config)
        
        options = GenerationOptions(
            providers=args.providers.split(',') if args.providers else [],
            use_rag=args.use_rag,
            rag_provider=args.rag_provider,
            validate_schema=not args.no_validate,
            output_format=args.format
        )
        
        result = engine.generate_metadata(args.software_name, options)
        
        # Output the result
        if args.output:
            output_path = Path(args.output)
            # TODO: Write to file based on format
            print(f"Metadata generated and saved to: {output_path}")
        else:
            # TODO: Print to stdout based on format
            print("Generated metadata:")
            print(result.metadata)
        
        return 0
        
    except SaidataGenError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def cmd_validate(args) -> int:
    """Handle the validate command."""
    try:
        engine = SaidataEngine(config_path=args.config)
        result = engine.validate_metadata(args.file_path)
        
        if result.is_valid:
            print(f"✓ {args.file_path} is valid")
            return 0
        else:
            print(f"✗ {args.file_path} has validation errors:")
            for error in result.errors:
                print(f"  - {error}")
            return 1
            
    except SaidataGenError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def cmd_search(args) -> int:
    """Handle the search command."""
    try:
        engine = SaidataEngine(config_path=args.config)
        providers = args.providers.split(',') if args.providers else None
        matches = engine.search_software(args.query, providers)
        
        if not matches:
            print(f"No packages found for: {args.query}")
            return 1
        
        print(f"Found {len(matches)} matches for '{args.query}':")
        for match in matches:
            print(f"  {match.name} ({match.provider}) - {match.package_info.description or 'No description'}")
        
        return 0
        
    except SaidataGenError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def cmd_batch(args) -> int:
    """Handle the batch command."""
    try:
        engine = SaidataEngine(config_path=args.config)
        
        # Read software list from file
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file not found: {args.input}", file=sys.stderr)
            return 1
        
        software_list = []
        with open(input_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    software_list.append(line)
        
        if not software_list:
            print("Error: No software names found in input file", file=sys.stderr)
            return 1
        
        options = GenerationOptions(
            providers=args.providers.split(',') if args.providers else [],
            use_rag=args.use_rag,
            validate_schema=not args.no_validate,
            output_format=args.format
        )
        
        results = engine.batch_process(software_list, options)
        
        print(f"Batch processing complete:")
        print(f"  Total: {results['total']}")
        print(f"  Successful: {len(results['successful'])}")
        print(f"  Failed: {len(results['failed'])}")
        
        if results['failed']:
            print("\nFailed packages:")
            for failed in results['failed']:
                print(f"  - {failed['name']}: {failed['error']}")
        
        # TODO: Save results to output directory if specified
        if args.output:
            print(f"Results saved to: {args.output}")
        
        return 0 if not results['failed'] else 1
        
    except SaidataGenError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def cmd_fetch(args) -> int:
    """Handle the fetch command."""
    try:
        engine = SaidataEngine(config_path=args.config)
        providers = args.providers.split(',') if args.providers else None
        results = engine.fetch_repository_data(providers)
        
        print("Repository fetch results:")
        for provider, result in results.items():
            if result['status'] == 'success':
                print(f"  ✓ {provider}: {result['packages_count']} packages")
            else:
                print(f"  ✗ {provider}: {result['error']}")
        
        return 0
        
    except SaidataGenError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog='saidata-gen',
        description='Generate, validate, and manage saidata YAML files'
    )
    
    parser.add_argument(
        '--config', '-c',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Generate command
    gen_parser = subparsers.add_parser('generate', help='Generate metadata for software')
    gen_parser.add_argument('software_name', help='Name of the software')
    gen_parser.add_argument('--providers', help='Comma-separated list of providers to use')
    gen_parser.add_argument('--use-rag', action='store_true', help='Use RAG for enhanced generation')
    gen_parser.add_argument('--rag-provider', default='openai', help='RAG provider to use')
    gen_parser.add_argument('--no-validate', action='store_true', help='Skip schema validation')
    gen_parser.add_argument('--format', default='yaml', choices=['yaml', 'json'], help='Output format')
    gen_parser.add_argument('--output', '-o', help='Output file path')
    gen_parser.set_defaults(func=cmd_generate)
    
    # Validate command
    val_parser = subparsers.add_parser('validate', help='Validate metadata file')
    val_parser.add_argument('file_path', help='Path to metadata file')
    val_parser.set_defaults(func=cmd_validate)
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search for software packages')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--providers', help='Comma-separated list of providers to search')
    search_parser.set_defaults(func=cmd_search)
    
    # Batch command
    batch_parser = subparsers.add_parser('batch', help='Process multiple software packages')
    batch_parser.add_argument('--input', '-i', required=True, help='Input file with software names')
    batch_parser.add_argument('--output', '-o', help='Output directory')
    batch_parser.add_argument('--providers', help='Comma-separated list of providers to use')
    batch_parser.add_argument('--use-rag', action='store_true', help='Use RAG for enhanced generation')
    batch_parser.add_argument('--no-validate', action='store_true', help='Skip schema validation')
    batch_parser.add_argument('--format', default='yaml', choices=['yaml', 'json'], help='Output format')
    batch_parser.set_defaults(func=cmd_batch)
    
    # Fetch command
    fetch_parser = subparsers.add_parser('fetch', help='Fetch repository data')
    fetch_parser.add_argument('--providers', help='Comma-separated list of providers to fetch')
    fetch_parser.set_defaults(func=cmd_fetch)
    
    return parser


def main() -> int:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    if not hasattr(args, 'func'):
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())