"""Feishu Bitable webhook notification module."""

import json
import logging
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


def send_webhook(webhook_url: str, payload: dict) -> bool:
    """Send a payload to a Feishu Bitable webhook."""
    headers = {"Content-Type": "application/json"}
    try:
        logger.info(f"Webhook payload: {json.dumps(payload, ensure_ascii=False)}")
        response = requests.post(
            webhook_url, headers=headers, data=json.dumps(payload), timeout=10
        )
        response.raise_for_status()
        logger.info(
            f"Webhook sent: {payload.get('仓库', '')} - {payload.get('Commit', '')}"
        )
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Webhook failed: {e}")
        return False


def build_test_payload(
    repo_name: str,
    branch: str,
    status: str,
    author: str,
    commit_hash: str,
    commit_message: str,
    suspects: str = "",
) -> dict:
    """Build payload for test mode results."""
    return {
        "仓库": repo_name,
        "分支": branch,
        "状态": status,
        "提交者": author,
        "Commit": commit_hash[:8],
        "提交信息": commit_message,
        "怀疑对象": suspects,
        "时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def build_watch_payload(
    repo_name: str,
    branch: str,
    author: str,
    commit_hash: str,
    commit_message: str,
    files_changed: str,
    diff_stat: str,
    risk_level: str = "",
    risk_score: int = 0,
    ai_title: str = "",
    ai_summary: str = "",
    change_id: str = "",
    remote: str = "",
) -> dict:
    """Build payload for watch mode results."""
    return {
        "标题": ai_title,
        "仓库": repo_name,
        "来源": remote,
        "分支": branch,
        "提交者": author,
        "Commit": commit_hash[:8],
        "ChangeId": change_id,
        "提交信息": commit_message,
        "变更文件": files_changed,
        "变更统计": diff_stat,
        "风险等级": risk_level,
        "风险评分": f"{risk_score}/10",
        "AI分析": ai_summary,
        "时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def push_test_result(
    webhook_url: str,
    repo_name: str,
    branch: str,
    passed: bool,
    author: str,
    commit_hash: str,
    commit_message: str,
    suspects: str = "",
) -> bool:
    """Push a test result to the webhook."""
    status = "✅ 通过" if passed else "❌ 失败"
    payload = build_test_payload(
        repo_name, branch, status, author, commit_hash, commit_message, suspects
    )
    return send_webhook(webhook_url, payload)


def push_watch_result(
    webhook_url: str,
    repo_name: str,
    branch: str,
    author: str,
    commit_hash: str,
    commit_message: str,
    files_changed: list,
    diff_stat: str,
    risk_level: str = "",
    risk_score: int = 0,
    ai_title: str = "",
    ai_summary: str = "",
    change_id: str = "",
    remote: str = "",
) -> bool:
    """Push a watch analysis result to the webhook."""
    files_str = ", ".join(files_changed[:10])
    if len(files_changed) > 10:
        files_str += f" ... (+{len(files_changed) - 10} files)"
    payload = build_watch_payload(
        repo_name,
        branch,
        author,
        commit_hash,
        commit_message,
        files_str,
        diff_stat,
        risk_level,
        risk_score,
        ai_title,
        ai_summary,
        change_id,
        remote,
    )
    return send_webhook(webhook_url, payload)
