# CLI Reference

Complete reference for all saidata-gen command-line interface commands and options.

## Global Options

These options apply to all commands:

| Option | Short | Description | Environment Variable |
|--------|-------|-------------|---------------------|
| `--config` | `-c` | Path to configuration file | `SAIDATA_GEN_CONFIG` |
| `--verbose` | `-v` | Enable verbose logging | `SAIDATA_GEN_VERBOSE` |
| `--help` | `-h` | Show help message | - |
| `--version` | | Show version information | - |

## Commands

### `generate`

Generate metadata for a software package in structured directory format.

```bash
saidata-gen generate [OPTIONS] SOFTWARE_NAME
```

**Note**: The generate command now always creates a structured directory output with `$software/defaults.yaml` and `$software/providers/$provider.yaml` files. Provider-specific files are only created when they differ from the defaults in `provider_defaults.yaml`.

#### Arguments

- `SOFTWARE_NAME`: Name of the software package to generate metadata for

#### Options

| Option | Short | Type | Default | Description | Environment Variable |
|--------|-------|------|---------|-------------|---------------------|
| `--providers` | `-p` | TEXT | all | Comma-separated list of providers | `SAIDATA_GEN_PROVIDERS` |
| `--ai` | | FLAG | false | Enable AI enhancement for missing fields | `SAIDATA_GEN_AI` |
| `--ai-provider` | | CHOICE | openai | AI provider (openai/anthropic/local) | `SAIDATA_GEN_AI_PROVIDER` |

| `--enhancement-types` | | TEXT | all | AI enhancement types (description,categorization,field_completion) | `SAIDATA_GEN_ENHANCEMENT_TYPES` |
| `--no-validate` | | FLAG | false | Skip schema validation | `SAIDATA_GEN_NO_VALIDATE` |
| `--format` | `-f` | CHOICE | yaml | Output format (yaml/json) | `SAIDATA_GEN_FORMAT` |
| `--output` | `-o` | PATH | . | Output directory path | `SAIDATA_GEN_OUTPUT` |
| `--confidence-threshold` | | FLOAT | 0.7 | Minimum confidence threshold | `SAIDATA_GEN_CONFIDENCE_THRESHOLD` |

#### Output Structure

The generate command creates a structured directory:

```
nginx/                         # Created in current directory or --output path
├── defaults.yaml              # Software-specific base configuration
└── providers/                 # Provider-specific overrides (only when different from defaults)
    ├── apt.yaml              # Only created if apt config differs from provider_defaults.yaml
    ├── brew.yaml             # Only created if brew config differs from provider_defaults.yaml
    └── docker.yaml           # Only created if docker config differs from provider_defaults.yaml
```

#### Examples

```bash
# Basic generation (creates nginx/ directory)
saidata-gen generate nginx

# Use specific providers
saidata-gen generate nginx --providers apt,brew,docker

# Generate with AI enhancement (new recommended way)
saidata-gen generate nginx --ai --ai-provider openai

# AI enhancement with specific types
saidata-gen generate nginx --ai --enhancement-types description,field_completion

# Generate in specific directory
saidata-gen generate nginx --output ./generated/

# Generate with JSON format (affects defaults.yaml format)
saidata-gen generate nginx --format json

# Skip validation with custom confidence threshold
saidata-gen generate nginx --no-validate --confidence-threshold 0.8

# AI enhancement
saidata-gen generate nginx --ai --ai-provider anthropic
```

#### Exit Codes

- `0`: Success
- `1`: Generation error or validation failure
- `130`: Interrupted by user (Ctrl+C)

---

### `validate`

Validate a metadata file against the saidata schema.

```bash
saidata-gen validate [OPTIONS] FILE_PATH
```

#### Arguments

- `FILE_PATH`: Path to the metadata file to validate

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--detailed` | `-d` | Show detailed validation information |

#### Examples

```bash
# Validate main configuration file
saidata-gen validate nginx/defaults.yaml

# Validate provider-specific file
saidata-gen validate nginx/providers/apt.yaml

# Validate with detailed output
saidata-gen validate nginx/defaults.yaml --detailed

# Validate all files in directory
find nginx/ -name "*.yaml" -exec saidata-gen validate {} \;
```

#### Exit Codes

- `0`: File is valid
- `1`: File is invalid or validation error

---

### `search`

Search for software packages across multiple repositories.

```bash
saidata-gen search [OPTIONS] QUERY
```

#### Arguments

- `QUERY`: Search query string

#### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--providers` | `-p` | TEXT | all | Comma-separated list of providers to search |
| `--limit` | `-l` | INTEGER | 20 | Maximum number of results to display |
| `--min-score` | | FLOAT | 0.0 | Minimum match score threshold |

