"""
kinopoisk.dev API wrapper.
Provides movie metadata: title, year, rating, poster, description, KP ID.

ARCHIVED: this bot is fully retired (see README). The Kinopoisk.dev API key
was retired for good after the security incident and is never supplied, so
this service is a permanent no-op stub — it makes no network calls and
always returns empty results.
"""
import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)

API_BASE = "https://api.kinopoisk.dev"


@dataclass
class MovieMeta:
    kp_id: int
    title: str
    title_orig: str
    year: Optional[int]
    rating_kp: Optional[float]
    rating_imdb: Optional[float]
    poster_url: Optional[str]
    description: Optional[str]
    content_type: str  # movie | series


class KinopoiskService:
    def __init__(self, api_key: str, session: aiohttp.ClientSession, timeout: int = 10):
        self._key = api_key
        self._session = session
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    @property
    def _headers(self) -> dict:
        return {"X-API-KEY": self._key, "Content-Type": "application/json"}

    async def search(self, query: str, limit: int = 10) -> list[MovieMeta]:
        if not self._key:
            return []
        params = {"query": query, "limit": limit}
        try:
            async with self._session.get(
                f"{API_BASE}/v1.4/movie/search",
                params=params, headers=self._headers, timeout=self._timeout
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except Exception as e:
            logger.warning("Kinopoisk search failed: %s", e)
            return []

        results = []
        for doc in data.get("docs", []):
            meta = self._parse_doc(doc)
            if meta:
                results.append(meta)
        return results

    async def get_by_id(self, kp_id: int) -> Optional[MovieMeta]:
        if not self._key:
            return None
        try:
            async with self._session.get(
                f"{API_BASE}/v1.4/movie/{kp_id}",
                headers=self._headers, timeout=self._timeout
            ) as resp:
                resp.raise_for_status()
                doc = await resp.json()
                return self._parse_doc(doc)
        except Exception as e:
            logger.warning("Kinopoisk get_by_id failed: %s", e)
            return None

    def _parse_doc(self, doc: dict) -> Optional[MovieMeta]:
        kp_id = doc.get("id")
        if not kp_id:
            return None
        title = doc.get("name") or doc.get("alternativeName") or ""
        if not title:
            return None

        rating = doc.get("rating") or {}
        poster = doc.get("poster") or {}
        doc_type = doc.get("type", "movie")
        content_type = "series" if doc_type in ("tv-series", "anime", "cartoon-series") else "movie"

        description = doc.get("description") or doc.get("shortDescription") or ""
        if len(description) > 900:
            description = description[:900] + "…"

        return MovieMeta(
            kp_id=kp_id,
            title=title,
            title_orig=doc.get("alternativeName") or "",
            year=doc.get("year"),
            rating_kp=rating.get("kp"),
            rating_imdb=rating.get("imdb"),
            poster_url=poster.get("url"),
            description=description or None,
            content_type=content_type,
        )
