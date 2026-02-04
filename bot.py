import os
import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================== CONFIG ==================

TOKEN = "7705759805:AAFx2IHX44ZPIRC3bCXCVqP23J9WeM0u7qc"
ADMIN_CHAT_ID = 194614510
DATA_FILE = "registered_users.json"

MOSCOW_TZ = ZoneInfo("Europe/Moscow")

COURTS = {
    "court10": {
        "title": "Корт 10 человек",
        "max_slots": 10,
        "price": 1400,
        "start_time": datetime(2026, 2, 5, 21, 30, tzinfo=MOSCOW_TZ),
        "users": []
    },
    "court4": {
        "title": "Корт 4 человека",
        "max_slots": 4,
        "price": 1600,
        "start_time": datetime(2026, 2, 5, 21, 30, tzinfo=MOSCOW_TZ),
        "users": []
    }
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# ================== TEXTS ==================

TERMS_TEXT = (
    "Пожалуйста, ознакомься с условиями участия:\n"
    "— Если участник из листа ожидания произведёт оплату раньше, чем участник из основного состава, он будет переведён в основной состав.\n"
    "— Просьба производить оплату заранее, так как требуется предварительная оплата аренды площадки.\n"
    "— Участник самостоятельно несёт ответственность за свою жизнь и здоровье.\n"
    "— Участник несёт ответственность за сохранность личных вещей.\n"
    "— Согласие на обработку персональных данных.\n"
    "— Согласие на фото- и видеосъёмку во время мероприятия.\n\n"
    "Условия оплаты и отмены участия:\n"
    "— При отмене участия менее чем за 24 часа до начала игры оплата не возвращается.\n"
    "— При отмене не позднее чем за 24 часа до игры средства возвращаются.\n"
    "— Допускается передача оплаченного места другому игроку при самостоятельном поиске замены.\n\n"
)

START_TEXT = (
    "Играем в волейбол Spivak Run\n\n"
    "Площадка:\n"
    "Пляжный центр «Лето»\n"
    "проспект маршала жукова 4 строение 2\n\n"
    "https://yandex.ru/maps/-/CLh3JG0S\n\n"
    "Дата: 5 февраля\n"
    "Сбор: 21:20\n"
    "Начало игры: 21:30\n\n"
    "Выбери корт для участия:"
)

REMINDER_24H = "Напоминание\nИгра состоится завтра в 21:30."
REMINDER_4H = "Напоминание\nИгра начнётся через 4 часа."

PAYMENT_TEXT = (
    "Для подтверждения участия необходимо произвести оплату.\n"
    "После оплаты отправь сюда чек (фото или файл)."
)

# ================== STORAGE ==================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {k: [] for k in COURTS}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({k: COURTS[k]["users"] for k in COURTS}, f, ensure_ascii=False, indent=2)


data = load_data()
for key in COURTS:
    COURTS[key]["users"] = data.get(key, [])

# ================== KEYBOARDS ==================

def courts_kb():
    kb = []
    for key, court in COURTS.items():
        kb.append([InlineKeyboardButton(court["title"], callback_data=f"join_{key}")])
    kb.append([InlineKeyboardButton("Информация по игре", callback_data="info")])
    return InlineKeyboardMarkup(kb)

# ================== HELPERS ==================

def format_user(u, position, status):
    username = f"@{u['username']}" if u.get("username") else "—"
    return (
        f"Имя: {u['first_name']}\n"
        f"Username: {username}\n"
        f"ID: {u['id']}\n"
        f"Статус: {status}\n"
        f"Позиция: {position}\n"
    )

# ================== USER ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_TEXT)
    await update.message.reply_text(TERMS_TEXT, reply_markup=courts_kb())

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "info":
        await show_info(query)
        return

    court_key = query.data.replace("join_", "")
    user = query.from_user
    court = COURTS[court_key]

    if any(u["id"] == user.id for u in court["users"]):
        await query.message.reply_text("Ты уже зарегистрирован.")
        return

    confirmed_count = len([u for u in court["users"] if u.get("confirmed")])
    confirmed = confirmed_count < court["max_slots"]

    court["users"].append({
        "id": user.id,
        "first_name": user.first_name,
        "username": user.username,
        "paid": False,
        "confirmed": confirmed,
        "receipt_file_id": None
    })
    save_data()

    position = len(court["users"])
    status = "Основной состав" if confirmed else "Лист ожидания"

    await query.message.reply_text(
        format_user(court["users"][-1], position, status) + "\n" + PAYMENT_TEXT
    )

async def show_info(query):
    text = "Участники по кортам:\n\n"
    for court in COURTS.values():
        text += f"{court['title']}:\n"
        for i, u in enumerate(court["users"], 1):
            status = "основной" if u.get("confirmed") else "ожидание"
            username = f"@{u['username']}" if u.get("username") else "—"
            text += f"{i}. {u['first_name']} ({username}) — {status}\n"
        text += "\n"
    await query.message.reply_text(text)

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    file_id = update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id

    for court_key, court in COURTS.items():
        for u in court["users"]:
            if u["id"] == user.id:
                u["receipt_file_id"] = file_id
                save_data()

                await context.bot.send_message(
                    ADMIN_CHAT_ID,
                    f"Чек от {u['first_name']} ({court['title']})"
                )
                await context.bot.send_photo(ADMIN_CHAT_ID, file_id)
                return

# ================== ADMIN ==================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    keyboard = []
    text = "Участники:\n\n"

    for court_key, court in COURTS.items():
        text += f"{court['title']}:\n"
        for i, u in enumerate(court["users"]):
            paid = "оплачено" if u.get("paid") else "не оплачено"
            username = f"@{u['username']}" if u.get("username") else "—"
            text += f"{i+1}. {u['first_name']} ({username}) — {paid}\n"

            keyboard.append([
                InlineKeyboardButton(
                    f"Подтвердить оплату {u['first_name']}",
                    callback_data=f"adm_pay_{court_key}_{i}"
                ),
                InlineKeyboardButton(
                    f"Удалить {u['first_name']}",
                    callback_data=f"adm_del_{court_key}_{i}"
                )
            ])
        text += "\n"

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, _, court_key, idx = query.data.split("_")
    idx = int(idx)
    court = COURTS[court_key]
    user = court["users"][idx]

    user["paid"] = True
    user["confirmed"] = True

    confirmed = [u for u in court["users"] if u.get("confirmed")]
    if len(confirmed) > court["max_slots"]:
        user["confirmed"] = False

    save_data()

    await context.bot.send_message(user["id"], "Оплата подтверждена. Ты в основном составе.")
    await query.edit_message_text("Оплата подтверждена")

async def admin_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, _, court_key, idx = query.data.split("_")
    idx = int(idx)
    user = COURTS[court_key]["users"].pop(idx)
    save_data()

    await context.bot.send_message(user["id"], "Ты удалён из списка")
    await query.edit_message_text("Игрок удалён")

# ================== REMINDERS ==================

async def reminders(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(MOSCOW_TZ)
    for court in COURTS.values():
        delta = court["start_time"] - now
        for u in court["users"]:
            if not u.get("confirmed"):
                continue
            if timedelta(hours=23, minutes=50) < delta < timedelta(hours=24, minutes=10):
                await context.bot.send_message(u["id"], REMINDER_24H)
            if timedelta(hours=3, minutes=50) < delta < timedelta(hours=4, minutes=10):
                await context.bot.send_message(u["id"], REMINDER_4H)

# ================== MAIN ==================

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))

    app.add_handler(CallbackQueryHandler(join, pattern="^(join_|info)"))
    app.add_handler(CallbackQueryHandler(admin_pay, pattern="^adm_pay_"))
    app.add_handler(CallbackQueryHandler(admin_del, pattern="^adm_del_"))

    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, receive_receipt))

    app.job_queue.run_repeating(reminders, interval=300)

    logging.info("BOT STARTED")
    app.run_polling()

if __name__ == "__main__":
    main()