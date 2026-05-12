"""Git repository operations for BlackPanKnight."""

import logging
import subprocess
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CommitInfo:
    hash: str
    author: str
    message: str
    date: str
    files_changed: list


def run_git(args: list, cwd: str) -> Optional[str]:
    """Run a git command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"git {' '.join(args)} failed: {e.stderr.strip()}")
        return None


def sync_repo(path: str, sync_command: str) -> bool:
    """Sync repository using the configured command."""
    if not sync_command:
        return True
    try:
        subprocess.run(
            sync_command,
            cwd=path,
            check=True,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Sync failed in {path}: {e}")
        return False


def get_branch_head(path: str, branch: str) -> Optional[str]:
    """Get the latest commit hash for a branch.

    Tries multiple remote prefixes to handle repos with non-origin remotes.
    """
    # Get all remotes for this repo
    remotes_output = run_git(["remote"], cwd=path)
    remotes = remotes_output.split("\n") if remotes_output else ["origin"]

    candidates = [f"{r}/{branch}" for r in remotes]
    candidates.extend([branch, f"refs/heads/{branch}"])

    for ref in candidates:
        result = run_git(["rev-parse", "--verify", ref], cwd=path)
        if result:
            return result
    return None


def get_commits_between(path: str, old_hash: str, new_hash: str) -> list:
    """Get list of CommitInfo between two commits (exclusive old, inclusive new)."""
    fmt = "%H%n%an%n%s%n%ai"
    log_output = run_git(
        ["log", f"{old_hash}..{new_hash}", f"--format={fmt}", "--name-only"],
        cwd=path,
    )
    if not log_output:
        return []

    commits = []
    entries = log_output.split("\n\n")
    for entry in entries:
        lines = entry.strip().split("\n")
        if len(lines) < 4:
            continue
        commit = CommitInfo(
            hash=lines[0],
            author=lines[1],
            message=lines[2],
            date=lines[3],
            files_changed=[f for f in lines[4:] if f.strip()],
        )
        commits.append(commit)
    return commits


def get_commit_diff(path: str, commit_hash: str, file_paths: list = None) -> str:
    """Get the diff for a specific commit, optionally filtered by paths."""
    args = ["show", "--format=", "--patch", commit_hash]
    if file_paths:
        args.append("--")
        args.extend(file_paths)
    return run_git(args, cwd=path) or ""


def get_single_commit(path: str, commit_hash: str) -> Optional[CommitInfo]:
    """Get info for a single commit."""
    fmt = "%H%n%an%n%s%n%ai"
    output = run_git(
        ["log", "-1", f"--format={fmt}", "--name-only", commit_hash],
        cwd=path,
    )
    if not output:
        return None
    lines = output.strip().split("\n")
    if len(lines) < 4:
        return None
    return CommitInfo(
        hash=lines[0],
        author=lines[1],
        message=lines[2],
        date=lines[3],
        files_changed=[f for f in lines[4:] if f.strip()],
    )
