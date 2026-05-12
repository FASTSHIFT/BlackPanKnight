"""Tests for git repository operations."""

import os
import subprocess
import tempfile

import pytest

from src.repo import (
    get_branch_head,
    get_commits_between,
    get_single_commit,
    run_git,
    sync_repo,
)


@pytest.fixture
def git_repo():
    """Create a temporary git repo with some commits."""
    tmpdir = tempfile.mkdtemp()
    subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmpdir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmpdir,
        check=True,
        capture_output=True,
    )

    # First commit
    filepath = os.path.join(tmpdir, "file.txt")
    with open(filepath, "w") as f:
        f.write("hello\n")
    subprocess.run(["git", "add", "."], cwd=tmpdir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=tmpdir,
        check=True,
        capture_output=True,
    )

    # Second commit
    with open(filepath, "w") as f:
        f.write("hello world\n")
    subprocess.run(["git", "add", "."], cwd=tmpdir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "update file"],
        cwd=tmpdir,
        check=True,
        capture_output=True,
    )

    yield tmpdir

    # Cleanup
    subprocess.run(["rm", "-rf", tmpdir])


def test_run_git_success(git_repo):
    result = run_git(["rev-parse", "HEAD"], cwd=git_repo)
    assert result is not None
    assert len(result) == 40  # SHA-1 hash


def test_run_git_failure(git_repo):
    result = run_git(["rev-parse", "--verify", "nonexistent"], cwd=git_repo)
    assert result is None


def test_get_branch_head(git_repo):
    # Get current branch name
    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=git_repo)
    head = get_branch_head(git_repo, branch)
    assert head is not None
    assert len(head) == 40


def test_get_branch_head_nonexistent(git_repo):
    head = get_branch_head(git_repo, "nonexistent-branch")
    assert head is None


def test_sync_repo_no_command(git_repo):
    assert sync_repo(git_repo, "") is True


def test_sync_repo_valid_command(git_repo):
    assert sync_repo(git_repo, "git status") is True


def test_sync_repo_invalid_command(git_repo):
    assert sync_repo(git_repo, "false") is False


def test_get_single_commit(git_repo):
    head = run_git(["rev-parse", "HEAD"], cwd=git_repo)
    commit = get_single_commit(git_repo, head)
    assert commit is not None
    assert commit.hash == head
    assert commit.author == "Test"
    assert commit.message == "update file"


def test_get_commits_between(git_repo):
    # Get first and second commit hashes
    log = run_git(["log", "--format=%H", "--reverse"], cwd=git_repo)
    hashes = log.split("\n")
    assert len(hashes) == 2

    commits = get_commits_between(git_repo, hashes[0], hashes[1])
    assert len(commits) >= 1
    assert commits[0].message == "update file"


def test_get_recent_commits(git_repo):
    from src.repo import get_recent_commits

    head = run_git(["rev-parse", "HEAD"], cwd=git_repo)
    commits = get_recent_commits(git_repo, head, n=2)
    assert len(commits) == 2
    assert commits[0].message == "update file"
    assert commits[1].message == "initial commit"


def test_get_recent_commits_single(git_repo):
    from src.repo import get_recent_commits

    head = run_git(["rev-parse", "HEAD"], cwd=git_repo)
    commits = get_recent_commits(git_repo, head, n=1)
    assert len(commits) == 1
    assert commits[0].hash == head
    assert commits[0].files_changed == ["file.txt"]
