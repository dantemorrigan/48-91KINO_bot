import logging
import os

import aiohttp
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from config import load_config
from db.database import init_db
from services.kinopoisk import KinopoiskService
from services.searcher import Searcher
from sources.kodik import KodikSource
from sources.hdrezka import HDRezkaSource
from handlers.start import cmd_start
from handlers.search import ask_query, handle_text, handle_pagination
from handlers.movie import show_movie, handle_fav_add
from handlers.favorites import show_favorites, handle_fav_clear

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application):
    await init_db()
    session = aiohttp.ClientSession()
    application.bot_data["http_session"] = session

    cfg = application.bot_data["config"]
    kp = KinopoiskService(cfg.kinopoisk_api_key, session, timeout=cfg.request_timeout)
    kodik = KodikSource(cfg.kodik_token, session, timeout=cfg.request_timeout)
    hdrezka = HDRezkaSource(session, timeout=cfg.request_timeout)

    application.bot_data["searcher"] = Searcher(kp, kodik, hdrezka)
    logger.info("Bot initialized. Kodik token: %s", "YES" if cfg.kodik_token else "NO")


async def post_shutdown(application):
    session = application.bot_data.get("http_session")
    if session:
        await session.close()


def main():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    cfg = load_config(config_path)

    app = (
        Application.builder()
        .token(cfg.token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    app.bot_data["config"] = cfg

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))

    # Inline buttons
    app.add_handler(CallbackQueryHandler(cmd_start, pattern="^home$"))
    app.add_handler(CallbackQueryHandler(ask_query, pattern="^search$"))
    app.add_handler(CallbackQueryHandler(show_favorites, pattern="^favorites$"))
    app.add_handler(CallbackQueryHandler(handle_fav_clear, pattern="^fav_clear$"))
    app.add_handler(CallbackQueryHandler(show_movie, pattern=r"^pick_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_fav_add, pattern=r"^fav_add_.+$"))
    app.add_handler(CallbackQueryHandler(handle_pagination, pattern=r"^page_\d+$"))
    app.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.answer(), pattern="^noop$"))

    # Text messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Starting bot polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
