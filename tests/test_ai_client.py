"""Tests for AI client response parsing."""

from src.ai.client import LLMClient


class TestParseResponse:
    def setup_method(self):
        # Create client without real connection for parsing tests
        self.client = LLMClient.__new__(LLMClient)

    def test_parse_standard_response(self):
        text = """风险等级：🔴 高风险
分析摘要：修改了调度器核心路径的锁机制，可能导致中断延迟增加
详细分析：
- core.c: 将 spinlock 替换为 mutex，在中断上下文中可能死锁
- fair.c: 新增了内存分配，在热路径中不推荐"""

        result = self.client._parse_response(text)
        assert result.risk_level == "🔴 高风险"
        assert "调度器核心路径" in result.summary
        assert "core.c" in result.detail

    def test_parse_low_risk(self):
        text = """风险等级：🟢 低风险
分析摘要：仅修改注释和日志输出，无性能影响
详细分析：无需关注"""

        result = self.client._parse_response(text)
        assert result.risk_level == "🟢 低风险"
        assert "注释" in result.summary

    def test_parse_with_colon_variant(self):
        text = """风险等级:🟡 中风险
分析摘要:引入了新的原子操作
详细分析:需要关注并发场景"""

        result = self.client._parse_response(text)
        assert "中风险" in result.risk_level
        assert "原子操作" in result.summary
