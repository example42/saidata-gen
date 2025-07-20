# Contributing to saidata-gen

Thank you for considering contributing to saidata-gen! This document provides guidelines and instructions for contributing to this project.

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## How Can I Contribute?

### Reporting Bugs

Before submitting a bug report:

1. Check the [issues](https://github.com/yourusername/saidata-gen/issues) to see if the bug has already been reported.
2. If you're unable to find an open issue addressing the problem, [open a new one](https://github.com/yourusername/saidata-gen/issues/new?template=bug_report.md).

### Suggesting Enhancements

Enhancement suggestions are tracked as [GitHub issues](https://github.com/yourusername/saidata-gen/issues).

1. Check the [issues](https://github.com/yourusername/saidata-gen/issues) to see if your enhancement has already been suggested.
2. If not, [create a new issue](https://github.com/yourusername/saidata-gen/issues/new?template=feature_request.md).

### Pull Requests

1. Fork the repository.
2. Create a new branch for your changes.
3. Make your changes.
4. Run tests to ensure your changes don't break existing functionality.
5. Submit a pull request.

## Development Setup

### Prerequisites

- Python 3.8 or higher
- pip
- git

### Installation

1. Clone your fork of the repository:
   ```bash
   git clone https://github.com/yourusername/saidata-gen.git
   cd saidata-gen
   ```

2. Install the package in development mode:
   ```bash
   pip install -e ".[dev]"
   ```

### Running Tests

```bash
pytest
```

### Code Style

We use [Black](https://black.readthedocs.io/) for code formatting and [flake8](https://flake8.pycqa.org/) for linting.

To format your code:
```bash
black saidata_gen tests
```

To lint your code:
```bash
flake8 saidata_gen tests
```

## Documentation

Please update the documentation when necessary. We use [Google-style docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).

## Versioning

We use [Semantic Versioning](https://semver.org/). Please make sure your changes are compatible with the versioning scheme.

## License

By contributing to saidata-gen, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).