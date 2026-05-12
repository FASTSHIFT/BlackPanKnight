"""Tests for watch mode logic."""

import pytest

from src.modes.watch_mode import compute_diff_stat, filter_commit_by_paths, process_commit
from src.repo import CommitInfo


@pytest.fixture
def sample_commit():
    return CommitInfo(
        hash="abc123def456",
        author="zhangsan",
        message="fix: optimize scheduler",
        date="2026-05-12 10:00:00 +0800",
        files_changed=[
            "kernel/sched/core.c",
            "kernel/sched/fair.c",
            "drivers/gpu/mali.c",
            "README.md",
            "include/linux/sched.h",
        ],
    )


class TestFilterCommitByPaths:
    def test_prefix_match(self, sample_commit):
        watch_paths = ["kernel/sched/"]
        matched = filter_commit_by_paths(sample_commit, watch_paths)
        assert "kernel/sched/core.c" in matched
        assert "kernel/sched/fair.c" in matched
        assert "drivers/gpu/mali.c" not in matched

    def test_glob_match(self, sample_commit):
        watch_paths = ["include/linux/*.h"]
        matched = filter_commit_by_paths(sample_commit, watch_paths)
        assert "include/linux/sched.h" in matched
        assert len(matched) == 1

    def test_multiple_patterns(self, sample_commit):
        watch_paths = ["kernel/sched/", "drivers/gpu/"]
        matched = filter_commit_by_paths(sample_commit, watch_paths)
        assert len(matched) == 3

    def test_no_match(self, sample_commit):
        watch_paths = ["arch/arm64/"]
        matched = filter_commit_by_paths(sample_commit, watch_paths)
        assert matched == []

    def test_empty_watch_paths(self, sample_commit):
        matched = filter_commit_by_paths(sample_commit, [])
        assert matched == []


class TestComputeDiffStat:
    def test_basic_diff(self):
        diff = """\
--- a/file.c
+++ b/file.c
@@ -1,3 +1,5 @@
 unchanged
+added line 1
+added line 2
-removed line
 unchanged
"""
        stat = compute_diff_stat(diff)
        assert stat == "+2/-1"

    def test_empty_diff(self):
        assert compute_diff_stat("") == "+0/-0"

    def test_only_additions(self):
        diff = "+new line\n+another\n"
        assert compute_diff_stat(diff) == "+2/-0"

    def test_only_removals(self):
        diff = "-old line\n-another\n"
        assert compute_diff_stat(diff) == "+0/-2"

    def test_ignores_file_headers(self):
        diff = "--- a/file.c\n+++ b/file.c\n+real add\n-real remove\n"
        assert compute_diff_stat(diff) == "+1/-1"


class TestWatchModeIntegration:
    """Integration tests verifying the full watch pipeline with real git parsing."""

    def test_unmatched_commit_not_processed(self):
        """A commit that doesn't match watch_paths should return False."""
        from unittest.mock import MagicMock, patch

        from src.config import GlobalConfig, RepoConfig

        repo = RepoConfig(
            name="Test",
            path="/tmp",
            branches=["main"],
            mode="watch",
            watch_paths=["drivers/gpu/"],
            webhook_url="http://x",
        )
        gc = GlobalConfig()
        commit = CommitInfo(
            hash="abc123",
            author="dev",
            message="docs: update readme",
            date="2026-01-01",
            files_changed=["README.md", "docs/guide.md"],
        )
        result = process_commit(repo, gc, commit, "main", None)
        assert result is False

    def test_matched_commit_pushes_webhook(self):
        """A commit matching watch_paths should push to webhook."""
        from unittest.mock import MagicMock, patch

        from src.config import GlobalConfig, RepoConfig

        repo = RepoConfig(
            name="Test",
            path="/tmp",
            branches=["main"],
            mode="watch",
            watch_paths=["drivers/gpu/", "src/core/"],
            webhook_url="http://x",
        )
        gc = GlobalConfig()
        commit = CommitInfo(
            hash="def456abc789",
            author="dev",
            message="perf: optimize gpu pipeline",
            date="2026-01-01",
            files_changed=["drivers/gpu/render.c", "README.md"],
        )

        with patch("src.modes.watch_mode.get_commit_diff") as mock_diff, \
             patch("src.modes.watch_mode.push_watch_result") as mock_push:
            mock_diff.return_value = "+new line\n-old line\n"
            mock_push.return_value = True

            result = process_commit(repo, gc, commit, "main", None)

            assert result is True
            mock_push.assert_called_once()
            call_kwargs = mock_push.call_args[1]
            assert call_kwargs["commit_hash"] == "def456abc789"
            assert "drivers/gpu/render.c" in call_kwargs["files_changed"]
            assert "README.md" not in call_kwargs["files_changed"]
