"""Tests for scripts/run_tests.py, the runner behind the pre-commit hook and CI."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from scripts import run_tests

CREDENTIALS = ("TEST_EMAIL", "TEST_PRN", "TEST_PHONE", "TEST_PASSWORD")


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    """Start every test with no credentials and outside GitHub Actions.

    load_dotenv is stubbed out, so a local .env cannot put the credentials back.
    """
    monkeypatch.setattr(run_tests, "load_dotenv", lambda: None)
    for variable in (*CREDENTIALS, "GITHUB_ACTIONS", "GITHUB_STEP_SUMMARY"):
        monkeypatch.delenv(variable, raising=False)


@pytest.fixture
def pytest_run():
    with patch.object(run_tests.subprocess, "run", return_value=MagicMock(returncode=0)) as run:
        yield run


def _set_credentials(monkeypatch, **overrides):
    for variable in CREDENTIALS:
        monkeypatch.setenv(variable, overrides.get(variable, "value"))


def test_with_credentials_every_test_runs(monkeypatch, pytest_run):
    _set_credentials(monkeypatch)

    assert run_tests.run_tests() == 0

    command = pytest_run.call_args.args[0]
    assert command[0] == "pytest"
    assert "--cov" in command
    assert "-m" not in command


@pytest.mark.parametrize("missing", CREDENTIALS)
def test_without_any_one_credential_the_live_tests_are_deselected(monkeypatch, pytest_run, caplog, missing):
    _set_credentials(monkeypatch, **{missing: ""})

    with caplog.at_level("WARNING"):
        run_tests.run_tests()

    command = pytest_run.call_args.args[0]
    assert command[-2:] == ["-m", "not secret_required"]
    # The coverage gate is not dropped with them
    assert "--cov" in command
    assert "Live PESU tests skipped" in caplog.text


def test_the_exit_code_is_pytests(monkeypatch, pytest_run):
    _set_credentials(monkeypatch)
    pytest_run.return_value = MagicMock(returncode=3)

    assert run_tests.run_tests() == 3


def test_a_skipped_run_is_announced_in_github_actions(monkeypatch, pytest_run, tmp_path, capsys):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))

    run_tests.run_tests()

    assert "::warning title=Live tests skipped::" in capsys.readouterr().out
    assert summary.read_text().startswith("> [!WARNING]\n> Live PESU tests skipped")


def test_github_actions_without_a_step_summary(monkeypatch, pytest_run, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    run_tests.run_tests()

    assert "::warning title=Live tests skipped::" in capsys.readouterr().out


def test_a_local_skipped_run_prints_no_annotation(pytest_run, capsys):
    run_tests.run_tests()

    assert "::warning" not in capsys.readouterr().out


@pytest.mark.parametrize("error", [FileNotFoundError("pytest"), subprocess.SubprocessError("boom")])
def test_a_runner_failure_is_exit_code_1(pytest_run, caplog, error):
    pytest_run.side_effect = error

    assert run_tests.run_tests() == 1
    assert caplog.records[-1].levelname == "ERROR"


def test_the_coverage_gate_lives_in_pyproject():
    """The 100% gate and what it measures are configured once, in pyproject.toml, not here."""
    import tomllib
    from pathlib import Path

    config = tomllib.loads(Path("pyproject.toml").read_text())["tool"]["coverage"]
    assert config["report"]["fail_under"] == 100
    assert config["run"]["branch"] is True
    assert set(config["run"]["source"]) == {"app", "scripts", ".github/scripts"}
    assert not any(arg.startswith("--cov-fail-under") or arg.startswith("--cov=") for arg in run_tests.COVERAGE_ARGS)
