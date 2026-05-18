import logging

from telegram import Update
from telegram.ext import ContextTypes

from ..services.searcher import Searcher
from ..services.kinopoisk import MovieMeta
from ..db.database import is_favorite, add_favorite
from ..utils.keyboards import movie_keyboard, series_keyboard
from ..utils.formatters import format_movie_card, format_no_video

logger = logging.getLogger(__name__)


async def show_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Called when user picks a movie from search results (pick_N callback)."""
    query = update.callback_query
    await query.answer()

    idx = int(query.data.split("_")[1])
    results: list[MovieMeta] = context.user_data.get("search_results", [])
    if not results or idx >= len(results):
        await query.edit_message_text("❌ Результаты поиска устарели. Попробуйте снова.")
        return

    meta = results[idx]
    context.user_data["current_meta"] = meta

    await query.edit_message_text("⏳ Загружаю информацию...")

    searcher: Searcher = context.bot_data["searcher"]
    try:
        video = await searcher.find_video(meta)
    except Exception as e:
        logger.error("find_video error: %s", e)
        video = None

    context.user_data["current_video"] = video

    chat_id = query.from_user.id
    fav = await is_favorite(chat_id, str(meta.kp_id))
    player_url = video.player_url if video else None

    card = format_movie_card(meta, video.source if video else "")
    if not video:
        card += "\n\n" + format_no_video()

    if meta.content_type == "series" and video and video.seasons:
        kb = series_keyboard(str(meta.kp_id), player_url, video.seasons, fav)
    else:
        kb = movie_keyboard(str(meta.kp_id), player_url, fav, meta.content_type == "series")

    # Send poster if available
    if meta.poster_url:
        try:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=meta.poster_url,
                caption=card,
                parse_mode="HTML",
                reply_markup=kb,
            )
            await query.message.delete()
            return
        except Exception:
            pass

    await query.edit_message_text(card, parse_mode="HTML", reply_markup=kb)


async def handle_fav_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles fav_add_<hash> callback."""
    query = update.callback_query
    await query.answer()

    meta: MovieMeta = context.user_data.get("current_meta")
    video = context.user_data.get("current_video")
    if not meta:
        await query.answer("Не удалось определить фильм.", show_alert=True)
        return

    player_url = video.player_url if video else ""
    chat_id = query.from_user.id
    added = await add_favorite(
        chat_id=chat_id,
        title=meta.title,
        url=str(meta.kp_id),
        player_url=player_url,
        content_type=meta.content_type,
    )

    if added:
        await query.answer("⭐ Добавлено в избранное!", show_alert=False)
    else:
        await query.answer("Избранное заполнено (макс. 30).", show_alert=True)
        return

    # Refresh keyboard
    fav = True
    if meta.content_type == "series" and video and video.seasons:
        kb = series_keyboard(str(meta.kp_id), player_url, video.seasons, fav)
    else:
        kb = movie_keyboard(str(meta.kp_id), player_url, fav, meta.content_type == "series")

    try:
        await query.edit_message_reply_markup(reply_markup=kb)
    except Exception:
        pass
