from ..services.kinopoisk import MovieMeta


def format_movie_card(meta: MovieMeta, source_name: str = "") -> str:
    lines = [f"<b>{meta.title}</b>"]
    if meta.title_orig and meta.title_orig != meta.title:
        lines.append(f"<i>{meta.title_orig}</i>")

    lines.append("──────────")

    info_parts = []
    if meta.year:
        info_parts.append(f"📅 {meta.year}")
    if meta.content_type == "series":
        info_parts.append("📺 Сериал")
    else:
        info_parts.append("🎬 Фильм")
    if info_parts:
        lines.append("  ".join(info_parts))

    ratings = []
    if meta.rating_kp and meta.rating_kp > 0:
        ratings.append(f"⭐ КП: <b>{meta.rating_kp:.1f}</b>")
    if meta.rating_imdb and meta.rating_imdb > 0:
        ratings.append(f"🎞 IMDB: <b>{meta.rating_imdb:.1f}</b>")
    if ratings:
        lines.append("  ".join(ratings))

    if meta.description:
        lines.append("──────────")
        lines.append(f"<i>{meta.description}</i>")

    if source_name:
        lines.append(f"\n<i>Источник: {source_name}</i>")

    return "\n".join(lines)


def format_no_video() -> str:
    return (
        "😔 <b>Видео не найдено</b>\n\n"
        "Фильм есть в базе, но ни один источник не вернул ссылку на видео.\n"
        "Попробуйте позже или поищите другое название."
    )


def format_search_header(query: str, count: int) -> str:
    if count == 0:
        return f"🔍 По запросу <b>{query}</b> ничего не найдено.\nПопробуйте другое название."
    return f"🔍 По запросу <b>{query}</b> найдено {count} результатов:"
