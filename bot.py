# bot.py
import os
import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
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

START_TEXT = "Выбери корт для участия:"
PAYMENT_TEXT = (
    "Оплата участия\n\n"
    "Перевод:\n8 925 826-57-45\n"
    "После оплаты отправь чек сюда."
)

REMINDER_24H = "Напоминание: игра завтра в 21:30."
REMINDER_4H = "Напоминание: игра начнётся через 4 часа."

# ================== STORAGE ==================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {k: [] for k in COURTS}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {k: COURTS[k]["users"] for k in COURTS},
            f,
            ensure_ascii=False,
            indent=2
        )

data = load_data()
for key in COURTS:
    COURTS[key]["users"] = data.get(key, [])

# ================== KEYBOARDS ==================

def courts_kb():
    kb = []
    for key, court in COURTS.items():
        if len([u for u in court["users"] if u.get("confirmed")]) < court["max_slots"]:
            kb.append([InlineKeyboardButton(court["title"], callback_data=f"join_{key}")])
    return InlineKeyboardMarkup(kb)

def admin_kb(court_key, idx):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Подтвердить оплату", callback_data=f"adm_pay_{court_key}_{idx}"),
            InlineKeyboardButton("Удалить", callback_data=f"adm_del_{court_key}_{idx}")
        ]
    ])

# ================== USER ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_TEXT, reply_markup=courts_kb())

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    court_key = query.data.replace("join_", "")
    user = query.from_user

    users = COURTS[court_key]["users"]
    if any(u["id"] == user.id for u in users):
        await query.message.reply_text("Ты уже зарегистрирован.")
        return

    users.append({
        "id": user.id,
        "name": user.first_name,
        "username": user.username,
        "paid": False,
        "confirmed": False,
        "receipt": None
    })
    save_data()

    await query.message.reply_text(PAYMENT_TEXT)

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user

    for court_key, court in COURTS.items():
        for u in court["users"]:
            if u["id"] == user.id and not u["receipt"]:
                u["receipt"] = True
                save_data()

                await context.bot.send_message(
                    ADMIN_CHAT_ID,
                    f"Чек от {u['name']} ({court['title']})",
                    reply_markup=admin_kb(court_key, court["users"].index(u))
                )
                return

# ================== ADMIN ==================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    text = "АДМИНКА\n\n"
    for court_key, court in COURTS.items():
        text += f"{court['title']}:\n"
        for i, u in enumerate(court["users"]):
            status = "оплачен" if u["confirmed"] else "ожидание"
            text += f"{i+1}. {u['name']} — {status}\n"
        text += "\n"

    await update.message.reply_text(text)

async def admin_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, _, court_key, idx = query.data.split("_")
    idx = int(idx)

    court = COURTS[court_key]
    user = court["users"][idx]

    user["confirmed"] = True
    user["paid"] = True

    confirmed = [u for u in court["users"] if u["confirmed"]]
    if len(confirmed) > court["max_slots"]:
        user["confirmed"] = False

    save_data()

    await context.bot.send_message(user["id"], "Оплата подтверждена. Ты в основном составе.")
    await query.edit_message_text("Оплата подтверждена.")

async def admin_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, _, court_key, idx = query.data.split("_")
    idx = int(idx)

    user = COURTS[court_key]["users"].pop(idx)
    save_data()

    await context.bot.send_message(user["id"], "Ты удалён из списка.")
    await query.edit_message_text("Игрок удалён.")

# ================== REMINDERS ==================

async def reminders(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(MOSCOW_TZ)
    for court in COURTS.values():
        delta = court["start_time"] - now
        for u in court["users"]:
            if not u["confirmed"]:
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

    app.add_handler(CallbackQueryHandler(join, pattern="^join_"))
    app.add_handler(CallbackQueryHandler(admin_pay, pattern="^adm_pay_"))
    app.add_handler(CallbackQueryHandler(admin_del, pattern="^adm_del_"))

    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, receive_receipt))

    app.job_queue.run_repeating(reminders, interval=300)

    logging.info("BOT STARTED")
    app.run_polling()

if __name__ == "__main__":
    main()
