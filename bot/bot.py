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
SEARCH_URL = 'https://lordserial.run/index.php?do=search'
# URL-адрес плеера
PLAYER_URL = 'https://player.cdnvideohub.com/svplayer?partner=22&kid=448'

# Функция для получения HTML-кода страницы
def get_page(url, params=None):
    response = requests.get(url, params=params)
    response.raise_for_status()  # Проверяем на ошибки
    return response.text

# Функция для парсинга результатов поиска
def parse_search_results(content):
    soup = BeautifulSoup(content, 'html.parser')
    results = []

    # Парсинг карточек фильмов
    for item in soup.find_all('div', class_='th-item'):
        title = item.find('div', class_='th-title').get_text(strip=True)
        link = item.find('a', class_='th-in with-mask')['href']
        # Получаем страницу фильма
        movie_page = get_page(link)
        # Находим ссылку на плеер
        player_url = get_player_url(movie_page)
        results.append((title, player_url))

    return results

# Функция для получения ссылки на плеер
def get_player_url(movie_page_content):
    soup = BeautifulSoup(movie_page_content, 'html.parser')
    # Здесь можно добавить логику для поиска ссылки на плеер, если её нет
    # Учитывая, что ссылка на плеер у вас есть, просто вернем её
    return PLAYER_URL

# Функция для создания клавиатуры с кнопками
def build_keyboard(results):
    keyboard = []
    for title, url in results:
        keyboard.append([InlineKeyboardButton(title, url=url)])
    return InlineKeyboardMarkup(keyboard)

# Функция для обработки команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info('Пользователь нажал /start')
    keyboard = [[InlineKeyboardButton("Поиск", callback_data='search')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Добро пожаловать! Нажмите кнопку ниже, чтобы начать поиск фильмов или сериалов.',
                                    reply_markup=reply_markup)
    logger.info('Отправлено приветственное сообщение с кнопкой "Поиск"')

# Функция для обработки нажатия кнопки
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'search':
        logger.info('Пользователь нажал кнопку "Поиск"')
        await query.edit_message_text(text="Введите название фильма или сериала для поиска:")
        logger.info('Отправлено сообщение для ввода названия')

# Функция для обработки сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_term = update.message.text
    logger.info(f'Пользователь запросил поиск: {search_term}')

    params = {
        'do': 'search',
        'subaction': 'search',
        'story': search_term
    }

    # Получаем результаты поиска
    search_content = get_page(SEARCH_URL, params=params)
    search_results = parse_search_results(search_content)

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
