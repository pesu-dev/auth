#!/usr/bin/env python3

import logging
import os
import subprocess
import sys

from dotenv import load_dotenv


def run_tests():
    load_dotenv()

    test_username = os.getenv("TEST_EMAIL") and os.getenv("TEST_PRN") and os.getenv("TEST_PHONE")
    test_password = os.getenv("TEST_PASSWORD")

    if not test_username or not test_password:
        logging.info("Secrets missing. Running only tests not requiring secrets...")
        command = [
            "pytest",
            "-m",
            "not secret_required",
            "--disable-warnings",
            "-v",
            "-s",
        ]
    else:
        logging.info("Running all tests with coverage...")
        command = [
            "pytest",
            "--cov=app",
            "--cov-report=term-missing",
            "--cov-fail-under=95",
            "--disable-warnings",
            "-v",
            "-s",
        ]

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
