"""LLM API client for code analysis (OpenAI-compatible)."""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from openai import OpenAI

from src.ai.prompts import WATCH_ANALYSIS_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class RiskScores:
    """Per-dimension risk scores (0-10)."""

    lock_sync: int = 0  # 锁/同步原语变更
    memory: int = 0  # 内存分配模式变化
    hot_path: int = 0  # 热路径修改
    algorithm: int = 0  # 算法复杂度变化
    config: int = 0  # 配置/频率变更
    scope: int = 0  # 影响面/代码量

    @property
    def total(self) -> int:
        """Weighted total score (0-10)."""
        raw = (
            self.lock_sync * 25
            + self.memory * 20
            + self.hot_path * 20
            + self.algorithm * 15
            + self.config * 10
            + self.scope * 10
        )
        return min(raw // 100, 10)

    @property
    def level(self) -> str:
        """Human-readable risk level based on total score."""
        t = self.total
        if t >= 6:
            return "🔴 高风险"
        elif t >= 3:
            return "🟡 中风险"
        else:
            return "🟢 低风险"


@dataclass
class AnalysisResult:
    title: str  # AI-generated one-line title
    scores: RiskScores = field(default_factory=RiskScores)
    summary: str = ""
    detail: str = ""

    @property
    def risk_level(self) -> str:
        return self.scores.level

    @property
    def risk_score(self) -> int:
        return self.scores.total


DEFAULT_PROMPT = WATCH_ANALYSIS_PROMPT


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
                temperature=0.5,
            )
            return self._parse_response(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return None

    def _build_prompt(
        self,
        commit_hash: str,
        author: str,
        message: str,
        diff: str,
        prompt_template: str = "",
    ) -> str:
        import random

        template = prompt_template or DEFAULT_PROMPT
        # Rotate style hint to ensure title diversity
        style_hints = [
            "用网络梗",
            "用古诗改编",
            "用歌词改编",
            "用俗语改编",
            "用吐槽风格",
            "用佛系风格",
            "用打工人风格",
            "用二次元风格",
            "用段子风格",
        ]
        if not hasattr(self, "_hint_idx"):
            self._hint_idx = random.randint(0, len(style_hints) - 1)
        hint = style_hints[self._hint_idx % len(style_hints)]
        self._hint_idx += 1

        # Random seed breaks AI response caching
        seed = random.randint(1000, 9999)

        return f"""{template}

（本次低风险标题请{hint}，seed={seed}，不要和之前重复）

---
Commit: {commit_hash}
Author: {author}
Message: {message}

Diff:
{diff}"""

    def _parse_response(self, text: str) -> AnalysisResult:
        """Parse LLM JSON response into AnalysisResult."""
        # Extract JSON from response (may be wrapped in ```json ... ```)
        json_match = re.search(r"\{[\s\S]*\}", text)
        if not json_match:
            logger.warning(f"No JSON found in LLM response: {text[:200]}")
            return AnalysisResult(title="解析失败", summary=text[:100])

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}, raw: {text[:200]}")
            return AnalysisResult(title="解析失败", summary=text[:100])

        scores_raw = data.get("scores", {})
        scores = RiskScores(
            lock_sync=int(scores_raw.get("lock_sync", 0)),
            memory=int(scores_raw.get("memory", 0)),
            hot_path=int(scores_raw.get("hot_path", 0)),
            algorithm=int(scores_raw.get("algorithm", 0)),
            config=int(scores_raw.get("config", 0)),
            scope=int(scores_raw.get("scope", 0)),
        )

        return AnalysisResult(
            title=data.get("title", ""),
            scores=scores,
            summary=data.get("summary", ""),
            detail=data.get("detail", ""),
        )
