#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发一条测试提醒，确认通知渠道是通的

用法：
    ./.venv/bin/python 测试提醒.py
"""
import json
import sys

from Monitor import Monitor


def main():
    cfg = json.load(open("config.json", encoding="utf-8"))
    notice = cfg.get("notice") or {}
    content = "这是一条测试提醒：发现 680元 余票 2 张，请及时购票！"

    # 只借用 Monitor 的推送方法，不初始化具体平台监控
    m = Monitor.__new__(Monitor)
    m._config = cfg
    m._Monitor__last_mac_alert_time = 0
    m._Monitor__last_alert_time = 0
    m._bark_keys = [k.strip() for k in (
        [notice["bark_key"]] if isinstance(notice.get("bark_key"), str) else (notice.get("bark_key") or [])
    ) if isinstance(k, str) and k.strip()]
    m._proxy = cfg.get("proxy") or None

    ok = False
    if notice.get("macos_notify", True) is not False:
        m.mac_alert(content, title="回流票提醒（测试）")
        print("✔ 已发送 macOS 系统通知（屏幕右上角，带 Glass 提示音）")
        ok = True

    if m._bark_keys:
        m.bark_alert(content)
        print(f"✔ 已推送 Bark（{len(m._bark_keys)} 个 key）")
        ok = True
    else:
        print("· Bark 未配置（可选，iOS 手机收推送用）")

    if (notice.get("email") or "").strip() and (notice.get("SMTP") or "").strip():
        print(f"· 邮件已配置，真实发现回流时会发到 {notice.get('email')}")
        ok = True
    else:
        print("· 邮件未配置（可选）")

    if not ok:
        print("!! 没有任何可用的提醒渠道，请检查 config.json 的 notice 段")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
