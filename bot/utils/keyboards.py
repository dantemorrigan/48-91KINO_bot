from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import Config


def is_safe_http_url(url: str | None) -> bool:
    """Only allow http(s) links to be rendered as clickable buttons/anchors."""
    return bool(url) and url.lower().startswith(("http://", "https://"))


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Поиск фильма / сериала", callback_data="search")],
        [InlineKeyboardButton("⭐ Избранное", callback_data="favorites")],
        [InlineKeyboardButton("👾 GitHub", url="https://github.com/dantemorrigan/48-91KINO_bot"),
         InlineKeyboardButton("💰 Поддержать", url="https://boosty.to/svdo/donate")],
    ])


def search_results_keyboard(results: list, page: int, per_page: int) -> InlineKeyboardMarkup:
    total = len(results)
    total_pages = max(1, (total + per_page - 1) // per_page)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = results[start:end]

    rows = []
    for i, meta in enumerate(page_items):
        idx = start + i
        label = meta.title
        if meta.year:
            label += f" ({meta.year})"
        emoji = "📺" if meta.content_type == "series" else "🎬"
        rows.append([InlineKeyboardButton(f"{emoji} {label}", callback_data=f"pick_{idx}")])

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"page_{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"page_{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton("🏠 Главная", callback_data="home")])
    return InlineKeyboardMarkup(rows)


def movie_keyboard(movie_url: str, player_url: str | None,
                   is_fav: bool, is_series: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if is_safe_http_url(player_url):
        label = "▶️ СМОТРЕТЬ" if not is_series else "▶️ СМОТРЕТЬ (плеер)"
        rows.append([InlineKeyboardButton(label, url=player_url)])
    else:
        rows.append([InlineKeyboardButton("❌ Видео не найдено", callback_data="noop")])

    fav_label = "✅ В избранном" if is_fav else "⭐ В избранное"
    fav_data = "noop" if is_fav else f"fav_add_{_encode(movie_url)}"
    rows.append([InlineKeyboardButton(fav_label, callback_data=fav_data)])
    rows.append([InlineKeyboardButton("🏠 Главная", callback_data="home")])
    return InlineKeyboardMarkup(rows)


def series_keyboard(movie_url: str, player_url: str | None,
                    seasons: list[dict], is_fav: bool) -> InlineKeyboardMarkup:
    rows = []
    if is_safe_http_url(player_url):
        rows.append([InlineKeyboardButton("▶️ СМОТРЕТЬ (все серии)", url=player_url)])

    if seasons:
        season_btns = [
            InlineKeyboardButton(
                f"Сезон {s['num']}",
                callback_data=f"season_{_encode(movie_url)}_{s['num']}"
            )
            for s in seasons[:8]
        ]
        # 2 per row
        for i in range(0, len(season_btns), 2):
            rows.append(season_btns[i:i + 2])

    fav_label = "✅ В избранном" if is_fav else "⭐ В избранное"
    fav_data = "noop" if is_fav else f"fav_add_{_encode(movie_url)}"
    rows.append([InlineKeyboardButton(fav_label, callback_data=fav_data)])
    rows.append([InlineKeyboardButton("🏠 Главная", callback_data="home")])
    return InlineKeyboardMarkup(rows)


def favorites_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 Очистить всё", callback_data="fav_clear")],
        [InlineKeyboardButton("🏠 Главная", callback_data="home")],
    ])


def _encode(url: str) -> str:
    import hashlib
    return hashlib.md5(url.encode()).hexdigest()[:12]
