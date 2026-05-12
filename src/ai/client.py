"""LLM API client for code analysis (OpenAI-compatible)."""

import logging
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    risk_level: str  # "🔴 高风险" / "🟡 中风险" / "🟢 低风险"
    summary: str
    detail: str


DEFAULT_PROMPT = """你是一个嵌入式系统性能分析专家。请分析以下 Git commit 的代码变更，
重点关注对系统性能的潜在影响。

关注维度：
1. 是否修改了热路径（高频调用的函数）
2. 是否引入/修改了锁、同步原语、原子操作
3. 内存分配模式是否变化（栈→堆、新增动态分配）
4. 算法复杂度是否变化
5. 是否影响 GPU/显示相关的调度或资源管理
6. 是否有明显的性能反模式（循环内分配、不必要的拷贝等）

请严格按以下格式输出（不要添加额外内容）：
风险等级：🔴 高风险 / 🟡 中风险 / 🟢 低风险（三选一）
分析摘要：一段话概括主要风险点（100字以内）
详细分析：逐文件分析变更影响"""


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    def analyze_diff(
        self,
        commit_hash: str,
        author: str,
        message: str,
        diff_content: str,
        prompt_template: str = "",
    ) -> Optional[AnalysisResult]:
        """Analyze a commit diff for performance risks."""
        if not diff_content.strip():
            return None

        # Truncate very large diffs to avoid token limits
        max_diff_chars = 12000
        if len(diff_content) > max_diff_chars:
            diff_content = diff_content[:max_diff_chars] + "\n... (truncated)"

        prompt = self._build_prompt(
            commit_hash, author, message, diff_content, prompt_template
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            return self._parse_response(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return None

    def _build_prompt(
        self, commit_hash: str, author: str, message: str, diff: str,
        prompt_template: str = "",
    ) -> str:
        template = prompt_template or DEFAULT_PROMPT
        return f"""{template}

---
Commit: {commit_hash}
Author: {author}
Message: {message}

Diff:
{diff}"""

    def _parse_response(self, text: str) -> AnalysisResult:
        """Parse LLM response into structured result."""
        lines = text.strip().split("\n")

        risk_level = "🟢 低风险"
        summary = ""
        detail_lines = []
        section = None

        for line in lines:
            if line.startswith("风险等级：") or line.startswith("风险等级:"):
                risk_level = line.split("：", 1)[-1].split(":", 1)[-1].strip()
                section = "risk"
            elif line.startswith("分析摘要：") or line.startswith("分析摘要:"):
                summary = line.split("：", 1)[-1].split(":", 1)[-1].strip()
                section = "summary"
            elif line.startswith("详细分析：") or line.startswith("详细分析:"):
                detail_lines.append(line.split("：", 1)[-1].split(":", 1)[-1].strip())
                section = "detail"
            elif section == "detail":
                detail_lines.append(line)

        return AnalysisResult(
            risk_level=risk_level,
            summary=summary,
            detail="\n".join(detail_lines).strip(),
        )
