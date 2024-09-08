import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import requests
from bs4 import BeautifulSoup

# Токен бота
TOKEN = '7287010414:AAGpZ0dlH6_0xns8Bq7rWxMjK_E9zG9w1nY'

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# URL-адрес поиска
SEARCH_URL = 'https://w140.zona.plus/search-form'

# Функция для получения HTML-кода страницы
def get_page(url):
    response = requests.get(url)
    response.raise_for_status()  # Проверяем на ошибки
    return response.text

# Функция для получения результатов поиска
def get_search_results(search_term):
    search_url = f'{SEARCH_URL}?query={search_term}'
    search_content = get_page(search_url)
    return parse_search_results(search_content)

# Функция для парсинга результатов поиска
def parse_search_results(content):
    soup = BeautifulSoup(content, 'html.parser')
    results = []

    for item in soup.find_all('li', class_='results-item-wrap'):
        title = item.find('div', class_='results-item-title').get_text(strip=True)
        link = item.find('a', class_='results-item')['href']
        results.append((title, link))

    return results

# Функция для извлечения ссылки на плеер
def extract_player_link(movie_page_content):
    soup = BeautifulSoup(movie_page_content, 'html.parser')

    # Отладочная информация
    logger.debug('HTML контент страницы фильма:\n' + soup.prettify())

    # Пытаемся найти ссылку в <link itemprop="embedUrl">
    embed_url = soup.find('link', itemprop='embedUrl')
    if embed_url:
        src = embed_url.get('href')
        if src:
            logger.debug(f'Найдена ссылка в <link itemprop="embedUrl">: {src}')
            return src

    # Также проверяем ссылку на страницу фильма
    movie_url = soup.find('link', itemprop='url')
    if movie_url:
        src = movie_url.get('href')
        if src:
            logger.debug(f'Найдена ссылка на страницу фильма в <link itemprop="url">: {src}')
            return src

    return None

# Функция для создания клавиатуры с кнопками
def build_keyboard(results):
    keyboard = []
    for idx, (title, _) in enumerate(results):
        keyboard.append([InlineKeyboardButton(title, callback_data=f"movie_{idx}")])
    keyboard.append([InlineKeyboardButton("Назад", callback_data='back')])
    return InlineKeyboardMarkup(keyboard)

# Глобальная переменная для хранения результатов поиска
search_results_cache = {}

# Функция для обработки команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info('Пользователь нажал /start')
    keyboard = [[InlineKeyboardButton("Поиск", callback_data='search')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_message = (
        "Добро пожаловать в Telegram-бота для поиска фильмов и сериалов! 🎬\n\n"
        "Основные функции бота:\n\n"
        "1. Поиск фильмов и сериалов:\n"
        "- Нажмите кнопку 'Поиск' в главном меню.\n"
        "- Введите название фильма или сериала, который вы ищете.\n"
        "- Бот покажет вам список результатов поиска.\n\n"
        "2. Выбор фильма или сериала:\n"
        "- После получения результатов поиска выберите нужный фильм, нажав на его название.\n"
        "- Бот предоставит вам ссылку на плеер, где вы сможете посмотреть фильм.\n\n"
    )
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    logger.info('Отправлено приветственное сообщение с кнопкой "Поиск"')

# Функция для обработки нажатия кнопки
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    logger.info(f'Нажата кнопка с данными: {data}')

    if data == 'search':
        logger.info('Пользователь нажал кнопку "Поиск"')
        await query.edit_message_text(text="Введите название фильма или сериала для поиска:")
        logger.info('Отправлено сообщение для ввода названия')
    elif data == 'back':
        await query.edit_message_text('Добро пожаловать! Нажмите кнопку ниже, чтобы начать поиск фильмов или сериалов.',
                                      reply_markup=InlineKeyboardMarkup(
                                          [[InlineKeyboardButton("Поиск", callback_data='search')]]))
    elif data.startswith('movie_'):
        # Обработка нажатия кнопки фильма
        index = int(data.split('_')[1])
        logger.info(f'Выбран фильм с индексом: {index}')
        results = search_results_cache.get('results', [])
        if 0 <= index < len(results):
            title, movie_url = results[index]
            movie_page_url = f'https://w140.zona.plus{movie_url}'
            movie_page_content = get_page(movie_page_url)
            player_url = extract_player_link(movie_page_content)
            if player_url:
                await query.edit_message_text(f"Смотреть фильм здесь: {player_url}")
            else:
                await query.edit_message_text("Не удалось найти плеер для этого фильма.")
        else:
            await query.edit_message_text("Некорректный выбор фильма.")
            logger.error(f'Некорректный индекс фильма: {index}, количество фильмов: {len(results)}')

# Функция для обработки сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_term = update.message.text
    logger.info(f'Пользователь запросил поиск: {search_term}')

    search_results = get_search_results(search_term)
    search_results_cache['results'] = search_results

    logger.info(f'Найдено {len(search_results)} результатов поиска')

    if not search_results:
        await update.message.reply_text('Ничего не найдено. Попробуйте другой запрос.')
    else:
        reply_markup = build_keyboard(search_results)
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
