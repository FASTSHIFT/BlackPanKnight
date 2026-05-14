"""Test mode: run test scripts and report results."""

import logging
import subprocess
from typing import Optional

from src.ai.client import LLMClient
from src.config import RepoConfig
from src.notify.webhook import push_test_result
from src.repo import CommitInfo

logger = logging.getLogger(__name__)

TEST_TITLE_PROMPT = """根据以下测试结果，生成一句带emoji的通知标题（20字以内）。
如果测试通过，用轻松愉快的语气（例：'🎉 全绿！今天又是美好的一天'、'✅ 稳如老狗，测试全过'）。
如果测试失败，用毒舌吐槽的语气点出问题（例：'💥 炸了！某某的提交把测试搞崩了'、'🫠 又挂了，这分支今天不太行'）。
只输出标题文本，不要其他内容。

测试结果: {status}
仓库: {repo}
分支: {branch}
提交者: {author}
提交信息: {message}"""


def generate_test_title(
    llm_client: Optional[LLMClient],
    passed: bool,
    repo_name: str,
    branch: str,
    author: str,
    message: str,
) -> str:
    """Generate AI title for test result, or return default."""
    if not llm_client:
        return ""

    status = "通过" if passed else "失败"
    prompt = TEST_TITLE_PROMPT.format(
        status=status,
        repo=repo_name,
        branch=branch,
        author=author,
        message=message,
    )

    try:
        response = llm_client.client.chat.completions.create(
            model=llm_client.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=50,
        )
        return response.choices[0].message.content.strip().strip('"').strip("'")
    except Exception as e:
        logger.warning(f"AI title generation failed: {e}")
        return ""


def run_test_script(script: str, cwd: str) -> int:
    """Run a test script and return exit code."""
    try:
        result = subprocess.run(
            [script], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        return result.returncode
    except FileNotFoundError:
        logger.error(f"Test script not found: {script}")
        return 1
    except Exception as e:
        logger.error(f"Test execution error: {e}")
        return 1


def process_commit(
    repo_config: RepoConfig,
    commit: CommitInfo,
    branch: str,
    last_pass_hash: str = None,
    llm_client: Optional[LLMClient] = None,
) -> bool:
    """Process a single commit in test mode. Returns True if test passed."""
    logger.info(f"[{repo_config.name}] Running tests for {commit.hash[:8]}")

    exit_code = run_test_script(repo_config.test_script, repo_config.path)
    passed = exit_code == 0

    # Generate AI title
    title = generate_test_title(
        llm_client,
        passed,
        repo_config.name,
        branch,
        commit.author,
        commit.message,
    )

    push_test_result(
        webhook_url=repo_config.webhook_url,
        repo_name=repo_config.name,
        branch=branch,
        passed=passed,
        author=commit.author,
        commit_hash=commit.hash,
        commit_message=commit.message,
        change_id=commit.change_id,
        title=title,
    )
    return passed
