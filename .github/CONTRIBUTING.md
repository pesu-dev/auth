# 🤝 Contributing to auth

Thank you for your interest in contributing to auth! This document provides guidelines and instructions for setting up
your development environment and contributing to the project.

<details>
<summary>📚 Table of Contents</summary>

- [🤝 Contributing to auth](#-contributing-to-auth)
- [🚧 Getting Started](#-getting-started)
- [🛠️ Development Environment Setup](#-development-environment-setup)
  - [Prerequisites](#prerequisites)
  - [Setting Up Your Environment](#setting-up-your-environment)
  - [Set Up Environment Variables](#set-up-environment-variables)
  - [Pre-commit Hooks](#pre-commit-hooks)
- [🤖 Coding Agents](#-coding-agents)
- [🧰 Running the Application](#-running-the-application)
- [🧪 Testing and Code Quality](#-testing-and-code-quality)
  - [Pre-commit Hooks](#pre-commit-hooks-1)
  - [Linting & Formatting](#linting--formatting)
- [🧪 Running Tests](#-running-tests)
  - [Tests that need credentials](#tests-that-need-credentials)
  - [Benchmark output](#benchmark-output)
  - [Writing Tests](#writing-tests)
- [🚀 Submitting Changes](#-submitting-changes)
  - [🔀 Create a Branch](#-create-a-branch)
  - [✏️ Make and Commit Changes](#-make-and-commit-changes)
  - [📤 Push and Open a Pull Request](#-push-and-open-a-pull-request)
- [❓ Need Help?](#-need-help)
- [🔐 Security](#-security)
- [✨ Code Style Guide](#-code-style-guide)
  - [✅ General Guidelines](#-general-guidelines)
  - [📝 Docstrings & Comments](#-docstrings--comments)
- [🏷️ GitHub Labels](#-github-labels)
- [🧩 Feature Suggestions](#-feature-suggestions)
- [📄 License](#-license)

</details>

## 🚧 Getting Started

We encourage developers to work on their own forks of the repository. This allows you to work on features or fixes
without affecting the main codebase until your changes are ready to be merged.

### 🌐 Deployment Environment

We maintain two deployment environments:

- **Staging**: https://pesu-auth-dev.onrender.com - [Status Page](https://6ns95sgb.status.cron-job.org/)
- **Production**: https://pesu-auth.onrender.com - [Status Page](https://xzlk85cp.status.cron-job.org/)

### 🔄 Development Workflow

The standard workflow for contributing is as follows:

1. Fork the repository on GitHub and clone it to your local machine with `--recurse-submodules` (see
   [Coding Agents](#-coding-agents)).
1. Create a new branch for your feature or bug fix.
1. Make your changes and commit them with clear, descriptive messages.
1. Push your branch to your fork on GitHub.
1. Create a Pull Request (PR) against the repository's `dev` branch (not `main`).
1. Wait for review and feedback from the maintainers, address any comments or suggestions.
1. Once approved, your changes will be merged into the `dev` branch and deployed to staging for testing.
1. After all pre-commit checks pass, deployment to staging is triggered automatically.
1. Production deployment is performed manually by authorized maintainers after successful staging validation.

> [!WARNING]
> Please note that you will not be able to push directly to either the `dev` or `main` branches of the repository. All
> PRs
> must be raised from a feature branch of your forked repository and target the `dev` branch. Direct PRs to `main` will be
> closed.

## 🛠️ Development Environment Setup

This section provides instructions for setting up your development environment to work on the project. We recommend
using a package manager like [`uv`](https://docs.astral.sh/uv/) to manage dependencies and avoid conflicts with other
projects.

### Prerequisites

- Python 3.14 or higher
- Git
- Docker

### Setting Up Your Environment

1. **Create and activate a virtual environment:**

   ```bash
   uv venv --python 3.14
   source .venv/bin/activate
   ```

1. **Install dependencies:**

   ```bash
   uv sync --all-groups
   ```

### Set Up Environment Variables

1. **Copy the example environment file to create your own:**

   ```bash
   cp .env.example .env
   ```

1. **Configure your test credentials:**
   Open the `.env` file and replace all `<YOUR_..._HERE>` placeholders with your actual test user details. Each variable
   has been documented in the `.env.example` file for clarity.

### Pre-commit Hooks

We use pre-commit hooks to ensure code quality and consistency. These will automatically run checks before you commit
your code. Install the pre-commit hooks by running:

```bash
pre-commit install
```

## 🤖 Coding Agents

This repository is set up for coding agents (Codex, Claude Code, Copilot, Cursor, Gemini and
others). Their instructions, skills and roles come from
[pesu-dev/skills](https://github.com/pesu-dev/skills), mounted as a git submodule at
`.agents/pesudev-skills`. `AGENTS.md` and `.agents/skills` are links into it: the two provider-neutral
locations agents read.

Clone with the submodule, or the links point at nothing and agents see no instructions:

```bash
git clone --recurse-submodules https://github.com/<your-username>/auth.git
# already cloned without it:
git submodule update --init
```

On Windows, turn on Developer Mode and run `git config --global core.symlinks true` before cloning,
so the links are checked out as links.

Do not edit `AGENTS.md` or `.agents/` here: open a pull request against
pesu-dev/skills instead. Dependabot opens a pull request here to update the submodule when that
repository changes.

In GitHub Copilot, each role (planner, implementer, reviewer and so on) is also a custom agent you
can pick from the agent picker or assign an issue to. They live in `.github/agents/`, which is
generated from the roles in the submodule: do not edit it by hand. When a submodule update adds,
removes or changes a role's frontmatter, the `sync-agents` pre-commit hook fails until you
regenerate them and commit the result:

```bash
uv run python scripts/sync_agents.py
```

Dependabot's submodule pull requests cannot do that themselves. If one fails `sync-agents`, open a
pull request from your fork that bumps the submodule to the same commit and regenerates the agents
(with the usual version bump); Dependabot then closes its own.

To hand an issue to Copilot's cloud agent, assign it on **your fork**, not here: the agent opens its
pull request in the repository it runs in, and pull requests to pesu-dev/auth must come from a fork.
Open the pull request from your fork to `dev` yourself once Copilot's is ready.

## 🧰 Running the Application

You can run the application using the same instructions as in the [README.md](../README.md) file. To ensure parity with
production, we recommend testing the app both locally and inside Docker. See the [README.md](../README.md) for Docker
instructions.

## 🧪 Testing and Code Quality

We enforce code quality and correctness using `pre-commit`, which runs formatters, linters, upgrade checks, and the test
suite automatically before every commit.

### Pre-commit Hooks

The following checks are enforced:

- ✅ `ruff` for linting and formatting (with auto-fix)
- ✅ `mdformat` to format Markdown files (with GFM support)
- ✅ `end-of-file-fixer`, `trailing-whitespace`, `check-yaml`, `check-toml`, `requirements-txt-fixer`, `check-added-large-files` for formatting
- ✅ `name-tests-test` to enforce test naming conventions
- ✅ `debug-statements` to prevent committed `print()` or `pdb`
- ✅ A local `pytest` hook that runs the full test suite

> [!WARNING]
> You will not be able to commit code that fails these checks.

### Linting & Formatting

All linting and formatting is handled by `ruff`. Run the following command to check
all files:

```bash
pre-commit run --all-files
```

## 🧪 Running Tests

We use `pytest`, and a pre-commit hook ensures tests are run automatically before every commit.

To run tests manually:

```bash
uv run pytest
```

To check coverage:

```bash
uv run pytest --cov
```

> [!NOTE]
> The pre-commit hook runs `python scripts/run_tests.py`, which uses the same underlying `pytest` runner.

### Tests that need credentials

Eleven tests are marked `secret_required` and log in to PESU Academy for real. They need the
`TEST_*` variables in your `.env`; without them `scripts/run_tests.py` deselects those tests, warns
that it has done so, and still enforces the coverage gate on the rest.

The test account allows **one active session**, so never run the live tests while another run is in
flight -- including CI. A second login is rejected and shows up as a puzzling `401`.

In CI, pull requests come from forks, and GitHub withholds secrets from fork pull requests. So
*Pre-Commit Checks* runs the reduced suite on every pull request -- it says so in the run's summary
-- and the live tests only run once the change reaches `dev`. Run them locally before you open a
pull request; CI will not cover them for you.

### Benchmark output

The scripts in `scripts/benchmark/` write their CSVs and plots to `benchmark/results/` at the
repository root, named `{script}_{date}_{time}.{ext}`. Pass `--output-dir` to write elsewhere,
`--tag` to label an experimental run, or `--output` to name one file explicitly. All of it is
gitignored.

```bash
cd scripts/benchmark
uv run python benchmark_requests.py --num-requests 100 --parallel --tag baseline
uv run python analyze_benchmark.py -f ../../benchmark/results/benchmark_requests_*.csv
```

### Writing Tests

- Write tests for all new features and bug fixes
- Place them in the `tests/` directory
- Name your test files and functions with the `test_` prefix (required by `pytest` and validated by pre-commit)
- Keep test cases small, meaningful, and well-named

## 🚀 Submitting Changes

### 🔀 Create a Branch

Start by creating a new branch for your work:

```bash
git checkout -b your-feature-name
```

Replace `your-feature-name` with a descriptive name related to the change (e.g., `fix-token-expiry-bug` or
`docs-update-readme`).

### ✏️ Make and Commit Changes

After making your changes, commit them with a clear, conventional message:

```bash
git add .
git commit -m "fix: resolve token expiry issue"
```

Use [Conventional Commits](https://www.conventionalcommits.org/) to keep commit history consistent:

| Type        | Use for…                                       |
| ----------- | ---------------------------------------------- |
| `feat:`     | New features                                   |
| `fix:`      | Bug fixes                                      |
| `docs:`     | Documentation changes                          |
| `style:`    | Formatting (no code change)                    |
| `refactor:` | Code changes that aren't bug fixes or features |
| `test:`     | Adding or modifying tests                      |
| `chore:`    | Maintenance (build, deps, etc.)                |

### 📤 Push and Open a Pull Request

1. Push your branch to your fork:

   ```bash
   git push origin your-feature-name
   ```

1. Open a Pull Request (PR) on GitHub targeting the `dev` branch.

1. In your PR:

   - Use a clear and descriptive title
   - Include a summary of your changes
   - Link any related issues using `Closes #issue-number`
   - Add screenshots, terminal output, or examples if relevant

After your PR is merged into `dev`, all `pre-commit` checks will run automatically. If they pass, deployment to staging is triggered.
The maintainers will review your PR, provide feedback, and may request changes. Once approved, your PR will be merged
into the `dev` branch and deployed to staging for testing. After successful validation, changes will be promoted to
production which is manually trigerred by authorized maintainers.

## ❓ Need Help?

If you get stuck or have questions:

1. Check the [README.md](../README.md) for setup and usage info.
1. Review [open issues](https://github.com/pesu-dev/auth/issues)
   or [pull requests](https://github.com/pesu-dev/auth/pulls) to see if someone else encountered the same problem.
1. Reach out to the maintainers on PESU Discord.
   - Use the `#pesu-auth` channel for questions related to this repository.
   - Search for existing discussions before posting.
1. Open a new issue if you're facing something new or need clarification.

## 🔐 Security

If you discover a security vulnerability, **please do not open a public issue**.

Instead, report it privately by contacting the maintainers. We take all security concerns seriously and will respond
promptly.

## ✨ Code Style Guide

To keep the codebase clean and maintainable, please follow these conventions:

### ✅ General Guidelines

- Write clean, readable code
- Use meaningful variable and function names
- Avoid large functions; keep logic modular and composable
- Use Python 3.14+ syntax when appropriate (e.g., `match`, `|` union types)
- Keep imports sorted and remove unused ones (handled automatically via `ruff`)

### 📝 Docstrings & Comments

- Add docstrings to all public functions, classes, and modules
- Use [Google-style docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) (or
  consistent alternatives)
- Write comments when logic is non-obvious and avoid restating the code

Example:

```python
def send_otp(email: str) -> bool:
    """
    Sends a one-time password to the given email.

    Args:
        email (str): User's email address

    Returns:
        bool: True if the OTP was sent successfully, False otherwise
    """
```

## 🏷️ GitHub Labels

We use GitHub labels to categorize and prioritize issues and pull requests. Here’s a guide to help you understand what
each label means:

### 🧑‍💻 Contribution Level

| Label              | Description                                                   |
| ------------------ | ------------------------------------------------------------- |
| `good first issue` | 🟢 Simple, well-scoped tasks good for first-time contributors |
| `help wanted`      | 🟡 Maintainers are actively seeking help on this issue        |

### 🐞 Bug & Error Handling

| Label       | Description                                                 |
| ----------- | ----------------------------------------------------------- |
| `bug`       | 🔴 A defect or unexpected behavior in the application       |
| `invalid`   | 🚫 The issue/PR is not valid or based on a misunderstanding |
| `wontfix`   | ❌ The issue is acknowledged but will not be fixed          |
| `duplicate` | 📑 This issue or PR duplicates an existing one              |

### ✨ Feature Development

| Label         | Description                                             |
| ------------- | ------------------------------------------------------- |
| `enhancement` | 🟢 A request or proposal for improvement or new feature |
| `feature`     | 🌟 Work related to adding a new capability              |
| `question`    | ❓ Request for clarification or discussion              |

### 📚 Documentation

| Label           | Description                                          |
| --------------- | ---------------------------------------------------- |
| `documentation` | 📘 Updates to README, docstrings, or inline comments |

### 🧪 Testing & CI/CD

| Label             | Description                                                       |
| ----------------- | ----------------------------------------------------------------- |
| `tests and ci/cd` | 🧪 Changes or issues related to testing or continuous integration |

### 🔒 Authentication & Core

| Label             | Description                                               |
| ----------------- | --------------------------------------------------------- |
| `authentication`  | 🔐 Login, CSRF, token handling, error flows               |
| `pesuacademy`     | 🎓 PESUAcademy client, authentication, and scraping logic |
| `student profile` | 🧑‍🎓 HTML parsing & profile field extraction logic          |

### 🧠 Meta / Organization

| Label        | Description                                        |
| ------------ | -------------------------------------------------- |
| `api`        | ⚙️ Core FastAPI application and route handlers     |
| `discussion` | 🗣️ Open-ended conversation about project direction |

> [!NOTE]
> When opening or triaging issues and PRs, feel free to suggest an appropriate label. Maintainers will review
> and apply them accordingly.

## 🧩 Feature Suggestions

If you want to propose a new feature:

1. Check if it already exists in [issues](https://github.com/pesu-dev/auth/issues)
1. Open a new issue using the **"Feature Request"** template if available
1. Clearly explain the use case, proposed solution, and any relevant context

## 📄 License

By contributing to this repository, you agree that your contributions will be licensed under the **MIT License**.
See [`LICENSE`](../LICENSE) for full license text.
