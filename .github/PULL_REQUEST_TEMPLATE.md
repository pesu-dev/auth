<!--
Set the PR title like this: `#IssueNumber` - [Pull Request Description]

Then delete this comment.
-->

## 📌 Description

Please provide a concise summary of the changes:

- What is the purpose of this PR?
- What problem does it solve, or what feature does it add?
- Any relevant motivation, background, or context?

> ℹ️ **Fixes / Related Issues**
> Fixes: #100
> Related: #001

## 🧱 Type of Change

> *Please indicate the type of changes introduced in your PR. Anything left unchecked will be assumed to be non-relevant*

- [ ] 🐛 Bug fix – Non-breaking fix for a functional/logic error
- [ ] ✨ New feature – Adds functionality without breaking existing APIs
- [ ] ⚠️ Breaking change – Introduces backward-incompatible changes (API, schema, etc.)
- [ ] 📝 Documentation update – README, docstrings, OpenAPI tags, etc.
- [ ] 🧪 Test suite change – Adds/updates unit, functional, or integration tests
- [ ] ⚙️ CI/CD pipeline update – Modifies GitHub Actions, pre-commit, or Docker build
- [ ] 🧹 Code quality / Refactor – Improves structure, readability, or style (no functional changes)
- [ ] 🐢 Performance improvement – Speeds up auth, scraping, or reduces I/O
- [ ] 🕵️ Debug/logging enhancement – Adds or improves logging/debug support
- [ ] 🔧 Developer tooling – Scripts, benchmarks, local testing improvements
- [ ] 🔒 Security fix – Addresses auth/session/data validation vulnerabilities
- [ ] 🧰 Dependency update – Updates libraries in `pyproject.toml`, `uv.lock`

## 🧪 How Has This Been Tested?

> *Please indicate how you tested your changes. Completing all the relevant items on this list is mandatory*

- [ ] Unit Tests (`tests/unit/`)
- [ ] Functional Tests (`tests/functional/`)
- [ ] Integration Tests (`tests/integration/`)
- [ ] Manual Testing

> ⚙️ **Test Configuration:**
>
> - OS: (e.g., `Linux`)
> - Python: (e.g., `3.14` via `uv`)
> - [ ] Docker build tested

## ✅ Checklist

> *Please indicate the work items you have carried out. Completing all the relevant items on this list is mandatory. Anything left unchecked will be assumed to be non-relevant*

- [ ] My code follows the [CONTRIBUTING.md](https://github.com/pesu-dev/auth/blob/main/.github/CONTRIBUTING.md) guidelines
- [ ] I've performed a self-review of my changes
- [ ] I've added/updated necessary comments and docstrings
- [ ] I've updated relevant docs (README or endpoint docs)
- [ ] No new warnings introduced
- [ ] I've added tests to cover my changes
- [ ] All tests pass locally (`scripts/run_tests.py`)
- [ ] I've run linting and formatting (`pre-commit run --all-files`)
- [ ] Docker image builds and runs correctly
- [ ] Changes are backwards compatible (if applicable)
- [ ] Feature flags or `.env` vars updated (if applicable)
- [ ] I've tested across multiple environments (if applicable)
- [ ] Benchmarks still meet expected performance (`scripts/benchmark/benchmark_requests.py`)

## 🛠️ Affected API Behaviour

> *Please indicate the areas affected by changes introduced in your PR*

- [ ] `app/app.py` – Modified `/authenticate` route logic
- [ ] `app/pesu.py` – Updated scraping or authentication handling

### 🧩 Models

- [ ] `app/models/request.py` – Input validation or request schema changes
- [ ] `app/models/response.py` – Authentication response formatting
- [ ] `app/models/profile.py` – Profile extraction logic

### 🐳 DevOps & Config

- [ ] `Dockerfile` – Changes to base image or build process
- [ ] `.github/workflows/*.yml` – CI/CD pipeline or deployment updates
- [ ] `pyproject.toml` / `uv.lock` – Dependency version changes
- [ ] `.pre-commit-config.yaml` – Linting or formatting hook changes

### 📊 Benchmarks & Analysis

- [ ] `scripts/benchmark/benchmark_requests.py` – Performance or latency measurement changes
- [ ] `scripts/benchmark/analyze_benchmark.py` – Benchmark result analysis changes
- [ ] `scripts/run_tests.py` – Custom test runner logic or behavior updates

## 📸 Screenshots / API Demos (if applicable)

> *Add any visual evidence that supports your changes. MANDATORY for breaking changes.*
>
> *Examples:*
>
> - *Terminal output from a successful `curl` request (redact sensitive data)*
> - *Screenshots of Postman/Bruno results*
> - *GIF of the endpoint working in a browser*
> - *JSON payloads (redact sensitive data)*

## 🧠 Additional Notes (if applicable)

> *Use this space to add any final context or implementation caveats.*
>
> *Examples:*
>
> - *Edge cases or limitations to be aware of*
> - *Follow-up work or tech debt to track*
> - *Known compatibility issues (e.g., with certain Python versions)*
> - *Any new issues this PR introduces or makes visible*
