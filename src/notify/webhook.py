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
    ai_summary: str = "",
    change_id: str = "",
) -> dict:
    """Build payload for watch mode results."""
    import random

    # Fun titles based on risk level
    if "高风险" in risk_level:
        titles = [
            "🚨 警报！锅正在飞来的路上",
            "🍳 高危变更！准备接锅",
            "⚠️ 危险操作！嫌疑人已锁定",
            "🔥 紧急！性能杀手出没",
        ]
    elif "中风险" in risk_level:
        titles = [
            "🤔 有点意思，建议关注",
            "👀 可疑变更，值得一看",
            "📋 中等风险，留个心眼",
            "🧐 这改动需要盯一下",
        ]
    else:
        titles = [
            "📝 例行报告，暂时安全",
            "✅ 低风险变更，记录在案",
            "😌 今日份平安，记录归档",
            "📋 常规变更，无需紧张",
        ]

    title = random.choice(titles)

    # Blame score (fun metric)
    added = int(diff_stat.split("/")[0].replace("+", "") or "0")
    removed = int(diff_stat.split("/")[1].replace("-", "") or "0")
    risk_multiplier = {"高风险": 3, "中风险": 2}.get(
        risk_level.replace("🔴 ", "").replace("🟡 ", "").replace("🟢 ", ""), 1
    )
    blame_score = (added + removed) * risk_multiplier

    return {
        "仓库": repo_name,
        "分支": branch,
        "提交者": author,
        "Commit": commit_hash[:8],
        "ChangeId": change_id,
        "提交信息": commit_message,
        "变更文件": files_changed,
        "变更统计": diff_stat,
        "AI风险等级": risk_level,
        "AI分析": ai_summary,
        "甩锅指数": f"{'🔥' * min(blame_score // 50, 5)} {blame_score}",
        "标题": title,
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
    ai_summary: str = "",
    change_id: str = "",
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
        ai_summary,
        change_id,
    )
    return send_webhook(webhook_url, payload)
