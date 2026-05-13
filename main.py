#!/usr/bin/env python3
"""BlackPanKnight - Git repo monitor with AI-powered risk analysis."""

import argparse
import logging

from src.config import load_config
from src.scheduler import Scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def test_webhook(config):
    """Send a test message using the real push interface."""
    from src.notify.webhook import push_watch_result

    webhook_url = config.global_config.webhook_url
    if not webhook_url and config.repos:
        webhook_url = config.repos[0].webhook_url

    if not webhook_url:
        print("❌ 未配置 webhook_url")
        return 1

    print(f"📤 发送测试消息到: {webhook_url[:50]}...")
    ok = push_watch_result(
        webhook_url=webhook_url,
        repo_name="BlackPanKnight",
        branch="test",
        author="黑锅侠",
        commit_hash="test1234abcd5678",
        commit_message="🛡️ Webhook 连通性测试",
        files_changed=["src/test.c", "include/test.h"],
        diff_stat="+42/-0",
        risk_level="🟢 低风险",
        ai_summary="这是一条测试消息，确认 webhook 推送正常工作",
        change_id="I0000000000000000000000000000000000000000",
    )
    if ok:
        print("✅ Webhook 测试成功！")
        return 0
    else:
        print("❌ Webhook 发送失败")
        return 1


def test_llm(config):
    """Test LLM API connectivity with a sample diff."""
    from src.ai.client import LLMClient

    gc = config.global_config
    if not gc.llm_base_url or not gc.llm_api_key:
        print("❌ 未配置 llm_base_url 或 llm_api_key")
        return 1

    print(f"🤖 测试 LLM: {gc.llm_model}")
    print(f"   Base URL: {gc.llm_base_url}")

    client = LLMClient(
        base_url=gc.llm_base_url, api_key=gc.llm_api_key, model=gc.llm_model
    )

    sample_diff = """--- a/include/spinlock.h
+++ b/include/spinlock.h
@@ -10,5 +10,8 @@
 static inline void spin_lock(spinlock_t *lock)
 {
-    while (atomic_exchange(&lock->val, 1)) { }
+    while (__atomic_test_and_set(&lock->val, __ATOMIC_ACQUIRE)) {
+        __asm__ volatile("wfe");
+    }
 }
"""

    print("   分析样本 diff...")
    result = client.analyze_diff(
        commit_hash="test123",
        author="test_user",
        message="perf: optimize spinlock acquire",
        diff_content=sample_diff,
    )

    if result:
        print("✅ LLM 测试成功！")
        print(f"   风险等级: {result.risk_level}")
        print(f"   分析摘要: {result.summary}")
        return 0
    else:
        print("❌ LLM 分析失败，请检查 API key 和模型名称")
        return 1


def test_repos(config):
    """Test all repo paths, branch resolution, and sync commands."""
    import os

    from src.repo import get_branch_head, sync_repo

    errors = 0
    gc = config.global_config

    for repo in config.repos:
        print(f"\n📂 [{repo.name}]")

        # 1. Check path exists
        if not os.path.isdir(repo.path):
            print(f"   ❌ 路径不存在: {repo.path}")
            errors += 1
            continue
        print("   ✅ 路径存在")

        # 2. Check it's a git repo
        git_dir = os.path.join(repo.path, ".git")
        if not os.path.exists(git_dir):
            print("   ❌ 不是 git 仓库 (无 .git)")
            errors += 1
            continue
        print("   ✅ Git 仓库")

        # 3. Test sync
        sync_cmd = repo.sync_command or gc.sync_command
        if sync_cmd:
            if sync_repo(repo.path, sync_cmd):
                print(f"   ✅ Sync 成功: {sync_cmd}")
            else:
                print(f"   ❌ Sync 失败: {sync_cmd}")
                errors += 1

        # 4. Check branches
        for branch in repo.branches:
            head = get_branch_head(repo.path, branch)
            if head:
                print(f"   ✅ 分支 {branch} -> {head[:8]}")
            else:
                print(f"   ❌ 分支 {branch} 无法解析")
                errors += 1

        # 5. Check watch_paths have recent matches (for watch mode)
        if repo.mode == "watch" and repo.watch_paths:
            from src.repo import get_single_commit

            head = get_branch_head(repo.path, repo.branches[0])
            if head:
                commit = get_single_commit(repo.path, head)
                if commit:
                    from src.modes.watch_mode import filter_commit_by_paths

                    matched = filter_commit_by_paths(commit, repo.watch_paths)
                    if matched:
                        print(f"   ✅ 最新提交命中 watch_paths: {matched[:3]}")
                    else:
                        print(
                            "   ⚠️  最新提交未命中 watch_paths (正常，不是每次都命中)"
                        )

    if errors == 0:
        print("\n🎉 所有仓库检查通过！")
    else:
        print(f"\n⚠️  {errors} 个问题需要修复")
    return 1 if errors else 0


