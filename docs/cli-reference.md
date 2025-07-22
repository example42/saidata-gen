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

Generate metadata for a software package.

```bash
saidata-gen generate [OPTIONS] SOFTWARE_NAME
```

#### Arguments

- `SOFTWARE_NAME`: Name of the software package to generate metadata for

#### Options

| Option | Short | Type | Default | Description | Environment Variable |
|--------|-------|------|---------|-------------|---------------------|
| `--providers` | `-p` | TEXT | all | Comma-separated list of providers | `SAIDATA_GEN_PROVIDERS` |
| `--use-rag` | | FLAG | false | Use RAG for enhanced generation | `SAIDATA_GEN_USE_RAG` |
| `--rag-provider` | | CHOICE | openai | RAG provider (openai/anthropic/local) | `SAIDATA_GEN_RAG_PROVIDER` |
| `--no-validate` | | FLAG | false | Skip schema validation | `SAIDATA_GEN_NO_VALIDATE` |
| `--format` | `-f` | CHOICE | yaml | Output format (yaml/json) | `SAIDATA_GEN_FORMAT` |
| `--output` | `-o` | PATH | - | Output file path | `SAIDATA_GEN_OUTPUT` |
| `--confidence-threshold` | | FLOAT | 0.7 | Minimum confidence threshold | `SAIDATA_GEN_CONFIDENCE_THRESHOLD` |

#### Examples

```bash
# Basic generation
saidata-gen generate nginx

# Use specific providers
saidata-gen generate nginx --providers apt,brew,docker

# Generate with AI enhancement
saidata-gen generate nginx --use-rag --rag-provider openai

# Save to file with JSON format
saidata-gen generate nginx --output nginx.json --format json

# Skip validation with custom confidence threshold
saidata-gen generate nginx --no-validate --confidence-threshold 0.8
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
# Basic validation
saidata-gen validate nginx.yaml

# Detailed validation output
saidata-gen validate nginx.yaml --detailed
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
| `--use-rag` | | FLAG | false | Use RAG for enhanced generation | `SAIDATA_GEN_USE_RAG` |
| `--rag-provider` | | CHOICE | openai | RAG provider | `SAIDATA_GEN_RAG_PROVIDER` |
| `--no-validate` | | FLAG | false | Skip schema validation | `SAIDATA_GEN_NO_VALIDATE` |
| `--format` | `-f` | CHOICE | yaml | Output format | `SAIDATA_GEN_FORMAT` |
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

# Use specific providers with RAG
saidata-gen batch --input software_list.txt --providers apt,brew --use-rag

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
- `SAIDATA_GEN_USE_RAG`: Enable RAG by default (true/false)
- `SAIDATA_GEN_RAG_PROVIDER`: Default RAG provider
- `SAIDATA_GEN_NO_VALIDATE`: Skip validation by default (true/false)
- `SAIDATA_GEN_FORMAT`: Default output format
- `SAIDATA_GEN_OUTPUT`: Default output path
- `SAIDATA_GEN_CONFIDENCE_THRESHOLD`: Default confidence threshold

### Batch Processing

- `SAIDATA_GEN_BATCH_INPUT`: Default batch input file
- `SAIDATA_GEN_BATCH_OUTPUT`: Default batch output directory
- `SAIDATA_GEN_MAX_CONCURRENT`: Default concurrency level
- `SAIDATA_GEN_CONTINUE_ON_ERROR`: Continue on error by default (true/false)
- `SAIDATA_GEN_PROGRESS_FORMAT`: Default progress format

### RAG Configuration

- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key
- `SAIDATA_GEN_RAG_MODEL`: Default model name
- `SAIDATA_GEN_RAG_TEMPERATURE`: Default temperature
- `SAIDATA_GEN_RAG_MAX_TOKENS`: Default max tokens

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

## Performance Tips

1. **Use caching**: Let the tool cache repository data for faster subsequent runs
2. **Limit providers**: Use `--providers` to focus on relevant package managers
3. **Adjust concurrency**: Use `--max-concurrent` for batch processing optimization
4. **Environment variables**: Set common options as environment variables
5. **Progress format**: Use `--progress-format simple` or `json` for better performance in scripts