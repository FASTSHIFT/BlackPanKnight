"""Tests for AI client response parsing."""

import json

from src.ai.client import LLMClient, RiskScores


class TestParseResponse:
    def setup_method(self):
        # Create client without real connection for parsing tests
        self.client = LLMClient.__new__(LLMClient)

    def test_parse_json_response(self):
        data = {
            "title": "spinlock换姿势了，小心翻车",
            "scores": {
                "lock_sync": 8,
                "memory": 0,
                "hot_path": 7,
                "algorithm": 0,
                "config": 0,
                "scope": 2,
            },
            "summary": "修改了调度器核心路径的锁机制",
            "detail": "core.c: 将 spinlock 替换为 mutex",
        }
        text = f"```json\n{json.dumps(data)}\n```"
        result = self.client._parse_response(text)
        assert result.title == "spinlock换姿势了，小心翻车"
        assert result.scores.lock_sync == 8
        assert result.scores.hot_path == 7
        assert result.risk_score >= 3
        assert "中风险" in result.risk_level or "高风险" in result.risk_level
        assert "调度器" in result.summary
        assert "core.c" in result.detail

    def test_parse_low_risk_json(self):
        data = {
            "title": "加了个日志，岁月静好",
            "scores": {
                "lock_sync": 0,
                "memory": 0,
                "hot_path": 0,
                "algorithm": 0,
                "config": 0,
                "scope": 0,
            },
            "summary": "仅修改注释和日志输出，无性能影响",
            "detail": "无需关注",
        }
        text = json.dumps(data)
        result = self.client._parse_response(text)
        assert result.risk_level == "🟢 低风险"
        assert result.risk_score == 0
        assert "日志" in result.summary

    def test_parse_invalid_response(self):
        text = "这不是JSON格式的回复"
        result = self.client._parse_response(text)
        assert result.title == "解析失败"

    def test_parse_partial_scores(self):
        data = {
            "title": "改了点东西",
            "scores": {"lock_sync": 5},
            "summary": "部分字段缺失",
            "detail": "",
        }
        text = json.dumps(data)
        result = self.client._parse_response(text)
        assert result.scores.lock_sync == 5
        assert result.scores.memory == 0


class TestRiskScores:
    def test_total_weighted(self):
        scores = RiskScores(lock_sync=10, memory=0, hot_path=0)
        # 10 * 25 / 100 = 2
        assert scores.total == 2

    def test_high_risk_threshold(self):
        scores = RiskScores(lock_sync=10, hot_path=10, memory=10)
        # (10*25 + 10*20 + 10*20) / 100 = 6
        assert scores.total >= 6
        assert scores.level == "🔴 高风险"

    def test_low_risk_all_zero(self):
        scores = RiskScores()
        assert scores.total == 0
        assert scores.level == "🟢 低风险"

    def test_medium_risk(self):
        scores = RiskScores(lock_sync=8, hot_path=6)
        # (8*25 + 6*20) / 100 = 3
        assert scores.total >= 3
        assert scores.level == "🟡 中风险"
