import json
import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import requests
from bs4 import BeautifulSoup
import hashlib

# Функция для получения данных с Кинопоиска
def get_kinopoisk_data(search_term):
    headers = {
        'X-API-KEY': '***KINOPOISK_KEY_REMOVED***',
        'Content-Type': 'application/json',
    }

    response = requests.get(
        f'https://api.kinopoisk.dev/v1.3/movie?name={search_term}&limit=1',
        headers=headers
    )

    if response.status_code == 200:
        data = response.json()
        if data and 'docs' in data:
            movie_info = data['docs'][0]
            return {
                'title': movie_info.get('name', 'Название отсутствует'),
                'rating': movie_info.get('rating', {}).get('kp', 'Нет рейтинга'),
                'poster_url': movie_info.get('poster', {}).get('url', '')
            }
    return None

# Загрузка токена из файла конфигурации
with open('config.json', 'r', encoding='utf-8') as file:
    config = json.load(file)
    TOKEN = config['TOKEN']

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# URL-адреса поиска
SEARCH_URL_LORDSERIAL = 'https://lordserial.run/index.php?do=search'
SEARCH_URL_GOODFILMS = 'https://zhqpg.goodfilms.fun/index.php?do=search'

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
def get_page(url, params=None):
    response = requests.get(url, params=params)
    response.raise_for_status()  # Проверяем на ошибки
    # Выводим первые 1000 символов HTML-кода для отладки
    logger.debug(f'HTML код страницы: {response.text[:1000]}')
    return response.text

# Функция для получения результатов поиска с сайта lordserial
def get_search_results_lordserial(search_term):
    params_lordserial = {'do': 'search', 'subaction': 'search', 'story': search_term}
    search_content_lordserial = get_page(SEARCH_URL_LORDSERIAL, params=params_lordserial)
    return parse_search_results_lordserial(search_content_lordserial)

# Функция для парсинга результатов поиска с сайта lordserial
def parse_search_results_lordserial(content):
    soup = BeautifulSoup(content, 'html.parser')
    results = []
    for item in soup.find_all('div', class_='th-item'):
        title = item.find('div', class_='th-title').get_text(strip=True)
        link = item.find('a', class_='th-in with-mask')['href']
        results.append((f"{title} (Источник 1)", link))
    return results

# Функция для получения результатов поиска с сайта goodfilms
def get_search_results_goodfilms(search_term):
    params_goodfilms = {
        'do': 'search',
        'subaction': 'search',
        'story': search_term,
        'result_from': 1
    }
    search_content_goodfilms = requests.post(SEARCH_URL_GOODFILMS, data=params_goodfilms).text
    return parse_search_results_goodfilms(search_content_goodfilms)

# Функция для парсинга результатов поиска с сайта goodfilms
def parse_search_results_goodfilms(content):
    soup = BeautifulSoup(content, 'html.parser')
    results = []
    for item in soup.find_all('div', class_='poster'):
        title = item.find('span', class_='poster__title').get_text(strip=True)
        link = item.find('a', class_='poster__link')['href']
        results.append((f"{title} (Источник 2)", link))
    return results

# Функция для получения результатов поиска из двух источников
def get_search_results(search_term):
    results_lordserial = get_search_results_lordserial(search_term)
    results_goodfilms = get_search_results_goodfilms(search_term)
    return results_lordserial + results_goodfilms

# Функция для извлечения информации о фильме
def extract_movie_info(movie_page_content, source):
    soup = BeautifulSoup(movie_page_content, 'html.parser')
    title = soup.find('h1')

    if source == 'goodfilms':
        description_div = soup.find('div', class_='pmovie__descr')
        description = description_div.find('div', class_='pmovie__text full-text clearfix') if description_div else None
        description_text = description.get_text(strip=True) if description else 'Описание отсутствует'
    else:
        description_div = soup.find('div', class_='fdesc')
        description_text = description_div.get_text(strip=True) if description_div else 'Описание отсутствует'

    title_text = title.get_text(strip=True) if title else 'Неизвестно'

    return {
        'title': title_text,
        'description': description_text,
    }

