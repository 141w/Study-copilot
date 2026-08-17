# Contributing to Study Copilot

Thank you for your interest in contributing! This guide will help you get started.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone git@github.com:<your-username>/Study-copilot.git`
3. Follow the [Installation Guide](docs/1-INSTALLATION/index.md) to set up your development environment
4. Create a feature branch: `git checkout -b feature/your-feature`

## Development Workflow

### Branch Naming

- `feature/description` — New features
- `fix/description` — Bug fixes
- `docs/description` — Documentation changes
- `refactor/description` — Code refactoring

### Code Standards

#### Backend (Python)
- Follow PEP 8
- Use type hints on all function signatures
- All I/O operations must be `async`
- Pydantic models for request/response validation
- Add docstrings to public functions
- Run tests before submitting: `cd backend && pytest tests/ -v`

#### Frontend (JavaScript/Vue)
- Vue 3 Composition API with `<script setup>`
- Pinia for state management
- TailwindCSS for styling
- ESLint + Prettier for formatting
- Run tests before submitting: `cd frontend && npx vitest run`

### Commit Messages

Use conventional commits:
```
feat: add document deletion endpoint
fix: resolve streaming timeout in chat
docs: update API reference
refactor: extract RAG pipeline into separate module
test: add quiz generator tests
```

### Pull Request Process

1. Ensure all tests pass
2. Update documentation if needed
3. Write a clear PR description explaining what and why
4. Link related issues
5. Request review from a maintainer

## Project Structure

```
backend/          → Python FastAPI backend
frontend/         → Vue3 frontend
docs/             → Documentation
```

See [CLAUDE.md](CLAUDE.md) for detailed architecture guidance.

## Adding Features

### New API Endpoint
1. Add route in `backend/app/api/`
2. Define Pydantic models
3. Add business logic in `backend/app/core/`
4. Register in `backend/app/main.py`
5. Write tests in `backend/tests/`

### New Frontend Page
1. Create view in `frontend/src/views/`
2. Add route in `frontend/src/router/`
3. Create Pinia store if needed
4. Add API methods in `frontend/src/services/api.js`
5. Write component tests

## Reporting Issues

- Use GitHub Issues
- Include steps to reproduce
- Include error messages and logs
- Specify your environment (OS, Python version, Node version)

## Questions?

Open a GitHub Discussion for general questions about the project.
