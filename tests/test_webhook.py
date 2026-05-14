"""Tests for webhook notification module."""

from unittest.mock import MagicMock, patch

from src.notify.webhook import (
    build_test_payload,
    build_watch_payload,
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
            suspects="",
        )
        assert payload["仓库"] == "Test Repo"
        assert payload["分支"] == "main"
        assert payload["状态"] == "✅ 通过"
        assert payload["Commit"] == "abc123de"
        assert payload["怀疑对象"] == ""

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
