"""Telegram Bot API orqali yuborish."""
from __future__ import annotations

import os

API = "https://api.telegram.org/bot{token}/{method}"


class Telegram:
    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not self.token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN o'rnatilmagan")

    def _call(self, method: str, **kwargs):
        import requests
        resp = requests.post(API.format(token=self.token, method=method), timeout=60, **kwargs)
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram xatosi: {data.get('description')}")
        return data["result"]

    def send(self, chat_id: str, messages: list[str]) -> None:
        for text in messages:
            self._call("sendMessage", data={"chat_id": chat_id, "text": text,
                                            "parse_mode": "HTML",
                                            "disable_web_page_preview": True})

    def send_file(self, chat_id: str, path: str, caption: str = "") -> None:
        with open(path, "rb") as fh:
            self._call("sendDocument", data={"chat_id": chat_id, "caption": caption},
                       files={"document": fh})
