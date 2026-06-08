"""Test mode: run test scripts and report results."""

import logging
import subprocess
from typing import Optional

from src.ai.client import LLMClient
from src.ai.prompts import TEST_TITLE_PROMPT
from src.config import RepoConfig
from src.notify.webhook import push_test_result
from src.repo import CommitInfo, checkout_branch

logger = logging.getLogger(__name__)


def generate_test_title(
    llm_client: Optional[LLMClient],
    passed: bool,
    repo_name: str,
    branch: str,
    author: str,
    message: str,
) -> str:
    """Generate AI title for test result, or return default."""
    import random

    if not llm_client:
        return ""

    status = "通过" if passed else "失败"

    style_hints = [
        "用网络梗",
        "用古诗改编",
        "用歌词改编",
        "用俗语改编",
        "用段子风格",
        "用打工人风格",
        "用二次元风格",
        "用体育解说风格",
        "用美食比喻",
    ]
    hint = random.choice(style_hints)

    prompt = TEST_TITLE_PROMPT.format(
        status=status,
        repo=repo_name,
        branch=branch,
        author=author,
        message=message,
    )
    prompt += f"\n（本次请{hint}，不要和之前重复）"

    try:
        response = llm_client.client.chat.completions.create(
            model=llm_client.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=50,
        )
        content = response.choices[0].message.content
        if not content:
            logger.warning(
                f"AI title generation returned empty content "
                f"(model={llm_client.model}, finish_reason="
                f"{response.choices[0].finish_reason})"
            )
            return ""
        return content.strip().strip('"').strip("'")
    except Exception as e:
        logger.warning(f"AI title generation failed: {e}")
        return ""


def run_test_script(script: str, cwd: str) -> tuple:
    """Run a test script. Returns (exit_code, combined_output).

    stdout and stderr are merged so the order of writes is preserved, and
    the result is decoded as UTF-8 with replacement so a single bad byte
    cannot lose the whole log. Output is what we send back for diagnostics
    when a test fails; never silently dropped.
    """
    try:
        result = subprocess.run(
            [script],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        )
        return result.returncode, result.stdout or ""
    except FileNotFoundError:
        msg = f"Test script not found: {script}"
        logger.error(msg)
        return 1, msg
    except Exception as e:
        msg = f"Test execution error: {e}"
        logger.error(msg)
        return 1, msg


def _tail(text: str, max_chars: int = 2000) -> str:
    """Return the last `max_chars` of `text`, with a marker if truncated."""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return "...(truncated)...\n" + text[-max_chars:]


def process_commit(
    repo_config: RepoConfig,
    commit: CommitInfo,
    branch: str,
    last_pass_hash: str = None,
    llm_client: Optional[LLMClient] = None,
) -> bool:
    """Process a single commit in test mode. Returns True if test passed."""
    logger.info(f"[{repo_config.name}] Running tests for {commit.hash[:8]}")

    # Check out the branch so the test runs against the right code, not
    # whatever happens to be in the working tree (e.g. a detached HEAD).
    if not checkout_branch(repo_config.path, branch, repo_config.remote):
        msg = f"checkout failed for {repo_config.remote}/{branch}"
        logger.error(f"[{repo_config.name}] {msg}, reporting failure")
        push_test_result(
            webhook_url=repo_config.webhook_url,
            repo_name=repo_config.name,
            branch=branch,
            passed=False,
            author=commit.author,
            commit_hash=commit.hash,
            commit_message=commit.message,
            change_id=commit.change_id,
            title="",
            test_log=msg,
        )
        return False

    exit_code, output = run_test_script(repo_config.test_script, repo_config.path)
    passed = exit_code == 0

    # Always log the script tail so failures are diagnosable from the daemon
    # log alone. On success it stays at debug to keep the log readable.
    log_tail = _tail(output)
    if passed:
        logger.debug(f"[{repo_config.name}] test_script output (tail):\n{log_tail}")
    else:
        logger.error(
            f"[{repo_config.name}] test_script exit={exit_code}, output (tail):\n{log_tail}"
        )

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
        test_log=log_tail if not passed else "",
    )
    return passed
