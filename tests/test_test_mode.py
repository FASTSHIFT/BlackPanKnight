"""Tests for test mode logic."""

import os
import stat
import tempfile
from unittest.mock import patch

import pytest

from src.config import RepoConfig
from src.modes.test_mode import process_commit, run_test_script
from src.repo import CommitInfo


@pytest.fixture
def passing_script():
    """Create a temp script that exits 0."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False)
    f.write("#!/bin/bash\nexit 0\n")
    f.close()
    os.chmod(f.name, os.stat(f.name).st_mode | stat.S_IEXEC)
    yield f.name
    os.unlink(f.name)


@pytest.fixture
def failing_script():
    """Create a temp script that exits 1."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False)
    f.write("#!/bin/bash\nexit 1\n")
    f.close()
    os.chmod(f.name, os.stat(f.name).st_mode | stat.S_IEXEC)
    yield f.name
    os.unlink(f.name)


class TestRunTestScript:
    def test_passing_script(self, passing_script):
        assert run_test_script(passing_script, "/tmp") == 0

    def test_failing_script(self, failing_script):
        assert run_test_script(failing_script, "/tmp") == 1

    def test_nonexistent_script(self):
        assert run_test_script("/nonexistent/script.sh", "/tmp") == 1


class TestProcessCommit:
    @patch("src.modes.test_mode.push_test_result")
    @patch("src.modes.test_mode.run_test_script")
    def test_process_passing(self, mock_run, mock_push):
        mock_run.return_value = 0
        mock_push.return_value = True

        repo = RepoConfig(
            name="R",
            path="/tmp",
            branches=["main"],
            mode="test",
            test_script="./t.sh",
            webhook_url="http://x",
        )
        commit = CommitInfo(
            hash="abc123",
            author="test",
            message="fix",
            date="now",
            files_changed=[],
        )

        result = process_commit(repo, commit, "main")
        assert result is True
        mock_push.assert_called_once()
        call_kwargs = mock_push.call_args
        assert call_kwargs[1]["passed"] is True

    @patch("src.modes.test_mode.get_commits_between")
    @patch("src.modes.test_mode.push_test_result")
    @patch("src.modes.test_mode.run_test_script")
    def test_process_failing_with_suspects(self, mock_run, mock_push, mock_between):
        mock_run.return_value = 1
        mock_push.return_value = True
        mock_between.return_value = [
            CommitInfo(
                hash="sus123",
                author="suspect",
                message="bad change",
                date="now",
                files_changed=[],
            )
        ]

        repo = RepoConfig(
            name="R",
            path="/tmp",
            branches=["main"],
            mode="test",
            test_script="./t.sh",
            webhook_url="http://x",
        )
        commit = CommitInfo(
            hash="abc123",
            author="test",
            message="fix",
            date="now",
            files_changed=[],
        )

        result = process_commit(repo, commit, "main", last_pass_hash="old123")
        assert result is False
        mock_between.assert_called_once()
