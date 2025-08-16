# Technology Stack

## Build System & Package Management
- **Build System**: setuptools with pyproject.toml configuration
- **Package Manager**: pip with optional dependencies for different feature sets
- **Python Version**: Requires Python >=3.8

## Core Dependencies
- **YAML Processing**: PyYAML >=6.0
- **Schema Validation**: jsonschema >=4.0.0
- **HTTP Requests**: requests >=2.25.0
- **CLI Framework**: Click >=8.0.0
- **Terminal UI**: Rich >=10.0.0 for enhanced console output
- **Data Validation**: Pydantic >=2.0.0
- **Retry Logic**: tenacity >=8.0.0

## Optional Feature Dependencies
- **RAG/AI Features**: openai, anthropic, chromadb
- **ML Features**: torch, transformers, datasets, pandas
- **Development**: pytest, black, isort, mypy, ruff

## Code Quality Tools
- **Formatter**: Black (line-length: 100)
- **Import Sorting**: isort (black profile)
- **Type Checking**: mypy with strict settings
- **Linting**: ruff

## Common Commands

### Development Setup
```bash
# Clone and install for development
git clone https://github.com/sai/saidata-gen.git
cd saidata-gen
pip install -e .[dev,rag,ml]
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=saidata_gen

# Run specific test file
pytest tests/test_core_engine.py
```

### Code Quality
```bash
# Format code
black saidata_gen/ tests/

# Sort imports
isort saidata_gen/ tests/

# Type checking
mypy saidata_gen/

# Linting
ruff check saidata_gen/
```

### Building & Distribution
```bash
# Build package
python -m build

# Build Docker image
docker build -t saidata-gen .

# Run via Docker
docker run --rm -v $(pwd):/workspace saidata-gen generate nginx
```

## Architecture Patterns
- **Plugin Architecture**: Fetcher factory pattern for package managers
- **Template System**: Hierarchical YAML templates with inheritance
- **Validation Pipeline**: Schema validation with quality assessment
- **Caching Layer**: Performance optimization for repeated operations
- **CLI + API**: Both command-line and programmatic interfaces