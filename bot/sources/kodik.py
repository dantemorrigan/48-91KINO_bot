"""
Kodik CDN source.
Works in two modes:
  1. With token (KODIK_TOKEN in config): uses official search API.
  2. Without token: extracts Kodik embed iframe from DLE-based pirate sites
     that expose it in plain HTML (no JS rendering needed).
"""
import re
import logging
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup

from .base import BaseSource, SearchResult, VideoInfo

logger = logging.getLogger(__name__)

# DLE-based sites that reliably expose Kodik iframe in plain HTML
_DLE_SITES = [
    "https://kinopub.me",
    "https://hdporno.tv",  # placeholder - replace with actual stable DLE sites
]

_KODIK_IFRAME_RE = re.compile(
    r'(https?:)?//(kodik\.(info|biz|cc)|anivod\.com|aniqit\.com)/[^\s"\'<>]+'
)

_KODIK_API = "https://kodikapi.com"


class KodikSource(BaseSource):
    name = "kodik"

    def __init__(self, token: Optional[str], session: aiohttp.ClientSession,
                 timeout: int = 15):
        self._token = token
        self._session = session
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def search(self, query: str) -> list[SearchResult]:
        if self._token:
            return await self._search_api(query)
        return []

    async def _search_api(self, query: str) -> list[SearchResult]:
        params = {
            "token": self._token,
            "title": query,
            "with_episodes": 1,
            "limit": 10,
        }
        try:
            async with self._session.get(
                f"{_KODIK_API}/search", params=params, timeout=self._timeout
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except Exception as e:
            logger.warning("Kodik API search failed: %s", e)
            return []

        results = []
        seen_titles = set()
        for item in data.get("results", []):
            title = item.get("title") or item.get("title_orig", "")
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            year = str(item.get("year", ""))
            link = item.get("link", "")
            if link.startswith("//"):
                link = "https:" + link
            content_type = "series" if "serial" in item.get("type", "") else "movie"
            results.append(SearchResult(
                title=title, year=year, url=link,
                source=self.name, content_type=content_type
            ))
        return results

    async def get_video(self, url: str) -> Optional[VideoInfo]:
        """
        For Kodik URLs we just return the URL itself — the Kodik player
        handles season/episode navigation internally.
        """
        if not url:
            return None
        if _KODIK_IFRAME_RE.search(url):
            if url.startswith("//"):
                url = "https:" + url
            return VideoInfo(player_url=url, source=self.name, title="")
        return None

    async def find_embed_in_page(self, page_url: str) -> Optional[str]:
        """Extract a Kodik iframe src from a pirate site page."""
        try:
            async with self._session.get(
                page_url, timeout=self._timeout,
                headers={"User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/124 Safari/537.36"
                )}
            ) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text(errors="replace")
        except Exception as e:
            logger.debug("Failed to fetch %s: %s", page_url, e)
            return None

        match = _KODIK_IFRAME_RE.search(html)
        if match:
            link = match.group(0)
            if link.startswith("//"):
                link = "https:" + link
            return link
        return None
