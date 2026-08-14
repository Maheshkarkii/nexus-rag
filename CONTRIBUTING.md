# Contributing & Developer Quality Guidelines

Thank you for contributing to the **AI Research Assistant** platform!

## 1. Local Developer Validation Commands

Before opening a Pull Request, run the following local quality checks to ensure CI pipeline compliance:

### Backend Quality Checks (Python 3.13)
```bash
# Navigate to backend directory
cd backend

# Run Ruff Linter
ruff check app

# Execute Pytest Test Suites (Services, Evaluation, Security, Jobs)
pytest tests/services tests/evaluation tests/security tests/jobs
```

### Frontend Quality Checks (Next.js 15 / Node 22)
```bash
# Navigate to frontend directory
cd frontend

# Run ESLint & Type Checker
npm run lint

# Execute Production Build Test
npm run build
```

### Container & Docker Validation
```bash
# Validate Docker Compose Configuration
docker compose config

# Test Local Docker Build
docker compose build
```

---

## 2. CI/CD Quality Gates

Every Pull Request and Push to `main` automatically triggers GitHub Actions:

1. **Backend Quality & Test Job**: Executes `ruff` linting, runs unit/integration tests, and generates code coverage reports.
2. **Frontend Quality & Build Job**: Executes ESLint, TypeScript type checking, and production Next.js compilation.
3. **Security & Secret Scanning**: Runs Stage 25 security regression tests (prompt injection, path traversal, formula escaping, cross-user isolation).
4. **Docker Container Validation**: Verifies `docker-compose.yml` and builds backend & frontend production images.

---

## 3. Pull Request Guidelines

* All CI jobs must pass cleanly (**PASS**) before merging.
* Critical security test failures in `tests/security` will automatically block pull request approvals.
* Never commit real secrets or credentials to source control.
