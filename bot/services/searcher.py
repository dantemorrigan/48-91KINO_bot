"""
Unified searcher: combines KinopoiskService (metadata) with source adapters (video links).
Falls back gracefully if any source fails.
"""
import asyncio
import logging
from typing import Optional

import aiohttp

from .kinopoisk import KinopoiskService, MovieMeta
from sources.kodik import KodikSource
from sources.hdrezka import HDRezkaSource
from sources.base import VideoInfo

logger = logging.getLogger(__name__)


class Searcher:
    def __init__(
        self,
        kinopoisk: KinopoiskService,
        kodik: KodikSource,
        hdrezka: HDRezkaSource,
    ):
        self._kp = kinopoisk
        self._kodik = kodik
        self._hdrezka = hdrezka

    async def search(self, query: str) -> list[MovieMeta]:
        """Search via kinopoisk.dev — rich metadata, accurate matches."""
        return await self._kp.search(query, limit=10)

    async def find_video(self, meta: MovieMeta) -> Optional[VideoInfo]:
        """
        Try to find a playable video link for the given movie/series.
        Order of attempts:
          1. Kodik API (if token available)
          2. HDRezka scraper
        Returns the first successful result.
        """
        tasks = []

        if self._kodik._token:
            tasks.append(self._find_via_kodik(meta))

        tasks.append(self._find_via_hdrezka(meta))

        if not tasks:
            return None

        # Run all sources concurrently, return first success
        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                if result:
                    return result
            except Exception as e:
                logger.warning("Video source error: %s", e)

        return None

    async def _find_via_kodik(self, meta: MovieMeta) -> Optional[VideoInfo]:
        results = await self._kodik.search(meta.title)
        if not results:
            return None
        best = results[0]
        return await self._kodik.get_video(best.url)

    async def _find_via_hdrezka(self, meta: MovieMeta) -> Optional[VideoInfo]:
        query = meta.title
        if meta.year:
            query = f"{query} {meta.year}"
        results = await self._hdrezka.search(query)
        if not results:
            return None
        # Pick best match by content type
        for r in results:
            if r.content_type == meta.content_type:
                info = await self._hdrezka.get_video(r.url)
                if info:
                    info.title = info.title or meta.title
                    return info
        # Fallback: try first result regardless
        info = await self._hdrezka.get_video(results[0].url)
        if info:
            info.title = info.title or meta.title
        return info
