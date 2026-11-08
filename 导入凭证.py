#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把浏览器/抓包工具里「Copy as cURL」的内容，自动写进 config.json 的 auth 段。

用法一（推荐，隐私更安全）：把 cURL 存成文件再导入
    ./.venv/bin/python 导入凭证.py pxq ~/Desktop/pxq.txt

用法二：直接从剪贴板读取（macOS）
    ./.venv/bin/python 导入凭证.py pxq

用法三：直接粘贴字符串
    ./.venv/bin/python 导入凭证.py pxq "curl 'https://m.piaoxingqiu.com/...' -H 'cookie: ...'"

平台代码：pxq=票星球, my=猫眼, dm=大麦, fwd=纷玩岛
导入后会自动跑一次诊断，能立刻看到 1270 是否被绕过。
"""
import json
import os
import re
import subprocess
import sys

CONFIG = "config.json"
# 这些头是每次请求自动生成的，存下来反而会出错
SKIP_HEADERS = {"host", "content-length", "connection", "accept-encoding", "cookie", ":authority", ":method", ":path", ":scheme"}


def read_curl(args):
    """从文件、命令行参数或剪贴板里取到 cURL 原始文本"""
    if args:
        joined = " ".join(args)
        path = os.path.expanduser(args[0])
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return joined
    try:
        text = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5).stdout
        if text.strip().startswith("curl"):
            return text
    except Exception:
        pass
    return ""


def parse_curl(text):
    """解析 cURL，返回 (url, headers dict, cookie 字符串)"""
    url = ""
    m = re.search(r"curl\s+(?:'([^']+)'|\"([^\"]+)\")", text)
    if m:
        url = m.group(1) or m.group(2)
    else:
        m = re.search(r"https?://[^\s'\"]+", text)
        url = m.group(0) if m else ""

    headers, cookie = {}, ""
    for hm in re.finditer(r"-H\s+(?:'([^']*)'|\"([^\"]*)\")", text):
        raw = hm.group(1) if hm.group(1) is not None else hm.group(2)
        if ":" not in raw:
            continue
        k, v = raw.split(":", 1)
        k, v = k.strip(), v.strip()
        if k.lower() == "cookie":
            cookie = v
        elif k.lower() not in SKIP_HEADERS:
            headers[k] = v
    for bm in re.finditer(r"(?:-b|--cookie)\s+(?:'([^']*)'|\"([^\"]*)\")", text):
        cookie = cookie or (bm.group(1) if bm.group(1) is not None else bm.group(2))
    return url, headers, cookie


def mask(value, keep=8):
    if not value:
        return "(空)"
    return value[:keep] + "..." + value[-4:] if len(value) > keep + 6 else "***"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    platform = sys.argv[1].lower()
    if platform not in ("pxq", "my", "dm", "fwd"):
        print("平台代码只能是 pxq / my / dm / fwd")
        return 1

    text = read_curl(sys.argv[2:])
    if not text.strip():
        print("没读到 cURL 内容。请把 cURL 存成 .txt 后把路径作为第二个参数，或先复制到剪贴板。")
        return 1

    url, headers, cookie = parse_curl(text)
    if not url and not headers:
        print("解析失败：内容看起来不是 cURL。")
        return 1

    with open(CONFIG, "r", encoding="utf-8") as f:
        config = json.load(f)
    auth = config.setdefault("auth", {})
    block = auth.setdefault(platform, {})
    if cookie:
        block["cookie"] = cookie
    access_token = ""
    for k, v in headers.items():
        if k.lower() in ("access-token", "access_token"):
            access_token = v
    if access_token:
        block["access_token"] = access_token
    block["headers"] = headers
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print("已写入 config.json → auth.%s" % platform)
    print("  请求地址 :", url[:110] or "(未识别)")
    print("  Cookie   :", mask(cookie), "长度", len(cookie))
    print("  token    :", mask(access_token))
    print("  携带头   :", ", ".join(sorted(headers.keys())) or "(无)")
    if not cookie and not access_token:
        print("\n!! 这份 cURL 里既没有 cookie 也没有 access-token，可能抓错了请求。")
        print("   请抓 m.piaoxingqiu.com 的 sessions_static_data 或 show_static_data 请求。")

    print("\n接下来跑诊断验证：")
    print(f"  ./.venv/bin/python 诊断.py {platform} <演出ID>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
