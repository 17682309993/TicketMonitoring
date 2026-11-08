import json
import logging

import requests
from requests import Response

from Monitor import Monitor


class PXQ(Monitor):

    show_start = False

    def __init__(self, perform: dict) -> None:
        super().__init__()
        self.show_info = {
            "platform": "票星球",
            "seat_info": list(),
            "session_info": list(),
            "show_id": perform.get('show_id'),
            "show_name": perform.get('show_name')
        }
        logging.info(f"票星球 {perform.get('show_name')} 开始加载")
        self.get_show_infos()
        logging.info(f"票星球 {self.show_info.get('show_name')} 加载成功")

    def get_show_infos(self):
        show_id = self.show_info.get('show_id')
        payload = self.request_json(f"https://m.piaoxingqiu.com/cyy_gatewayapi/show/pub/v3/show/{show_id}/sessions_static_data")
        if payload.get("statusCode") != 200:
            code = payload.get("statusCode")
            hint = ""
            if code == 1270:
                hint = ("；1270 通常是 show_id 填成了 stdShowId。票星球同一场演出有两个 ID，"
                        "接口只认 showId（网页地址里那个往往不能直接用），请运行 "
                        "`./.venv/bin/python 查演出ID.py 演出关键词` 取正确的 showId")
            raise RuntimeError(
                f"票星球接口拒绝访问 statusCode={code} "
                f"msg={payload.get('comments') or payload.get('message')}{hint}"
            )
        data = payload.get("data") or {}
        for session in data.get("sessionVOs") or []:
            session_id = session.get("bizShowSessionId")
            session_name = session.get("sessionName")
            self.show_info["session_info"].append({
                "session_id": session_id,
                "session_name": session_name,
            })
            seat_payload = self.request_json(
                f'https://m.piaoxingqiu.com/cyy_gatewayapi/show/pub/v3/show/{show_id}/show_session/{session_id}/seat_plans_static_data')
            for seat in (seat_payload.get("data") or {}).get("seatPlans") or []:
                self.show_info["seat_info"].append({
                    "session_id": session_id,
                    "session_name": session_name,
                    "seat_plan_id": seat.get("seatPlanId"),
                    "seat_plan_name": seat.get("seatPlanName"),
                })
        if not self.show_info["session_info"]:
            raise RuntimeError("票星球返回了空场次列表，演出 ID 可能不正确或演出已下架")

    def monitor(self) -> list:
        logging.info(f"票星球 {self.show_info.get('show_name')} 监控中")
        can_buy_list = []
        show_id = self.show_info.get('show_id')

        if not self.show_start:
            payload = self.request_json(
                f'https://m.piaoxingqiu.com/cyy_gatewayapi/show/pub/v3/show/{show_id}/sessions_dynamic_data')
            if payload.get("statusCode") == 200:
                for session in (payload.get("data") or {}).get("sessionVOs") or []:
                    if (session.get("sessionSaleTimeCountdown") or 0) > 0:
                        logging.info(f"票星球 {self.show_info.get('show_name')} 尚未开售，等待开票倒计时")
                        return can_buy_list
                self.show_start = True
        seat_names = {s.get("seat_plan_id"): s.get("seat_plan_name") for s in self.show_info.get("seat_info") or []}
        for session in self.show_info.get("session_info"):
            session_id = session.get("session_id")
            payload = self.request_json(
                f'https://m.piaoxingqiu.com/cyy_gatewayapi/show/pub/v3/show/{show_id}/show_session/{session_id}/seat_plans_dynamic_data')
            if payload.get("statusCode") != 200:
                logging.warning(
                    f"票星球 余票接口返回 statusCode={payload.get('statusCode')} "
                    f"msg={payload.get('comments')}（本轮跳过，下轮再试）")
                continue
            for seat in (payload.get("data") or {}).get("seatPlans") or []:
                count = seat.get("canBuyCount") or 0
                if count > 0:
                    plan_id = seat.get("seatPlanId")
                    can_buy_list.append(plan_id)
                    logging.info(
                        f"票星球 发现余票：{session.get('session_name')} / "
                        f"{seat_names.get(plan_id, plan_id)} 可购 {count} 张")
        return can_buy_list

    def request(self, url: str) -> Response:
        return requests.get(
            url=url,
            headers=self.headers(),
            proxies=super()._proxy,
            verify=False,
            timeout=10
        )

    # 带凭证的 JSON 请求，便于把平台返回的错误原样抛出来
    def request_json(self, url: str) -> dict:
        response = self.request(url)
        try:
            return response.json()
        except Exception:
            raise RuntimeError(f"票星球返回了非 JSON 内容：http={response.status_code} body={response.text[:200]}")

    def headers(self) -> dict:
        headers = {
            'ver': '3.1.5',
            'xweb_xhr': '1',
            'Accept': '*/*',
            'src': 'weixin_mini',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Host': 'm.piaoxingqiu.com',
            'terminal-src': 'WEIXIN_MINI',
            'Accept-Language': 'zh-CN,zh',
            'Sec-Fetch-Site': 'cross-site',
            'Content-Type': 'application/json',
            "merchant-id": "6267a80eed218542786f1494",
            'Referer': 'https://servicewechat.com/wxad60dd8123a62329/238/page-frame.html',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36 MicroMessenger/6.8.0(0x16080000) NetType/WIFI MiniProgramEnv/Mac MacWechat/WMPF XWEB/30817',
        }
        # 用 config.json 里 auth.pxq 的抓包凭证覆盖默认头
        auth = super().auth("pxq")
        headers.update(auth.get("headers") or {})
        if auth.get("access_token"):
            headers["access-token"] = auth["access_token"]
        if auth.get("cookie"):
            headers["Cookie"] = auth["cookie"]
        return headers
