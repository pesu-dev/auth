#!/usr/bin/env python3
"""Check that a pull request raises the project version and keeps uv.lock in step.

Used by .github/workflows/ci_checks.yml. Compares the ``project.version`` in the base
branch's pyproject.toml against the pull request's, and requires the latter to be strictly
greater. Also checks that uv.lock records the same version, since bumping pyproject.toml without
re-running ``uv lock`` leaves the lockfile stale.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

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


def parse_version(version: str) -> tuple[int, ...]:
    """Parse a dotted version string into a comparable tuple of integers.

    Args:
        version (str): A version such as "4.0.1".

    Returns:
        tuple[int, ...]: The numeric components, e.g. (4, 0, 1).

    Raises:
        SystemExit: If the version is not a plain dotted-numeric string.
    """
    if not re.fullmatch(r"\d+(\.\d+)*", version):
        raise SystemExit(f"❌ Cannot compare non-numeric version {version!r}.")
    return tuple(int(part) for part in version.split("."))


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

    if parse_version(head_version) <= parse_version(base_version):
        print(
            f"\n❌ The project version must be raised above {base_version}, but this PR leaves it "
            f"at {head_version}.\n\n"
            "   Every pull request raises `version` in pyproject.toml exactly once, so that what\n"
            "   is deployed can be identified. One merge to dev is one bump:\n\n"
            "     minor (x.Y.0) - the default. Raise the minor by one, whatever the change.\n"
            "     major (X.0.0) - reserved for a backwards-incompatible API or schema change.\n\n"
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

    print(f"\n✅ Version raised from {base_version} to {head_version}, with uv.lock in step.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())  # pragma: no cover
