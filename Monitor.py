import json
import logging
import subprocess
from time import time

import requests
import urllib3


class Monitor:
    __last_alert_time = 0
    __last_mac_alert_time = 0
    _proxy = None
    # proxy在config.json中配置格式为: {
    #     "http": "http://10.16.10.24:12001",
    #     "https": "http://10.16.10.24:12001"
    #   }
    # 频繁请求请添加代理，自建代理见GitHub: https://github.com/ThinkerWen/ProxyServer

    def __init__(self):
        file = open("config.json", "r", encoding="utf-8")
        config = json.load(file)
        file.close()
        self._config = config
        proxy = config.get("proxy")
        self._proxy = proxy if proxy else None

        # Bark 推送 key 从 config.json 的 notice.bark_key 读取，支持单个字符串或数组
        bark_key = (config.get("notice") or {}).get("bark_key")
        if isinstance(bark_key, str):
            bark_key = [bark_key]
        self._bark_keys = [k.strip() for k in (bark_key or []) if isinstance(k, str) and k.strip()]

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        logging.basicConfig(format='%(asctime)s.%(msecs)03d [%(filename)s:%(lineno)d] : %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)

    # 读取 config.json 中 auth.<平台> 的凭证，用于重放你自己抓包得到的请求
    # 结构： "auth": { "pxq": { "cookie": "...", "access_token": "...", "headers": {"x-xxx": "..."} } }
    def auth(self, platform_key: str) -> dict:
        return (self._config.get("auth") or {}).get(platform_key) or {}

    # iOS Bark 推送，见 GitHub: https://github.com/Finb/Bark
    # key 放在 config.json 的 notice.bark_key（字符串或数组），没配就自动跳过
    # 用 POST + JSON 推送，比把中文塞进 URL 路径更稳；level=timeSensitive 可穿透专注模式
    def bark_alert(self, content: str, title: str = "回流票提醒") -> bool:
        if not self._bark_keys:
            return False
        if time() - self.__last_alert_time < 10:
            return False
        self.__last_alert_time = time()

        notice = self._config.get("notice") or {}
        server = (notice.get("bark_server") or "https://api.day.app").rstrip("/")
        payload = {
            "title": title,
            "body": content,
            "sound": notice.get("bark_sound") or "alarm",
            "group": notice.get("bark_group") or "回流票",
            "level": "timeSensitive",
        }
        sent = False
        for key in self._bark_keys:
            try:
                resp = requests.post(f"{server}/{key}", json=payload, proxies=self._proxy, timeout=10)
                try:
                    result = resp.json()
                except Exception:
                    result = {}
                if result.get("code") == 200:
                    sent = True
                    logging.info("Bark 推送成功")
                else:
                    logging.warning(
                        f"Bark 推送失败 key={key[:4]}… http={resp.status_code} "
                        f"code={result.get('code')} message={result.get('message') or resp.text[:80]}")
            except Exception as e:
                logging.warning(f"Bark 推送异常 key={key[:4]}…：{e}")
        return sent

    # macOS 本地通知：不需要任何 key，发现回流时在屏幕右上角弹窗 + 响一声
    # 可在 config.json 的 notice.macos_notify 设为 false 关闭
    def mac_alert(self, content: str, title: str = "回流票提醒"):
        if (self._config.get("notice") or {}).get("macos_notify", True) is False:
            return
        if time() - self.__last_mac_alert_time < 10:
            return
        self.__last_mac_alert_time = time()
        safe = str(content).replace("\\", "\\\\").replace('"', '\\"')
        safe_title = str(title).replace("\\", "\\\\").replace('"', '\\"')
        try:
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{safe}" with title "{safe_title}" sound name "Glass"'],
                capture_output=True, timeout=10,
            )
        except Exception as e:
            logging.warning(f"macOS 通知失败：{e}")
