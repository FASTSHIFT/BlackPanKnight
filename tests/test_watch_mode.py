"""Tests for watch mode logic."""

import pytest

from src.modes.watch_mode import compute_diff_stat, filter_commit_by_paths
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
