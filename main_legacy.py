#!/usr/bin/env python3

# MIT License
#
# Copyright (c) 2025 VIFEX
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import argparse
import subprocess
import time
import os
import requests
import json
import logging
from pprint import pprint

# Configure basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def send_webhook_message(webhook_url, payload):
    """Send message to webhook (same implementation as before)"""
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(webhook_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        logging.info(f"Message: {payload} sent successfully")
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send message: {e}")
        return False


def git_checkout_branch(branch_name):
    """Checkout specified git branch"""
    try:
        subprocess.run(["git", "checkout", branch_name], check=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to checkout branch {branch_name}: {e}")
        return False


def get_branch_commit_hash(branch_name):
    """Return the latest commit hash for a given branch name.

    Tries several references (local branch, origin/branch, direct name) to be robust.
    Returns None if the branch cannot be resolved.
    """
    candidates = [f"refs/heads/{branch_name}", f"origin/{branch_name}", branch_name]
    for ref in candidates:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--verify", ref],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            continue
    logging.error(f"Could not resolve branch '{branch_name}' to a commit hash")
    return None


def get_latest_commit_hash():
    """Get latest commit hash"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, stdout=subprocess.PIPE, text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to get commit hash: {e}")
        return None


def run_tests(test_script):
    """Run test script and return exit code"""
    try:
        result = subprocess.run([test_script])
        return result.returncode
    except subprocess.CalledProcessError as e:
        logging.error(f"Tests failed: {e}")
        return 1
    except FileNotFoundError:
        logging.error(f"Test script not found: {test_script}")
        exit(1)


def get_commit_log(commit_hash_begin, commit_hash_end=0):
    """Get commit log for a range of commits"""
    try:
        # Use subprocess to call Git command to get commit log
        if commit_hash_end != 0:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    f"{commit_hash_begin}..{commit_hash_end}",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
            )
        else:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    "-1",
                    f"{commit_hash_begin}",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
            )
        commit_log = result.stdout.strip()
        logging.info(f"Commit log: {commit_log}")
    except subprocess.CalledProcessError as e:
        commit_log = f"Error fetching commit log for {commit_hash_begin}..{commit_hash_end}: {e.stderr.strip()}"
    return commit_log


def on_test_begin(webhook_url, branch, commit_hash):
    """Send begin message to webhook"""
    payload = {
        "title": "黑锅侠，出击!",
        "content": f"分支: {branch}\n最新提交:\n{get_commit_log(commit_hash)}",
    }
    send_webhook_message(webhook_url, payload)


def on_test_success(webhook_url, branch, commit_hash):
    """Send success message to webhook"""
    payload = {
        "title": "叮铃铃~ 测试通过!",
        "content": f"分支: {branch}\n最新提交:\n{get_commit_log(commit_hash)}",
    }
    send_webhook_message(webhook_url, payload)


def on_test_failure(webhook_url, branch, commit_hash, last_test_pass_commit):
    """Send failure message to webhook"""

    commit_log = get_commit_log(commit_hash)
    if last_test_pass_commit:
        commit_log = get_commit_log(last_test_pass_commit, commit_hash)

    payload = {
        "title": "铛铛铛! 测试失败!",
        "content": f"分支: {branch}\n怀疑对象:\n{commit_log}",
    }
    send_webhook_message(webhook_url, payload)


def monitor_repo(args):
    """Monitor git repo for changes and run tests.

    Supports monitoring multiple branches (comma-separated via --branch).
    For each branch we track the last seen commit and last commit that passed tests.
    When a branch changes we checkout that branch, run tests, and send webhook messages
    that include the branch name.
    """
    os.chdir(args.dir)

    # Determine branches to monitor
    if getattr(args, "branches", None):
        branches = args.branches
    elif args.branch:
        branches = [b.strip() for b in args.branch.split(",") if b.strip()]
    else:
        # No branch specified: use current checked-out branch
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                check=True,
                stdout=subprocess.PIPE,
                text=True,
            )
            branches = [result.stdout.strip()]
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to determine current branch: {e}")
            return False

    logging.info(f"Monitoring branches: {branches}")

    # Initialize per-branch trackers
    last_commit = {b: None for b in branches}
    last_test_pass_commit = {b: None for b in branches}

    while True:
        for branch in branches:
            # Checkout the branch first
            if not git_checkout_branch(branch):
                logging.error(f"Skipping tests for {branch} because checkout failed")
                continue

            # Sync updates from remote if command provided
            if args.sync_command:
                try:
                    subprocess.run(args.sync_command, check=True, shell=True)
                except subprocess.CalledProcessError as e:
                    logging.error(f"Failed to fetch updates: {e}")
                    continue

            # Get current commit hash for this branch
            current_commit = get_branch_commit_hash(branch)
            if not current_commit:
                logging.error(
                    f"Skipping tests for {branch} because branch can't be resolved"
                )
                continue

            # Check for new commits
            if current_commit != last_commit.get(branch):
                logging.info(f"New commit detected: {current_commit}")
                on_test_begin(args.url, branch, current_commit)

                if run_tests(args.test_script) == 0:
                    on_test_success(args.url, branch, current_commit)
                    last_test_pass_commit[branch] = current_commit
                else:
                    on_test_failure(
                        args.url, branch, current_commit, last_test_pass_commit[branch]
                    )

                last_commit[branch] = current_commit

        time.sleep(args.interval_minutes * 60 + args.interval_hours * 60 * 60)


def main():
    parser = argparse.ArgumentParser(description="Monitor git repo and run tests")
    parser.add_argument("--url", "-u", required=True, help="Webhook URL")
    parser.add_argument(
        "--interval-hours",
        type=float,
        default=1,
        help="Check interval in hours (default: 1 hours)",
    )
    parser.add_argument(
        "--interval-minutes",
        type=float,
        default=0,
        help="Check interval in minutes (default: 0 minutes)",
    )
    parser.add_argument("--dir", "-d", required=True, help="Git repo directory")
    parser.add_argument(
        "--branch",
        "-b",
        help="Git branch to monitor, e.g. 'main' or 'dev'. For multiple branches, use comma-separated values like 'main,dev'. If not specified, the current branch is used.",
    )
    parser.add_argument(
        "--test-script",
        "-t",
        required=True,
        help="Test script to run",
    )
    parser.add_argument(
        "--sync-command",
        help="Command to sync updates from remote",
    )
    args = parser.parse_args()
    pprint(args)

    monitor_repo(args)


if __name__ == "__main__":
    main()
