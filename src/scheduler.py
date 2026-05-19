"""Polling scheduler for multi-repo monitoring."""

import logging
import os
import time
from typing import Optional

from src.ai.client import LLMClient
from src.config import AppConfig
from src.modes import test_mode, watch_mode
from src.repo import (
    get_branch_head,
    get_commits_between,
    get_recent_commits,
    sync_repo,
)

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, config: AppConfig):
        self.config = config
        self.llm_client: Optional[LLMClient] = None
        # Per-repo, per-branch state: {(repo_name, branch): commit_hash}
        self._last_commit: dict = {}

        # Initialize LLM client if any repo needs AI
        gc = config.global_config
        if gc.llm_base_url and gc.llm_api_key:
            self.llm_client = LLMClient(
                base_url=gc.llm_base_url,
                api_key=gc.llm_api_key,
                model=gc.llm_model,
            )

    def run_once(self):
        """Run a single polling cycle across all repos."""
        for repo_config in self.config.repos:
            if not os.path.isdir(repo_config.path):
                logger.warning(
                    f"[{repo_config.name}] Path not found: {repo_config.path}, skipping"
                )
                continue

            logger.info(f"Checking repo: {repo_config.name}")

            if not sync_repo(repo_config.path, repo_config.sync_command):
                continue

            for branch in repo_config.branches:
                self._check_branch(repo_config, branch)

    def _check_branch(self, repo_config, branch: str):
        """Check a single branch for new commits."""
        # Fallback webhook_url and sync_command from global config
        if not repo_config.webhook_url:
            repo_config.webhook_url = self.config.global_config.webhook_url
        if not repo_config.sync_command:
            repo_config.sync_command = self.config.global_config.sync_command
        if not repo_config.ai_prompt:
            repo_config.ai_prompt = self.config.global_config.ai_prompt

        key = (repo_config.name, branch)
        current_hash = get_branch_head(repo_config.path, branch)
        if not current_hash:
            logger.warning(f"Cannot resolve branch {branch} in {repo_config.name}")
            return

        last_hash = self._last_commit.get(key)
        if last_hash == current_hash:
            return  # No new commits

        if last_hash is None:
            # First run: just record current state, don't process
            logger.info(
                f"[{repo_config.name}/{branch}] Initial commit: {current_hash[:8]}"
            )
            self._last_commit[key] = current_hash
            return

        # Get new commits
        commits = get_commits_between(repo_config.path, last_hash, current_hash)
        if not commits:
            self._last_commit[key] = current_hash
            return

        logger.info(
            f"[{repo_config.name}/{branch}] {len(commits)} new commit(s) detected"
        )

        if repo_config.mode == "test":
            # Only test the latest commit (HEAD), skip intermediate ones
            test_mode.process_commit(
                repo_config,
                commits[0],
                branch,
                None,
                self.llm_client,
            )
        elif repo_config.mode == "watch":
            for commit in commits:
                watch_mode.process_commit(
                    repo_config,
                    self.config.global_config,
                    commit,
                    branch,
                    self.llm_client,
                )

        self._last_commit[key] = current_hash

    def run_forever(self):
        """Run polling loop indefinitely."""
        logger.info("BlackPanKnight started. Monitoring repos...")
        while True:
            try:
                self.run_once()
            except Exception as e:
                logger.error(f"Error in polling cycle: {e}", exc_info=True)

            interval = self.config.global_config.poll_interval_minutes
            logger.info(f"Sleeping {interval} minutes...")
            time.sleep(interval * 60)

    def run_test_now(self):
        """Immediately run tests for all test-mode repos and report results."""
        logger.info("Running tests now...")
        for repo_config in self.config.repos:
            if repo_config.mode != "test":
                continue

            if not os.path.isdir(repo_config.path):
                logger.warning(
                    f"[{repo_config.name}] Path not found: {repo_config.path}, skipping"
                )
                continue

            # Apply global fallbacks
            if not repo_config.webhook_url:
                repo_config.webhook_url = self.config.global_config.webhook_url
            if not repo_config.sync_command:
                repo_config.sync_command = self.config.global_config.sync_command

            if not sync_repo(repo_config.path, repo_config.sync_command):
                logger.error(f"[{repo_config.name}] Sync failed, skipping")
                continue

            for branch in repo_config.branches:
                head = get_branch_head(repo_config.path, branch)
                if not head:
                    logger.warning(
                        f"[{repo_config.name}] Cannot resolve branch {branch}"
                    )
                    continue

                commit = get_recent_commits(repo_config.path, head, n=1)
                if not commit:
                    continue

                logger.info(f"[{repo_config.name}/{branch}] Running test...")
                test_mode.process_commit(
                    repo_config, commit[0], branch, None, self.llm_client
                )

    def run_head(self, n: int = 1):
        """Analyze the latest N commits on each branch (no state tracking)."""
        logger.info(f"Analyzing HEAD (latest {n} commits per branch)...")
        for repo_config in self.config.repos:
            if not os.path.isdir(repo_config.path):
                logger.warning(
                    f"[{repo_config.name}] Path not found: {repo_config.path}, skipping"
                )
                continue

            # Apply global fallbacks
            if not repo_config.webhook_url:
                repo_config.webhook_url = self.config.global_config.webhook_url
            if not repo_config.sync_command:
                repo_config.sync_command = self.config.global_config.sync_command
            if not repo_config.ai_prompt:
                repo_config.ai_prompt = self.config.global_config.ai_prompt

            if not sync_repo(repo_config.path, repo_config.sync_command):
                continue

            for branch in repo_config.branches:
                head = get_branch_head(repo_config.path, branch)
                if not head:
                    logger.warning(
                        f"[{repo_config.name}] Cannot resolve branch {branch}"
                    )
                    continue

                commits = get_recent_commits(repo_config.path, head, n)
                logger.info(
                    f"[{repo_config.name}/{branch}] Analyzing {len(commits)} commit(s)"
                )

                for commit in commits:
                    if repo_config.mode == "test":
                        test_mode.process_commit(
                            repo_config, commit, branch, None, self.llm_client
                        )
                    elif repo_config.mode == "watch":
                        watch_mode.process_commit(
                            repo_config,
                            self.config.global_config,
                            commit,
                            branch,
                            self.llm_client,
                        )
