"""Tests for configuration loading and validation."""

import os
import tempfile

import pytest

from src.config import AppConfig, load_config


@pytest.fixture
def valid_config_yaml():
    return """
global:
  llm_base_url: "http://localhost:8080/v1/"
  llm_api_key: "test-key"
  llm_model: "test-model"
  poll_interval_minutes: 10

repos:
  - name: "Test Repo"
    path: "/tmp/test"
    branches:
      - "main"
    sync_command: "git fetch origin"
    mode: test
    test_script: "./run.sh"
    webhook_url: "https://example.com/webhook"
    poll_interval_minutes: 5

  - name: "Watch Repo"
    path: "/tmp/watch"
    branches:
      - "dev"
    mode: watch
    watch_paths:
      - "src/"
      - "include/*.h"
    webhook_url: "https://example.com/webhook2"
    ai_analysis: true
"""


@pytest.fixture
def config_file(valid_config_yaml):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(valid_config_yaml)
        f.flush()
        yield f.name
    os.unlink(f.name)


def test_load_valid_config(config_file):
    config = load_config(config_file)
    assert isinstance(config, AppConfig)
    assert config.global_config.llm_base_url == "http://localhost:8080/v1/"
    assert config.global_config.llm_api_key == "test-key"
    assert config.global_config.llm_model == "test-model"
    assert config.global_config.poll_interval_minutes == 10
    assert len(config.repos) == 2


def test_load_test_repo(config_file):
    config = load_config(config_file)
    repo = config.repos[0]
    assert repo.name == "Test Repo"
    assert repo.mode == "test"
    assert repo.test_script == "./run.sh"
    assert repo.branches == ["main"]
    assert repo.poll_interval_minutes == 5


def test_load_watch_repo(config_file):
    config = load_config(config_file)
    repo = config.repos[1]
    assert repo.name == "Watch Repo"
    assert repo.mode == "watch"
    assert repo.watch_paths == ["src/", "include/*.h"]
    assert repo.ai_analysis is True


def test_missing_config_file():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path.yaml")


def test_empty_config():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("")
        f.flush()
        path = f.name
    try:
        with pytest.raises(ValueError, match="empty"):
            load_config(path)
    finally:
        os.unlink(path)


def test_test_mode_missing_script():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""
repos:
  - name: "Bad"
    path: "/tmp"
    branches: ["main"]
    mode: test
    webhook_url: "http://x"
""")
        f.flush()
        path = f.name
    try:
        with pytest.raises(ValueError, match="test_script"):
            load_config(path)
    finally:
        os.unlink(path)


def test_watch_mode_missing_paths():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""
repos:
  - name: "Bad"
    path: "/tmp"
    branches: ["main"]
    mode: watch
    webhook_url: "http://x"
""")
        f.flush()
        path = f.name
    try:
        with pytest.raises(ValueError, match="watch_paths"):
            load_config(path)
    finally:
        os.unlink(path)


def test_invalid_mode():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""
repos:
  - name: "Bad"
    path: "/tmp"
    branches: ["main"]
    mode: invalid
    webhook_url: "http://x"
""")
        f.flush()
        path = f.name
    try:
        with pytest.raises(ValueError, match="invalid mode"):
            load_config(path)
    finally:
        os.unlink(path)


def test_global_ai_prompt():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""
global:
  ai_prompt: "Custom prompt here"
repos:
  - name: "R"
    path: "/tmp"
    branches: ["main"]
    mode: watch
    watch_paths: ["src/"]
    webhook_url: "http://x"
""")
        f.flush()
        path = f.name
    try:
        config = load_config(path)
        assert config.global_config.ai_prompt == "Custom prompt here"
    finally:
        os.unlink(path)


def test_repo_ai_prompt_override():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""
global:
  ai_prompt: "Global prompt"
repos:
  - name: "R"
    path: "/tmp"
    branches: ["main"]
    mode: watch
    watch_paths: ["src/"]
    webhook_url: "http://x"
    ai_prompt: "Repo specific prompt"
""")
        f.flush()
        path = f.name
    try:
        config = load_config(path)
        assert config.global_config.ai_prompt == "Global prompt"
        assert config.repos[0].ai_prompt == "Repo specific prompt"
    finally:
        os.unlink(path)


def test_global_webhook_and_sync():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""
global:
  webhook_url: "http://global-hook"
  sync_command: "git fetch origin"
repos:
  - name: "R"
    path: "/tmp"
    branches: ["main"]
    mode: watch
    watch_paths: ["src/"]
""")
        f.flush()
        path = f.name
    try:
        config = load_config(path)
        assert config.global_config.webhook_url == "http://global-hook"
        assert config.global_config.sync_command == "git fetch origin"
        assert config.repos[0].webhook_url == ""  # not set at repo level
    finally:
        os.unlink(path)


def test_repo_remote_field(config_file):
    """Verify remote field is parsed from config."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""
repos:
  - name: "Test"
    path: "/tmp"
    branches: ["main"]
    remote: "upstream"
    mode: watch
    watch_paths: ["src/"]
    webhook_url: "http://x"
""")
        f.flush()
        path = f.name

    try:
        config = load_config(path)
        assert config.repos[0].remote == "upstream"
    finally:
        os.unlink(path)


def test_repo_remote_default_empty(config_file):
    """Verify remote defaults to empty string when not specified."""
    config = load_config(config_file)
    assert config.repos[0].remote == ""
