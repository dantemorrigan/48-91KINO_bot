import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    token: str
    kinopoisk_api_key: str
    kodik_token: Optional[str] = None
    request_timeout: int = 15
    max_favorites: int = 30
    results_per_page: int = 5
    rate_limit_seconds: float = 1.5


def load_config(path: str = "config.json") -> Config:
    # Environment variables take priority (for Railway/cloud hosting)
    token = os.environ.get("BOT_TOKEN")
    kodik = os.environ.get("KODIK_TOKEN")

    # Fall back to config.json for local development
    if not token:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            token = token or data.get("TOKEN", "")
            kodik = kodik or data.get("KODIK_TOKEN")
        except FileNotFoundError:
            pass

    if not token:
        raise RuntimeError(
            "Telegram bot token not found. "
            "Set BOT_TOKEN environment variable or add TOKEN to config.json"
        )

    # Kinopoisk integration is permanently disabled: the bot is archived and
    # its Kinopoisk.dev API key was retired for good after the compromise.
    return Config(
        token=token,
        kinopoisk_api_key="",
        kodik_token=kodik or None,
    )
