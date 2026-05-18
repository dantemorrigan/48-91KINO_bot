"""
HDRezka scraper source.
HDRezka is one of the most stable Russian-language pirate sites.
We use it for:
  - Search (returns structured results)
  - Extracting iframe embed URLs from movie/series pages
  - Series: extracting season/episode list from page HTML
"""
import logging
import re
from typing import Optional
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from .base import BaseSource, SearchResult, VideoInfo

logger = logging.getLogger(__name__)

BASE_URL = "https://rezka.ag"
SEARCH_URL = f"{BASE_URL}/search/"

_IFRAME_RE = re.compile(
    r'(https?:)?//(kodik\.(info|biz|cc)|anivod\.com|videocdn\.tv|'
    r'hdvb\.ru|collaps\.[a-z]+|[a-z0-9-]+\.[a-z]{2,6})/[^\s"\'<>]+'
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9",
}


class HDRezkaSource(BaseSource):
    name = "hdrezka"

    def __init__(self, session: aiohttp.ClientSession, timeout: int = 15):
        self._session = session
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def _get(self, url: str, **kwargs) -> Optional[str]:
        try:
            async with self._session.get(
                url, headers=HEADERS, timeout=self._timeout, **kwargs
            ) as resp:
                if resp.status != 200:
                    logger.debug("HDRezka %s returned %s", url, resp.status)
                    return None
                return await resp.text(errors="replace")
        except Exception as e:
            logger.warning("HDRezka fetch error for %s: %s", url, e)
            return None

    async def search(self, query: str) -> list[SearchResult]:
        html = await self._get(SEARCH_URL, params={"do": "search", "subaction": "search", "q": query})
        if not html:
            return []
        return self._parse_search(html)

    def _parse_search(self, html: str) -> list[SearchResult]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for item in soup.select(".b-content__inline_item"):
            link_tag = item.select_one(".b-content__inline_item-link a")
            if not link_tag:
                continue
            title = link_tag.get_text(strip=True)
            url = link_tag.get("href", "")
            if not url or not title:
                continue

            meta = item.select_one(".b-content__inline_item-link div")
            year = ""
            if meta:
                year_match = re.search(r"\b(19|20)\d{2}\b", meta.get_text())
                if year_match:
                    year = year_match.group(0)

            cover = item.select_one(".b-content__inline_item-cover")
            content_type = "series" if cover and "serial" in cover.get("class", []) else "movie"

            results.append(SearchResult(
                title=title, year=year, url=url,
                source=self.name, content_type=content_type
            ))
        return results[:10]

    async def get_video(self, url: str) -> Optional[VideoInfo]:
        html = await self._get(url)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        title = ""
        h1 = soup.select_one("h1")
        if h1:
            title = h1.get_text(strip=True)

        # Try to find any CDN iframe in the page
        iframe = soup.find("iframe")
        player_url = None
        if iframe and iframe.get("src"):
            src = iframe["src"]
            if src.startswith("//"):
                src = "https:" + src
            player_url = src
        else:
            # Search in raw HTML for known CDN patterns
            match = _IFRAME_RE.search(html)
            if match:
                player_url = match.group(0)
                if player_url.startswith("//"):
                    player_url = "https:" + player_url

        if not player_url:
            # HDRezka uses its own player via JS — try to find stream init data
            player_url = self._extract_hdrezka_player(html, url)

        if not player_url:
            return None

        seasons = self._extract_seasons(soup)
        return VideoInfo(
            player_url=player_url,
            source=self.name,
            title=title,
            seasons=seasons,
        )

    def _extract_hdrezka_player(self, html: str, page_url: str) -> Optional[str]:
        """
        HDRezka serves its own player. The page itself IS the player if opened directly.
        We return the page URL — when opened in browser it shows the built-in player.
        """
        if "initCDNMovies" in html or "initCDNSerialEvents" in html:
            return page_url
        return None

    def _extract_seasons(self, soup: BeautifulSoup) -> list[dict]:
        seasons = []
        season_tabs = soup.select(".b-simple_seasons-list .b-simple_seasons--tabs li")
        if not season_tabs:
            return seasons
        for tab in season_tabs:
            season_num = tab.get("data-tab_id") or tab.get_text(strip=True)
            try:
                season_num = int(season_num)
            except (ValueError, TypeError):
                continue
            seasons.append({"num": season_num, "episodes": []})
        return seasons
