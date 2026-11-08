#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
票星球 演出ID / 场次 / 余票 查询工具

用法：
    ./.venv/bin/python 查演出ID.py 大连英博          # 按关键词搜索演出
    ./.venv/bin/python 查演出ID.py -s 697834bc1203fa00012dede1   # 查该演出的场次与余票

说明：
    票星球同一场演出有两个 ID：
      showId    —— 场次/票价接口要用的 ID（填进 config.json 的 monitor_list）
      stdShowId —— 标准展示 ID，网页地址里常见，但接口不能直接用！
    填错就会一直报 1270「当前访客较多」，看起来像被风控，其实是 ID 不对。
"""
import json
import sys

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36")
H = {
    "Accept": "application/json",
    "User-Agent": UA,
    "Content-Type": "application/json",
    "src": "WEB",
    "terminal-src": "WEB",
    "utc-offset": "480",
    "Referer": "https://m.piaoxingqiu.com/",
}
BASE = "https://m.piaoxingqiu.com/cyy_gatewayapi"


def api(path):
    r = requests.get(BASE + path, headers=H, timeout=20, verify=False)
    try:
        return r.json()
    except Exception:
        return {"statusCode": r.status_code, "comments": r.text[:120]}


def search(keyword):
    payload = api("/home/pub/v3/show_list/search_by_front"
                  "?src=WEB&channelId=&terminalSrc=WEB&offset=0&length=20"
                  f"&keyword={requests.utils.quote(keyword)}")
    code = payload.get("statusCode")
    if code != 200:
        print(f"搜索失败 statusCode={code} msg={payload.get('comments')}")
        return
    items = (payload.get("data") or {}).get("searchData") or []
    shows = [i for i in items if i.get("searchType") == "SHOW"]
    if not shows:
        print("没有搜到演出，换个关键词试试（用演出全名里的连续几个字）")
        return
    print(f"共 {len(shows)} 个结果：\n")
    for i, it in enumerate(shows, 1):
        print(f"[{i}] {it.get('showName')}")
        print(f"    时间: {it.get('showDate')}   城市: {it.get('cityName')}   场馆: {it.get('venueName')}")
        print(f"    状态: {it.get('showStatus')}   售罄: {it.get('soldOut')}   起价: ¥{it.get('minOriginalPrice')}")
        print(f"    showId    (填这个) : {it.get('showId')}")
        print(f"    stdShowId (别填)   : {it.get('stdShowId')}")
        print()
    print("把上面 showId 那一行填进 config.json 的 monitor_list，例如：")
    print('  { "show_id": "%s", "show_name": "%s", "platform": 3, "deadline": "2026-11-08 15:30:00" }'
          % (shows[0].get("showId"), shows[0].get("showName")))


def sessions(show_id):
    payload = api(f"/show/pub/v3/show/{show_id}/sessions_static_data")
    code = payload.get("statusCode")
    if code != 200:
        print(f"场次加载失败 statusCode={code} msg={payload.get('comments')}")
        if code == 1270:
            print("提示：1270 通常是 show_id 填成了 stdShowId，请用 `查演出ID.py 关键词` 重新取 showId")
        return

    dynamic = api(f"/show/pub/v3/show/{show_id}/sessions_dynamic_data")
    dyn_map = {}
    if dynamic.get("statusCode") == 200:
        for s in (dynamic.get("data") or {}).get("sessionVOs") or []:
            dyn_map[s.get("bizShowSessionId")] = s

    for s in (payload.get("data") or {}).get("sessionVOs") or []:
        sid = s.get("bizShowSessionId")
        d = dyn_map.get(sid) or {}
        print(f"场次: {s.get('sessionName')}")
        print(f"  场次ID: {sid}")
        print(f"  售罄: {d.get('hasSessionSoldOut')}   状态: {d.get('sessionStatus')}")

        plans = api(f"/show/pub/v3/show/{show_id}/show_session/{sid}/seat_plans_static_data")
        names = {p.get("seatPlanId"): p.get("seatPlanName")
                 for p in (plans.get("data") or {}).get("seatPlans") or []}
        dyn = api(f"/show/pub/v3/show/{show_id}/show_session/{sid}/seat_plans_dynamic_data")
        rows = (dyn.get("data") or {}).get("seatPlans") or []
        if not rows:
            print("  余票: 取不到（该场次未开售或无票档）")
        else:
            print("  票档余票：")
            for p in rows:
                pid = p.get("seatPlanId")
                print(f"    {str(names.get(pid, pid)):>10s}  canBuy={p.get('canBuyCount')}  "
                      f"saleStarted={p.get('saleStarted')}")
        print()


def main():
    args = [a for a in sys.argv[1:] if a.strip()]
    if not args:
        print(__doc__)
        return
    if args[0] in ("-s", "--session"):
        if len(args) < 2:
            print("用法: 查演出ID.py -s <showId>")
            return
        sessions(args[1].strip())
    else:
        search(" ".join(args))


if __name__ == "__main__":
    main()