def test_all(config):
    """Run all connectivity tests."""
    print("=" * 50)
    print("  BlackPanKnight 全链路测试")
    print("=" * 50)

    results = []

    # 1. Config validation (already passed if we got here)
    print("\n[1/4] 配置文件校验")
    print(f"   ✅ 加载成功: {len(config.repos)} 个仓库")
    results.append(0)

    # 2. Repos
    print("\n[2/4] 仓库连通性")
    results.append(test_repos(config))

    # 3. Webhook
    print("\n[3/4] Webhook 推送")
    results.append(test_webhook(config))

    # 4. LLM
    print("\n[4/4] LLM API")
    results.append(test_llm(config))

    # Summary
    print("\n" + "=" * 50)
    passed = sum(1 for r in results if r == 0)
    total = len(results)
    if passed == total:
        print(f"  ✅ 全部通过 ({passed}/{total})")
    else:
        print(f"  ⚠️  {passed}/{total} 通过")
    print("=" * 50)
    return 0 if passed == total else 1


def main():
    parser = argparse.ArgumentParser(
        description="BlackPanKnight - Git 仓库监控 + AI 风险分析"
    )
    parser.add_argument(
        "--config",
        "-c",
        default="config.yaml",
        help="配置文件路径 (default: config.yaml)",
    )
    parser.add_argument("--repo", "-r", help="只运行指定名称的仓库（用于调试）")
    parser.add_argument("--once", action="store_true", help="只运行一次轮询（不循环）")
    parser.add_argument(
        "--analyze-head",
        type=int,
        nargs="?",
        const=1,
        metavar="N",
        help="分析每个分支最新 N 个提交 (默认 1)",
    )
    parser.add_argument(
        "--test-webhook", action="store_true", help="发送测试消息到 webhook"
    )
    parser.add_argument("--test-llm", action="store_true", help="测试 LLM API 连通性")
    parser.add_argument(
        "--test-repos", action="store_true", help="测试仓库路径、分支、sync"
    )
    parser.add_argument(
        "--test-all", action="store_true", help="全链路测试（仓库+webhook+LLM）"
    )
    args = parser.parse_args()

    config = load_config(args.config)

    if args.test_all:
        return test_all(config)

    if args.test_webhook:
        return test_webhook(config)

    if args.test_llm:
        return test_llm(config)

    if args.test_repos:
        return test_repos(config)

    # Filter to single repo if specified
    if args.repo:
        config.repos = [r for r in config.repos if r.name == args.repo]
        if not config.repos:
            print(f"Error: repo '{args.repo}' not found in config")
            return 1

    scheduler = Scheduler(config)

    if args.analyze_head:
        scheduler.run_head(n=args.analyze_head)
    elif args.once:
        scheduler.run_once()
    else:
        scheduler.run_forever()

    return 0


if __name__ == "__main__":
    exit(main())
