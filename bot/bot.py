import json
import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import requests
from bs4 import BeautifulSoup
import hashlib

# Загрузка токена из файла конфигурации
with open('config.json', 'r') as file:
    config = json.load(file)
    TOKEN = config['TOKEN']

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# URL-адрес поиска для второго источника
SEARCH_URL_LORDSERIAL = 'https://lordserial.run/index.php?do=search'

# Глобальные переменные для хранения результатов поиска и избранного
search_results_cache = {}


# Подключение к базе данных SQLite
def get_db_connection():
    conn = sqlite3.connect('favorites.db')
    conn.row_factory = sqlite3.Row
    return conn


# Создание таблиц, если они не существуют
def create_tables():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_favorites (
            chat_id INTEGER,
            title TEXT,
            url TEXT,
            player_url TEXT,
            PRIMARY KEY (chat_id, title)
        )
    ''')
    conn.close()


create_tables()


# Функция для получения HTML-кода страницы
def get_page(url: str, params: dict = None) -> str:
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Проверка успешности запроса
        return response.text
    except requests.RequestException as e:
        print(f"Ошибка при получении страницы: {e}")
        return ""


# Функция для поиска фильмов на Goodfilms
def search_goodfilms(query):
    url = 'https://zhqpg.goodfilms.fun/index.php?do=search'
    payload = {
        'do': 'search',
        'subaction': 'search',
        'search_start': '0',
        'full_search': '0',
        'result_from': '1',
        'story': query
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    response = requests.post(url, data=payload, headers=headers)

    soup = BeautifulSoup(response.content, 'html.parser')

    results = []
    for item in soup.find_all('div', class_='poster has-overlay grid-item d-flex fd-column'):
        title = item.find('span', class_='poster__title').text.strip()
        link = item.find('a', class_='poster__link')['href']
        genres = item.find('div', class_='poster__subtitle').text.strip()
        ratings = item.find('div', class_='poster__ratings').text.strip()
        image = item.find('img')['src']

        results.append({
            'title': title,
            'link': 'https://zhqpg.goodfilms.fun' + link,
            'genres': genres,
            'ratings': ratings,
            'image': 'https://zhqpg.goodfilms.fun' + image
        })

    return results


# Функция для получения плеера фильма
def get_movie_player(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    video_tag = soup.find('video')
    if video_tag:
        video_src = video_tag['src']
        track = video_tag.find('track')['src'] if video_tag.find('track') else None
        return {'video_src': video_src, 'track': track}
    return None


# Функция для парсинга результатов поиска на LordSerial
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
    # Получаем результаты из первого источника
    results_goodfilms = search_goodfilms(search_term)

    # Получаем результаты из второго источника
    params_lordserial = {'do': 'search', 'subaction': 'search', 'story': search_term}
    search_content_lordserial = get_page(SEARCH_URL_LORDSERIAL, params=params_lordserial)
    results_lordserial = parse_search_results(search_content_lordserial)

    # Объединяем результаты
    combined_results = [(result['title'], result['link']) for result in results_goodfilms] + results_lordserial
    return combined_results


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


def get_unique_id(url):
    return hashlib.md5(url.encode()).hexdigest()[:10]


# Функция для создания клавиатуры на странице фильма
def build_movie_keyboard(movie_url, player_url, is_favorite=False):
    unique_id = get_unique_id(movie_url)
    keyboard = []

    if player_url:
        keyboard.append([InlineKeyboardButton("▶️ СМОТРЕТЬ", url=player_url)])
    else:
        keyboard.append([InlineKeyboardButton("❓ Не найден плеер", callback_data='none')])

    if is_favorite:
        keyboard.append([InlineKeyboardButton("✅ Уже в избранном", callback_data='none')])
    else:
        keyboard.append([InlineKeyboardButton("⭐ Добавить в избранное", callback_data=f"favorite_{unique_id}")])

    keyboard.append([InlineKeyboardButton("🏠 Главная", callback_data='home')])

    return InlineKeyboardMarkup(keyboard)


# Функция для получения избранного конкретного пользователя:
def get_user_favorites(chat_id):
    conn = get_db_connection()
    cursor = conn.execute('SELECT title, player_url FROM user_favorites WHERE chat_id = ?', (chat_id,))
    favorites = cursor.fetchall()
    conn.close()
    return {'favorites': [row['title'] for row in favorites],
            'links': {row['title']: row['player_url'] for row in favorites}}  # Используем player_url


# Функция для обработки команды /start
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


# Функция для обработки нажатия кнопки
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    chat_id = query.message.chat_id

    if data == 'search':
        await query.edit_message_text(
            text="🔍 Введите название фильма или сериала, который вы хотите найти:"
        )
        return

    if data == 'favorites':
        favorites = get_user_favorites(chat_id)
        if not favorites['favorites']:
            await query.edit_message_text(
                text="⚠️ В избранном пока ничего нет. Используйте поиск для добавления фильмов."
            )
        else:
            favorite_titles = '\n'.join(favorites['favorites'])
            await query.edit_message_text(
                text=f"📚 Ваше избранное:\n{favorite_titles}",
                reply_markup=build_favorites_keyboard()
            )
        return

    if data.startswith('movie_'):
        index = int(data.split('_')[1])
        results = search_results_cache.get('results', [])
        if 0 <= index < len(results):
            title, movie_url = results[index]
            if 'goodfilms' in movie_url:
                movie_page_content = get_page(movie_url)
                movie_info = extract_movie_info(movie_page_content)
                player_url = get_movie_player(movie_url).get('video_src')  # Используем новый метод

            else:
                movie_page_content = get_page(movie_url)
                movie_info = extract_movie_info(movie_page_content)
                player_url = extract_player_link(movie_page_content)

            conn = get_db_connection()
            cursor = conn.execute('SELECT 1 FROM user_favorites WHERE chat_id = ? AND url = ?', (chat_id, movie_url))
            is_favorite = cursor.fetchone() is not None
            conn.close()

            response_message = (
                f"<b>Название:</b> {movie_info['title']}\n"
                "──────────\n"
                f"<b>Описание:</b>\n<i>{movie_info['description']}</i>\n"
                "──────────\n"
            )

            await query.edit_message_text(
                text=response_message,
                parse_mode='HTML',
                reply_markup=build_movie_keyboard(movie_url, player_url, is_favorite)
            )
        return

    if data.startswith('favorite_'):
        unique_id = data.split('_')[1]
        movie_url = next((url for url, uid in search_results_cache['results'] if get_unique_id(url) == unique_id), None)

        if movie_url:
            conn = get_db_connection()
            conn.execute('INSERT OR IGNORE INTO user_favorites (chat_id, title, url, player_url) VALUES (?, ?, ?, ?)',
                         (chat_id, movie_url, movie_url, ''))
            conn.commit()
            conn.close()

            await query.edit_message_text(
                text="✅ Фильм добавлен в избранное!",
                reply_markup=build_favorites_keyboard()
            )
        return

    if data.startswith('prev_') or data.startswith('next_'):
        current_page = int(data.split('_')[1])
        search_term = search_results_cache.get('search_term', '')
        results = get_search_results(search_term)
        search_results_cache['results'] = results
        total_pages = (len(results) + 4) // 5
        reply_markup = build_keyboard(results, current_page, total_pages)
        await query.edit_message_text(
            text=f"🔍 Результаты поиска по запросу '{search_term}':",
            reply_markup=reply_markup
        )
        return

    if data == 'home':
        await start(update, context)
        return


# Функция для обработки текстовых сообщений (поиск)
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_term = update.message.text
    if search_term:
        search_results = get_search_results(search_term)
        search_results_cache['results'] = search_results
        search_results_cache['search_term'] = search_term
        total_pages = (len(search_results) + 4) // 5
        reply_markup = build_keyboard(search_results, 1, total_pages)
        await update.message.reply_text(
            text=f"🔍 Результаты поиска по запросу '{search_term}':",
            reply_markup=reply_markup
        )


# Запуск бота
if __name__ == '__main__':
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_handler(CallbackQueryHandler(button))

    application.run_polling()
