# Телеграм Бот от канала 48/91 для поиска фильмов и сериалов

Этот Telegram-бот позволяет искать фильмы и сериалы, а также добавлять их в избранное. Бот использует два источника данных для поиска. Подробности ниже.

## Оглавление

- [Описание](#описание)
- [Установка](#установка)
- [Использование](#использование)
- [Команды](#команды)
- [Техническая документация](#техдок)

## Описание

Этот бот позволяет искать фильмы и сериалы через Telegram. Он осуществляет поиск по двум источникам:

- **LordSerial**: [https://lordserial.run/](https://lordserial.run/)
- **GoodFilms**: [https://zhqpg.goodfilms.fun/](https://zhqpg.goodfilms.fun/)

Пользователи могут просматривать результаты поиска, добавлять фильмы в избранное и получать ссылки на плееры для просмотра контента.

## Установка

1. **Клонируйте репозиторий:**
    ```bash
    git clone https://github.com/your-username/your-repo.git
    cd your-repo
    ```

2. **Установите зависимости:**
    ```bash
    pip install -r requirements.txt
    ```

3. **Создайте файл конфигурации:**
    В корневом каталоге проекта создайте файл `config.json` и добавьте ваш Telegram токен:
    ```json
    {
        "TOKEN": "ВАШ_ТЕЛЕГРАМ_ТОКЕН"
    }
    ```

4. **Создайте базу данных:**
    Создайте базу данных SQLite для хранения избранных фильмов:
    ```bash
    python -c "from bot import create_tables"
    ```

## Использование

1. **Запустите бота:**
    ```bash
    python bot.py
    ```

2. **В Telegram найдите бота по его имени и отправьте команду `/start`, чтобы начать использовать бота.**

## Команды

- **`/start`** - Начать работу с ботом.
- **Поиск фильмов и сериалов** - Введите название фильма или сериала для поиска.
- **Избранное** - Просмотреть список избранных фильмов.

### Команды в боте

- **🔍 Поиск**: Начать поиск фильма или сериала.
- **⭐ Избранное**: Посмотреть избранные фильмы.
- **▶️ СМОТРЕТЬ**: Перейти к просмотру фильма.
- **⭐ Добавить в избранное**: Добавить фильм в избранное.
- **🏠 Главная**: Вернуться на главную страницу.

# Техническая документация по Telegram боту для поиска фильмов

## Введение

Данный документ предоставляет техническое описание работы Telegram бота для поиска фильмов и сериалов. Бот поддерживает поиск по двум источникам и управление избранными фильмами. Основные компоненты включают взаимодействие с API, парсинг веб-страниц и работу с SQLite базой данных.

## Структура проекта

- `config.json` — Файл конфигурации с токеном бота.
- `favorites.db` — SQLite база данных для хранения избранных фильмов.
- Основной скрипт (`main.py`) — Реализация логики бота.

## Зависимости

- `telegram` — библиотека для взаимодействия с Telegram API.
- `telegram.ext` — расширение для упрощения работы с Telegram API.
- `requests` — для выполнения HTTP-запросов.
- `beautifulsoup4` — для парсинга HTML.
- `sqlite3` — для работы с SQLite базой данных.
- `hashlib` — для генерации уникальных идентификаторов.

## Основные компоненты

### 1. Инициализация

**Файл конфигурации:**

```python
with open('config.json', 'r') as file:
    config = json.load(file)
    TOKEN = config['TOKEN']
```

Токен бота загружается из конфигурационного файла `config.json`.

**Настройка логирования:**

```python
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
```

Логирование настроено для отслеживания событий и ошибок.

### 2. База данных

**Подключение к базе данных:**

```python
def get_db_connection():
    conn = sqlite3.connect('favorites.db')
    conn.row_factory = sqlite3.Row
    return conn
```

**Создание таблиц:**

```python
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
```

Таблица `user_favorites` используется для хранения избранных фильмов пользователей.

### 3. Получение и парсинг данных

**Запрос HTML-кода страницы:**

```python
def get_page(url, params=None):
    response = requests.get(url, params=params)
    response.raise_for_status()
    logger.debug(f'HTML код страницы: {response.text[:1000]}')
    return response.text
```

**Поиск на сайте lordserial:**

```python
def get_search_results_lordserial(search_term):
    params_lordserial = {'do': 'search', 'subaction': 'search', 'story': search_term}
    search_content_lordserial = get_page(SEARCH_URL_LORDSERIAL, params=params_lordserial)
    return parse_search_results_lordserial(search_content_lordserial)

def parse_search_results_lordserial(content):
    soup = BeautifulSoup(content, 'html.parser')
    results = []
    for item in soup.find_all('div', class_='th-item'):
        title = item.find('div', class_='th-title').get_text(strip=True)
        link = item.find('a', class_='th-in with-mask')['href']
        results.append((f"{title} (Источник 1)", link))
    return results
```

**Поиск на сайте goodfilms:**

```python
def get_search_results_goodfilms(search_term):
    params_goodfilms = {
        'do': 'search',
        'subaction': 'search',
        'story': search_term,
        'result_from': 1
    }
    search_content_goodfilms = requests.post(SEARCH_URL_GOODFILMS, data=params_goodfilms).text
    return parse_search_results_goodfilms(search_content_goodfilms)

def parse_search_results_goodfilms(content):
    soup = BeautifulSoup(content, 'html.parser')
    results = []
    for item in soup.find_all('div', class_='poster'):
        title = item.find('span', class_='poster__title').get_text(strip=True)
        link = item.find('a', class_='poster__link')['href']
        results.append((f"{title} (Источник 2)", link))
    return results
```

**Общий поиск:**

```python
def get_search_results(search_term):
    results_lordserial = get_search_results_lordserial(search_term)
    results_goodfilms = get_search_results_goodfilms(search_term)
    return results_lordserial + results_goodfilms
```

### 4. Обработка информации о фильме

**Извлечение информации:**

```python
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
```

**Извлечение ссылки на плеер:**

```python
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
```

### 5. Создание клавиатуры

**Клавиатура для поиска и избранного:**

```python
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

def build_favorites_keyboard():
    keyboard = [
        [InlineKeyboardButton("🏠 Главная", callback_data='home')]
    ]
    return InlineKeyboardMarkup(keyboard)
```

**Клавиатура для страницы фильма:**

```python
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
```

### 6. Обработка команд и сообщений

**Команда /start:**

```python
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
```

**Обработка нажатий на кнопки:**

```python
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data

 = query.data
    logger.info(f'Нажата кнопка с данными: {data}')
    if data == 'search':
        await query.edit_message_text(text="Введите название фильма или сериала для поиска:")
    elif data == 'favorites':
        chat_id = update.callback_query.message.chat_id
        user_favorites = get_user_favorites(chat_id)
        if not user_favorites['favorites']:
            await query.edit_message_text('Избранные фильмы пусты.', reply_markup=build_favorites_keyboard())
        else:
            favorites_message = '\n'.join([f"{idx + 1}. <a href='{user_favorites['links'][title]}'>{title}</a>"
                                           for idx, title in enumerate(user_favorites['favorites'])])
            await query.edit_message_text(f'Ваши избранные фильмы:\n{favorites_message}', parse_mode='HTML',
                                          reply_markup=build_favorites_keyboard())
    elif data.startswith('movie_'):
        index = int(data.split('_')[1])
        results = search_results_cache.get('results', [])
        if 0 <= index < len(results):
            title, movie_url = results[index]
            source = 'goodfilms' if 'Источник 2' in title else 'lordserial'
            movie_page_content = get_page(movie_url)
            movie_info = extract_movie_info(movie_page_content, source)
            player_url = extract_player_link(movie_page_content)
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
                conn.execute('''INSERT OR IGNORE INTO user_favorites (chat_id, title, url, player_url)
                                VALUES (?, ?, ?, ?)''', (chat_id, movie_info['title'], movie_url, player_url))
                conn.commit()
                conn.close()
                await query.answer("Фильм добавлен в избранное.", show_alert=True)
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
```

**Обработка текстовых сообщений (поиск):**

```python
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    search_term = update.message.text
    chat_id = update.message.chat_id
    results = get_search_results(search_term)
    search_results_cache['results'] = results
    search_results_cache['url_map'] = {get_unique_id(url): url for _, url in results}
    total_pages = (len(results) + 4) // 5
    search_results_cache['total_pages'] = total_pages
    if not results:
        await context.bot.send_message(chat_id=chat_id, text="Результатов не найдено.")
    else:
        await context.bot.send_message(chat_id=chat_id, text="Результаты поиска:",
                                       reply_markup=build_keyboard(results, current_page=1, total_pages=total_pages))
```

**Обработка ошибок:**

```python
async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error('Произошла ошибка при обработке обновления:', exc_info=context.error)
```

### 7. Запуск бота

```python
if __name__ == '__main__':
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error)
    application.run_polling()
```
