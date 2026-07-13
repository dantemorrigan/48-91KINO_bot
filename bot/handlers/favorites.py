import html

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from db.database import get_favorites, clear_favorites
from utils.keyboards import favorites_keyboard, is_safe_http_url


async def show_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.from_user.id
    favs = await get_favorites(chat_id)

    if not favs:
        await query.edit_message_text(
            "⭐ <b>Избранное пусто</b>\n\nДобавляйте фильмы и сериалы через поиск.",
            parse_mode="HTML",
            reply_markup=favorites_keyboard(),
        )
        return

    lines = ["⭐ <b>Ваше избранное:</b>\n"]
    for i, fav in enumerate(favs, 1):
        emoji = "📺" if fav.get("content_type") == "series" else "🎬"
        title = html.escape(fav["title"])
        player = fav.get("player_url", "")
        if player and is_safe_http_url(player):
            lines.append(f'{i}. {emoji} <a href="{html.escape(player, quote=True)}">{title}</a>')
        else:
            lines.append(f"{i}. {emoji} {title}")

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=favorites_keyboard(),
        disable_web_page_preview=True,
    )


async def handle_fav_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await clear_favorites(query.from_user.id)
    await query.edit_message_text(
        "🗑 Избранное очищено.",
        reply_markup=favorites_keyboard(),
    )
