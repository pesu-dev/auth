"""Tests for .github/scripts/check_version_bump.py, the CI check that every PR raises the version."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "check_version_bump.py"
_spec = importlib.util.spec_from_file_location("check_version_bump", SCRIPT)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)


def _pyproject(tmp_path, name, version):
    path = tmp_path / name
    path.write_text(f'[project]\nname = "pesu-auth"\nversion = "{version}"\n')
    return path


def _lock(tmp_path, version):
    path = tmp_path / "uv.lock"
    path.write_text(f'version = 1\n\n[[package]]\nname = "pesu-auth"\nversion = "{version}"\nsource = {{ editable = "." }}\n')
    return path


def _run(monkeypatch, base, head, lock):
    monkeypatch.setattr(
        "sys.argv",
        ["check", "--base-pyproject", str(base), "--head-pyproject", str(head), "--head-lock", str(lock)],
    )
    return check.main()


def test_reads_the_project_version(tmp_path):
    assert check.read_project_version(_pyproject(tmp_path, "p.toml", "4.18.0")) == "4.18.0"


def test_reads_the_locked_version(tmp_path):
    assert check.read_lock_version(_lock(tmp_path, "5.0.0")) == "5.0.0"


def test_a_lock_without_the_project_has_no_version(tmp_path):
    path = tmp_path / "uv.lock"
    path.write_text('version = 1\n\n[[package]]\nname = "fastapi"\nversion = "0.141.1"\n')
    assert check.read_lock_version(path) is None


def test_the_real_lock_matches_the_real_pyproject():
    root = SCRIPT.parents[2]
    assert check.read_lock_version(root / "uv.lock") == check.read_project_version(root / "pyproject.toml")


@pytest.mark.parametrize(("version", "parsed"), [("4.18.0", (4, 18, 0)), ("10.0.1", (10, 0, 1)), ("0.0.0", (0, 0, 0))])
def test_parses_major_minor_patch_versions(version, parsed):
    assert check.parse_version(version) == parsed


@pytest.mark.parametrize("version", ["5", "5.0", "5.0.0.1", "5.0.0rc1", "v5.0.0", "5..0", "5.0.x", ""])
def test_anything_but_major_minor_patch_is_refused(version):
    with pytest.raises(SystemExit, match="not a MAJOR.MINOR.PATCH version"):
        check.parse_version(version)


def test_the_next_versions_reset_the_numbers_to_their_right():
    assert check.next_versions((4, 18, 1)) == {"patch": (4, 18, 2), "minor": (4, 19, 0), "major": (5, 0, 0)}


def test_versions_are_written_back_as_dotted_strings():
    assert check.format_version((5, 0, 0)) == "5.0.0"


@pytest.mark.parametrize(
    ("base", "head", "bump"),
    [
        ("4.18.0", "4.18.1", "patch"),
        ("4.18.0", "4.19.0", "minor"),
        ("4.18.0", "5.0.0", "major"),
        ("4.18.3", "4.18.4", "patch"),
        ("4.18.3", "4.19.0", "minor"),
        ("4.18.3", "5.0.0", "major"),
        ("4.9.0", "4.10.0", "minor"),  # numbers, not text: 10 follows 9
        ("0.0.0", "0.0.1", "patch"),
    ],
)
def test_a_one_step_bump_passes(tmp_path, monkeypatch, capsys, base, head, bump):
    result = _run(
        monkeypatch, _pyproject(tmp_path, "base.toml", base), _pyproject(tmp_path, "head.toml", head), _lock(tmp_path, head)
    )

    assert result == 0
    assert f"Version raised from {base} to {head} (a {bump} bump)" in capsys.readouterr().out


@pytest.mark.parametrize(
    "head",
    [
        "4.18.0",  # unchanged
        "4.17.9",  # lower
        "3.99.99",  # lower major
        "4.18.2",  # two patches
        "4.20.0",  # two minors
        "6.0.0",  # two majors
        "4.19.1",  # a minor that keeps a patch
        "5.0.1",  # a major that keeps a patch
        "5.1.0",  # a major that keeps a minor
        "5.18.0",  # a major that does not reset the minor
    ],
)
def test_anything_but_a_one_step_bump_fails(tmp_path, monkeypatch, capsys, head):
    base = _pyproject(tmp_path, "base.toml", "4.18.0")
    result = _run(monkeypatch, base, _pyproject(tmp_path, "head.toml", head), _lock(tmp_path, head))

    output = capsys.readouterr().out
    assert result == 1
    assert f"must go up by exactly one step from 4.18.0, but this PR sets it to {head}" in output
    # It says what the version could be instead
    for allowed in ("4.18.1", "4.19.0", "5.0.0"):
        assert allowed in output


def test_a_version_that_is_not_major_minor_patch_fails(tmp_path, monkeypatch):
    base = _pyproject(tmp_path, "base.toml", "4.18.0")

    with pytest.raises(SystemExit, match="not a MAJOR.MINOR.PATCH version"):
        _run(monkeypatch, base, _pyproject(tmp_path, "head.toml", "5.0"), _lock(tmp_path, "5.0"))


def test_a_stale_lock_fails(tmp_path, monkeypatch, capsys):
    base = _pyproject(tmp_path, "base.toml", "4.18.0")
    result = _run(monkeypatch, base, _pyproject(tmp_path, "head.toml", "5.0.0"), _lock(tmp_path, "4.18.0"))

    assert result == 1
    assert "uv.lock says 4.18.0" in capsys.readouterr().out
