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

    # Пробуем найти iframe как обычно
    iframe = soup.find('iframe')
    if iframe:
        return iframe['src']

    # Если iframe не найден, пробуем найти другой элемент с плеером
    # Например, плеер может быть внутри div с классом 'player-container'
    player_div = soup.find('div', class_='player-container')
    if player_div:
        # Проверяем наличие ссылки внутри этого блока
        player_link = player_div.find('a')
        if player_link and 'href' in player_link.attrs:
            return player_link['href']

    # Если ссылка на плеер не найдена, возвращаем None
    return None

# Функция для получения результатов поиска
def get_search_results(search_term):
    # LordSerial
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
        keyboard.append([InlineKeyboardButton("Предыдущая", callback_data=f'prev_{current_page - 1}')])
    if current_page < total_pages:
        keyboard.append([InlineKeyboardButton("Следующая", callback_data=f'next_{current_page + 1}')])

    return InlineKeyboardMarkup(keyboard)

# Глобальные переменные для хранения результатов поиска
search_results_cache = {}
previous_state_cache = {}

# Функция для обработки команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info('Пользователь нажал /start')
    keyboard = [[InlineKeyboardButton("Поиск", callback_data='search')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_message = (
        "Добро пожаловать в бота для поиска фильмов и сериалов от канала 48/91 (https://t.me/tommorow4891)! 🎬\n\n"
        "Нажмите 'Поиск' для начала."
    )
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

# Функция для обработки нажатия кнопки
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    logger.info(f'Нажата кнопка с данными: {data}')

    # Обработка кнопки "Поиск"
    if data == 'search':
        await query.edit_message_text(text="Введите название фильма или сериала для поиска:")

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
                f"*Название:* {movie_info['title']}\n"
                f"*Описание:* {movie_info['description']}\n"
            )

            if player_url:
                response_message += f"[Смотреть фильм здесь]({player_url})"
            else:
                response_message += "Не удалось найти плеер для этого фильма."

            await query.edit_message_text(response_message, parse_mode='Markdown')
        else:
            await query.edit_message_text("Некорректный выбор фильма.")

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

# Функция для обработки сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_term = update.message.text
    logger.info(f'Пользователь запросил поиск: {search_term}')

    # Получаем результаты поиска с сайта LordSerial
    search_results = get_search_results(search_term)
    search_results_cache['results'] = search_results  # Сохраняем результаты поиска в кэш
    search_results_cache['search_term'] = search_term  # Сохраняем запрос
    search_results_cache['total_results'] = len(search_results)  # Сохраняем общее количество результатов

    logger.info(f'Найдено {len(search_results)} результатов поиска')

    if not search_results:
        await update.message.reply_text('Ничего не найдено. Попробуйте другой запрос.')
    else:
        total_pages = (len(search_results) // 5) + (1 if len(search_results) % 5 > 0 else 0)
        reply_markup = build_keyboard(search_results, 1, total_pages)  # Начальная страница
        await update.message.reply_text('Результаты поиска:', reply_markup=reply_markup)

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
