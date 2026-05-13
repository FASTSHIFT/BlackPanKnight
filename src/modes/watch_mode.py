"""Watch mode: monitor file changes and run AI analysis."""

import fnmatch
import logging
from typing import Optional

from src.ai.client import AnalysisResult, LLMClient
from src.config import GlobalConfig, RepoConfig
from src.notify.webhook import push_watch_result
from src.repo import CommitInfo, get_commit_diff

logger = logging.getLogger(__name__)


def filter_commit_by_paths(commit: CommitInfo, watch_paths: list) -> list:
    """Filter commit's changed files against watch_paths patterns."""
    matched = []
    for f in commit.files_changed:
        for pattern in watch_paths:
            if fnmatch.fnmatch(f, pattern) or f.startswith(pattern):
                matched.append(f)
                break
    return matched


def compute_diff_stat(diff_content: str) -> str:
    """Compute +/- line stats from a diff string."""
    added = 0
    removed = 0
    for line in diff_content.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return f"+{added}/-{removed}"


def process_commit(
    repo_config: RepoConfig,
    global_config: GlobalConfig,
    commit: CommitInfo,
    branch: str,
    llm_client: Optional[LLMClient] = None,
) -> bool:
    """Process a single commit in watch mode."""
    matched_files = filter_commit_by_paths(commit, repo_config.watch_paths)
    if not matched_files:
        return False

    logger.info(
        f"[{repo_config.name}] Commit {commit.hash[:8]} matched "
        f"{len(matched_files)} file(s)"
    )

    # Get diff for matched files only
    diff_content = get_commit_diff(repo_config.path, commit.hash, matched_files)
    diff_stat = compute_diff_stat(diff_content)

    # AI analysis
    risk_level = ""
    ai_summary = ""
    if repo_config.ai_analysis and llm_client and diff_content:
        prompt_template = repo_config.ai_prompt or global_config.ai_prompt
        result: Optional[AnalysisResult] = llm_client.analyze_diff(
            commit_hash=commit.hash,
            author=commit.author,
            message=commit.message,
            diff_content=diff_content,
            prompt_template=prompt_template,
        )
        if result:
            risk_level = result.risk_level
            ai_summary = result.summary

    # Push to webhook
    return push_watch_result(
        webhook_url=repo_config.webhook_url,
        repo_name=repo_config.name,
        branch=branch,
        author=commit.author,
        commit_hash=commit.hash,
        commit_message=commit.message,
        files_changed=matched_files,
        diff_stat=diff_stat,
        risk_level=risk_level,
        ai_summary=ai_summary,
        change_id=commit.change_id,
        remote=repo_config.remote,
    )