# Функция для извлечения ссылки на плеер
def extract_player_link(movie_page_content):
    soup = BeautifulSoup(movie_page_content, 'html.parser')
    iframe = soup.find('iframe')
    if iframe:
        src = iframe['src']
        if src.startswith('//'):
            src = 'https:' + src
        return src

    player_div = soup.find('div', class_='player-container')
    if player_div:
        player_link = player_div.find('a')
        if player_link and 'href' in player_link.attrs:
            href = player_link['href']
            if href.startswith('//'):
                href = 'https:' + href
            return href

    return None

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
        [InlineKeyboardButton("🏠 Главная", callback_data='home')],
        [InlineKeyboardButton("🗑 Очистить избранное", callback_data='clear_favorites')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_unique_id(url):
    return hashlib.md5(url.encode()).hexdigest()[:10]

# Функция для создания клавиатуры на странице фильма
def build_movie_keyboard(movie_url, player_url, is_favorite=False):
    unique_id = get_unique_id(movie_url)
    keyboard = []

    if player_url:
        logger.debug(f'Player URL: {player_url}')
        keyboard.append([InlineKeyboardButton("▶️ СМОТРЕТЬ", url=player_url)])
    else:
        keyboard.append([InlineKeyboardButton("❓ Не найден плеер", callback_data='none')])

    if is_favorite:
        keyboard.append([InlineKeyboardButton("✅ Уже в избранном", callback_data='none')])
    else:
        keyboard.append([InlineKeyboardButton("⭐ Добавить в избранное", callback_data=f"favorite_{unique_id}")])

    keyboard.append([InlineKeyboardButton("🏠 Главная", callback_data='home')])

    return InlineKeyboardMarkup(keyboard)

# Функция для получения избранного конкретного пользователя
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

    # Логирование chat_id и типа обновления
    if update.message:
        chat_id = update.message.chat_id
        logger.info(f'Обновление типа: message, chat_id: {chat_id}')
    elif update.callback_query:
        chat_id = update.callback_query.message.chat_id
        logger.info(f'Обновление типа: callback_query, chat_id: {chat_id}')

    # Клавиатура
    keyboard = [
        [InlineKeyboardButton("🔍 Поиск", callback_data='search')],
        [InlineKeyboardButton("⭐ Избранное", callback_data='favorites')],
        [InlineKeyboardButton("👾 Исходный код бота на Github", url='https://github.com/dantemorrigan/48-91KINO_bot')],
        [InlineKeyboardButton("💰 Поддержать проект", url='https://boosty.to/svdo/donate')]  # Добавили кнопку
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Сообщение с жирным текстом-ссылкой
    welcome_message = (
        "🎬 Добро пожаловать в бота для поиска фильмов и сериалов от канала "
        '<a href="https://t.me/tommorow4891"><b>48/91</b></a>! 🎬\n\n'
        "Нажмите 'Поиск' для начала."
    )

    # Отправляем сообщение
    await context.bot.send_message(
        chat_id=chat_id,
        text=welcome_message,
        reply_markup=reply_markup,
        parse_mode='HTML'  # Включаем HTML для работы ссылок и форматирования
    )

# Обновленный код для обработки нажатий на кнопку фильма
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    logger.info(f'Нажата кнопка с данными: {data}')

    if data == 'search':
        await query.edit_message_text(text="Введите название фильма или сериала для поиска:")

    elif data == 'favorites':
        chat_id = update.callback_query.message.chat_id
        user_favorites = get_user_favorites(chat_id)

        if not user_favorites['favorites']:
            await query.edit_message_text('В избранном пусто.', reply_markup=build_favorites_keyboard())
        else:
            favorites_message = '\n'.join([f"{idx + 1}. <a href='{user_favorites['links'][title]}'>{title}</a>"
                                           for idx, title in enumerate(user_favorites['favorites'])])
            await query.edit_message_text(f'Ваше избранное:\n{favorites_message}', parse_mode='HTML',
                                          reply_markup=build_favorites_keyboard())

    elif data == 'clear_favorites':
        chat_id = update.callback_query.message.chat_id
        conn = get_db_connection()
        conn.execute('DELETE FROM user_favorites WHERE chat_id = ?', (chat_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text("Избранное очищено.", reply_markup=build_favorites_keyboard())

    elif data.startswith('movie_'):
        index = int(data.split('_')[1])
        results = search_results_cache.get('results', [])
        if 0 <= index < len(results):
            title, movie_url = results[index]
            # Определяем источник для парсинга
            source = 'goodfilms' if 'Источник 2' in title else 'lordserial'
            movie_page_content = get_page(movie_url)
            movie_info = extract_movie_info(movie_page_content, source)
            player_url = extract_player_link(movie_page_content)

            # Получение данных с Кинопоиска
            kinopoisk_data = get_kinopoisk_data(title.split(' (')[0])
            kinopoisk_info = ""
            if kinopoisk_data:
                kinopoisk_info = (f"<b>🔥 Рейтинг КП:</b> {kinopoisk_data['rating']}\n"
                                  f"<b>🎨 Обложка:</b> <a href='{kinopoisk_data['poster_url']}'>Посмотреть</a>")

            chat_id = update.callback_query.message.chat_id
            conn = get_db_connection()
            cursor = conn.execute('SELECT 1 FROM user_favorites WHERE chat_id = ? AND url = ?', (chat_id, movie_url))
            is_favorite = cursor.fetchone() is not None
            conn.close()

            response_message = (
                f"<b>Название:</b> {movie_info['title']}\n"
                "──────────\n"
                f"<b>Описание:</b>\n<i>{movie_info['description']}</i>\n"
                "──────────\n"
                f"{kinopoisk_info}"
            )

            await query.edit_message_text(
                text=response_message,
                parse_mode='HTML',
                reply_markup=build_movie_keyboard(movie_url, player_url, is_favorite)
            )

    elif data.startswith('favorite_'):
        unique_id = data.split('_')[1]
        movie_url = search_results_cache.get('url_map', {}).get(unique_id, '')
        chat_id = update.callback_query.message.chat_id

        if movie_url:
            movie_page_content = get_page(movie_url)
            player_url = extract_player_link(movie_page_content)

            if player_url:
                movie_info = extract_movie_info(movie_page_content, 'goodfilms')

                conn = get_db_connection()
                cursor = conn.execute('SELECT COUNT(*) FROM user_favorites WHERE chat_id = ?', (chat_id,))
                favorite_count = cursor.fetchone()[0]

                if favorite_count < 30:
                    conn.execute('''INSERT OR IGNORE INTO user_favorites (chat_id, title, url, player_url)
                                    VALUES (?, ?, ?, ?)''', (chat_id, movie_info['title'], movie_url, player_url))
                    conn.commit()
                    await query.answer("Фильм добавлен в избранное.", show_alert=True)
                else:
                    await query.answer("Избранное уже заполнено. Максимум 30 элементов.", show_alert=True)

                conn.close()
                await query.edit_message_reply_markup(reply_markup=build_movie_keyboard(movie_url, player_url, True))
            else:
                await query.answer("Произошла ошибка. Попробуйте снова.", show_alert=True)

    elif data == 'home':
        await start(update, context)

    elif data.startswith('next_') or data.startswith('prev_'):
        current_page = int(data.split('_')[1])
        results = search_results_cache.get('results', [])
        total_pages = search_results_cache.get('total_pages', 1)
        await query.edit_message_reply_markup(reply_markup=build_keyboard(results, current_page, total_pages))

# Функция для обработки текста от пользователя (поиск)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_term = update.message.text
    chat_id = update.message.chat_id



    # Отправляем сообщение с "Идет поиск... 🔍"
    search_message = await context.bot.send_message(chat_id=chat_id, text="Идет поиск... 🔍")

    # Выполняем поиск
    results = get_search_results(search_term)
    search_results_cache['results'] = results
    search_results_cache['url_map'] = {get_unique_id(url): url for _, url in results}

    total_pages = (len(results) + 4) // 5
    search_results_cache['total_pages'] = total_pages

    if not results:
        # Обновляем сообщение на "Результатов не найдено", если ничего не найдено
        await context.bot.edit_message_text(chat_id=chat_id, message_id=search_message.message_id,
                                            text="Результатов не найдено.")
    else:
        # Обновляем сообщение с результатами поиска
        await context.bot.edit_message_text(chat_id=chat_id, message_id=search_message.message_id,
                                            text="Результаты поиска:",
                                            reply_markup=build_keyboard(results, current_page=1, total_pages=total_pages))

# Функция для обработки ошибок
async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error('Произошла ошибка при обработке обновления:', exc_info=context.error)

if __name__ == '__main__':
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error)

    application.run_polling()
