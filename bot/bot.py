import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import requests
from bs4 import BeautifulSoup

# Загрузка токена из файла конфигурации
with open('config.json', 'r') as file:
    config = json.load(file)
    TOKEN = config['TOKEN']

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# URL-адрес поиска
SEARCH_URL_LORDSERIAL = 'https://lordserial.run/index.php?do=search'

# Глобальные переменные для хранения результатов поиска и избранного
search_results_cache = {}
favorite_movies_cache = {}

# Функция для получения HTML-кода страницы
def get_page(url, params=None):
    response = requests.get(url, params=params)
    response.raise_for_status()  # Проверяем на ошибки
    return response.text

# Функция для парсинга результатов поиска
def parse_search_results(content):
    soup = BeautifulSoup(content, 'html.parser')
    results = []
    for item in soup.find_all('div', class_='th-item'):
        title = item.find('div', class_='th-title').get_text(strip=True)
        link = item.find('a', class_='th-in with-mask')['href']
        results.append((f"{title} (Источник 1)", link))
    return results

# Функция для извлечения информации о фильме
def extract_movie_info(movie_page_content):
    soup = BeautifulSoup(movie_page_content, 'html.parser')
    title = soup.find('h1').get_text(strip=True)
    description = soup.find('div', class_='fdesc').get_text(strip=True)
    return {
        'title': title,
        'description': description,
    }

# Функция для извлечения ссылки на плеер
def extract_player_link(movie_page_content):
    soup = BeautifulSoup(movie_page_content, 'html.parser')
    iframe = soup.find('iframe')
    if iframe:
        return iframe['src']
    player_div = soup.find('div', class_='player-container')
    if player_div:
        player_link = player_div.find('a')
        if player_link and 'href' in player_link.attrs:
            return player_link['href']
    return None

# Функция для получения результатов поиска
def get_search_results(search_term):
    params_lordserial = {'do': 'search', 'subaction': 'search', 'story': search_term}
    search_content_lordserial = get_page(SEARCH_URL_LORDSERIAL, params=params_lordserial)
    results_lordserial = parse_search_results(search_content_lordserial)
    return results_lordserial

# Функция для создания клавиатуры с кнопками
def build_keyboard(results, current_page, total_pages):
    keyboard = []
    start_index = (current_page - 1) * 5
    end_index = start_index + 5
    paginated_results = results[start_index:end_index]

    for idx, (title, _) in enumerate(paginated_results):
        keyboard.append([InlineKeyboardButton(title, callback_data=f"movie_{start_index + idx}")])

    if current_page > 1:
        keyboard.append([InlineKeyboardButton("⬅️ Предыдущая", callback_data=f'prev_{current_page - 1}')])
    if current_page < total_pages:
        keyboard.append([InlineKeyboardButton("Следующая ➡️", callback_data=f'next_{current_page + 1}')])

    return InlineKeyboardMarkup(keyboard)

# Функция для создания клавиатуры с кнопками на странице избранного
def build_favorites_keyboard():
    keyboard = [
        [InlineKeyboardButton("🏠 Главная", callback_data='home')]
    ]
    return InlineKeyboardMarkup(keyboard)

# Функция для создания клавиатуры на странице фильма
def build_movie_keyboard(movie_url):
    keyboard = [
        [InlineKeyboardButton("⭐ Добавить в избранное", callback_data=f"favorite_{movie_url}")],
        [InlineKeyboardButton("🏠 Главная", callback_data='home')]
    ]
    return InlineKeyboardMarkup(keyboard)

