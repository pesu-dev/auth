# Development

How to set up a development environment, run the application, and work with the tooling. The contribution workflow and
rules are in [CONTRIBUTING.md](../.github/CONTRIBUTING.md); testing is in [testing.md](testing.md).

## Environment setup

This section provides instructions for setting up your development environment to work on the project. We recommend
using a package manager like [`uv`](https://docs.astral.sh/uv/) to manage dependencies and avoid conflicts with other
projects.

### Prerequisites

- Python 3.14 or higher
- Git
- Docker

### Setting Up Your Environment

Install every dependency group:

```bash
uv sync --all-groups
```

### Set Up Environment Variables

1. **Copy the example environment file to create your own:**

   ```bash
   cp .env.example .env
   ```

1. **Configure your test credentials:**
   Open the `.env` file and replace the example values with the details of a PESU Academy account you can test with.
   Each variable is documented in `.env.example`. There is a `TEST_*` variable for every profile field, and the live
   tests compare each one exactly with what the API returns for that account. Leave a variable empty when the account
   has no value for that field (for example `TEST_MIDDLE_NAME`, or `TEST_SEMESTER` and `TEST_SECTION` if the account
   has graduated), since the API then returns `null`. CI reads the same variables from the repository's
   secrets, where such a field simply has no secret. The file is gitignored: never commit it or paste its values anywhere.

### Installing the pre-commit hooks

We use pre-commit hooks to ensure code quality and consistency. These will automatically run checks before you commit
your code. Install the pre-commit hooks by running:

```bash
uv run pre-commit install
```

## Running the application

You can run the application using the same instructions as in the [README.md](../README.md) file. To ensure parity with
production, we recommend testing the app both locally and inside Docker. See the [README.md](../README.md) for Docker
instructions. The container runs as an unprivileged user (`UID 10001:10001`) with read-only application files.

The API Explorer at `/` is served directly from `app/templates/playground.html`, which holds its HTML, styles and
scripts. It needs no frontend build step or third-party UI dependencies.

### Configuration

| Setting         | Default   | What it does                                                                  |
| --------------- | --------- | ----------------------------------------------------------------------------- |
| `--host`        | `0.0.0.0` | The address to listen on                                                      |
| `--port`        | `5000`    | The port to listen on. Also read from `PORT`; `--port` wins when both are set |
| `--debug`       | off       | Logs at `DEBUG` instead of `INFO`, and reloads the app when a file changes    |
| `METRICS_TOKEN` | unset     | Requires this bearer token on `/metrics` (see [metrics.md](metrics.md))       |

The application reads nothing else from the environment. `.env` is only read by the tests and the benchmarks.

## Coding agents

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

## Code quality

We enforce code quality and correctness using `pre-commit`, which runs formatters, linters, upgrade checks, and the test
suite automatically before every commit.

### Pre-commit Hooks

The following checks are enforced:

- ✅ `ruff` for linting and formatting (with auto-fix), running from `uv.lock` so it is the same version as CI
- ✅ `uv-lock` to check that `uv.lock` matches `pyproject.toml`
- ✅ `mdformat` to format Markdown files (with GFM support)
- ✅ `end-of-file-fixer`, `trailing-whitespace`, `check-yaml`, `check-toml`, `check-added-large-files` for formatting
- ✅ `check-symlinks` to catch broken links such as `AGENTS.md`; it also fails until the submodule is checked out
- ✅ `name-tests-test` to enforce test naming conventions
- ✅ `debug-statements` to prevent committed debugger calls, such as `pdb` or `breakpoint()`
- ✅ `sync-agents` to check that `.github/agents/` matches the roles in the agent submodule
- ✅ A local `pytest` hook that runs the full test suite

CI runs the same hooks in the `Pre-commit hooks` job, except `pytest`, because the tests run in the
`Test suite & coverage` job. A PR that passes `uv run pre-commit run --all-files` locally also passes that job.

> [!WARNING]
> You will not be able to commit code that fails these checks.

### Checks that only run in CI

A few checks require the PR itself or Docker and cannot be run as pre-commit hooks. Here is how to run each one
locally:

- **PR source checker:** verifies the PR does not come from the `main` branch and targets `dev`. There is nothing to
  run; just open the PR that way.

- **Version check:** verifies the version in `pyproject.toml` was bumped relative to `dev`:

  ```bash
  git remote add upstream https://github.com/pesu-dev/auth.git   # skip if you already have it
  git fetch upstream
  git show upstream/dev:pyproject.toml > /tmp/base_pyproject.toml
  python3 .github/scripts/check_version_bump.py --base-pyproject /tmp/base_pyproject.toml \
    --head-pyproject pyproject.toml --head-lock uv.lock --base-ref dev
  ```

- **Build image on PR, and Container security & smoke test:** verifies the image builds, runs as UID 10001, and
  answers `/health`:

  ```bash
  docker build . --tag pesu-auth-test
  docker run --rm pesu-auth-test id -u          # prints 10001
  docker run --rm -d --name pesu-auth-smoke -p 5000:5000 pesu-auth-test
  sleep 5 && curl --fail http://localhost:5000/health; docker stop pesu-auth-smoke
  ```

## Documenting a route

Every route in the OpenAPI schema needs a tag, a docstring (which becomes its description) and a module in `app/docs/`
holding an `ApiDocs` with an example for each response it can give, including a success and a `500`. The route passes
them in with `responses=` and, for a request body, `openapi_extra=`. `tests/unit/test_openapi_docs.py` fails if any of
this is missing or an example does not match its model, and `tests/unit/test_openapi_contract.py` checks that the real
responses match what is documented.

The API Explorer and Swagger UI are built from `/openapi.json`, so a documented route appears in both with no other
changes. Add the route to the endpoint table and its own section in the README too.

## Adding an error type

Subclass `PESUAcademyError` in `app/exceptions/`, with the status code and a fixed message as defaults, and raise it
with the specifics in `detail=`. The existing handler renders it and counts it in `errors_total` under its class name.
Document the response in the route's `app/docs/` module and in the README's response table, and add it to the error
table in [architecture.md](architecture.md) and the `errors_total` row in [metrics.md](metrics.md).

## Adding a profile field

Read it in the model for its block in `app/models/upstream.py`, return it from `PESUAcademy._build_profile`, and add it
to `ProfileField` and `ProfileModel` in `app/models/profile.py`, whose descriptions become the Swagger docs. Add it to
both full-profile examples in `app/docs/authenticate.py` and to the README's `ProfileObject` table, and to the fixture
payloads and `FULL_PROFILE` in `tests/unit/conftest.py`; tests check that each lists every field, in order.

For the live tests, give a new field a `TEST_*` variable named after it (`TEST_BRANCH_SHORT_CODE` for
`branchShortCode`) in `.env.example` and in `PROFILE_VARIABLES` in `tests/conftest.py`, so they compare it with the test
account's real value; a unit test fails until every field has one. If the field is an integer, also list it in
`INTEGER_FIELDS` there. Add the variable to the test job's `env` in `.github/workflows/ci_checks.yml`, and ask a
maintainer to add the matching repository secret.
