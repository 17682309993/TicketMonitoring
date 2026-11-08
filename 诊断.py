#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""接口诊断工具：直接打印平台返回的原始内容，用来判断是「配置写错」「凭证过期」还是「被风控」

用法：
    ./.venv/bin/python 诊断.py pxq 697834bc1203fa00012dede1
    ./.venv/bin/python 诊断.py my  374212
    ./.venv/bin/python 诊断.py dm  1094567880917
    ./.venv/bin/python 诊断.py fwd 12345

参数：平台代码（pxq=票星球, my=猫眼, dm=大麦, fwd=纷玩岛）+ 演出 ID
"""
import json
import sys

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

UA_WX = ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_5_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) '
         'Mobile/15E148 MicroMessenger/8.0.53(0x18003531) NetType/WIFI Language/zh_CN')


def load_auth(platform_key):
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return (json.load(f).get("auth") or {}).get(platform_key) or {}
    except Exception:
        return {}


def pxq(show_id):
    from Monitor_PXQ import PXQ
    auth = load_auth("pxq")
    headers = {  # 复用主程序的头，避免两处不一致
        'ver': '3.1.5', 'xweb_xhr': '1', 'Accept': '*/*', 'src': 'weixin_mini',
        'terminal-src': 'WEIXIN_MINI', 'Accept-Language': 'zh-CN,zh',
        'Content-Type': 'application/json', 'merchant-id': '6267a80eed218542786f1494',
        'Referer': 'https://servicewechat.com/wxad60dd8123a62329/238/page-frame.html',
        'User-Agent': UA_WX,
    }
    headers.update(auth.get("headers") or {})
    if auth.get("access_token"):
        headers["access-token"] = auth["access_token"]
    if auth.get("cookie"):
        headers["Cookie"] = auth["cookie"]
    urls = [
        f"https://m.piaoxingqiu.com/cyy_gatewayapi/show/pub/v3/show/{show_id}/sessions_static_data",
        f"https://m.piaoxingqiu.com/cyy_gatewayapi/show/pub/v3/show/{show_id}/sessions_dynamic_data",
    ]
    hint = {1270: "被前端风控拦截（阿里无痕验证）。需要在 auth.pxq 里补 cookie / access_token，且多半仍需小程序端签名，纯请求可能无解",
            200: "成功"}
    return urls, headers, hint


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    platform, show_id = sys.argv[1].lower(), sys.argv[2]
    urls, headers, hint = pxq(show_id) if platform == "pxq" else (None, None, None)

    if platform == "pxq":
        for url in urls:
            print("=" * 100)
            print("GET", url)
            try:
                r = requests.get(url, headers=headers, timeout=15, verify=False)
                print("HTTP", r.status_code, "| Content-Type", r.headers.get("content-type"))
                try:
                    payload = r.json()
                    print("statusCode:", payload.get("statusCode"), "| msg:", payload.get("comments") or payload.get("message"))
                    data = payload.get("data")
                    if isinstance(data, dict) and data.get("sessionVOs"):
                        print("演出:", data.get("showName"), "| 场次数:", len(data["sessionVOs"]))
                        for s in data["sessionVOs"][:5]:
                            print("   -", s.get("sessionName"), "| 售罄:", s.get("hasSessionSoldOut"),
                                  "| 倒计时:", s.get("sessionSaleTimeCountdown"))
                    print("原始返回:", json.dumps(payload, ensure_ascii=False)[:300])
                    code = payload.get("statusCode")
                    if code in hint:
                        print(">>>", hint[code])
                except Exception:
                    print("非 JSON 返回:", r.text[:300])
            except Exception as e:
                print("请求失败:", type(e).__name__, e)

    elif platform == "dm":
        from Monitor_DM import DM
        auth = load_auth("dm")
        print("auth.dm.cookie 是否已配置:", bool(auth.get("cookie")))
        url = DM.get_show_url()(show_id)
        headers = {'x-tap': 'wx', 'Host': 'mtop.damai.cn', 'Accept': 'application/json',
                   'content-type': 'application/x-www-form-urlencoded',
                   'Referer': 'https://servicewechat.com/wx938b41d0d7e8def0/350/page-frame.html',
                   'User-Agent': UA_WX}
        cookies = {}
        for part in (auth.get("cookie") or "").split(";"):
            if "=" in part:
                k, v = part.split("=", 1)
                cookies[k.strip()] = v.strip()
        r = requests.get(url, headers=headers, cookies=cookies or None, timeout=15, verify=False)
        payload = r.json()
        print("HTTP", r.status_code, "| ret:", payload.get("ret"))
        if not cookies:
            print(">>> 未配置 auth.dm.cookie，正在使用仓库内置的 2024 年失效 Cookie，必然触发 RGV587 滑块验证")

    elif platform == "my":
        from Monitor_MY import MY
        token = (load_auth("my").get("token") or "").strip()
        if not token:
            print("!! 请先在 config.json 的 auth.my.token 填入猫眼 token")
            return 1
        r = requests.post(f"https://wx.maoyan.com/my/odea/project/shows?token={token}&clientPlatform=2",
                          json={"projectId": show_id}, headers=MY.headers(), timeout=15, verify=False)
        payload = r.json()
        print("HTTP", r.status_code, "| success:", payload.get("success"), "| error:", payload.get("error"))
        data = payload.get("data")
        if isinstance(data, dict):
            print("演出名:", data.get("showName") or data.get("name"), "| 场次数:", len(data.get("showListVO") or []))

    elif platform == "fwd":
        url = (f"https://api.livelab.com.cn/performance/app/project/get_performs"
               f"?project_id={show_id}&v=1694683437294&retry=false")
        r = requests.get(url, timeout=15, verify=False)
        print("HTTP", r.status_code, "| 返回:", r.text[:300])

    else:
        print("未知平台代码:", platform)
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
