"""LLM API client for code analysis (OpenAI-compatible)."""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from openai import OpenAI

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


DEFAULT_PROMPT = """你是一个嵌入式系统性能分析专家。请分析以下 Git commit 的代码变更，
重点关注对系统性能的潜在影响。

请按以下维度分别打分（0-10，0=无影响，10=极高风险）：
1. lock_sync: 锁/同步原语/原子操作变更
2. memory: 内存分配模式变化（栈→堆、新增动态分配、内存池调整）
3. hot_path: 热路径修改（高频调用函数、中断处理、调度器核心路径）
4. algorithm: 算法复杂度变化（O(n)→O(n²)、循环嵌套增加等）
5. config: 系统配置变更（时钟频率、DVFS策略、缓存策略、调度参数）
6. scope: 影响面（修改文件数、跨模块影响、公共头文件变更）

评分原则：
- 纯注释/日志/打点/文档修改 = 所有维度 0 分
- 新增 tracepoint/性能监控代码 = 所有维度 0 分（观测不影响被观测）
- 仅修改测试代码 = 所有维度 0 分

请严格按以下 JSON 格式输出（不要添加其他内容）：
```json
{
  "title": "一句话标题，带emoji开头，用轻松幽默的语气概括变更影响，像同事间吐槽（25字以内，例：'🔧 spinlock换姿势了，小心翻车'、'🎨 渲染路径升级，GPU要加班了'）",
  "scores": {
    "lock_sync": 0,
    "memory": 0,
    "hot_path": 0,
    "algorithm": 0,
    "config": 0,
    "scope": 0
  },
  "summary": "一段话分析摘要（80字以内）",
  "detail": "逐文件分析变更影响"
}
```"""


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
                temperature=0.1,
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
        template = prompt_template or DEFAULT_PROMPT
        return f"""{template}

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
