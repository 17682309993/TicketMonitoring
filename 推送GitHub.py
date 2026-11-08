#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过 GitHub API 推送代码（当 git push 因网络不通而超时时使用）

原理：不走 git 传输协议（github.com:443），改用 api.github.com 的 Git Data 接口
逐个上传文件 → 建 tree → 建 commit → 移动分支指针。国内网络下 api.github.com
通常能通，而 github.com 会挂，所以这个脚本是 git push 的兜底方案。

用法：
    ./.venv/bin/python 推送GitHub.py                    # 推到 origin 对应仓库的 main
    ./.venv/bin/python 推送GitHub.py --repo 用户名/仓库名
    ./.venv/bin/python 推送GitHub.py -m "提交说明"
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time

try:
    import requests
except ImportError:
    sys.exit("缺少 requests，请先执行：./.venv/bin/pip install requests")

API = "https://api.github.com"
CWD = os.path.dirname(os.path.abspath(__file__))


def sh(*args, **kw):
    return subprocess.run(args, cwd=CWD, capture_output=True, text=True, **kw)


def get_token():
    r = sh("gh", "auth", "token")
    token = r.stdout.strip()
    if not token:
        sys.exit("拿不到 GitHub token，请先运行：gh auth login")
    return token


def guess_repo():
    """从 git remote origin 里读出 owner/repo"""
    r = sh("git", "remote", "get-url", "origin")
    url = r.stdout.strip()
    m = re.search(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?$", url)
    if not m:
        sys.exit("无法从 origin 推断仓库，请用 --repo 用户名/仓库名 指定")
    return f"{m.group(1)}/{m.group(2)}"


class GH:
    def __init__(self, token):
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "TicketMonitoring-push",
        })
        self.s.trust_env = True  # 走系统代理

    def req(self, method, path, **kw):
        url = path if path.startswith("http") else API + path
        for attempt in range(4):
            try:
                r = self.s.request(method, url, timeout=45, **kw)
            except Exception as e:
                if attempt == 3:
                    raise
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code in (200, 201):
                return r.json() if r.text.strip() else {}
            if r.status_code == 404:
                return None
            if r.status_code == 409 and method == "GET":
                # 空仓库时读取 ref / tree 会返回 409，等价于“还没有”
                return None
            if r.status_code in (409, 422) and attempt < 3:
                # 空仓库 blob 409、ref 已存在 422，等一下重试
                time.sleep(2)
                continue
            raise RuntimeError(f"{method} {path} -> {r.status_code} {r.text[:400]}")
        return None


def seed_empty_repo(gh, repo, branch, files):
    """空仓库不允许直接建 blob（GitHub 返回 409 Git Repository is empty）。
    先用 Contents API 提交一个文件，把仓库“激活”，之后就能正常用 Git Data 接口。"""
    # 优先用 .gitignore 作为种子文件，它在最终态里本来就存在，不会多出冗余内容
    priority = [".gitignore", "README.md", "requirements.txt"]
    pick = next((p for p in priority if any(f[0] == p for f in files)), files[0][0])
    full = os.path.join(CWD, pick)
    with open(full, "rb") as f:
        raw = f.read()
    print(f"· 仓库是空的，先用 {pick} 初始化…")
    gh.req(
        "POST", f"/repos/{repo}/contents/{pick}",
        json={
            "message": "chore: 初始化仓库",
            "content": base64.b64encode(raw).decode(),
            "branch": branch,
        },
    )
    # 等分支真正可读
    for _ in range(6):
        if gh.req("GET", f"/repos/{repo}/git/ref/heads/{branch}"):
            return
        time.sleep(2)
    raise RuntimeError("初始化后仍读不到分支，请稍后重试")


def index_entries():
    """从 git 暂存区读出 (路径, 模式)：只包含会被 git 跟踪的文件，
    因此 .gitignore 里的 config.json / .venv 天然被排除。"""
    r = sh("git", "ls-files", "-s", "-z")
    if r.returncode != 0:
        sys.exit("读取 git 索引失败：" + r.stderr)
    entries = []
    for item in r.stdout.split("\0"):
        if not item.strip():
            continue
        meta, path = item.split("\t", 1)
        mode, _sha, _stage = meta.split()
        entries.append((path, mode))
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", help="owner/repo，默认从 origin 推断")
    ap.add_argument("-m", "--message", help="提交说明")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--public", action="store_true", help="顺便把仓库改为公开")
    args = ap.parse_args()

    repo = args.repo or guess_repo()
    gh = GH(get_token())

    info = gh.req("GET", f"/repos/{repo}")
    if not info:
        sys.exit(f"仓库 {repo} 不存在或无权访问")
    print(f"仓库：{repo}（{'私有' if info.get('private') else '公开'}）")

    files = index_entries()
    print(f"待上传：{len(files)} 个文件")

    # 0) 空仓库先初始化（否则建 blob 会 409）
    if not gh.req("GET", f"/repos/{repo}/git/ref/heads/{args.branch}"):
        seed_empty_repo(gh, repo, args.branch, files)

    # 1) 上传 blob（内容用 base64，避免编码问题）
    tree = []
    for path, mode in files:
        full = os.path.join(CWD, path)
        with open(full, "rb") as f:
            raw = f.read()
        res = gh.req(
            "POST", f"/repos/{repo}/git/blobs",
            json={"content": base64.b64encode(raw).decode(), "encoding": "base64"},
        )
        tree.append({"path": path, "mode": mode, "type": "blob", "sha": res["sha"]})
        print(f"  ✓ {path}  ({len(raw)} B)")

    # 2) 建 tree（base_tree 为空 = 整树替换，保证远端与本地完全一致）
    tree_res = gh.req("POST", f"/repos/{repo}/git/trees", json={"tree": tree})
    tree_sha = tree_res["sha"]
    print(f"tree: {tree_sha}")

    # 3) 父提交（空仓库则没有）
    head = gh.req("GET", f"/repos/{repo}/git/ref/heads/{args.branch}")
    parents = [head["object"]["sha"]] if head else []

    # 4) 建 commit
    message = args.message
    if not message:
        r = sh("git", "log", "-1", "--pretty=%B")
        message = r.stdout.strip() or "chore: 同步本地代码"
    cfg_name = sh("git", "config", "user.name").stdout.strip() or "TicketMonitoring"
    cfg_mail = sh("git", "config", "user.email").stdout.strip() or "noreply@example.com"
    commit = gh.req(
        "POST", f"/repos/{repo}/git/commits",
        json={"message": message, "tree": tree_sha, "parents": parents},
    )
    commit_sha = commit["sha"]
    print(f"commit: {commit_sha[:10]}  {'（新建分支）' if not parents else '（基于 ' + parents[0][:10] + '）'}")

    # 5) 移动分支指针
    if head:
        gh.req("PATCH", f"/repos/{repo}/git/refs/heads/{args.branch}", json={"sha": commit_sha, "force": True})
    else:
        gh.req("POST", f"/repos/{repo}/git/refs", json={"ref": f"refs/heads/{args.branch}", "sha": commit_sha})

    # 6) 可选：仓库转公开
    if args.public and info.get("private"):
        gh.req("PATCH", f"/repos/{repo}", json={"private": False})
        print("仓库已改为公开")

    url = f"https://github.com/{repo}"
    print(f"\n✅ 推送完成：{url}")
    print(f"   分支 {args.branch} → {commit_sha[:10]}，共 {len(files)} 个文件")
    return url


if __name__ == "__main__":
    main()
