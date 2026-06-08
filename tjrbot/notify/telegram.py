"""Telegram phone alerts via the Bot API (simple HTTP, no extra SDK)."""

from __future__ import annotations

import requests


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base = f"https://api.telegram.org/bot{token}"

    def send(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message. Returns True on success, False on any failure."""
        if not self.token or not self.chat_id:
            return False
        try:
            r = requests.post(
                f"{self.base}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            return r.ok
        except requests.RequestException:
            return False
