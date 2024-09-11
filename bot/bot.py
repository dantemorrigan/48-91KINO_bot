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

# URL-адрес поиска
SEARCH_URL_LORDSERIAL = 'https://lordserial.run/index.php?do=search'
SEARCH_URL_BEFILM1 = 'https://t1.befilm1.life/index.php?do=search'

# Глобальные переменные для хранения результатов поиска и избранного
search_results_cache = {}
favorite_movies_cache = {}  # Это можно удалить после интеграции с БД

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
def get_page(url, params=None):
    logger.info(f"Запрос на URL: {url} с параметрами: {params}")
    response = requests.get(url, params=params)
    response.raise_for_status()  # Проверяем на ошибки
    logger.info(f"Получен ответ: {response.text[:200]}")  # Логируем только часть ответа
    return response.text

# Функция для парсинга результатов поиска
def parse_search_results_lordserial(content):
    soup = BeautifulSoup(content, 'html.parser')
    results = []
    for item in soup.find_all('div', class_='th-item'):
        title = item.find('div', class_='th-title').get_text(strip=True)
        link = item.find('a', class_='th-in with-mask')['href']
        results.append((f"{title} (Источник 1)", link))
    return results

# Функция для парсинга результатов поиска с сайта befilm1
def parse_search_results_befilm1(content):
    soup = BeautifulSoup(content, 'html.parser')
    results = []
    for item in soup.find_all('div', class_='th-item'):
        title = item.find('div', class_='th-title').get_text(strip=True)
        link = item.find('a', class_='th-in with-mask')['href']
        results.append((f"{title} (Источник 2)", link))
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
    logger.info(
        "Страница фильма для проверки плеера:\n" + movie_page_content[:1000])  # Логируем начало страницы для проверки

    # Попробуем сначала найти iframe
    iframe = soup.find('iframe')
    if iframe and 'src' in iframe.attrs:
        logger.info("Найден iframe: " + iframe['src'])
        return iframe['src']

    # Попробуем найти div с классом 'player-container'
    player_div = soup.find('div', class_='player-container')
    if player_div:
        player_link = player_div.find('a')
        if player_link and 'href' in player_link.attrs:
            logger.info("Найден player_link: " + player_link['href'])
            return player_link['href']

    # Если ничего не найдено, вернем None
    logger.info("Плеер не найден")
    return None


# Функция для получения результатов поиска
logging.basicConfig(level=logging.ERROR)

def get_search_results(search_term):
    try:
        # Определите параметры для первого источника
        params_lordserial = {'do': 'search', 'subaction': 'search', 'story': search_term}
        # Определите параметры для второго источника
        params_befilm1 = {'story': search_term}

        # Получите результаты поиска для первого источника
        search_content_lordserial = get_page(SEARCH_URL_LORDSERIAL, params=params_lordserial)
        results_lordserial = parse_search_results_lordserial(search_content_lordserial)

        # Получите результаты поиска для второго источника
        search_content_befilm1 = get_page(SEARCH_URL_BEFILM1, params=params_befilm1)
        results_befilm1 = parse_search_results_befilm1(search_content_befilm1)

        # Объедините результаты и верните
        return results_lordserial + results_befilm1

    except Exception as e:
        logging.error(f"Ошибка при выполнении поиска: {e}")
        return []

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
def build_movie_keyboard(movie_url, is_favorite=False):
    unique_id = get_unique_id(movie_url)
    keyboard = []

    if is_favorite:
        keyboard.append([InlineKeyboardButton("✅ Уже в избранном", callback_data='none')])
    else:
        keyboard.append([InlineKeyboardButton("⭐ Добавить в избранное", callback_data=f"favorite_{unique_id}")])

    # Добавление кнопки "СМОТРЕТЬ ФИЛЬМ" если ссылка на плеер есть
    if movie_url:
        keyboard.append([InlineKeyboardButton("▶️ Смотреть фильм", url=movie_url)])

    keyboard.append([InlineKeyboardButton("🏠 Главная", callback_data='home')])

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

