import json
import logging
import smtplib
import time
from email.mime.text import MIMEText
from typing import Dict

class EmailNotifier:
    def __init__(self):
        with open("config.json", "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self.last_sent: Dict[str, float] = {}

    def should_send(self, identifier: str) -> bool:
        """检查是否应该发送邮件"""
        current_time = time.time()
        last_sent = self.last_sent.get(identifier, 0)
        interval = self.config.get("notice", {}).get("interval_sec", 300)
        if current_time - last_sent >= interval:
            self.last_sent[identifier] = current_time
            return True
        return False

    def send_notification(self, identifier: str, subject: str, content: str) -> bool:
        """发送邮件通知"""
        email_config = self.config.get("notice", {}) or {}
        sender = (email_config.get("email") or "").strip()
        auth_code = (email_config.get("SMTP") or "").strip()
        # 未填写邮箱/授权码时直接跳过，避免每次回流都尝试登录并报错
        if not sender or not auth_code or sender.startswith("xx@"):
            return False

        msg = MIMEText(content, 'plain', 'utf-8')
        msg['From'] = sender
        msg['To'] = sender
        msg['Subject'] = subject

        server = None
        try:
            # 创建SMTP连接（QQ邮箱默认 smtp.qq.com:587，可在 config.json 中覆盖）
            server = smtplib.SMTP(email_config.get("smtp_host") or 'smtp.qq.com',
                                  int(email_config.get("smtp_port") or 587),
                                  timeout=10)
            server.starttls()

            # 登录SMTP服务器
            server.login(sender, auth_code)

            # 发送邮件
            server.send_message(msg)
            logging.info(f"Email sent for {identifier}")
            return True
        except smtplib.SMTPException as e:
            # 记录SMTP特定错误
            logging.warning(f"SMTP warning: {e}")
            return True  # 即使有警告也认为发送成功
        except Exception as e:
            # 记录其他错误
            logging.error(f"Failed to send email: {e}")
            return False
        finally:
            # 确保关闭连接
            try:
                if server is not None:
                    server.quit()
            except Exception:
                pass
