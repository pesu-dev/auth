# Contributing to auth

Thank you for your interest in contributing to auth! This document provides guidelines and instructions for setting up your development environment and contributing to the project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Environment Setup](#development-environment-setup)
- [Code Quality and Standards](#code-quality-and-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)

## Getting Started

Before you begin contributing, please:

1. Fork the repository on GitHub
2. Clone your fork locally
3. Set up your development environment following the instructions below

## Development Environment Setup

### Prerequisites

- Python 3.10 or higher
- Git
- Docker (optional but recommended)

### Setting Up Your Environment

You can set up your development environment using either `conda` or `uv`. Choose the method that works best for you.

#### Option 1: Using conda

1. **Create and activate a virtual environment:**
   ```bash
   conda create -n pesu-auth python=3.10
   conda activate pesu-auth
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install pytest pytest-cov httpx python-dotenv pre-commit
   ```

#### Option 2: Using uv

1. **Install dependencies:**
   ```bash
   uv sync --all-extras
   ```

### Environment Configuration

1. **Set up environment variables:**
   ```bash
   cp .env.example .env
   ```

2. **Configure your test credentials:**
   Open the `.env` file and replace all `<YOUR_..._HERE>` placeholders with your actual test user details. Each variable has been documented in the `.env.example` file for clarity.

### Pre-commit Hooks

We use pre-commit hooks to ensure code quality and consistency.

1. **Install pre-commit hooks:**
   ```bash
   pre-commit install
   ```

2. **Test the hooks:**
   ```bash
   pre-commit run --all-files
   ```

## Running the Application

### Development Mode

#### Using conda:
```bash
python -m app.app
```

#### Using uv:
```bash
uv run python -m app.app
```

### Using Docker

1. **Build the Docker image:**
   ```bash
   docker build . --tag pesu-auth
   ```

2. **Run the container:**
   ```bash
   docker run --name pesu-auth -d -p 5000:5000 pesu-auth
   ```

3. **Access the API at:** `http://localhost:5000/`

## Code Quality and Standards

### Pre-commit Checks

Before submitting any code, ensure that all pre-commit checks pass:

```bash
pre-commit run --all-files
```

### Code Style

- Follow PEP 8 guidelines for Python code
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions small and focused

### Linting

The project uses flake8 for linting. Ensure your code passes all linting checks.

## Testing

### Running Tests

We use pytest for testing. Run the test suite with:

```bash
pytest
```

### Test Coverage

To check test coverage:

```bash
pytest --cov
```

### Writing Tests

- Write tests for new features and bug fixes
- Ensure tests are clear and well-documented
- Use descriptive test names that explain what is being tested

## Submitting Changes

### Pull Request Process

1. **Create a new branch** for your feature or bug fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** and commit them with clear, descriptive messages:
   ```bash
   git add .
   git commit -m "feat: add new authentication endpoint"
   ```

3. **Push your branch** to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

4. **Create a Pull Request** on GitHub with:
   - A clear title and description
   - Reference to any related issues
   - Screenshots or examples if applicable

### Commit Message Guidelines (To be Modified)

Use conventional commit messages:

- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `style:` for formatting changes
- `refactor:` for code refactoring
- `test:` for adding tests
- `chore:` for maintenance tasks

## Need Help?

If you have questions or need help:

1. Check the [README.md](README.md) for basic usage information
2. Look through existing [issues](https://github.com/pesu-dev/auth/issues) and [pull requests](https://github.com/pesu-dev/auth/pulls)
3. Create a new issue if you can't find an answer

## Security

If you discover a security vulnerability, please report it privately by emailing the maintainers rather than opening a public issue.

## License

By contributing to auth, you agree that your contributions will be licensed under the MIT License.

Thank you for contributing to auth!!
