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
