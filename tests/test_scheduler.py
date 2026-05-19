"""Tests for the polling scheduler."""

from unittest.mock import MagicMock, patch

import pytest

from src.config import AppConfig, GlobalConfig, RepoConfig
from src.scheduler import Scheduler


@pytest.fixture
def watch_config():
    return AppConfig(
        global_config=GlobalConfig(
            llm_base_url="http://localhost/v1/",
            llm_api_key="test",
            llm_model="test-model",
            poll_interval_minutes=1,
        ),
        repos=[
            RepoConfig(
                name="Test Watch",
                path="/tmp/fake",
                branches=["main"],
                mode="watch",
                watch_paths=["src/"],
                webhook_url="http://hook",
                sync_command="echo ok",
            )
        ],
    )


@pytest.fixture
def test_config():
    return AppConfig(
        global_config=GlobalConfig(poll_interval_minutes=1),
        repos=[
            RepoConfig(
                name="Test Runner",
                path="/tmp/fake",
                branches=["main"],
                mode="test",
                test_script="./test.sh",
                webhook_url="http://hook",
            )
        ],
    )


def test_scheduler_init_with_llm(watch_config):
    scheduler = Scheduler(watch_config)
    assert scheduler.llm_client is not None


def test_scheduler_init_without_llm(test_config):
    scheduler = Scheduler(test_config)
    assert scheduler.llm_client is None


@patch("src.scheduler.os.path.isdir", return_value=True)
@patch("src.scheduler.sync_repo")
@patch("src.scheduler.get_branch_head")
def test_run_once_first_run_records_state(
    mock_head, mock_sync, mock_isdir, watch_config
):
    mock_sync.return_value = True
    mock_head.return_value = "abc123" * 7  # 42 chars but we just need non-None

    scheduler = Scheduler(watch_config)
    scheduler.run_once()

    # First run should just record state, not process
    assert scheduler._last_commit[("Test Watch", "main")] == "abc123" * 7


@patch("src.scheduler.os.path.isdir", return_value=True)
@patch("src.scheduler.sync_repo")
@patch("src.scheduler.get_branch_head")
def test_run_once_no_change(mock_head, mock_sync, mock_isdir, watch_config):
    mock_sync.return_value = True
    mock_head.return_value = "abc123"

    scheduler = Scheduler(watch_config)
    scheduler._last_commit[("Test Watch", "main")] = "abc123"
    scheduler.run_once()

    # No change, nothing should happen
    assert scheduler._last_commit[("Test Watch", "main")] == "abc123"


@patch("src.scheduler.os.path.isdir", return_value=True)
@patch("src.scheduler.watch_mode.process_commit")
@patch("src.scheduler.get_commits_between")
@patch("src.scheduler.sync_repo")
@patch("src.scheduler.get_branch_head")
def test_run_once_new_commits_watch(
    mock_head, mock_sync, mock_commits, mock_process, mock_isdir, watch_config
):
    mock_sync.return_value = True
    mock_head.return_value = "new_hash"
    mock_commits.return_value = [
        MagicMock(hash="new_hash", author="test", message="fix")
    ]
    mock_process.return_value = True

    scheduler = Scheduler(watch_config)
    scheduler._last_commit[("Test Watch", "main")] = "old_hash"
    scheduler.run_once()

    mock_process.assert_called_once()
    assert scheduler._last_commit[("Test Watch", "main")] == "new_hash"


@patch("src.scheduler.os.path.isdir", return_value=True)
@patch("src.scheduler.test_mode.process_commit")
@patch("src.scheduler.get_commits_between")
@patch("src.scheduler.sync_repo")
@patch("src.scheduler.get_branch_head")
def test_run_once_new_commits_test(
    mock_head, mock_sync, mock_commits, mock_process, mock_isdir, test_config
):
    mock_sync.return_value = True
    mock_head.return_value = "new_hash"
    mock_commits.return_value = [
        MagicMock(hash="new_hash", author="test", message="fix")
    ]
    mock_process.return_value = True  # test passed

    scheduler = Scheduler(test_config)
    scheduler._last_commit[("Test Runner", "main")] = "old_hash"
    scheduler.run_once()

    mock_process.assert_called_once()
    assert scheduler._last_commit[("Test Runner", "main")] == "new_hash"


@patch("src.scheduler.sync_repo")
def test_run_once_sync_failure(mock_sync, watch_config):
    mock_sync.return_value = False

    scheduler = Scheduler(watch_config)
    scheduler.run_once()

    # Should not crash, just skip
    assert ("Test Watch", "main") not in scheduler._last_commit


@patch("src.scheduler.sync_repo")
@patch("src.scheduler.get_branch_head")
def test_run_once_branch_unresolvable(mock_head, mock_sync, watch_config):
    mock_sync.return_value = True
    mock_head.return_value = None

    scheduler = Scheduler(watch_config)
    scheduler.run_once()

    assert ("Test Watch", "main") not in scheduler._last_commit


@patch("src.scheduler.os.path.isdir", return_value=True)
@patch("src.scheduler.watch_mode.process_commit")
@patch("src.scheduler.get_recent_commits")
@patch("src.scheduler.get_branch_head")
@patch("src.scheduler.sync_repo")
def test_run_head_watch(
    mock_sync, mock_head, mock_recent, mock_process, mock_isdir, watch_config
):
    mock_sync.return_value = True
    mock_head.return_value = "abc12345"
    mock_recent.return_value = [
        MagicMock(hash="abc12345", author="dev", message="fix perf")
    ]
    mock_process.return_value = True

    scheduler = Scheduler(watch_config)
    scheduler.run_head(n=1)

    mock_recent.assert_called_once_with("/tmp/fake", "abc12345", 1)
    mock_process.assert_called_once()


