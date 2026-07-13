import html
import logging

from telegram import Update
from telegram.ext import ContextTypes

from services.searcher import Searcher
from utils.keyboards import search_results_keyboard
from utils.formatters import format_search_header
from utils.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

_limiter = RateLimiter(min_interval=1.5)
RESULTS_PER_PAGE = 5


async def ask_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Called when user presses 'Search' button."""
    query = update.callback_query
    await query.answer()
    context.user_data["awaiting_search"] = True
    await query.edit_message_text("🔍 Введите название фильма или сериала:")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles free-text input — performs search if awaiting_search is set."""
    if not context.user_data.get("awaiting_search"):
        return

    user_id = update.effective_user.id
    if not _limiter.is_allowed(user_id):
        await update.message.reply_text("⏳ Подождите секунду перед следующим поиском.")
        return

    context.user_data["awaiting_search"] = False
    search_term = update.message.text.strip()
    if not search_term:
        return

    status = await update.message.reply_text("🔍 Ищу...")

    searcher: Searcher = context.bot_data["searcher"]
    try:
        results = await searcher.search(search_term)
    except Exception as e:
        logger.error("Search error: %s", e)
        await status.edit_text("❌ Ошибка при поиске. Попробуйте позже.")
        return

    if not results:
        await status.edit_text(
            f"😔 По запросу <b>{html.escape(search_term)}</b> ничего не найдено.",
            parse_mode="HTML"
        )
        return

    context.user_data["search_results"] = results
    context.user_data["search_query"] = search_term
    context.user_data["search_page"] = 1

    header = format_search_header(search_term, len(results))
    kb = search_results_keyboard(results, page=1, per_page=RESULTS_PER_PAGE)
    await status.edit_text(header, parse_mode="HTML", reply_markup=kb)


async def handle_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles page_N callback data."""
    query = update.callback_query
    await query.answer()
    page = int(query.data.split("_")[1])
    context.user_data["search_page"] = page

    results = context.user_data.get("search_results", [])
    search_term = context.user_data.get("search_query", "")
    if not results:
        await query.edit_message_text("Результаты устарели. Выполните новый поиск.")
        return

    header = format_search_header(search_term, len(results))
    kb = search_results_keyboard(results, page=page, per_page=RESULTS_PER_PAGE)
    await query.edit_message_text(header, parse_mode="HTML", reply_markup=kb)