# Функция для получения избранного конкретного пользователя:
def get_user_favorites(chat_id):
    conn = get_db_connection()
    cursor = conn.execute('SELECT title, url, player_url FROM user_favorites WHERE chat_id = ?', (chat_id,))
    favorites = cursor.fetchall()
    conn.close()
    return {'favorites': [row['title'] for row in favorites], 'links': {row['title']: row['player_url'] for row in favorites}}  # Используем player_url

# Обновленная функция для обработки нажатия кнопки
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    logger.info(f'Нажата кнопка с данными: {data}')

    # Обработка кнопки "Поиск"
    if data == 'search':
        await query.edit_message_text(text="Введите название фильма или сериала для поиска:")

    # Обновляем вывод избранного
    elif data == 'favorites':
        chat_id = update.callback_query.message.chat_id
        user_favorites = get_user_favorites(chat_id)

        if not user_favorites['favorites']:
            await query.edit_message_text(text="Избранное пусто. Нажмите 'Главная' для возврата.")
        else:
            favorites_text = "\n".join([f"{idx + 1}. {title}" for idx, title in enumerate(user_favorites['favorites'])])
            reply_markup = build_favorites_keyboard()
            await query.edit_message_text(
                text=f"Ваши избранные фильмы:\n{favorites_text}",
                reply_markup=reply_markup
            )

    # Обработка кнопок страницы фильма
    elif data.startswith('movie_'):
        index = int(data.split('_')[1])
        search_results = search_results_cache.get('results', [])
        movie_url = search_results[index][1]
        movie_page_content = get_page(movie_url)
        movie_info = extract_movie_info(movie_page_content)
        player_link = extract_player_link(movie_page_content)

        if player_link:
            keyboard = build_movie_keyboard(player_link, is_favorite=False)
            await query.edit_message_text(
                text=f"<b>{movie_info['title']}</b>\n\n{movie_info['description']}",
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        else:
            await query.edit_message_text(
                text=f"<b>{movie_info['title']}</b>\n\n{movie_info['description']}\n\n🛑 Ссылка на плеер не найдена.",
                parse_mode='HTML'
            )

    # Обработка кнопок "Добавить в избранное" и "Избранное"
    elif data.startswith('favorite_'):
        unique_id = data.split('_')[1]
        chat_id = update.callback_query.message.chat_id

        # Найти URL для добавления в избранное
        for title, url in search_results_cache.get('results', []):
            if get_unique_id(url) == unique_id:
                player_url = extract_player_link(get_page(url))
                if player_url:
                    conn = get_db_connection()
                    conn.execute('INSERT OR REPLACE INTO user_favorites (chat_id, title, url, player_url) VALUES (?, ?, ?, ?)',
                                 (chat_id, title, url, player_url))
                    conn.commit()
                    conn.close()
                    await query.edit_message_text(text="Фильм добавлен в избранное.", parse_mode='HTML')
                else:
                    await query.edit_message_text(text="Не удалось найти ссылку на плеер.", parse_mode='HTML')
                break

    elif data == 'home':
        await start(update, context)

    # Обработка кнопок навигации
    elif data.startswith('prev_') or data.startswith('next_'):
        current_page = int(data.split('_')[1])
        search_term = search_results_cache.get('search_term', '')
        search_results = get_search_results(search_term)
        search_results_cache['results'] = search_results
        total_pages = (len(search_results) + 4) // 5
        reply_markup = build_keyboard(search_results, current_page, total_pages)
        await query.edit_message_text(text="Результаты поиска:", reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.message.chat_id

    if text:
        search_results = get_search_results(text)
        search_results_cache['results'] = search_results
        search_results_cache['search_term'] = text

        total_pages = (len(search_results) + 4) // 5
        reply_markup = build_keyboard(search_results, 1, total_pages)
        await update.message.reply_text(text="Результаты поиска:", reply_markup=reply_markup)

def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button))

    application.run_polling()

if __name__ == '__main__':
    main()