#### Examples

```bash
# Basic search
saidata-gen search "web server"

# Search specific providers
saidata-gen search nginx --providers apt,brew

# Limit results with minimum score
saidata-gen search python --limit 10 --min-score 0.5
```

#### Exit Codes

- `0`: Success
- `1`: Search error

---

### `batch`

Process multiple software packages in batch.

```bash
saidata-gen batch [OPTIONS]
```

#### Options

| Option | Short | Type | Default | Description | Environment Variable |
|--------|-------|------|---------|-------------|---------------------|
| `--input` | `-i` | PATH | **required** | Input file with software names | `SAIDATA_GEN_BATCH_INPUT` |
| `--output` | `-o` | PATH | current dir | Output directory | `SAIDATA_GEN_BATCH_OUTPUT` |
| `--providers` | `-p` | TEXT | all | Comma-separated providers list | `SAIDATA_GEN_PROVIDERS` |
| `--ai` | | FLAG | false | Enable AI enhancement for missing fields | `SAIDATA_GEN_AI` |
| `--ai-provider` | | CHOICE | openai | AI provider (openai/anthropic/local) | `SAIDATA_GEN_AI_PROVIDER` |

| `--enhancement-types` | | TEXT | all | AI enhancement types | `SAIDATA_GEN_ENHANCEMENT_TYPES` |
| `--no-validate` | | FLAG | false | Skip schema validation | `SAIDATA_GEN_NO_VALIDATE` |
| `--format` | `-f` | CHOICE | yaml | Output format | `SAIDATA_GEN_FORMAT` |
| `--output-structure` | | CHOICE | flat | Output structure (flat/hierarchical) | `SAIDATA_GEN_OUTPUT_STRUCTURE` |
| `--max-concurrent` | | INTEGER | 5 | Maximum concurrent processing | `SAIDATA_GEN_MAX_CONCURRENT` |
| `--continue-on-error` | | FLAG | true | Continue on individual failures | `SAIDATA_GEN_CONTINUE_ON_ERROR` |
| `--fail-fast` | | FLAG | false | Stop on first failure | - |
| `--progress-format` | | CHOICE | rich | Progress format (rich/simple/json) | `SAIDATA_GEN_PROGRESS_FORMAT` |
| `--dry-run` | | FLAG | false | Show what would be processed | - |
| `--show-details` | | FLAG | false | Show detailed results | - |

#### Input File Format

The input file should contain one software name per line. Lines starting with `#` are treated as comments.

```
nginx
apache2
# This is a comment
mysql-server
postgresql
redis
```

#### Examples

```bash
# Basic batch processing
saidata-gen batch --input software_list.txt

# Save to specific directory
saidata-gen batch --input software_list.txt --output ./generated/

# Use specific providers with AI enhancement
saidata-gen batch --input software_list.txt --providers apt,brew --ai --ai-provider openai

# CI/CD friendly with JSON progress
saidata-gen batch --input software_list.txt --progress-format json

# High concurrency processing
saidata-gen batch --input software_list.txt --max-concurrent 10

# Dry run to preview
saidata-gen batch --input software_list.txt --dry-run

# Stop on first failure
saidata-gen batch --input software_list.txt --fail-fast
```

#### Exit Codes

- `0`: All packages processed successfully
- `1`: One or more packages failed (unless `--continue-on-error` is used)
- `130`: Interrupted by user (Ctrl+C)

---

### `list-providers`

List all available providers and their status.

```bash
saidata-gen list-providers [OPTIONS]
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--show-templates` | `-t` | Show template file paths |
| `--validate` | `-v` | Validate provider templates |
| `--format` | `-f` | Output format (table/json/yaml) |

#### Examples

```bash
# List all providers
saidata-gen list-providers

# Show template paths and validation status
saidata-gen list-providers --show-templates --validate

# Output as JSON for scripting
saidata-gen list-providers --format json
```

#### Exit Codes

- `0`: Success
- `1`: Error listing providers

---

### `validate-config`

Validate provider configurations and suggest optimizations.

```bash
saidata-gen validate-config [OPTIONS]
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--provider` | `-p` | Validate specific provider |
| `--show-suggestions` | `-s` | Show optimization suggestions |
| `--quality-threshold` | | Minimum quality score threshold (0.0-1.0) |

#### Examples

```bash
# Validate all provider configurations
saidata-gen validate-config

# Validate specific provider with suggestions
saidata-gen validate-config --provider apt --show-suggestions

# Check configurations with quality threshold
saidata-gen validate-config --quality-threshold 0.8
```

#### Exit Codes

- `0`: All configurations valid
- `1`: Validation issues found

