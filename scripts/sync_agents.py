"""Generate the GitHub Copilot custom agents in .github/agents/ from the pesu-dev/skills roles."""

#!/usr/bin/env python3

import argparse
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ROLES_PATH = ".agents/pesudev-skills/auth/agents"
AGENTS_PATH = ".github/agents"
FIX_COMMAND = "uv run python scripts/sync_agents.py"


def read_frontmatter(role_file: Path) -> str:
    """Return a role file's YAML frontmatter block, delimiters included, exactly as written.

    The block is copied rather than parsed and re-serialised, so the wrappers are byte-for-byte stable
    and no YAML dependency is needed.

    Args:
        role_file: The role's Markdown file.

    Returns:
        The frontmatter, from the opening ``---`` line to the closing one, ending in a newline.

    Raises:
        ValueError: If the file does not start with a frontmatter block.
    """
    text = role_file.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{role_file} has no YAML frontmatter")
    end = text.find("\n---\n", len("---\n"))
    if end == -1:
        raise ValueError(f"{role_file} has an unterminated YAML frontmatter block")
    return text[: end + len("\n---\n")]


def render_agent(role_file: Path) -> str:
    """Render the Copilot custom agent that wraps a role.

    The body only points at the role file: Copilot cannot read the pesu-dev/skills submodule from
    GitHub.com, so the wrapper has to exist here, but the role file stays the single definition.

    Args:
        role_file: The role's Markdown file.

    Returns:
        The contents of ``.github/agents/<role>.agent.md``.
    """
    name = role_file.stem
    role_path = f"{ROLES_PATH}/{name}.md"
    return (
        f"{read_frontmatter(role_file)}\n"
        f"<!-- Generated from {role_path} by `{FIX_COMMAND}`. Do not edit. -->\n"
        "\n"
        f"You are the `{name}` role. Read `{role_path}` and follow it exactly: it is your full definition.\n"
        "If `.agents/pesudev-skills` is empty, run `git submodule update --init` first.\n"
        "`AGENTS.md` has the rules that always apply.\n"
    )


def sync_agents(roles_dir: Path, agents_dir: Path, check: bool) -> int:
    """Bring ``agents_dir`` in line with the roles in ``roles_dir``, or only report the differences.

    Args:
        roles_dir: The directory holding the role files.
        agents_dir: The directory holding the generated custom agents.
        check: Report differences and fail instead of writing anything.

    Returns:
        The exit code: 0 when the agents are (now) in sync, 1 otherwise.
    """
    role_files = sorted(roles_dir.glob("*.md"))
    if not role_files:
        # An uninitialised submodule is an empty directory. Treating that as "no roles" would
        # delete every wrapper, so it is an error instead.
        logging.error(f"No roles found in {roles_dir}. Run `git submodule update --init` first.")
        return 1

    expected = {f"{role_file.stem}.agent.md": render_agent(role_file) for role_file in role_files}
    actual = {path.name: path.read_text(encoding="utf-8") for path in agents_dir.glob("*.agent.md")}
    missing = sorted(expected.keys() - actual.keys())
    extra = sorted(actual.keys() - expected.keys())
    stale = sorted(name for name in expected.keys() & actual.keys() if expected[name] != actual[name])

    if check:
        for label, names in (("missing", missing), ("extra", extra), ("out of date", stale)):
            for name in names:
                logging.error(f"{agents_dir / name} is {label}")
        if missing or extra or stale:
            logging.error(f"The Copilot custom agents do not match the roles. Run: {FIX_COMMAND}")
            return 1
        return 0

    agents_dir.mkdir(parents=True, exist_ok=True)
    for name in missing + stale:
        (agents_dir / name).write_text(expected[name], encoding="utf-8", newline="\n")
        logging.info(f"Wrote {agents_dir / name}")
    for name in extra:
        (agents_dir / name).unlink()
        logging.info(f"Removed {agents_dir / name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Parse the command line and run the sync.

    Args:
        argv: The arguments, without the program name. Defaults to ``sys.argv[1:]``.

    Returns:
        The exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if .github/agents/ is out of date, write nothing")
    parser.add_argument("--roles-dir", type=Path, default=REPO_ROOT / ROLES_PATH, help=argparse.SUPPRESS)
    parser.add_argument("--agents-dir", type=Path, default=REPO_ROOT / AGENTS_PATH, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    return sync_agents(args.roles_dir, args.agents_dir, args.check)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(main())
