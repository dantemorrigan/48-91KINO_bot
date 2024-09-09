#Импортируем необходимые библиотеки
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import requests
from bs4 import BeautifulSoup

# Токен бота
TOKEN = '***TELEGRAM_TOKEN_REMOVED***'

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# URL-адреса поиска
SEARCH_URL_LORDSERIAL = 'https://lordserial.run/index.php?do=search'
SEARCH_URL_BEFILM = 'https://t1.befilm1.life/index.php?do=search'


# Функция для получения HTML-кода страницы
def get_page(url, params=None):
    response = requests.get(url, params=params)
    response.raise_for_status()  # Проверяем на ошибки
    return response.text


# Функции для парсинга результатов поиска
def parse_search_results(content):
    soup = BeautifulSoup(content, 'html.parser')
    results = []
    for item in soup.find_all('div', class_='th-item'):
        title = item.find('div', class_='th-title').get_text(strip=True)
        link = item.find('a', class_='th-in with-mask')['href']
        results.append((f"{title} (Источник 1)", link))
    return results


def parse_befilm_search_results(content):
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
    imdb_rating = soup.find('div', class_='frate frate-imdb').get_text(strip=True) if soup.find('div',
                                                                                                class_='frate frate-imdb') else "Нет"
    kp_rating = soup.find('div', class_='frate frate-kp').get_text(strip=True) if soup.find('div',
                                                                                            class_='frate frate-kp') else "Нет"
    year = soup.find('span', itemprop='dateCreated').get_text(strip=True) if soup.find('span',
                                                                                       itemprop='dateCreated') else "Не указано"
    country = soup.find('a', href=True, text=True).get_text(strip=True) if soup.find('a', href=True,
                                                                                     text=True) else "Не указано"
    premiere = soup.find_all('li')[3].get_text(strip=True).replace('Премьера:', '').strip() if len(
        soup.find_all('li')) > 3 else "Не указана"

    return {
        'title': title,
        'description': description,
        'imdb_rating': imdb_rating,
        'kp_rating': kp_rating,
        'year': year,
        'country': country,

    }


# Функция для извлечения ссылки на плеер
def extract_player_link(movie_page_content):
    soup = BeautifulSoup(movie_page_content, 'html.parser')
    iframe = soup.find('iframe')
    if iframe:
        return iframe['src']
    return None


# Функция для объединения результатов поиска
def get_combined_search_results(search_term):
    params_lordserial = {'do': 'search', 'subaction': 'search', 'story': search_term}
    search_content_lordserial = get_page(SEARCH_URL_LORDSERIAL, params=params_lordserial)
    results_lordserial = parse_search_results(search_content_lordserial)

    params_befilm = {'do': 'search', 'subaction': 'search', 'story': search_term}
    search_content_befilm = get_page(SEARCH_URL_BEFILM, params=params_befilm)
    results_befilm = parse_befilm_search_results(search_content_befilm)

    combined_results = results_lordserial + results_befilm
    return combined_results


# Функция для создания клавиатуры с кнопками
def build_keyboard(results, show_back=True):
    keyboard = []
    for idx, (title, _) in enumerate(results):
        keyboard.append([InlineKeyboardButton(title, callback_data=f"movie_{idx}")])
    if show_back:
        keyboard.append([InlineKeyboardButton("Назад", callback_data='back')])
    return InlineKeyboardMarkup(keyboard)


# Глобальная переменная для хранения результатов поиска
search_results_cache = {}
previous_state_cache = {}


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
        "- Бот предоставит вам краткую информацию о фильме и ссылку на плеер, где вы сможете посмотреть фильм.\n\n"
    )
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    logger.info('Отправлено приветственное сообщение с кнопкой "Поиск"')


# Функция для обработки нажатия кнопки
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    logger.info(f'Нажата кнопка с данными: {data}')

    # Обработка кнопки "Поиск"
    if data == 'search':
        logger.info('Пользователь нажал кнопку "Поиск"')
        previous_state_cache[query.from_user.id] = 'start'
        await query.edit_message_text(text="Введите название фильма или сериала для поиска:")
        logger.info('Отправлено сообщение для ввода названия')

    # Обработка кнопки "Назад"
    elif data == 'back':
        previous_state = previous_state_cache.get(query.from_user.id, 'start')
        if previous_state == 'search':
            await query.edit_message_text('Добро пожаловать! Нажмите кнопку ниже, чтобы начать поиск фильмов или сериалов.',
                                          reply_markup=InlineKeyboardMarkup(
                                              [[InlineKeyboardButton("Поиск", callback_data='search')]]))
        elif previous_state == 'results':
            search_results = search_results_cache.get('results', [])
            reply_markup = build_keyboard(search_results, show_back=False)
            await query.edit_message_text('Результаты поиска:', reply_markup=reply_markup)
        elif previous_state == 'movie':
            search_results = search_results_cache.get('results', [])
            reply_markup = build_keyboard(search_results)
            await query.edit_message_text('Результаты поиска:', reply_markup=reply_markup)
        logger.info('Возврат к предыдущему состоянию')

    # Обработка выбора фильма
    elif data.startswith('movie_'):
        index = int(data.split('_')[1])
        logger.info(f'Выбран фильм с индексом: {index}')
        results = search_results_cache.get('results', [])
        if 0 <= index < len(results):
            title, movie_url = results[index]
            movie_page_content = get_page(movie_url)
            movie_info = extract_movie_info(movie_page_content)
            player_url = extract_player_link(movie_page_content)

            response_message = (
                f"*Название:* {movie_info['title']}\n"
                f"*Описание:* {movie_info['description']}\n"
                f"*Рейтинг IMDb:* {movie_info['imdb_rating']}\n"
                f"*Рейтинг Кинопоиск:* {movie_info['kp_rating']}\n"
                f"*Год выхода:* {movie_info['year']}\n"
                f"*Страна:* {movie_info['country']}\n"
            )

            if player_url:
                response_message += f"[Смотреть фильм здесь]({player_url})"
            else:
                response_message += "Не удалось найти плеер для этого фильма."

            previous_state_cache[query.from_user.id] = 'movie'
            await query.edit_message_text(response_message, parse_mode='Markdown')
        else:
            await query.edit_message_text("Некорректный выбор фильма.")
            logger.error(f'Некорректный индекс фильма: {index}, количество фильмов: {len(results)}')


# Функция для обработки сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_term = update.message.text
    logger.info(f'Пользователь запросил поиск: {search_term}')

    # Получаем результаты поиска с двух сайтов
    search_results = get_combined_search_results(search_term)
    search_results_cache['results'] = search_results  # Сохраняем результаты поиска в глобальную переменную

    logger.info(f'Найдено {len(search_results)} результатов поиска')

    if not search_results:
        await update.message.reply_text('Ничего не найдено. Попробуйте другой запрос.')
    else:
        reply_markup = build_keyboard(search_results)
        previous_state_cache[update.message.from_user.id] = 'results'
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