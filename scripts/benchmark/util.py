"""Utility functions for the benchmark scripts."""

import os
import time
from datetime import datetime
from pathlib import Path

import httpx2
from dotenv import load_dotenv

load_dotenv()

# Anchored to the repository root rather than the working directory, so results land in the same
# place whether a script is run from scripts/benchmark/ or from the repository root.
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "benchmark" / "results"


def resolve_output_path(
    script_name: str,
    extension: str,
    output: str | None = None,
    output_dir: str | None = None,
    tag: str | None = None,
) -> Path:
    """Resolve where a script should write an output file, creating the directory if needed.

    An explicit output path wins. Otherwise the name is built from the script name and the current
    time, so repeated runs no longer overwrite each other, with an optional tag for telling
    experimental runs apart.

    Args:
        script_name: The name of the calling script, used as the filename stem
        extension: The file extension, without a leading dot
        output: An explicit output path, which overrides every other argument but --output-dir
        output_dir: The directory to write into, defaulting to benchmark/results at the repo root
        tag: An optional identifier appended to the generated filename

    Returns:
        The resolved path, whose parent directory is guaranteed to exist
    """
    directory = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    if output:
        path = Path(output)
        # A bare filename is placed in the output directory; an explicit path is honoured as given
        if path.parent == Path():
            path = directory / path
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{tag}" if tag else ""
        path = directory / f"{script_name}_{timestamp}{suffix}.{extension}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def make_request(
    host: str = "http://localhost:5000",
    route: str = "authenticate",
    profile: bool = True,
    timeout: float = 10.0,
) -> tuple[dict, float]:
    """Make a request to the authentication endpoint and return the response and elapsed time.

    Args:
        host: The host to make the request to
        route: The route to make the request to
        profile: Whether to fetch the profile information or not
        timeout: The timeout for the request

    Returns:
        Tuple of response JSON and elapsed time in seconds
    """
    with httpx2.Client(follow_redirects=True, timeout=httpx2.Timeout(timeout)) as client:
        if route == "authenticate":
            data = {
                "username": os.getenv("TEST_PRN"),
                "password": os.getenv("TEST_PASSWORD"),
                "profile": profile,
            }
            start_time = time.time()
            response = client.post(
                f"{host}/{route}",
                json=data,
                follow_redirects=True,
            )
        else:
            start_time = time.time()
            response = client.get(
                f"{host}/{route}",
                follow_redirects=True,
            )
    elapsed_time = time.time() - start_time
    # Not every route answers with JSON: /readme is a 308 to GitHub. An unconditional .json()
    # crashes the sequential runner outright and, in the parallel runner, is swallowed as a failed
    # request -- which silently skews the numbers being measured.
    try:
        body = response.json()
    except ValueError:
        body = {"status": response.is_success, "text": response.text}
    return body, elapsed_time
