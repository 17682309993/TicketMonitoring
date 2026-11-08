#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键配置 Bark 推送并试推一条

用法（三种都行）：
    ./.venv/bin/python 配置Bark.py https://api.day.app/你的key/推送内容
    ./.venv/bin/python 配置Bark.py 你的key
    ./.venv/bin/python 配置Bark.py            # 不带参数时自动读剪贴板

怎么拿 key：iPhone 打开 Bark → 首页「服务器」下方那一长串就是 key；
也可以点「复制推送地址」，把整条 https://api.day.app/xxx/推送内容 粘过来。
"""
import json
import re
import subprocess
import sys
from urllib.parse import urlparse

import requests

CONFIG = "config.json"


def from_clipboard():
    try:
        return subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return ""


def parse(raw):
    """从「完整推送地址」或「裸 key」里解析出 (服务器, key)"""
    raw = raw.strip().strip('"').strip("'")
    if not raw:
        return None, None
    if raw.startswith("http"):
        u = urlparse(raw)
        segs = [s for s in u.path.split("/") if s]
        key = None
        for seg in segs:
            if re.fullmatch(r"[A-Za-z0-9_\-]{8,64}", seg):
                key = seg
                break
        if not key:
            return None, None
        idx = segs.index(key)
        prefix = "/".join(segs[:idx])
        server = f"{u.scheme}://{u.netloc}" + (f"/{prefix}" if prefix else "")
        return server, key
    if re.fullmatch(r"[A-Za-z0-9_\-]{8,64}", raw):
        return "https://api.day.app", raw
    return None, None


def load_config():
    with open(CONFIG, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")


def push(server, key, title, body):
    try:
        r = requests.post(f"{server.rstrip('/')}/{key}",
                          json={"title": title, "body": body, "sound": "alarm",
                                "group": "回流票", "level": "timeSensitive"},
                          timeout=15)
    except Exception as e:
        return False, f"网络异常：{type(e).__name__} {e}"
    try:
        j = r.json()
    except Exception:
        return False, f"http={r.status_code} 返回非 JSON：{r.text[:120]}"
    if j.get("code") == 200:
        return True, j.get("message") or "success"
    return False, f"code={j.get('code')} message={j.get('message')}（http={r.status_code}）"


def main():
    raw = " ".join(sys.argv[1:]).strip()
    if not raw:
        raw = from_clipboard()
        if raw:
            print(f"从剪贴板读到：{raw[:60]}{'…' if len(raw) > 60 else ''}")
    if not raw:
        print(__doc__)
        return 1

    server, key = parse(raw)
    if not key:
        print("!! 没识别出 Bark key。key 由字母数字组成（约 22 位），或直接粘完整推送地址。")
        return 1

    print(f"服务器：{server}")
    print(f"key   ：{key[:4]}…{key[-4:]}（共 {len(key)} 位）")

    ok, msg = push(server, key, "Bark 配置测试", "如果看到这条，说明回流票提醒可以正常推到你手机了。")
    if not ok:
        print(f"!! 试推失败：{msg}")
        print("   常见原因：key 复制不全、Bark App 没点开过（未注册设备）、服务器地址不对。")
        return 1
    print(f"✔ 试推成功：{msg}")

    cfg = load_config()
    notice = cfg.setdefault("notice", {})
    notice["bark_key"] = key
    if server and server != "https://api.day.app":
        notice["bark_server"] = server
    else:
        notice.pop("bark_server", None)
    save_config(cfg)
    print(f"✔ 已写入 {CONFIG} 的 notice.bark_key，之后发现回流会自动推手机")
    return 0


if __name__ == "__main__":
    sys.exit(main())