@patch("src.scheduler.os.path.isdir", return_value=True)
@patch("src.scheduler.test_mode.process_commit")
@patch("src.scheduler.get_recent_commits")
@patch("src.scheduler.get_branch_head")
@patch("src.scheduler.sync_repo")
def test_run_head_test(
    mock_sync, mock_head, mock_recent, mock_process, mock_isdir, test_config
):
    mock_sync.return_value = True
    mock_head.return_value = "def67890"
    mock_recent.return_value = [
        MagicMock(hash="def67890", author="dev", message="add test")
    ]
    mock_process.return_value = True

    scheduler = Scheduler(test_config)
    scheduler.run_head(n=1)

    mock_recent.assert_called_once_with("/tmp/fake", "def67890", 1)
    mock_process.assert_called_once()


@patch("src.scheduler.os.path.isdir", return_value=True)
@patch("src.scheduler.get_branch_head")
@patch("src.scheduler.sync_repo")
def test_run_head_branch_not_found(mock_sync, mock_head, mock_isdir, watch_config):
    mock_sync.return_value = True
    mock_head.return_value = None

    scheduler = Scheduler(watch_config)
    scheduler.run_head(n=1)


@patch("src.scheduler.os.path.isdir", return_value=True)
@patch("src.scheduler.sync_repo")
def test_run_head_sync_failure(mock_sync, mock_isdir, watch_config):
    mock_sync.return_value = False

    scheduler = Scheduler(watch_config)
    scheduler.run_head(n=1)


@patch("src.scheduler.os.path.isdir", return_value=True)
@patch("src.scheduler.test_mode.process_commit")
@patch("src.scheduler.get_recent_commits")
@patch("src.scheduler.sync_repo")
@patch("src.scheduler.get_branch_head")
def test_run_test_now(
    mock_head, mock_sync, mock_recent, mock_process, mock_isdir, test_config
):
    mock_sync.return_value = True
    mock_head.return_value = "head_hash"
    mock_recent.return_value = [
        MagicMock(hash="head_hash", author="dev", message="fix")
    ]
    mock_process.return_value = True

    scheduler = Scheduler(test_config)
    scheduler.run_test_now()

    mock_process.assert_called_once()


@patch("src.scheduler.os.path.isdir", return_value=True)
@patch("src.scheduler.test_mode.process_commit")
@patch("src.scheduler.get_recent_commits")
@patch("src.scheduler.sync_repo")
@patch("src.scheduler.get_branch_head")
def test_run_test_now_skips_watch_repos(
    mock_head, mock_sync, mock_recent, mock_process, mock_isdir, watch_config
):
    scheduler = Scheduler(watch_config)
    scheduler.run_test_now()

    # watch mode repos should be skipped
    mock_process.assert_not_called()


@patch("src.scheduler.os.path.isdir", return_value=True)
@patch("src.scheduler.sync_repo")
def test_run_test_now_sync_failure(mock_sync, mock_isdir, test_config):
    mock_sync.return_value = False

    scheduler = Scheduler(test_config)
    scheduler.run_test_now()


@patch("src.scheduler.os.path.isdir", return_value=True)
@patch("src.scheduler.test_mode.process_commit")
@patch("src.scheduler.get_commits_between")
@patch("src.scheduler.sync_repo")
@patch("src.scheduler.get_branch_head")
def test_test_mode_only_tests_latest_commit(
    mock_head, mock_sync, mock_commits, mock_process, mock_isdir, test_config
):
    """Test mode should only run tests on the latest commit, not all."""
    mock_sync.return_value = True
    mock_head.return_value = "new_hash"
    # 3 new commits, most recent first
    commits = [
        MagicMock(hash="commit_3_latest", author="c", message="third"),
        MagicMock(hash="commit_2", author="b", message="second"),
        MagicMock(hash="commit_1", author="a", message="first"),
    ]
    mock_commits.return_value = commits
    mock_process.return_value = True

    scheduler = Scheduler(test_config)
    scheduler._last_commit[("Test Runner", "main")] = "old_hash"
    scheduler.run_once()

    # Should only be called once with the latest commit
    mock_process.assert_called_once()
    call_args = mock_process.call_args[0]
    assert call_args[1].hash == "commit_3_latest"


@patch("src.scheduler.os.path.isdir", return_value=True)
@patch("src.scheduler.watch_mode.process_commit")
@patch("src.scheduler.get_commits_between")
@patch("src.scheduler.sync_repo")
@patch("src.scheduler.get_branch_head")
def test_watch_mode_processes_all_commits(
    mock_head, mock_sync, mock_commits, mock_process, mock_isdir, watch_config
):
    """Watch mode should process every new commit individually."""
    mock_sync.return_value = True
    mock_head.return_value = "new_hash"
    commits = [
        MagicMock(hash="commit_3", author="c", message="third"),
        MagicMock(hash="commit_2", author="b", message="second"),
        MagicMock(hash="commit_1", author="a", message="first"),
    ]
    mock_commits.return_value = commits
    mock_process.return_value = True

    scheduler = Scheduler(watch_config)
    scheduler._last_commit[("Test Watch", "main")] = "old_hash"
    scheduler.run_once()

    # Should be called for each commit
    assert mock_process.call_count == 3
