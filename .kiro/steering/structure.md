# Project Structure

## Root Directory Organization
- **Configuration**: `pyproject.toml`, `pytest.ini` - Build and test configuration
- **Documentation**: `docs/` - Comprehensive documentation including API reference, CLI guide, deployment
- **Examples**: `examples/` - Usage examples, configurations, and use cases
- **Schemas**: `schemas/` - JSON schema definitions (saidata-0.1.schema.json)
- **Scripts**: `scripts/` - Build, deployment, and utility scripts
- **Tests**: `tests/` - Comprehensive test suite with fixtures

## Core Package Structure (`saidata_gen/`)

### CLI Module (`cli/`)
- Entry point for command-line interface
- Uses Click framework with Rich for enhanced output

### Core Module (`core/`)
- **`engine.py`**: Central orchestrator (SaidataEngine class)
- **`interfaces.py`**: Type definitions and data contracts
- **`models.py`**: Core data models using Pydantic
- **`exceptions.py`**: Custom exception hierarchy
- **`cache.py`**: Caching layer for performance
- **`performance.py`**: Performance monitoring and optimization
- **`aggregation.py`**: Data aggregation utilities

### Fetcher Module (`fetcher/`)
- **`base.py`**: Abstract base fetcher class
- **`factory.py`**: Factory pattern for fetcher instantiation
- **Package-specific fetchers**: `apt.py`, `brew.py`, `dnf.py`, `winget.py`, etc.
- **`rpm_utils.py`**: Shared utilities for RPM-based systems

### Generator Module (`generator/`)
- **`core.py`**: Main metadata generation logic
- **`templates.py`**: Template processing and rendering

### Templates Module (`templates/`)
- **Provider templates**: Hierarchical YAML templates organized by package manager
- **Template guidelines**: Documentation for template structure and conventions
- **Common configurations**: Shared template components

### Validation Module (`validation/`)
- **`schema.py`**: JSON schema validation
- **`quality.py`**: Quality assessment and scoring

### Search Module (`search/`)
- **`engine.py`**: Main search orchestrator
- **`fuzzy.py`**: Fuzzy matching algorithms
- **`ranking.py`**: Search result ranking
- **`comparison.py`**: Package comparison utilities

### RAG Module (`rag/`)
- **`engine.py`**: RAG system orchestrator
- **`providers.py`**: AI provider integrations (OpenAI, Anthropic)
- **`exceptions.py`**: RAG-specific exceptions

### ML Module (`ml/`)
- **`dataset.py`**: Training dataset management
- **`export.py`**: Data export for model training
- **`training.py`**: Model fine-tuning utilities

## Key Architectural Patterns

### Hierarchical Templates
Templates follow a hierarchical structure:
```
providers/
├── {provider}/
│   ├── default.yaml          # Base configuration
│   ├── {os}.yaml            # OS-specific overrides
│   └── {os}/                # Version-specific overrides
│       └── {version}.yaml
```

### Factory Pattern
- Fetchers use factory pattern for dynamic instantiation
- Supports plugin-like architecture for adding new package managers

### Interface-Driven Design
- Core interfaces defined in `interfaces.py`
- Consistent data contracts across modules
- Type hints throughout codebase

### Modular Architecture
- Clear separation of concerns between modules
- Each module has specific responsibility
- Minimal coupling between components

## File Naming Conventions
- **Python files**: snake_case (e.g., `core_engine.py`)
- **Test files**: `test_` prefix (e.g., `test_core_engine.py`)
- **Configuration files**: lowercase with extensions (e.g., `pyproject.toml`)
- **Documentation**: kebab-case for multi-word files (e.g., `api-reference.md`)