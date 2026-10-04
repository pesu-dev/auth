"""Script to run all the tests with coverage."""

#!/usr/bin/env python3

import logging
import os
import subprocess
import sys

from dotenv import load_dotenv

# What is measured, branch coverage and the 100% gate are configured in [tool.coverage] in
# pyproject.toml, so a plain `pytest --cov` measures exactly what this runner and CI enforce
COVERAGE_ARGS = ["--cov", "--cov-report=term-missing"]


def announce_skipped_live_tests() -> None:
    """Make a secretless run visibly partial, in the log and in the GitHub Actions UI.

    Without this the fallback is invisible: pre-commit swallows a passing hook's output, so a run
    that silently skipped the live tests looks identical to a full one.
    """
    message = (
        "Live PESU tests skipped: TEST_* credentials are not available. Coverage is still "
        "enforced, but nothing was verified against the real upstream service."
    )
    logging.warning(message)
    if os.getenv("GITHUB_ACTIONS") == "true":
        print(f"::warning title=Live tests skipped::{message}")
        if summary_path := os.getenv("GITHUB_STEP_SUMMARY"):
            with open(summary_path, "a") as summary:
                summary.write(f"> [!WARNING]\n> {message}\n")


def run_tests() -> int:
    """Run all the tests with coverage and return the exit code."""
    load_dotenv()

    # Every username the live tests log in with: one missing would send None as a username
    test_username = all(os.getenv(name) for name in ("TEST_EMAIL", "TEST_PRN", "TEST_SRN", "TEST_PHONE"))
    test_password = os.getenv("TEST_PASSWORD")

    command = ["pytest", *COVERAGE_ARGS, "--disable-warnings", "-v", "-s"]
    if not test_username or not test_password:
        # The coverage gate applies here too. It used to be dropped along with the live tests,
        # which meant a pull request could lower coverage without any check noticing -- and every
        # pull request takes this path, since fork PRs never receive secrets.
        announce_skipped_live_tests()
        command += ["-m", "not secret_required"]
    else:
        logging.info("Running all tests with coverage...")

    try:
        result = subprocess.run(command, check=False)
        return result.returncode
    except FileNotFoundError:
        logging.exception("Error: pytest not found. Please ensure pytest is installed.")
        return 1
    except Exception:
        logging.exception("Error running tests")
        return 1


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)
