"""Tests for test mode logic."""

import os
import stat
import tempfile
from unittest.mock import MagicMock, patch

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

    @patch("src.modes.test_mode.push_test_result")
    @patch("src.modes.test_mode.run_test_script")
    def test_process_failing(self, mock_run, mock_push):
        mock_run.return_value = 1
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
        assert result is False
        mock_push.assert_called_once()
        call_kwargs = mock_push.call_args
        assert call_kwargs[1]["passed"] is False


class TestGenerateTestTitle:
    def test_returns_empty_without_llm(self):
        from src.modes.test_mode import generate_test_title

        title = generate_test_title(None, True, "Repo", "main", "dev", "fix")
        assert title == ""

    @patch("src.modes.test_mode.LLMClient")
    def test_returns_title_on_success(self, mock_cls):
        from src.modes.test_mode import generate_test_title

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "🎉 全绿！稳如老狗"
        mock_client.client.chat.completions.create.return_value = mock_response
        mock_client.model = "test-model"

        title = generate_test_title(mock_client, True, "Repo", "main", "dev", "fix")
        assert "全绿" in title

    @patch("src.modes.test_mode.LLMClient")
    def test_returns_empty_on_failure(self, mock_cls):
        from src.modes.test_mode import generate_test_title

        mock_client = MagicMock()
        mock_client.client.chat.completions.create.side_effect = Exception("err")
        mock_client.model = "test-model"

        title = generate_test_title(mock_client, False, "Repo", "main", "dev", "fix")
        assert title == ""
