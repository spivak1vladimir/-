import os
import json
import logging
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ---------------- НАСТРОЙКИ ----------------
TOKEN = "8429687481:AAF3BBz4eh7ATrXWhVDZKC1Xf3r8Ojc6ya4"
ADMIN_CHAT_ID = 194614510
MAX_SLOTS = 12
DATA_FILE = "registered_users.json"

RUN_DATETIME = datetime(2026, 2, 15, 11, 00)
RUN_DATE_TEXT = "15.02.26"
RUN_TITLE_TEXT = "Выбегаем из кофейни YCP"
START_POINT = "YCP, Адрес: ул. Мясницкая 13, стр. 21, Москва"
START_MAP_LINK_8KM = "https://yandex.ru/maps/-/CPQXy4JI"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- ДАННЫЕ ----------------
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        registered_users = json.load(f)
        if not isinstance(registered_users, list):
            registered_users = []
else:
    registered_users = []

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(registered_users, f, ensure_ascii=False, indent=2)

def build_info_text():
    text = (
        f"{RUN_DATE_TEXT}\n{RUN_TITLE_TEXT}\n\n"
        f"Старт: {START_POINT}\nСбор: 10:30\nСтарт: 11:00\n\n"
        f"Маршрут 8 км:\n{START_MAP_LINK_8KM}\n\n"
        f"Участники ({len(registered_users)}):\n"
    )
    if not registered_users:
        text += "— пока нет участников"
    else:
        for i, u in enumerate(registered_users, start=1):
            username = f"@{u['username']}" if u["username"] else "—"
            text += f"{i}. {u['name']} {username}\n"
    return text
# ---------------- /START ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"{RUN_DATE_TEXT}\n"
        f"{RUN_TITLE_TEXT}\n\n"
        "Рад, что ты присоединился к пробежке Spivak Run.\n\n"
        "Условия участия:\n"
        "— Участник самостоятельно несёт ответственность за свою жизнь и здоровье.\n"
        "— Участник несёт ответственность за сохранность личных вещей.\n"
        "— Согласие на обработку персональных данных.\n"
        "— Согласие на фото- и видеосъёмку.\n\n"
        "Если согласен — нажми кнопку ниже."
    )

    keyboard = [
        [InlineKeyboardButton("Согласен, зарегистрироваться (8 км)", callback_data="agree")],
        [InlineKeyboardButton("Информация о забеге", callback_data="info")]
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------------- РЕГИСТРАЦИЯ ----------------
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    user_id = str(user.id)

    if any(u["id"] == user_id for u in registered_users):
        await query.edit_message_text(build_info_text(), reply_markup=info_keyboard())
        return

    if len(registered_users) >= MAX_SLOTS:
        await query.edit_message_text("Все места заняты.", reply_markup=info_keyboard())
        return

    user_data = {"id": user_id, "name": user.first_name, "username": user.username or ""}
    registered_users.append(user_data)
    save_data()

    await context.bot.send_message(
        ADMIN_CHAT_ID,
        f"Новый участник\nИмя: {user.first_name}\nUsername: @{user.username}\nID: {user_id}"
    )

    await query.edit_message_text(build_info_text(), reply_markup=info_keyboard())

# ---------------- КНОПКИ ИНФОРМАЦИИ ----------------
def info_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Информация о забеге", callback_data="info")],
        [InlineKeyboardButton("Отменить регистрацию", callback_data="cancel")]
    ])

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = build_info_text()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=info_keyboard())
    else:
        await update.message.reply_text(text, reply_markup=info_keyboard())

# ---------------- ОТМЕНА ----------------
async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)

    for u in registered_users:
        if u["id"] == user_id:
            registered_users.remove(u)
            save_data()
            await context.bot.send_message(
                ADMIN_CHAT_ID,
                f"Участник отменил регистрацию\nИмя: {u['name']}\nUsername: @{u['username']}\nID: {u['id']}"
            )
            break

    await query.edit_message_text(build_info_text(), reply_markup=info_keyboard())

# ---------------- АДМИН ----------------
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("Доступ запрещён.")
        return

    text = build_info_text()
    keyboard = []
    for i, u in enumerate(registered_users):
        keyboard.append([InlineKeyboardButton(f"Удалить {u['name']}", callback_data=f"del_{i}")])
    if not keyboard:
        keyboard = [[InlineKeyboardButton("Участников нет", callback_data="noop")]]
    await update.message.reply_text(text)
    await update.message.reply_text("Управление участниками:", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("del_"):
        index = int(query.data.split("_")[1])
        if index < len(registered_users):
            removed = registered_users.pop(index)
            save_data()
            await query.message.reply_text(f"{removed['name']} удалён из списка.")

# ---------------- НАПОМИНАНИЕ ----------------
async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"{RUN_DATE_TEXT}\n{RUN_TITLE_TEXT}\n\n"
        "Завтра пробежка.\n\n"
        f"Старт: {START_POINT}\nСбор: 10:30\nСтарт: 11:00\n\n"
        f"Маршрут 8 км:\n{START_MAP_LINK_8KM}"
    )
    for u in registered_users:
        try:
            await context.bot.send_message(chat_id=int(u["id"]), text=text)
        except Exception:
            pass
    await context.bot.send_message(
        ADMIN_CHAT_ID,
        f"Напоминание отправлено.\nВсего участников: {len(registered_users)}"
    )

# ---------------- ЗАПУСК ----------------

def main():
    app = Application.builder().token(TOKEN).build()

    # команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("admin", admin))

    # обработчики кнопок
    app.add_handler(CallbackQueryHandler(register, pattern="^agree$"))
    app.add_handler(CallbackQueryHandler(cancel_registration, pattern="^cancel$"))
    app.add_handler(CallbackQueryHandler(admin_actions, pattern="^del_"))
    app.add_handler(CallbackQueryHandler(info, pattern="^info$"))  # ✅ добавили для кнопки

    # напоминание за 24 часа
    reminder_time = RUN_DATETIME - timedelta(hours=24)
    app.job_queue.run_once(send_reminder, reminder_time)

    logger.info("Бот запущен")
    app.run_polling()
if __name__ == "__main__":
    main()