# Обновленная функция для обработки команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info('Пользователь нажал /start')
    keyboard = [
        [InlineKeyboardButton("🔍 Поиск", callback_data='search')],
        [InlineKeyboardButton("⭐ Избранное", callback_data='favorites')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_message = (
        "🎬 Добро пожаловать в бота для поиска фильмов и сериалов от канала <b>48/91</b> (https://t.me/tommorow4891)! 🎬\n\n"
        "Нажмите 'Поиск' для начала."
    )

    # Проверяем, содержит ли обновление сообщение
    if update.message:
        chat_id = update.message.chat_id
    else:
        chat_id = update.callback_query.message.chat_id

    await context.bot.send_message(
        chat_id=chat_id,
        text=welcome_message,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
# Обновленная функция для обработки нажатия кнопки
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    logger.info(f'Нажата кнопка с данными: {data}')

    # Обработка кнопки "Поиск"
    if data == 'search':
        await query.edit_message_text(text="Введите название фильма или сериала для поиска:")

        # Обработка кнопки "Избранное"
    elif data == 'favorites':
        favorites = favorite_movies_cache.get('favorites', [])
        if not favorites:
            await query.edit_message_text('Избранные фильмы пусты.', reply_markup=build_favorites_keyboard())
        else:
            favorites_message = '\n'.join(
                [f"{idx + 1}. <a href='{favorite_movies_cache['links'][title]}'>{title}</a>" for idx, title in
                 enumerate(favorites)])
            await query.edit_message_text(f'Ваши избранные фильмы:\n{favorites_message}', parse_mode='HTML',
                                          reply_markup=build_favorites_keyboard())

    # Обработка выбора фильма
    elif data.startswith('movie_'):
        index = int(data.split('_')[1])
        results = search_results_cache.get('results', [])
        if 0 <= index < len(results):
            title, movie_url = results[index]
            movie_page_content = get_page(movie_url)
            movie_info = extract_movie_info(movie_page_content)
            player_url = extract_player_link(movie_page_content)

            response_message = (
                f"<b>Название:</b> {movie_info['title']}\n"
                "──────────\n"
                f"<b>Описание:</b>\n<i>{movie_info['description']}</i>\n"
                "──────────\n"
            )

            if player_url:
                response_message += f"<b><a href='{player_url}'>СМОТРЕТЬ ФИЛЬМ ЗДЕСЬ</a></b>"
            else:
                response_message += "Не удалось найти плеер для этого фильма."

            reply_markup = build_movie_keyboard(movie_url)
            await query.edit_message_text(response_message, parse_mode='HTML', reply_markup=reply_markup)
        else:
            await query.edit_message_text("Некорректный выбор фильма.", reply_markup=build_favorites_keyboard())

    # Обработка перехода на следующую страницу
    elif data.startswith('next_'):
        page = int(data.split('_')[1])
        total_results = search_results_cache['total_results']
        total_pages = (total_results // 5) + (1 if total_results % 5 > 0 else 0)

        results = search_results_cache.get('results', [])
        reply_markup = build_keyboard(results, page, total_pages)
        await query.edit_message_text('Результаты поиска:', reply_markup=reply_markup)

    # Обработка перехода на предыдущую страницу
    elif data.startswith('prev_'):
        page = int(data.split('_')[1])
        total_results = search_results_cache['total_results']
        total_pages = (total_results // 5) + (1 if total_results % 5 > 0 else 0)

        results = search_results_cache.get('results', [])
        reply_markup = build_keyboard(results, page, total_pages)
        await query.edit_message_text('Результаты поиска:', reply_markup=reply_markup)

    # Обработка добавления в избранное
    elif data.startswith('favorite_'):
        movie_url = data.split('_')[1]
        movie_info = extract_movie_info(get_page(movie_url))
        favorites = favorite_movies_cache.get('favorites', [])
        links = favorite_movies_cache.get('links', {})
        if movie_info['title'] not in favorites:
            favorites.append(movie_info['title'])
            links[movie_info['title']] = movie_url
            favorite_movies_cache['favorites'] = favorites
            favorite_movies_cache['links'] = links
            await query.edit_message_text(f"{movie_info['title']} добавлен в избранное.", reply_markup=build_favorites_keyboard())
        else:
            await query.edit_message_text(f"{movie_info['title']} уже в избранном.", reply_markup=build_favorites_keyboard())

    # Обработка кнопки "Главная"
    elif data == 'home':
        await start(update, context)


# Функция для обработки сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_term = update.message.text
    logger.info(f'Пользователь запросил поиск: {search_term}')

    # Отправляем сообщение с индикатором поиска
    search_message = await update.message.reply_text('🔍 Поиск…')

    # Получаем результаты поиска с сайта LordSerial
    search_results = get_search_results(search_term)
    search_results_cache['results'] = search_results  # Сохраняем результаты поиска в кэш
    search_results_cache['search_term'] = search_term  # Сохраняем запрос
    search_results_cache['total_results'] = len(search_results)  # Сохраняем общее количество результатов

    logger.info(f'Найдено {len(search_results)} результатов поиска')

    if not search_results:
        await search_message.edit_text('Ничего не найдено. Попробуйте другой запрос.')
    else:
        total_pages = (len(search_results) // 5) + (1 if len(search_results) % 5 > 0 else 0)
        reply_markup = build_keyboard(search_results, 1, total_pages)  # Начальная страница
        await search_message.edit_text('Результаты поиска:', reply_markup=reply_markup)

# Основная функция
def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info('Бот запущен')
    application.run_polling()

if __name__ == '__main__':
    main()
