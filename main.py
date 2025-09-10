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


def on_test_begin(webhook_url, commit_hash):
    """Send begin message to webhook"""
    payload = {
        "title": "黑锅侠，出击!",
        "content": f"最新提交:\n{get_commit_log(commit_hash)}",
    }
    send_webhook_message(webhook_url, payload)


def on_test_success(webhook_url, commit_hash):
    """Send success message to webhook"""
    payload = {
        "title": "叮铃铃~ 测试通过!",
        "content": f"最新提交:\n{get_commit_log(commit_hash)}",
    }
    send_webhook_message(webhook_url, payload)


def on_test_failure(webhook_url, commit_hash, last_test_pass_commit):
    """Send failure message to webhook"""

    commit_log = get_commit_log(commit_hash)
    if last_test_pass_commit:
        commit_log = get_commit_log(last_test_pass_commit, commit_hash)

    payload = {
        "title": "铛铛铛! 测试失败!",
        "content": f"怀疑对象:\n{commit_log}",
    }
    send_webhook_message(webhook_url, payload)


def monitor_repo(args):
    """Monitor git repo for changes and run tests"""
    os.chdir(args.dir)
    if args.branch and not git_checkout_branch(args.branch):
        return False

    last_commit = 0
    last_test_pass_commit = 0

    while True:
        if args.sync_command:
            try:
                subprocess.run(args.sync_command, check=True, shell=True)
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to fetch updates: {e}")

        current_commit = get_latest_commit_hash()
        if current_commit != last_commit:
            logging.info(f"New commit detected: {current_commit}")
            on_test_begin(args.url, current_commit)

            if run_tests(args.test_script) == 0:
                on_test_success(args.url, current_commit)
                last_test_pass_commit = current_commit
            else:
                on_test_failure(args.url, current_commit, last_test_pass_commit)

            last_commit = current_commit

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
        help="Git branch to monitor",
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
