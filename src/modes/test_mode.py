"""Test mode: run test scripts and report results."""

import logging
import subprocess

from src.config import RepoConfig
from src.notify.webhook import push_test_result
from src.repo import CommitInfo, get_commits_between

logger = logging.getLogger(__name__)


def run_test_script(script: str, cwd: str) -> int:
    """Run a test script and return exit code."""
    try:
        result = subprocess.run(
            [script], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return result.returncode
    except FileNotFoundError:
        logger.error(f"Test script not found: {script}")
        return 1
    except Exception as e:
        logger.error(f"Test execution error: {e}")
        return 1


def process_commit(
    repo_config: RepoConfig,
    commit: CommitInfo,
    branch: str,
    last_pass_hash: str = None,
) -> bool:
    """Process a single commit in test mode. Returns True if test passed."""
    logger.info(f"[{repo_config.name}] Running tests for {commit.hash[:8]}")

    exit_code = run_test_script(repo_config.test_script, repo_config.path)
    passed = exit_code == 0

    suspects = ""
    if not passed and last_pass_hash:
        suspect_commits = get_commits_between(
            repo_config.path, last_pass_hash, commit.hash
        )
        suspects = "\n".join(
            f"  {c.hash[:8]} {c.author}: {c.message}" for c in suspect_commits
        )

    push_test_result(
        webhook_url=repo_config.webhook_url,
        repo_name=repo_config.name,
        branch=branch,
        passed=passed,
        author=commit.author,
        commit_hash=commit.hash,
        commit_message=commit.message,
        suspects=suspects,
    )
    return passed
