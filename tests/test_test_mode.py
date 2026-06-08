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
        code, output = run_test_script(passing_script, "/tmp")
        assert code == 0
        assert isinstance(output, str)

    def test_failing_script(self, failing_script):
        code, _ = run_test_script(failing_script, "/tmp")
        assert code == 1

    def test_nonexistent_script(self):
        code, output = run_test_script("/nonexistent/script.sh", "/tmp")
        assert code == 1
        assert "not found" in output.lower()

    def test_captures_stdout_and_stderr(self):
        """Output must include both stdout and stderr writes."""
        import os
        import stat
        import tempfile

        f = tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False)
        f.write(
            "#!/bin/bash\n" "echo hello-stdout\n" "echo hello-stderr 1>&2\n" "exit 7\n"
        )
        f.close()
        os.chmod(f.name, os.stat(f.name).st_mode | stat.S_IEXEC)
        try:
            code, output = run_test_script(f.name, "/tmp")
            assert code == 7
            assert "hello-stdout" in output
            assert "hello-stderr" in output
        finally:
            os.unlink(f.name)


class TestProcessCommit:
    @patch("src.modes.test_mode.checkout_branch")
    @patch("src.modes.test_mode.push_test_result")
    @patch("src.modes.test_mode.run_test_script")
    def test_process_passing(self, mock_run, mock_push, mock_checkout):
        mock_run.return_value = (0, "ok")
        mock_push.return_value = True
        mock_checkout.return_value = True

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
        mock_checkout.assert_called_once()
        mock_push.assert_called_once()
        call_kwargs = mock_push.call_args
        assert call_kwargs[1]["passed"] is True

    @patch("src.modes.test_mode.checkout_branch")
    @patch("src.modes.test_mode.push_test_result")
    @patch("src.modes.test_mode.run_test_script")
    def test_process_failing(self, mock_run, mock_push, mock_checkout):
        mock_run.return_value = (1, "boom: something exploded")
        mock_push.return_value = True
        mock_checkout.return_value = True

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
        # Failure must carry the script tail so it's diagnosable.
        assert "boom" in call_kwargs[1]["test_log"]

    @patch("src.modes.test_mode.checkout_branch")
    @patch("src.modes.test_mode.push_test_result")
    @patch("src.modes.test_mode.run_test_script")
    def test_process_checkout_failure(self, mock_run, mock_push, mock_checkout):
        """If checkout fails, must report failure and never run the test."""
        mock_checkout.return_value = False
        mock_push.return_value = True

        repo = RepoConfig(
            name="R",
            path="/tmp",
            branches=["dev-graphic"],
            remote="vela",
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

        result = process_commit(repo, commit, "dev-graphic")
        assert result is False
        # Test script must NOT run when checkout fails
        mock_run.assert_not_called()
        # Failure must still be reported, with checkout reason in test_log
        mock_push.assert_called_once()
        kwargs = mock_push.call_args[1]
        assert kwargs["passed"] is False
        assert "checkout" in kwargs["test_log"].lower()

    @patch("src.modes.test_mode.checkout_branch")
    @patch("src.modes.test_mode.push_test_result")
    @patch("src.modes.test_mode.run_test_script")
    def test_process_checks_out_correct_branch(
        self, mock_run, mock_push, mock_checkout
    ):
        """checkout_branch must be called with the branch and remote."""
        mock_run.return_value = (0, "")
        mock_push.return_value = True
        mock_checkout.return_value = True

        repo = RepoConfig(
            name="R",
            path="/repo",
            branches=["dev-graphic"],
            remote="vela",
            mode="test",
            test_script="./t.sh",
            webhook_url="http://x",
        )
        commit = CommitInfo(
            hash="abc123", author="t", message="m", date="now", files_changed=[]
        )

        process_commit(repo, commit, "dev-graphic")
        mock_checkout.assert_called_once_with("/repo", "dev-graphic", "vela")


class TestTail:
    def test_short_returned_intact(self):
        from src.modes.test_mode import _tail

        assert _tail("hello", 100) == "hello"

    def test_empty(self):
        from src.modes.test_mode import _tail

        assert _tail("", 100) == ""

    def test_long_truncated_with_marker(self):
        from src.modes.test_mode import _tail

        text = "A" * 50 + "\nLAST_LINE\n"
        out = _tail(text, max_chars=20)
        assert "truncated" in out
        assert out.endswith("LAST_LINE\n")
        # The kept portion is bounded.
        assert len(out) <= len("...(truncated)...\n") + 20


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
