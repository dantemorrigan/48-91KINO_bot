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
    sources: list = field(default_factory=lambda: ["kodik", "hdrezka"])


def load_config(path: str = "config.json") -> Config:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Config(
        token=data["TOKEN"],
        kinopoisk_api_key=data.get("KINOPOISK_API_KEY", ""),
        kodik_token=data.get("KODIK_TOKEN"),
    )
