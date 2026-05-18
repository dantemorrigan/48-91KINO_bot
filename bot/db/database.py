import os

import aiosqlite
from typing import Optional

# /data is the persistent mount on Amvera; falls back to local dir for dev
DB_PATH = os.path.join(os.environ.get("DATA_DIR", "."), "favorites.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_favorites (
                chat_id INTEGER,
                title TEXT,
                url TEXT,
                player_url TEXT,
                content_type TEXT DEFAULT 'movie',
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (chat_id, url)
            )
        """)
        await db.commit()


async def get_favorites(chat_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT title, url, player_url, content_type FROM user_favorites "
            "WHERE chat_id = ? ORDER BY added_at DESC",
            (chat_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def add_favorite(chat_id: int, title: str, url: str, player_url: str,
                       content_type: str = "movie") -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM user_favorites WHERE chat_id = ?", (chat_id,)
        )
        count = (await cursor.fetchone())[0]
        if count >= 30:
            return False
        await db.execute(
            "INSERT OR IGNORE INTO user_favorites (chat_id, title, url, player_url, content_type) "
            "VALUES (?, ?, ?, ?, ?)",
            (chat_id, title, url, player_url, content_type)
        )
        await db.commit()
        return True


async def remove_favorite(chat_id: int, url: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM user_favorites WHERE chat_id = ? AND url = ?",
            (chat_id, url)
        )
        await db.commit()


async def clear_favorites(chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM user_favorites WHERE chat_id = ?", (chat_id,))
        await db.commit()


async def is_favorite(chat_id: int, url: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM user_favorites WHERE chat_id = ? AND url = ?",
            (chat_id, url)
        )
        return await cursor.fetchone() is not None
