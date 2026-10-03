"""Failure-path checks for the pre-commit/CI local-server owner."""

import json
from unittest.mock import MagicMock

import pytest

from scripts.fuzz import run_checks


@pytest.fixture
def runner(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("API_TOKEN", "private-environment-value")
    probe = MagicMock()
    probe.__enter__.return_value.connect_ex.return_value = 1
    monkeypatch.setattr(run_checks.socket, "socket", lambda: probe)
    server = MagicMock()
    launch = MagicMock(return_value=server)
    monkeypatch.setattr(run_checks.subprocess, "Popen", launch)
    monkeypatch.setattr(run_checks, "_wait_for_server", lambda process: None)
    return server, launch


@pytest.mark.parametrize("pytest_status,cli_status", [(0, 0), (1, 0), (0, 1)])
def test_runner_runs_both_checks_and_cleans_up(runner, monkeypatch, pytest_status, cli_status):
    server, launch = runner
    commands = []

    def run(command, *, env, check):
        commands.append(command)
        assert env["API_TOKEN"] == "secret-token"
        if "pytest" in command:
            return MagicMock(returncode=pytest_status)
        (run_checks.Path("schemathesis-report") / "cli.json").write_text(
            json.dumps(
                {
                    "operations": {"tested": 4},
                    "exit_code": cli_status,
                }
            )
        )
        return MagicMock(returncode=cli_status)

    monkeypatch.setattr(run_checks.subprocess, "run", run)
    assert run_checks.main() == int(bool(pytest_status or cli_status))
    assert len(commands) == 2
    server.terminate.assert_called_once()
    server.wait.assert_called_once()
    assert launch.call_args.kwargs["env"]["API_TOKEN"] == "secret-token"


def test_runner_stops_server_if_startup_fails(runner, monkeypatch):
    server, _ = runner

    def fail_startup(process):
        raise RuntimeError("Startup failed")

    monkeypatch.setattr(run_checks, "_wait_for_server", fail_startup)
    with pytest.raises(RuntimeError, match="Startup failed"):
        run_checks.main()
    server.terminate.assert_called_once()
    server.wait.assert_called_once()
