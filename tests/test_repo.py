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


@pytest.fixture
def multi_file_repo():
    """Create a repo with multi-file commits and subdirectories."""
    tmpdir = tempfile.mkdtemp()
    subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "dev@test.com"],
        cwd=tmpdir, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Developer"],
        cwd=tmpdir, check=True, capture_output=True,
    )

    # Create subdirectories
    os.makedirs(os.path.join(tmpdir, "src/core"), exist_ok=True)
    os.makedirs(os.path.join(tmpdir, "include"), exist_ok=True)
    os.makedirs(os.path.join(tmpdir, "drivers/gpu"), exist_ok=True)

    # Commit 1: single file
    with open(os.path.join(tmpdir, "README.md"), "w") as f:
        f.write("# Project\n")
    subprocess.run(["git", "add", "."], cwd=tmpdir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=tmpdir, check=True, capture_output=True,
    )

    # Commit 2: multiple files across directories
    with open(os.path.join(tmpdir, "src/core/sched.c"), "w") as f:
        f.write("void sched_init(void) {}\n")
    with open(os.path.join(tmpdir, "include/spinlock.h"), "w") as f:
        f.write("#pragma once\n")
    with open(os.path.join(tmpdir, "drivers/gpu/render.c"), "w") as f:
        f.write("void gpu_render(void) {}\n")
    subprocess.run(["git", "add", "."], cwd=tmpdir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: add core modules"],
        cwd=tmpdir, check=True, capture_output=True,
    )

    # Commit 3: modify existing + add new
    with open(os.path.join(tmpdir, "src/core/sched.c"), "w") as f:
        f.write("void sched_init(void) { /* optimized */ }\n")
    with open(os.path.join(tmpdir, "src/core/mutex.c"), "w") as f:
        f.write("void mutex_lock(void) {}\n")
    subprocess.run(["git", "add", "."], cwd=tmpdir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "perf: optimize scheduler lock"],
        cwd=tmpdir, check=True, capture_output=True,
    )

    yield tmpdir
    subprocess.run(["rm", "-rf", tmpdir])


def test_multi_file_commit_files_changed(multi_file_repo):
    """Verify files_changed correctly lists all files in a multi-file commit."""
    head = run_git(["rev-parse", "HEAD"], cwd=multi_file_repo)
    commit = get_single_commit(multi_file_repo, head)
    assert commit is not None
    assert sorted(commit.files_changed) == ["src/core/mutex.c", "src/core/sched.c"]


def test_commits_between_multi_file(multi_file_repo):
    """Verify get_commits_between parses multiple commits with multiple files."""
    log = run_git(["log", "--format=%H", "--reverse"], cwd=multi_file_repo)
    hashes = log.split("\n")
    assert len(hashes) == 3

    # Get commits 2 and 3 (between first and last)
    commits = get_commits_between(multi_file_repo, hashes[0], hashes[2])
    assert len(commits) == 2

    # Most recent first
    assert commits[0].message == "perf: optimize scheduler lock"
    assert sorted(commits[0].files_changed) == ["src/core/mutex.c", "src/core/sched.c"]

    assert commits[1].message == "feat: add core modules"
    assert sorted(commits[1].files_changed) == [
        "drivers/gpu/render.c", "include/spinlock.h", "src/core/sched.c"
    ]


def test_commits_between_preserves_author(multi_file_repo):
    """Verify author field is correctly parsed for each commit."""
    log = run_git(["log", "--format=%H", "--reverse"], cwd=multi_file_repo)
    hashes = log.split("\n")
    commits = get_commits_between(multi_file_repo, hashes[0], hashes[2])
    for c in commits:
        assert c.author == "Developer"


def test_single_commit_with_subdirectory_files(multi_file_repo):
    """Verify subdirectory paths are fully preserved in files_changed."""
    log = run_git(["log", "--format=%H", "--reverse"], cwd=multi_file_repo)
    hashes = log.split("\n")
    # Second commit has files in subdirs
    commit = get_single_commit(multi_file_repo, hashes[1])
    assert "drivers/gpu/render.c" in commit.files_changed
    assert "include/spinlock.h" in commit.files_changed
    assert "src/core/sched.c" in commit.files_changed


def test_commits_between_no_new_commits(multi_file_repo):
    """Verify empty list when old_hash == new_hash."""
    head = run_git(["rev-parse", "HEAD"], cwd=multi_file_repo)
    commits = get_commits_between(multi_file_repo, head, head)
    assert commits == []


def test_get_commit_diff_filtered(multi_file_repo):
    """Verify get_commit_diff filters by file paths correctly."""
    from src.repo import get_commit_diff

    log = run_git(["log", "--format=%H", "--reverse"], cwd=multi_file_repo)
    hashes = log.split("\n")
    # Commit 2 has 3 files, filter to only gpu
    diff = get_commit_diff(multi_file_repo, hashes[1], ["drivers/gpu/render.c"])
    assert "gpu_render" in diff
    assert "spinlock" not in diff


def test_get_commit_diff_no_filter(multi_file_repo):
    """Verify get_commit_diff returns full diff without filter."""
    from src.repo import get_commit_diff

    log = run_git(["log", "--format=%H", "--reverse"], cwd=multi_file_repo)
    hashes = log.split("\n")
    diff = get_commit_diff(multi_file_repo, hashes[1])
    assert "gpu_render" in diff
    assert "spinlock" in diff
    assert "sched_init" in diff
