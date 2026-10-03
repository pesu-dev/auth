"""Run URL pytest and CLI checks with a locally owned offline server."""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from scripts.fuzz.target import SYNTHETIC_TOKEN


def _wait_for_server(server: subprocess.Popen[bytes]) -> None:
    """Wait at most thirty seconds for the owned server to serve its schema.

    Args:
        server (subprocess.Popen[bytes]): The server process started by this runner.

    Raises:
        RuntimeError: If startup fails or the schema never becomes available.
    """
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError("Mocked API exited during startup; see schemathesis-report/server.log.")
        try:
            with urlopen("http://127.0.0.1:8080/openapi.json", timeout=1) as response:
                if response.status == 200:
                    return
        except URLError, TimeoutError:
            time.sleep(0.1)
    raise RuntimeError("Mocked API did not become ready within thirty seconds.")


def main() -> int:
    """Run both checks, verify operation coverage, and always stop the local server.

    Returns:
        int: Zero only when both runners passed and all four operations were exercised.

    Raises:
        RuntimeError: If port 8080 is occupied or the server cannot start.
    """
    # Refuse to test somebody else's server: unsanitized reports are only for this mocked app.
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", 8080)) == 0:
            raise RuntimeError("Port 8080 is already occupied; stop that server before running OpenAPI fuzz checks.")
    reports = Path("schemathesis-report")
    reports.mkdir(exist_ok=True)
    for filename in ("pytest.xml", "cli.xml", "cli.json", "schema-coverage.html"):
        (reports / filename).unlink(missing_ok=True)
    # Never inherit a real API token into the unsanitized configuration.
    environment = {
        **os.environ,
        "API_TOKEN": SYNTHETIC_TOKEN,
        "SCHEMATHESIS_COVERAGE_REPORT_HTML_PATH": str(reports / "schema-coverage.html"),
        "PYTHONPATH": str(Path.cwd()),
    }
    environment.pop("SCHEMATHESIS_HOOKS", None)
    with (reports / "server.log").open("wb") as server_log:
        server = subprocess.Popen(
            [sys.executable, "-m", "scripts.fuzz.target"],
            env=environment,
            stdout=server_log,
            stderr=server_log,
        )
        try:
            _wait_for_server(server)
            pytest_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "scripts/fuzz/test_api_url.py",
                    f"--junitxml={reports / 'pytest.xml'}",
                ],
                env=environment,
                check=False,
            )
            # CLI reports remain available even when pytest finds a failure.
            cli_result = subprocess.run(
                [
                    str(Path(sys.executable).with_name("schemathesis.exe" if os.name == "nt" else "schemathesis")),
                    "--config-file",
                    "scripts/fuzz/schemathesis.toml",
                    "run",
                    "http://127.0.0.1:8080/openapi.json",
                    "--report",
                    "junit,json",
                    "--report-junit-path",
                    str(reports / "cli.xml"),
                    "--report-json-path",
                    str(reports / "cli.json"),
                ],
                env=environment,
                check=False,
            )
            report = json.loads((reports / "cli.json").read_text())
            complete = report["operations"]["tested"] == 4 and report["exit_code"] == 0
            return int(bool(pytest_result.returncode or cli_result.returncode or not complete))
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
