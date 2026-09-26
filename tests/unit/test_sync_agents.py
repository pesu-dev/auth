from pathlib import Path

import pytest

from scripts.sync_agents import AGENTS_PATH, REPO_ROOT, ROLES_PATH, main, read_frontmatter, sync_agents

FRONTMATTER = "---\nname: reviewer\ndescription: Reviews diffs. Read-only.\ntools: [\"read\"]\n---\n"


@pytest.fixture
def roles_dir(tmp_path: Path) -> Path:
    roles = tmp_path / "roles"
    roles.mkdir()
    (roles / "reviewer.md").write_text(f"{FRONTMATTER}\n# Reviewer\n\nThe full role.\n")
    (roles / "planner.md").write_text("---\nname: planner\ndescription: Plans.\n---\n\n# Planner\n")
    return roles


@pytest.fixture
def agents_dir(tmp_path: Path) -> Path:
    return tmp_path / "agents"


def test_generates_one_wrapper_per_role(roles_dir, agents_dir):
    assert sync_agents(roles_dir, agents_dir, check=False) == 0

    assert sorted(path.name for path in agents_dir.iterdir()) == ["planner.agent.md", "reviewer.agent.md"]
    wrapper = (agents_dir / "reviewer.agent.md").read_text()
    # The frontmatter is copied verbatim; the body only points at the role file
    assert wrapper.startswith(FRONTMATTER)
    assert f"Read `{ROLES_PATH}/reviewer.md` and follow it exactly" in wrapper
    assert "The full role." not in wrapper


def test_sync_is_idempotent(roles_dir, agents_dir):
    sync_agents(roles_dir, agents_dir, check=False)
    before = {path.name: path.read_text() for path in agents_dir.iterdir()}

    assert sync_agents(roles_dir, agents_dir, check=False) == 0
    assert {path.name: path.read_text() for path in agents_dir.iterdir()} == before
    assert sync_agents(roles_dir, agents_dir, check=True) == 0


def test_sync_rewrites_stale_and_removes_extra_wrappers(roles_dir, agents_dir):
    sync_agents(roles_dir, agents_dir, check=False)
    (agents_dir / "reviewer.agent.md").write_text("edited by hand\n")
    (agents_dir / "removed-role.agent.md").write_text("---\nname: removed-role\n---\n")
    (agents_dir / "README.md").write_text("not a custom agent\n")

    assert sync_agents(roles_dir, agents_dir, check=False) == 0

    assert (agents_dir / "reviewer.agent.md").read_text().startswith(FRONTMATTER)
    assert not (agents_dir / "removed-role.agent.md").exists()
    assert (agents_dir / "README.md").exists()


@pytest.mark.parametrize(
    ("change", "label"),
    [
        (lambda agents: (agents / "planner.agent.md").unlink(), "planner.agent.md is missing"),
        (lambda agents: (agents / "extra.agent.md").write_text("x"), "extra.agent.md is extra"),
        (lambda agents: (agents / "reviewer.agent.md").write_text("x"), "reviewer.agent.md is out of date"),
    ],
)
def test_check_fails_without_writing(roles_dir, agents_dir, caplog, change, label):
    sync_agents(roles_dir, agents_dir, check=False)
    change(agents_dir)
    before = {path.name: path.read_text() for path in agents_dir.iterdir()}

    assert sync_agents(roles_dir, agents_dir, check=True) == 1

    assert label in caplog.text
    assert "uv run python scripts/sync_agents.py" in caplog.text
    assert {path.name: path.read_text() for path in agents_dir.iterdir()} == before


def test_check_fails_when_role_frontmatter_changes(roles_dir, agents_dir):
    sync_agents(roles_dir, agents_dir, check=False)
    (roles_dir / "planner.md").write_text("---\nname: planner\ndescription: Plans better.\n---\n")

    assert sync_agents(roles_dir, agents_dir, check=True) == 1


def test_missing_submodule_fails_and_keeps_wrappers(roles_dir, agents_dir, tmp_path, caplog):
    sync_agents(roles_dir, agents_dir, check=False)
    empty_submodule = tmp_path / "empty"
    empty_submodule.mkdir()

    assert sync_agents(empty_submodule, agents_dir, check=False) == 1

    assert "git submodule update --init" in caplog.text
    assert len(list(agents_dir.iterdir())) == 2


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("# No frontmatter\n", "has no YAML frontmatter"),
        ("---\nname: broken\n", "unterminated YAML frontmatter"),
    ],
)
def test_read_frontmatter_rejects_bad_roles(tmp_path, text, error):
    role_file = tmp_path / "broken.md"
    role_file.write_text(text)

    with pytest.raises(ValueError, match=error):
        read_frontmatter(role_file)


def test_main_parses_arguments(roles_dir, agents_dir):
    args = ["--roles-dir", str(roles_dir), "--agents-dir", str(agents_dir)]

    assert main([*args, "--check"]) == 1
    assert main(args) == 0
    assert main([*args, "--check"]) == 0


def test_committed_agents_match_the_submodule():
    roles_dir = REPO_ROOT / ROLES_PATH
    if not any(roles_dir.glob("*.md")):
        pytest.skip("the pesu-dev/skills submodule is not checked out")

    assert sync_agents(roles_dir, REPO_ROOT / AGENTS_PATH, check=True) == 0
