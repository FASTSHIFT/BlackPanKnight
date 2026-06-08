"""Tests for webhook notification module."""

from unittest.mock import MagicMock, patch

from src.notify.webhook import (
    build_test_payload,
    build_watch_payload,
    push_test_result,
    push_watch_result,
    send_webhook,
)


class TestBuildPayloads:
    def test_build_test_payload(self):
        payload = build_test_payload(
            repo_name="Test Repo",
            branch="main",
            status="✅ 通过",
            author="zhangsan",
            commit_hash="abc123def456",
            commit_message="fix: bug",
        )
        assert payload["标题"] == "叮铃铃~ 测试通过!"
        assert payload["仓库"] == "Test Repo"
        assert payload["分支"] == "main"
        assert payload["状态"] == "✅ 通过"
        assert payload["Commit"] == "abc123de"

    def test_build_watch_payload(self):
        payload = build_watch_payload(
            repo_name="Watch Repo",
            branch="dev",
            author="lisi",
            commit_hash="def456abc789",
            commit_message="perf: optimize",
            files_changed="a.c, b.c",
            diff_stat="+10/-5",
            risk_level="🔴 高风险",
            risk_score=65,
            ai_title="热路径被动了，注意性能",
            ai_summary="修改了热路径",
            remote="upstream",
        )
        assert payload["仓库"] == "Watch Repo"
        assert payload["风险等级"] == "🔴 高风险"
        assert payload["风险评分"] == "65/10"
        assert payload["标题"] == "热路径被动了，注意性能"
        assert payload["变更统计"] == "+10/-5"
        assert payload["来源"] == "upstream"


class TestSendWebhook:
    @patch("src.notify.webhook.requests.post")
    def test_send_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        result = send_webhook("http://example.com/hook", {"key": "value"})
        assert result is True
        mock_post.assert_called_once()

    @patch("src.notify.webhook.requests.post")
    def test_send_failure(self, mock_post):
        from requests.exceptions import ConnectionError

        mock_post.side_effect = ConnectionError("timeout")

        result = send_webhook("http://example.com/hook", {"key": "value"})
        assert result is False


class TestBuildWatchPayloadRemote:
    def test_remote_in_payload(self):
        payload = build_watch_payload(
            repo_name="Test",
            branch="main",
            author="dev",
            commit_hash="abc123def456",
            commit_message="fix: something",
            files_changed="a.c",
            diff_stat="+1/-1",
            risk_level="🟢 低风险",
            ai_summary="safe",
            change_id="I123",
            remote="upstream",
        )
        assert payload["来源"] == "upstream"

    def test_remote_empty_when_not_provided(self):
        payload = build_watch_payload(
            repo_name="Test",
            branch="main",
            author="dev",
            commit_hash="abc123def456",
            commit_message="fix: something",
            files_changed="a.c",
            diff_stat="+1/-1",
        )
        assert payload["来源"] == ""


class TestPushFunctions:
    @patch("src.notify.webhook.send_webhook")
    def test_push_watch_result(self, mock_send):
        mock_send.return_value = True
        result = push_watch_result(
            webhook_url="http://x",
            repo_name="R",
            branch="main",
            author="dev",
            commit_hash="abc123def456",
            commit_message="fix",
            files_changed=["a.c", "b.c", "c.c"],
            diff_stat="+10/-5",
            risk_level="🟢 低风险",
            risk_score=2,
            ai_title="📝 诗句",
            ai_summary="safe",
            change_id="I123",
            remote="upstream",
        )
        assert result is True
        mock_send.assert_called_once()

    @patch("src.notify.webhook.send_webhook")
    def test_push_watch_result_truncates_files(self, mock_send):
        mock_send.return_value = True
        files = [f"file{i}.c" for i in range(15)]
        push_watch_result(
            webhook_url="http://x",
            repo_name="R",
            branch="main",
            author="dev",
            commit_hash="abc123def456",
            commit_message="fix",
            files_changed=files,
            diff_stat="+10/-5",
        )
        payload = mock_send.call_args[0][1]
        assert "+5 files" in payload["变更文件"]

    @patch("src.notify.webhook.send_webhook")
    def test_push_test_result_pass(self, mock_send):
        mock_send.return_value = True
        result = push_test_result(
            webhook_url="http://x",
            repo_name="R",
            branch="main",
            passed=True,
            author="dev",
            commit_hash="abc123def456",
            commit_message="fix",
        )
        assert result is True
        payload = mock_send.call_args[0][1]
        assert payload["状态"] == "✅ 通过"
        assert payload["标题"] == "叮铃铃~ 测试通过!"

    @patch("src.notify.webhook.send_webhook")
    def test_push_test_result_fail_with_title(self, mock_send):
        mock_send.return_value = True
        push_test_result(
            webhook_url="http://x",
            repo_name="R",
            branch="main",
            passed=False,
            author="dev",
            commit_hash="abc123def456",
            commit_message="fix",
            title="💥 炸了！",
        )
        payload = mock_send.call_args[0][1]
        assert payload["状态"] == "❌ 失败"
        assert payload["标题"] == "💥 炸了！"

    @patch("src.notify.webhook.send_webhook")
    def test_push_test_result_includes_log_on_failure(self, mock_send):
        """test_log must reach the webhook payload when provided."""
        mock_send.return_value = True
        push_test_result(
            webhook_url="http://x",
            repo_name="R",
            branch="main",
            passed=False,
            author="dev",
            commit_hash="abc123def456",
            commit_message="fix",
            test_log="gcovr version is 4.2, which is lower than 8.2",
        )
        payload = mock_send.call_args[0][1]
        assert "测试日志" in payload
        assert "gcovr" in payload["测试日志"]

    @patch("src.notify.webhook.send_webhook")
    def test_push_test_result_omits_log_on_success(self, mock_send):
        """Successful payloads stay compact; no 测试日志 field."""
        mock_send.return_value = True
        push_test_result(
            webhook_url="http://x",
            repo_name="R",
            branch="main",
            passed=True,
            author="dev",
            commit_hash="abc123def456",
            commit_message="fix",
        )
        payload = mock_send.call_args[0][1]
        assert "测试日志" not in payload
