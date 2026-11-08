import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Union

from Monitor_DM import DM
from Monitor_FWD import FWD
from Monitor_MY import MY
from Monitor_PXQ import PXQ
from email_notifier import EmailNotifier


def get_task(show: dict) -> Union[DM, MY, FWD, PXQ, None]:
    if show.get("platform") == 0:
        return DM(show)
    elif show.get("platform") == 1:
        return MY(show)
    elif show.get("platform") == 2:
        return FWD(show)
    elif show.get("platform") == 3:
        return PXQ(show)
    else:
        return None


class Runner:
    def __init__(self):
        self.email_notifier = EmailNotifier()
        self.threadPool = ThreadPoolExecutor(max_workers=100, thread_name_prefix="ticket_monitor_")

    def loop_monitor(self, monitor: Union[DM, MY, FWD, PXQ], show: dict) -> None:
        while datetime.strptime(show.get("deadline"), "%Y-%m-%d %H:%M:%S") > datetime.now():
            try:
                if monitor.monitor():
                    info = f"{monitor.show_info.get('platform')} {show.get('show_name')} 已回流，请及时购票！"
                    # Get show identifier
                    show_id = f"{monitor.show_info.get('platform')}_{show.get('show_name')}"
                    
                    # Send email notification if enough time has passed
                    if self.email_notifier.should_send(show_id):
                        logging.info(f"->发送邮件提醒:{show.get('show_name')}")
                        subject = f"Ticket Alert: {show.get('show_name')}"
                        self.email_notifier.send_notification(show_id, subject, info)

                    logging.info(info)
                    monitor.bark_alert(info)
                    monitor.mac_alert(info)
            except Exception as e:
                logging.info(f"发生错误：{e}")
            finally:
                # 轮询间隔默认 1 秒，节奏太快容易被风控，可在该演出的配置里用 interval_sec 调整
                try:
                    time.sleep(float(show.get("interval_sec") or 1))
                except Exception:
                    time.sleep(1)

    def start(self):
        file = open("config.json", "r", encoding="utf-8")
        show_list = json.load(file).get("monitor_list") or []
        file.close()

        if not show_list:
            logging.warning("config.json 中 monitor_list 为空，请先添加要监控的演出")
            return

        for show in show_list:
            # 截止时间已过的条目直接跳过，避免无意义地请求接口
            try:
                if datetime.strptime(show.get("deadline"), "%Y-%m-%d %H:%M:%S") <= datetime.now():
                    logging.warning(f"监控对象 {show.get('show_name')} 已过截止时间，跳过")
                    continue
            except Exception:
                logging.warning(f"监控对象 {show.get('show_name')} 的 deadline 格式不正确，应形如 2026-12-31 23:59:59，跳过")
                continue

            # 单个演出初始化失败（如 token 过期）不影响其他演出的监控
            try:
                task = get_task(show)
            except Exception as e:
                logging.error(f"监控对象 {show.get('show_name')} 加载失败 show_id: {show.get('show_id')} 原因: {e}")
                continue

            if task:
                self.threadPool.submit(self.loop_monitor, task, show)
            else:
                logging.error(f"监控对象 {show.get('show_name')} 加载失败 show_id: {show.get('show_id')} platform 取值应为 0/1/2/3")
        self.threadPool.shutdown(wait=True)


if __name__ == '__main__':
    runner = Runner()
    runner.start()
