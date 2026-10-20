import logging
import smtplib
import time
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

import requests

from .config import AlertsCfg

log = logging.getLogger(__name__)


class Channel(Protocol):
    def send(self, title: str, body: str) -> bool: ...


class TelegramChannel:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id

    def send(self, title: str, body: str) -> bool:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": f"*{title}*\n\n{body}",
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
            r.raise_for_status()
            return True
        except Exception as e:
            log.error("Telegram: %s", e)
            return False


class WebhookChannel:
    def __init__(self, url: str):
        self.url = url

    def send(self, title: str, body: str) -> bool:
        try:
            r = requests.post(
                self.url,
                json={"text": f"*{title}*\n{body}"},
                timeout=10,
            )
            r.raise_for_status()
            return True
        except Exception as e:
            log.error("Webhook: %s", e)
            return False


class EmailChannel:
    def __init__(self, cfg):
        self.cfg = cfg

    def send(self, title: str, body: str) -> bool:
        try:
            msg = EmailMessage()
            msg["Subject"] = title
            msg["From"] = self.cfg.from_
            msg["To"] = self.cfg.to
            msg.set_content(body)
            with smtplib.SMTP(self.cfg.smtp_host, self.cfg.smtp_port,
                              timeout=15) as s:
                s.starttls()
                s.login(self.cfg.smtp_user, self.cfg.smtp_password)
                s.send_message(msg)
            return True
        except Exception as e:
            log.error("Email: %s", e)
            return False


@dataclass
class Alert:
    key: str
    title: str
    body: str


class AlertManager:
    def __init__(self, cfg: AlertsCfg):
        self.cfg = cfg
        self.channels: list[Channel] = []
        self.last_sent: dict[str, float] = {}

        if cfg.telegram.enabled and cfg.telegram.bot_token:
            self.channels.append(
                TelegramChannel(cfg.telegram.bot_token, cfg.telegram.chat_id)
            )
        if cfg.webhook.enabled and cfg.webhook.url:
            self.channels.append(WebhookChannel(cfg.webhook.url))
        if cfg.email.enabled and cfg.email.smtp_host:
            self.channels.append(EmailChannel(cfg.email))

    def send(self, alert: Alert) -> None:
        now = time.time()
        last = self.last_sent.get(alert.key, 0)
        if now - last < self.cfg.cooldown_seconds:
            log.debug("cooldown لـ %s", alert.key)
            return

        for ch in self.channels:
            if ch.send(alert.title, alert.body):
                self.last_sent[alert.key] = now
                return

        log.warning("لم يُرسل تنبيه (%s) — لا قنوات", alert.key)
