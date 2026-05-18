from telegram import Update
from telegram.ext import ContextTypes

from ..utils.keyboards import main_menu_keyboard

WELCOME = (
    "🎬 Добро пожаловать в бота для поиска фильмов и сериалов "
    'от канала <a href="https://t.me/tommorow4891"><b>48/91</b></a>!\n\n'
    "Нажмите <b>Поиск</b>, введите название — и смотрите."
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    msg = update.message or (update.callback_query and update.callback_query.message)
    if not msg:
        return

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(
                WELCOME, parse_mode="HTML", reply_markup=main_menu_keyboard()
            )
        except Exception:
            await context.bot.send_message(
                msg.chat_id, WELCOME, parse_mode="HTML",
                reply_markup=main_menu_keyboard()
            )
    else:
        await msg.reply_text(WELCOME, parse_mode="HTML", reply_markup=main_menu_keyboard())
