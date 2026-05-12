"""Configuration loader and validator for BlackPanKnight."""

import os
from dataclasses import dataclass, field
from typing import Optional

import yaml


@dataclass
class GlobalConfig:
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    poll_interval_minutes: int = 30
    webhook_url: str = ""
    sync_command: str = ""
    ai_prompt: str = ""


@dataclass
class RepoConfig:
    name: str = ""
    path: str = ""
    branches: list = field(default_factory=list)
    sync_command: str = ""
    mode: str = "watch"  # "test" or "watch"
    test_script: str = ""
    webhook_url: str = ""
    watch_paths: list = field(default_factory=list)
    ai_analysis: bool = True
    ai_prompt: str = ""
    poll_interval_minutes: Optional[int] = None


@dataclass
class AppConfig:
    global_config: GlobalConfig = field(default_factory=GlobalConfig)
    repos: list = field(default_factory=list)


def load_config(config_path: str) -> AppConfig:
    """Load and validate configuration from YAML file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not raw:
        raise ValueError("Config file is empty")

    app_config = AppConfig()

    # Parse global config
    global_raw = raw.get("global", {})
    app_config.global_config = GlobalConfig(
        llm_base_url=global_raw.get("llm_base_url", ""),
        llm_api_key=global_raw.get("llm_api_key", ""),
        llm_model=global_raw.get("llm_model", "gpt-4o"),
        poll_interval_minutes=global_raw.get("poll_interval_minutes", 30),
        webhook_url=global_raw.get("webhook_url", ""),
        sync_command=global_raw.get("sync_command", ""),
        ai_prompt=global_raw.get("ai_prompt", ""),
    )

    # Parse repos
    for repo_raw in raw.get("repos", []):
        repo = RepoConfig(
            name=repo_raw.get("name", ""),
            path=repo_raw.get("path", ""),
            branches=repo_raw.get("branches", []),
            sync_command=repo_raw.get("sync_command", ""),
            mode=repo_raw.get("mode", "watch"),
            test_script=repo_raw.get("test_script", ""),
            webhook_url=repo_raw.get("webhook_url", ""),
            watch_paths=repo_raw.get("watch_paths", []),
            ai_analysis=repo_raw.get("ai_analysis", True),
            ai_prompt=repo_raw.get("ai_prompt", ""),
            poll_interval_minutes=repo_raw.get("poll_interval_minutes"),
        )
        _validate_repo(repo)
        app_config.repos.append(repo)

    return app_config


def _validate_repo(repo: RepoConfig):
    """Validate a single repo configuration."""
    if not repo.name:
        raise ValueError("Repo config missing 'name'")
    if not repo.path:
        raise ValueError(f"Repo '{repo.name}' missing 'path'")
    if not repo.branches:
        raise ValueError(f"Repo '{repo.name}' missing 'branches'")
    if repo.mode not in ("test", "watch"):
        raise ValueError(f"Repo '{repo.name}' invalid mode: {repo.mode}")
    if repo.mode == "test" and not repo.test_script:
        raise ValueError(f"Repo '{repo.name}' mode=test requires 'test_script'")
    if repo.mode == "watch" and not repo.watch_paths:
        raise ValueError(f"Repo '{repo.name}' mode=watch requires 'watch_paths'")
