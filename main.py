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
    args = parser.parse_args()

    config = load_config(args.config)

    # Filter to single repo if specified
    if args.repo:
        config.repos = [r for r in config.repos if r.name == args.repo]
        if not config.repos:
            print(f"Error: repo '{args.repo}' not found in config")
            return 1

    scheduler = Scheduler(config)

    if args.once:
        scheduler.run_once()
    else:
        scheduler.run_forever()

    return 0


if __name__ == "__main__":
    exit(main())
