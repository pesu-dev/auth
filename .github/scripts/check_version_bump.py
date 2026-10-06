#!/usr/bin/env python3
"""Check that a pull request raises the project version by exactly one step and keeps uv.lock in step.

Used by .github/workflows/ci_checks.yml. Compares the ``project.version`` in the base branch's
pyproject.toml against the pull request's. From a base of MAJOR.MINOR.PATCH, the pull request's must
be the next patch (MAJOR.MINOR.PATCH+1), the next minor (MAJOR.MINOR+1.0) or the next major
(MAJOR+1.0.0): anything else either leaves the version where it was or skips a version that never
reaches dev. Also checks that uv.lock records the same version, since bumping pyproject.toml without
re-running ``uv lock`` leaves the lockfile stale.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

VERSION_PATTERN = re.compile(r"(\d+)\.(\d+)\.(\d+)")
LOCK_VERSION_PATTERN = re.compile(
    r'^name = "pesu-auth"\nversion = "(?P<version>[^"]+)"',
    re.MULTILINE,
)


def read_project_version(path: Path) -> str:
    """Read ``project.version`` out of a pyproject.toml file.

    Args:
        path (Path): Path to the pyproject.toml file.

    Returns:
        str: The declared project version.
    """
    with path.open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def read_lock_version(path: Path) -> str | None:
    """Read the pesu-auth version recorded in a uv.lock file.

    Args:
        path (Path): Path to the uv.lock file.

    Returns:
        str | None: The locked version, or None if the package entry is absent.
    """
    match = LOCK_VERSION_PATTERN.search(path.read_text())
    return match.group("version") if match else None


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse a MAJOR.MINOR.PATCH version string into a tuple of integers.

    Args:
        version (str): A version such as "4.0.1".

    Returns:
        tuple[int, int, int]: The major, minor and patch numbers, e.g. (4, 0, 1).

    Raises:
        SystemExit: If the version is not three dot-separated numbers.
    """
    if not (match := VERSION_PATTERN.fullmatch(version)):
        raise SystemExit(f"❌ {version!r} is not a MAJOR.MINOR.PATCH version, such as 5.0.0.")
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def next_versions(version: tuple[int, int, int]) -> dict[str, tuple[int, int, int]]:
    """List the versions one step above a version, by the kind of bump each one is.

    A bump resets every number to its right, so after 4.18.1 come 4.18.2, 4.19.0 and 5.0.0.

    Args:
        version (tuple[int, int, int]): The base version.

    Returns:
        dict[str, tuple[int, int, int]]: The next patch, minor and major versions.
    """
    major, minor, patch = version
    return {
        "patch": (major, minor, patch + 1),
        "minor": (major, minor + 1, 0),
        "major": (major + 1, 0, 0),
    }


def format_version(version: tuple[int, int, int]) -> str:
    """Write a version tuple back as a string.

    Args:
        version (tuple[int, int, int]): The version, e.g. (5, 0, 0).

    Returns:
        str: The dotted version, e.g. "5.0.0".
    """
    return ".".join(str(part) for part in version)


def main() -> int:
    """Compare the base and head versions and report the outcome.

    Returns:
        int: 0 if the version was bumped correctly, 1 otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-pyproject", type=Path, required=True)
    parser.add_argument("--head-pyproject", type=Path, required=True)
    parser.add_argument("--head-lock", type=Path, required=True)
    parser.add_argument("--base-ref", default="the base branch")
    args = parser.parse_args()

    base_version = read_project_version(args.base_pyproject)
    head_version = read_project_version(args.head_pyproject)
    lock_version = read_lock_version(args.head_lock)

    print(f"{args.base_ref} version : {base_version}")
    print(f"this PR's version : {head_version}")
    print(f"uv.lock version   : {lock_version}")

    allowed = next_versions(parse_version(base_version))
    bump = next((kind for kind, version in allowed.items() if version == parse_version(head_version)), None)
    if bump is None:
        print(
            f"\n❌ The project version must go up by exactly one step from {base_version}, but this PR "
            f"sets it to {head_version}.\n\n"
            "   Every pull request raises `version` in pyproject.toml exactly once, so that what\n"
            "   is deployed can be identified. One merge to dev is one bump, to one of:\n\n"
            f"     {format_version(allowed['minor']):<8} minor - the default, whatever the change.\n"
            f"     {format_version(allowed['patch']):<8} patch - a fix that changes no behaviour callers rely on.\n"
            f"     {format_version(allowed['major']):<8} major - a backwards-incompatible API or schema change.\n\n"
            "   Bump once per pull request, not once per feature within it -- a second bump\n"
            "   skips a version that never reaches dev.\n\n"
            "   Then run `uv lock` so uv.lock records the new version, and commit both files.",
        )
        return 1

    if lock_version != head_version:
        print(
            f"\n❌ pyproject.toml says {head_version} but uv.lock says {lock_version}.\n\n"
            "   Run `uv lock` and commit uv.lock alongside pyproject.toml, otherwise the\n"
            "   lockfile is stale and the Docker build installs a differently versioned project.",
        )
        return 1

    print(f"\n✅ Version raised from {base_version} to {head_version} (a {bump} bump), with uv.lock in step.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())  # pragma: no cover
