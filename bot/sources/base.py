from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchResult:
    title: str
    year: Optional[str]
    url: str
    source: str
    content_type: str = "movie"  # movie | series


@dataclass
class VideoInfo:
    player_url: str
    source: str
    title: str
    seasons: list[dict] = field(default_factory=list)
    # seasons = [{"num": 1, "episodes": [{"num": 1, "url": "..."}]}]


class BaseSource(ABC):
    name: str = "base"

    @abstractmethod
    async def search(self, query: str) -> list[SearchResult]:
        ...

    @abstractmethod
    async def get_video(self, url: str) -> Optional[VideoInfo]:
        ...