---

### `fetch`

Fetch repository data from package managers.

```bash
saidata-gen fetch [OPTIONS]
```

#### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--providers` | `-p` | Comma-separated list of providers to fetch |
| `--cache-dir` | | Cache directory for repository data |
| `--force-refresh` | | Force refresh of cached data |
| `--show-stats` | | Show detailed statistics |

#### Examples

```bash
# Fetch from all providers
saidata-gen fetch

# Fetch from specific providers
saidata-gen fetch --providers apt,brew,winget

# Force refresh cached data
saidata-gen fetch --force-refresh

# Show detailed statistics
saidata-gen fetch --show-stats
```

#### Exit Codes

- `0`: All fetches successful
- `1`: One or more fetches failed

---

### `config`

Configuration management commands.

#### `config init`

Initialize saidata-gen configuration.

```bash
saidata-gen config init [OPTIONS]
```

##### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--config-dir` | Configuration directory | `~/.saidata-gen` |
| `--force` | Overwrite existing configuration | false |

##### Examples

```bash
# Initialize with default settings
saidata-gen config init

# Initialize in custom directory
saidata-gen config init --config-dir /etc/saidata-gen

# Force overwrite existing config
saidata-gen config init --force
```

## Environment Variables

All CLI options can be configured using environment variables:

### Core Configuration

- `SAIDATA_GEN_CONFIG`: Configuration file path
- `SAIDATA_GEN_VERBOSE`: Enable verbose logging (true/false)
- `SAIDATA_GEN_LOG_LEVEL`: Log level (DEBUG/INFO/WARNING/ERROR)
- `SAIDATA_GEN_LOG_FORMAT`: Custom log format string

### Generation Options

- `SAIDATA_GEN_PROVIDERS`: Default providers list
- `SAIDATA_GEN_AI`: Enable AI enhancement by default (true/false)
- `SAIDATA_GEN_AI_PROVIDER`: Default AI provider (openai/anthropic/local)
- `SAIDATA_GEN_ENHANCEMENT_TYPES`: Default AI enhancement types

- `SAIDATA_GEN_NO_VALIDATE`: Skip validation by default (true/false)
- `SAIDATA_GEN_FORMAT`: Default output format
- `SAIDATA_GEN_OUTPUT`: Default output path
- `SAIDATA_GEN_OUTPUT_STRUCTURE`: Default output structure (flat/hierarchical)
- `SAIDATA_GEN_CONFIDENCE_THRESHOLD`: Default confidence threshold

### Batch Processing

- `SAIDATA_GEN_BATCH_INPUT`: Default batch input file
- `SAIDATA_GEN_BATCH_OUTPUT`: Default batch output directory
- `SAIDATA_GEN_MAX_CONCURRENT`: Default concurrency level
- `SAIDATA_GEN_CONTINUE_ON_ERROR`: Continue on error by default (true/false)
- `SAIDATA_GEN_PROGRESS_FORMAT`: Default progress format

### AI Configuration

- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key
- `SAIDATA_GEN_AI_MODEL`: Default AI model name
- `SAIDATA_GEN_AI_TEMPERATURE`: Default temperature (0.0-1.0)
- `SAIDATA_GEN_AI_MAX_TOKENS`: Default max tokens
- `SAIDATA_GEN_AI_TIMEOUT`: AI request timeout (seconds)
- `SAIDATA_GEN_AI_MAX_RETRIES`: Maximum retry attempts
- `SAIDATA_GEN_AI_RATE_LIMIT_RPM`: Rate limit requests per minute
- `SAIDATA_GEN_AI_RATE_LIMIT_TPM`: Rate limit tokens per minute


- `SAIDATA_GEN_RAG_TEMPERATURE`: Default temperature (use SAIDATA_GEN_AI_TEMPERATURE)
- `SAIDATA_GEN_RAG_MAX_TOKENS`: Default max tokens (use SAIDATA_GEN_AI_MAX_TOKENS)

### Cache and Performance

- `SAIDATA_GEN_CACHE_DIR`: Cache directory
- `SAIDATA_GEN_CACHE_TTL`: Cache time-to-live (seconds)
- `SAIDATA_GEN_REQUEST_TIMEOUT`: HTTP request timeout
- `SAIDATA_GEN_RETRY_COUNT`: Number of retries

### CI/CD Integration

- `CI`: Detected automatically (GitHub Actions, Jenkins, etc.)
- `GITHUB_ACTIONS`: GitHub Actions environment
- `JENKINS_URL`: Jenkins environment

## Exit Codes

Standard exit codes used by saidata-gen:

