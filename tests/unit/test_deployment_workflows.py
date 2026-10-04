"""Execute production promotion against local Git repositories to prove commit pinning."""

import os
import subprocess
import textwrap
from pathlib import Path

import pytest


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True, stderr=subprocess.PIPE).strip()


@pytest.fixture
def promotion_repo(tmp_path):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    repo = tmp_path / "checkout"
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "remote", "add", "origin", str(remote))
    (repo / "version").write_text("base")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "push", "origin", "main")
    git(repo, "checkout", "-b", "dev")
    (repo / "version").write_text("approved")
    git(repo, "commit", "-am", "approved")
    target = git(repo, "rev-parse", "HEAD")
    (repo / "version").write_text("later dev change")
    git(repo, "commit", "-am", "later change")
    git(repo, "push", "origin", "dev")
    git(repo, "checkout", "main")
    return repo, remote, base, target


def promote(repo, target):
    workflow = Path(".github/workflows/deploy_prod.yml").read_text()
    marker = "      - name: Verify release tag and fast-forward main to the approved commit\n        id: promote\n        run: |\n"
    script = textwrap.dedent(workflow.split(marker, 1)[1].split("\n  build_and_push_image:", 1)[0])
    script = script.replace("${{ steps.app-token.outputs.app-slug }}", "release-bot")
    return subprocess.run(
        ["bash", "-c", script],
        cwd=repo,
        env={**os.environ, "TARGET_SHA": target, "TAG": "v4.17.0", "GITHUB_OUTPUT": str(repo / "workflow-output")},
        capture_output=True,
        text=True,
    )


def test_production_promotes_approved_commit_when_dev_advances(promotion_repo):
    repo, remote, _, target = promotion_repo
    result = promote(repo, target)
    assert result.returncode == 0, result.stderr
    assert git(remote, "rev-parse", "main") == target
    assert git(remote, "rev-parse", "dev") != target
    assert (repo / "workflow-output").read_text() == f"previous_sha={git(repo, 'rev-parse', 'HEAD~1')}\n"


def test_production_refuses_to_rewind_main(promotion_repo):
    repo, remote, _, target = promotion_repo
    git(repo, "merge", "--ff-only", "origin/dev")
    git(repo, "push", "origin", "main")
    previous = git(remote, "rev-parse", "main")
    result = promote(repo, target)
    assert result.returncode != 0
    assert "cannot fast-forward" in result.stdout
    assert git(remote, "rev-parse", "main") == previous


def test_production_rollback_uses_release_tag_after_failed_promotion(promotion_repo):
    repo, remote, base, failed = promotion_repo
    git(repo, "tag", "v4.16.0", base)
    git(repo, "push", "origin", "v4.16.0")
    git(repo, "merge", "--ff-only", failed)
    git(repo, "push", "origin", "main")
    target = git(repo, "rev-parse", "origin/dev")
    result = promote(repo, target)
    assert result.returncode == 0, result.stderr
    assert (repo / "workflow-output").read_text() == f"previous_sha={base}\n"
    assert git(remote, "rev-parse", "main") == target


def test_production_rejects_conflicting_release_tag_before_main_changes(promotion_repo):
    repo, remote, base, target = promotion_repo
    git(repo, "tag", "v4.17.0", base)
    git(repo, "push", "origin", "v4.17.0")
    result = promote(repo, target)
    assert result.returncode != 0
    assert "different commit" in result.stdout
    assert git(remote, "rev-parse", "main") == base
