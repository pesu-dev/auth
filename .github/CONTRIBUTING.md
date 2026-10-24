# 🤝 Contributing to auth

Thank you for your interest in contributing to auth! This document covers how to contribute, and the rules and
policies contributions follow. How the project is developed, tested and deployed is documented in [`docs/`](../docs).

<details>
<summary>📚 Table of Contents</summary>

- [🤝 Contributing to auth](#-contributing-to-auth)
- [🚧 Getting Started](#-getting-started)
  - [🌐 Deployment Environment](#-deployment-environment)
  - [🔄 Development Workflow](#-development-workflow)
- [🛠️ Development Environment Setup](#-development-environment-setup)
- [🤖 Coding Agents](#-coding-agents)
- [🧪 Testing and Code Quality](#-testing-and-code-quality)
- [🚀 Submitting Changes](#-submitting-changes)
  - [🔀 Create a Branch](#-create-a-branch)
  - [✏️ Make and Commit Changes](#-make-and-commit-changes)
  - [🔢 Bump the Version](#-bump-the-version)
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

- **Staging**: https://pesuauth-dev.onrender.com - [Status Page](https://6ns95sgb.status.cron-job.org/)
- **Production**: https://pesuauth.onrender.com - [Status Page](https://xzlk85cp.status.cron-job.org/)

Merges to `dev` deploy to staging automatically. Production is deployed manually by maintainers, after the change has
been validated on staging. How both pipelines work is described in [docs/deployment.md](../docs/deployment.md).

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
1. Once merged into `dev` and CI passes, deployment to staging is triggered automatically.
1. Production deployment is performed manually by authorized maintainers after successful staging validation.

> [!WARNING]
> Please note that you will not be able to push directly to either the `dev` or `main` branches of the repository. All
> PRs
> must be raised from a feature branch of your forked repository and target the `dev` branch. Direct PRs to `main` will be
> closed.

## 🛠️ Development Environment Setup

You need Python 3.14 or higher, [`uv`](https://docs.astral.sh/uv/), Git and Docker. In a clone of your fork:

```bash
uv sync --all-groups
cp .env.example .env           # then fill in the TEST_* variables for the live tests
uv run pre-commit install
```

The full setup, what each variable means and how to run the app are in
[docs/development.md](../docs/development.md).

## 🤖 Coding Agents

This repository is set up for coding agents. Their instructions, skills and roles come from
[pesu-dev/skills](https://github.com/pesu-dev/skills), mounted as a git submodule at `.agents/pesudev-skills`, so clone
with `--recurse-submodules`.

- Do not edit `AGENTS.md` or `.agents/` here: open a pull request against pesu-dev/skills instead.
- Do not edit `.github/agents/` by hand: it is generated from the roles by `uv run python scripts/sync_agents.py`.
- Hand an issue to Copilot's cloud agent on **your fork**, not here, since pull requests to pesu-dev/auth must come from
  a fork.

How the submodule, the generated agents and Dependabot's submodule updates work is described in
[docs/development.md](../docs/development.md#coding-agents).

## 🧪 Testing and Code Quality

- Every commit must pass the pre-commit hooks, which run the linters, formatters and the full test suite. You will not
  be able to commit code that fails them, and CI runs the same hooks.
- Add tests with every feature and bug fix. Coverage is measured over every Python file outside `tests/`, counting
  branches, and the gate is **100%**.
- Never let a unit test reach PESU Academy; use the fixtures in `tests/unit/conftest.py`.
- Run the live tests locally before you open a pull request. GitHub withholds secrets from fork pull requests, so CI
  only runs them once the change reaches `dev`.
- Every live test run and benchmark makes real logins to PESU Academy: run them when you need them, not in a loop, and
  never alongside each other.

How to run the tests, the live tests and the benchmarks, and how to write tests, is in
[docs/testing.md](../docs/testing.md). The hooks, and how to run the checks that only run in CI, are in
[docs/development.md](../docs/development.md#code-quality).

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

### 🔢 Bump the Version

Every pull request raises `version` in `pyproject.toml` by exactly one step from `dev`'s, once for the whole pull
request, and runs `uv lock` so `uv.lock` records the same version. For example, if the version on `dev` is `4.18.0`, the
new version is one of:

| Bump  | Next version | Use for…                                                                                                                                                  |
| ----- | ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| minor | `4.19.0`     | The default, whatever the change                                                                                                                          |
| patch | `4.18.1`     | Anything that was meant to be part of the last minor release but was missed or split out into its own pull request, whether a feature, fix, docs or tests |
| major | `5.0.0`      | A backwards-incompatible API or schema change                                                                                                             |

The *Version check* in CI fails on anything else: an unchanged version, a skipped one such as `4.20.0`, or one that
does not reset the numbers to its right, such as `4.19.1`.

### 📤 Push and Open a Pull Request

1. Push your branch to your fork:

   ```bash
   git push origin your-feature-name
   ```

1. Open a Pull Request (PR) on GitHub targeting the `dev` branch.

1. In your PR:

   - Use a [Conventional Commit](https://www.conventionalcommits.org/) title, such as `feat: add X` or `fix: handle Y`
     (`feat!:` or `fix!:` for a breaking change), as the pull request template describes
   - Include a summary of your changes
   - Link any related issues using `Closes #issue-number`
   - Add screenshots, terminal output, or examples if relevant

The maintainers will review your PR, provide feedback, and may request changes. Once approved, your PR will be merged
into the `dev` branch. When CI passes on `dev`, deployment to staging is triggered automatically. After successful
validation, changes will be promoted to production, which is triggered manually by authorized maintainers.

## ❓ Need Help?

If you get stuck or have questions:

1. Check the [README.md](../README.md) for usage, and [`docs/`](../docs) for development, testing and deployment.
1. Review [open issues](https://github.com/pesu-dev/auth/issues)
   or [pull requests](https://github.com/pesu-dev/auth/pulls) to see if someone else encountered the same problem.
1. Reach out to the maintainers on PESU Discord.
   - Use the `#pesu-auth` channel for questions related to this repository.
   - Search for existing discussions before posting.
1. Open a new issue if you're facing something new or need clarification.

## 🔐 Security

If you discover a security vulnerability, **please do not open a public issue**.

Instead, report it as described in [SECURITY.md](SECURITY.md). We take all security concerns seriously and will
respond promptly.

This service handles students' PESU passwords on every request, so changes must never log, store or return a password,
the access token PESU Academy issues, or any personal data beyond what the API already returns.

## ✨ Code Style Guide

To keep the codebase clean and maintainable, please follow these conventions:

### ✅ General Guidelines

- Write clean, readable code
- Use meaningful variable and function names
- Avoid large functions; keep logic modular and composable
- Use Python 3.14+ syntax when appropriate (e.g., `match`, `|` union types)
- Keep imports sorted and remove unused ones (handled automatically via `ruff`)
- Report a failure by raising a `PESUAcademyError` subclass. Its `message` is what the caller receives, so keep it
  to the fixed text the API documents; put the specifics, such as the username or what PESU Academy answered, in
  `detail=`, which only the log sees

### 📝 Docstrings & Comments

- Add docstrings to all public functions, classes, and modules
- Use [Google-style docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) (or
  consistent alternatives)
- Write comments when logic is non-obvious and avoid restating the code

Example:

```python
def send_otp(email: str) -> bool:
    """Send a one-time password to the given email address.

    Args:
        email (str): The user's email address.

    Returns:
        bool: True if the OTP was sent, False otherwise.
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

| Label             | Description                                              |
| ----------------- | -------------------------------------------------------- |
| `authentication`  | 🔐 Login, token handling, error flows                    |
| `pesuacademy`     | 🎓 PESUAcademy client, authentication, and profile logic |
| `student profile` | 🧑‍🎓 Profile response parsing & field mapping logic        |

### 🧠 Meta / Organization

| Label | Description                                    |
| ----- | ---------------------------------------------- |
| `api` | ⚙️ Core FastAPI application and route handlers |

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