- `0`: Success
- `1`: General error (validation failure, generation error, etc.)
- `2`: Configuration error
- `130`: Interrupted by user (Ctrl+C)

## Shell Completion

Enable shell completion for better CLI experience:

### Bash

```bash
eval "$(_SAIDATA_GEN_COMPLETE=bash_source saidata-gen)"
```

### Zsh

```bash
eval "$(_SAIDATA_GEN_COMPLETE=zsh_source saidata-gen)"
```

### Fish

```bash
eval (env _SAIDATA_GEN_COMPLETE=fish_source saidata-gen)
```

Add these lines to your shell's configuration file (`.bashrc`, `.zshrc`, etc.) for persistent completion.

## Logging

Control logging output:

```bash
# Debug level logging
export SAIDATA_GEN_LOG_LEVEL=DEBUG
saidata-gen generate nginx --verbose

# Custom log format
export SAIDATA_GEN_LOG_FORMAT="%(levelname)s: %(message)s"
saidata-gen generate nginx
```

## AI Enhancement Configuration

### Setting Up AI Providers

#### OpenAI Configuration

```bash
# Set API key via environment variable
export OPENAI_API_KEY="your-openai-api-key"

# Or store securely using the API key manager
python -c "
from saidata_gen.ai.enhancer import APIKeyManager
manager = APIKeyManager()
manager.store_api_key('openai', 'your-openai-api-key')
"

# Configure model and parameters
export SAIDATA_GEN_AI_MODEL="gpt-3.5-turbo"
export SAIDATA_GEN_AI_TEMPERATURE="0.1"
export SAIDATA_GEN_AI_MAX_TOKENS="1000"
```

#### Anthropic Configuration

```bash
# Set API key
export ANTHROPIC_API_KEY="your-anthropic-api-key"

# Configure model
export SAIDATA_GEN_AI_MODEL="claude-3-haiku-20240307"
export SAIDATA_GEN_AI_PROVIDER="anthropic"
```

#### Local Model Configuration

```bash
# For local models (e.g., Ollama)
export SAIDATA_GEN_AI_PROVIDER="local"
export SAIDATA_GEN_AI_MODEL="llama2"
export SAIDATA_GEN_AI_BASE_URL="http://localhost:11434"
```

### AI Enhancement Types

Control what AI enhances with `--enhancement-types`:

- `description`: Generate software descriptions
- `categorization`: Determine categories and tags
- `field_completion`: Fill missing URLs, license, platforms

```bash
# Enhance only descriptions
saidata-gen generate nginx --ai --enhancement-types description

# Enhance descriptions and categories
saidata-gen generate nginx --ai --enhancement-types description,categorization

# Enhance all fields (default)
saidata-gen generate nginx --ai --enhancement-types all
```

### Rate Limiting and Performance

Configure AI rate limits to avoid API throttling:

```bash
export SAIDATA_GEN_AI_RATE_LIMIT_RPM=60    # Requests per minute
export SAIDATA_GEN_AI_RATE_LIMIT_TPM=90000 # Tokens per minute
export SAIDATA_GEN_AI_MAX_RETRIES=3        # Retry attempts
export SAIDATA_GEN_AI_TIMEOUT=30           # Request timeout
```

## Development Tools

### Provider Template Analysis

For developers working on provider templates, use the analysis script to identify redundant configurations:

```bash
# Analyze all provider templates
python scripts/analyze_provider_templates.py

# This will generate a report showing:
# - Redundant keys that can be removed
# - Provider-specific overrides to keep
# - Redundancy percentage per provider
# - Recommendations for optimization
```

The analysis script helps maintain clean provider templates by identifying configurations that duplicate the defaults and can be safely removed.

### Configuration Validation

Use the configuration validator to ensure template quality:

```bash
# Validate all provider configurations
saidata-gen validate-config

# Validate specific provider with suggestions
saidata-gen validate-config --provider apt --show-suggestions

# Check quality threshold
saidata-gen validate-config --quality-threshold 0.8
```

### Provider Template Cleanup

Clean up redundant configurations automatically:

```bash
# Analyze what can be cleaned up (dry run)
python scripts/cleanup_provider_configs.py --provider apt --dry-run

# Apply cleanup
python scripts/cleanup_provider_configs.py --provider apt

# Clean up all providers
python scripts/cleanup_provider_configs.py --all
```

## Performance Tips

1. **Use caching**: Let the tool cache repository data for faster subsequent runs
2. **Limit providers**: Use `--providers` to focus on relevant package managers
3. **Adjust concurrency**: Use `--max-concurrent` for batch processing optimization
4. **Environment variables**: Set common options as environment variables
5. **Progress format**: Use `--progress-format simple` or `json` for better performance in scripts